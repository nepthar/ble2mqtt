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

OUTPUT = False

# def make_metric(mname, val):
#   metric = None
#   match val:
#     case Enum():
#       states = [x.name.lower() for x in list(val.__class__)]
#       metric = Enum(key, "BLE Forwarded enum", states=states)
#     case float() | int():
#       metric = Gauge(key, "BLE Forwarded gauge")
#     case None:
#       pass
#     case _:
#       pass

#   return metric


# def update_metric(metric, val):
#   match val:
#     case Enum():

#     case float() | int():

#     case _:
#       raise Exception(f"Unable to update metric {metric} with unknown type, {val}")




class Ble2Mqtt:
  """
      Listens for BLE broadcasts from devices defined in config.py and
      publishes those to mqtt, providing some deduping and rate limiting
  """

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

    self.mqtt_pub_interval_s = config_map['mqtt_pub_interval_s']
    self.mqtt_prefix = config_map['mqtt_prefix']
    self.mqtt_client = aiomqtt.Client(
      config_map['mqtt_broker_addr'],
      username=config_map.get('mqtt_user'),
      password=config_map.get('mqtt_pass'))
    self.queue = asyncio.Queue(maxsize=250)
    self.bs_callback = lambda dev, data: self.on_advertise(dev, data)

    self.metric_cache = TTLCache(maxsize=10000, ttl=config_map['metric_ttl_s'])

    for device in self.known_devices.values():
      device.throttle_s = config_map["ble_throttle_s"]

    self.reporter = reporter.scoped(*config_map.get('metric_prefix', []))

    self.queue_depth = reporter.gauge("queue_depth", "Beacon reading queue depth")
    self.queue_depth.set_function(lambda: self.queue.qsize())

    self.bc = self.reporter.counter('beacons', 'Number of BLE beacons seen', labelnames=['status'])
    self.bc_h = self.bc.labels('handled')
    self.bc_i = self.bc.labels('ignored')
    self.bc_f = self.bc.labels('full')

  def _queue_getall(self):
    ret = []
    try:
      while True:
        ret.append(self.queue.get_nowait())
        self.queue.task_done()
    except asyncio.QueueEmpty:
      return ret

  def on_advertise(self, device: BLEDevice, advertisement: AdvertisementData):
    addr = device.address.upper()
    found_device = self.known_devices.get(addr)

    if found_device and not found_device.should_throttle():
      readings_dict = found_device.decode(device, advertisement)
      if readings_dict:
        readings_dict = {k: self.adjust_value(v) for k, v in readings_dict.items()}
        readings_json = json.dumps(readings_dict)
        try:
          self.queue.put_nowait((found_device.name, readings_json))
          self.bc_h.inc()
        except asyncio.QueueFull:
          self.bc_f.inc()
        return

    self.bc_i.inc()

  async def process_queue(self):
    while True:
      await asyncio.sleep(self.mqtt_pub_interval_s)

      # Ensure that we only keep the most recent value for each key
      to_publish = { k: v for k, v in self._queue_getall() }
      if to_publish:

        # Update all counters/gauges

        async with self.mqtt_client as mqtt:
          for item in to_publish.items():
            await mqtt.publish(
              f"{self.mqtt_prefix}{item[0]}", payload=str(item[1]))

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
    ble2mqtt.queue.put_nowait(('b2m/alive', "true"))


  pc.start_http_server(8088)
  loop.run_forever()
