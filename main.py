#!/usr/bin/env python3
import asyncio
import aiomqtt
import json
from enum import Enum
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from victron_ble.devices.base import OperationMode

import prometheus_client as pc

from cachetools import TTLCache

from metrics import NullReporter, Reporter

from prometheus_client.registry import Collector


class Ble2Mqtt:
  """
      Listens for BLE broadcasts from devices defined in config.py and
      publishes those to mqtt, providing some deduping and rate limiting
  """

  METRIC_CACHE_SIZE = 10000

  @staticmethod
  def adjust_value(val):
    match val:
      case float():
        return round(val, 2)
      case Enum():
        return val.name
      case _:
        return val

  def __init__(self, config_map, reporter=Reporter()):
    self.known_devices = config_map['devices']
    self.metric_path = tuple(config_map.get('metric_path', ()))

    self.mqtt_pub_interval_s = config_map['mqtt_pub_interval_s']
    self.mqtt_prefix = ('/'.join(self.metric_path) + '/') if self.metric_path else ''
    self.mqtt_client = aiomqtt.Client(
      config_map['mqtt_broker_addr'],
      username=config_map.get('mqtt_user'),
      password=config_map.get('mqtt_pass'))
    self.queue = asyncio.Queue(maxsize=250)
    self.bs_callback = lambda dev, data: self.on_advertise(dev, data)

    ## TODO: Make this NOT per-device?
    for device in self.known_devices.values():
      device.throttle_s = config_map["ble_throttle_s"]

    self.pm_prefix = ('_'.join(self.metric_path) + '_') if self.metric_path else ''
    self.reporter = reporter.scoped(*self.metric_path)

    self.queue_depth = reporter.gauge("queue_depth", "Beacon reading queue depth")
    self.queue_depth.set_function(lambda: self.queue.qsize())

    self.bc = self.reporter.counter('beacons', 'Number of BLE beacons seen', labelnames=['status'])
    self.bc_h = self.bc.labels('handled')
    self.bc_i = self.bc.labels('ignored')
    self.bc_f = self.bc.labels('full')

    self.gauge_cache = TTLCache(maxsize=self.METRIC_CACHE_SIZE, ttl=config_map['metric_ttl_s'])
    self.state_cache = TTLCache(maxsize=self.METRIC_CACHE_SIZE, ttl=config_map['metric_ttl_s'])

    self.unhandled_ctr = self.reporter.counter('unhandled_metric_type', 'Couldnt make it a gauge or enum')

  def _queue_getall(self):
    ret = []
    try:
      while True:
        ret.append(self.queue.get_nowait())
        self.queue.task_done()
    except asyncio.QueueEmpty:
      return ret

  def _update_state(self, key, new_value):
    enum = self.state_cache.get(key)
    if not enum:
      states = {s.name.lower() for s in list(new_value.__class__)}

      # When you enumerate over a 'Flags' type, it skipps the zero case
      # which corresponds to no flags present. However, it's still a
      # state in the enumeration, so we have to manually add it here. Ugh.
      zero_state_name = new_value.__class__(0).name.lower()
      states.add(zero_state_name)

      enum = pc.Enum(f"{self.pm_prefix}{key}", "Proxied Enum", states=list(states))
      self.state_cache[key] = enum

    enum.state(new_value.name.lower())

  def _update_gauge(self, key, new_value):
    gauge = self.gauge_cache.get(key)
    if not gauge:
      gauge = pc.Gauge(f"{self.pm_prefix}{key}", "Proxied Gauge")
      self.gauge_cache[key] = gauge
    gauge.set(new_value)

  def on_advertise(self, device: BLEDevice, advertisement: AdvertisementData):
    addr = device.address.upper()
    found_device = self.known_devices.get(addr)

    if found_device and not found_device.should_throttle():
      readings_dict = found_device.decode(device, advertisement)
      if readings_dict:
        try:
          self.queue.put_nowait((found_device.name, readings_dict))
          self.bc_h.inc()
        except asyncio.QueueFull:
          self.bc_f.inc()
        return

    self.bc_i.inc()

  async def publish_to_mqtt(self, to_publish):
    async with self.mqtt_client as mqtt:
      for devname, readings in to_publish.items():
        adjusted = { k: Ble2Mqtt.adjust_value(v) for k, v in readings.items() }
        await mqtt.publish(
          f"{self.mqtt_prefix}{devname}", payload=json.dumps(adjusted))

  def update_metrics(self, to_publish):
    for devname, readings in to_publish.items():
      for k, v in readings.items():
        mkey = f"{devname}_{k}" #'_'.join(self.metric_path + (devname, k))

        match v:
          case float() | int():
            self._update_gauge(mkey, v)
          case Enum():
            self._update_state(mkey, v)
          case _:
            self.unhandled_ctr.inc()

  async def process_queue(self):
    while True:
      await asyncio.sleep(self.mqtt_pub_interval_s)

      # Ensure we only keep the most recent value for each key
      to_publish = { k: v for k, v in self._queue_getall() }
      if to_publish:
        self.update_metrics(to_publish)
        await self.publish_to_mqtt(to_publish)

  def prepare(self, loop):
    async def scan():
      self.scanner = BleakScanner(detection_callback=self.bs_callback)
      await self.scanner.start()

    loop.create_task(scan())
    loop.create_task(self.process_queue())

  async def stop(self):
    await self.scanner.stop()


def dump_names(loop):
  def on_advertise(device: BLEDevice, adv: AdvertisementData):
    addr = device.address.upper()
    if device.name:
      print(f"{device} rssi={adv.rssi}")

  async def scan():
    scanner = BleakScanner(detection_callback=on_advertise)
    await scanner.start()

  loop.create_task(scan())


if __name__ == "__main__":
  from config import CurrentConfig
  import sys
  import signal

  loop = asyncio.new_event_loop()
  asyncio.set_event_loop(loop)
  ble2mqtt = None

  def ctrl_c(sig, frame):
    if ble2mqtt:
      loop.call_soon(ble2mqtt.stop)
    loop.stop()
    print("\nBye")
    sys.exit(0)

  signal.signal(signal.SIGINT, ctrl_c)

  cmd = sys.argv[1] if len(sys.argv) > 1 else None

  if cmd == 'scan':
    dump_names(loop)
  else:
    ble2mqtt = Ble2Mqtt(CurrentConfig)
    ble2mqtt.prepare(loop)
    ble2mqtt.queue.put_nowait(('b2m', {"alive": "true"}))

  e = pc.Enum('my_test_enum', "desc", states=['one', 'two', 'three'])
  e.state('one')

  e.state('two')

  e = pc.Gauge('fake_enum', "desc", ["state"])
  e.labels('one').set(1)
  e.labels('two').set(1)

  pc.start_http_server(8088)
  loop.run_forever()
