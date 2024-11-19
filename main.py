#!/usr/bin/env python3
import asyncio
import aiomqtt
import json
from enum import Enum, Flag
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from victron_ble.devices.base import OperationMode

from obs import reporter, default_registry

from consumers import MqttPublisher, OpenMetricPublisher

#from obs.exporter import PrometheusExporter, LinesExporter



from pprint import pp

def dig(dict_like, keys):
  if not keys:
    return dict_like
  key = keys[0]
  if key in dict_like:
    return dig(dict_like[key], keys[1:])


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

  def __init__(self, config_map, reporter=reporter()):
    self.known_devices = config_map['devices']
    self.metric_path = tuple(config_map.get('metric_path', ()))

    self.mqtt_exporter = MqttPublisher(
      broker=config_map['mqtt_broker_addr'],
      username=config_map.get('mqtt_user'),
      password=config_map.get('mqtt_pass'),
      prefix=self.metric_path,
      registry=reporter.registry
    )

    self.mqtt_pub_interval_s = config_map['mqtt_pub_interval_s']

    self.om_server = OpenMetricPublisher(
      reporter.registry,
      port=8088
    )

    #self.queue = asyncio.Queue(maxsize=250)
    self.bs_callback = lambda dev, data: self.on_advertise(dev, data)

    ## TODO: Make this NOT per-device?
    for device in self.known_devices.values():
      device.throttle_s = config_map["ble_throttle_s"]

    self.int_metrics = reporter.scoped("ble2mqtt")
    self.reporter = reporter.scoped(*self.metric_path)

    bctr = self.int_metrics.counter('beacons', "How each beacon was processed")
    self.bc_h = bctr.labeled("action", "handled")
    self.bc_i = bctr.labeled("action", "ignored")
    self.bc_t = bctr.labeled("action", "throttled")

    self.unhandled_ctr = self.int_metrics.counter('unhandled', 'BLE Beacon data that could not become a metric')

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

    if found_device:
      if found_device.should_throttle():
        self.bc_t.inc()
        return

      readings_dict = found_device.decode(device, advertisement)
      if readings_dict:
        self.bc_h.inc()
        self.update_metrics_from_readings(found_device.name, readings_dict)
        return

    self.bc_i.inc()

  def update_metrics_from_readings(self, devname, readings):
    scoped = self.reporter.scoped(devname)
    for key, val in readings.items():
      match val:
        case float() | int():
          val = round(val, 3)
          gauge = scoped.gauge(key).set(val)
        case Enum() | Flag():
          state = scoped.state(key).set(val.name.lower())
        case _:
          self.unhandled_ctr.inc()

  def prepare(self, loop):
    async def scan():
      self.scanner = BleakScanner(detection_callback=self.bs_callback)
      await self.scanner.start()

    async def export_mqtt():
      while True:
        await asyncio.sleep(self.mqtt_pub_interval_s)
        await self.mqtt_exporter.publish()

    loop.create_task(scan())
    self.om_server.setup(loop)

    loop.create_task(export_mqtt())

  async def stop(self):
    await self.scanner.stop()
    await self.om_server.stop()
    loop.stop()
    loop.close()

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
  from consumers import MqttPublisher
  import sys
  import signal

  loop = asyncio.new_event_loop()
  asyncio.set_event_loop(loop)
  ble2mqtt = None

  def ctrl_c(sig, frame):
    print("\nBye!")
    sys.exit(0)

  signal.signal(signal.SIGINT, ctrl_c)

  cmd = sys.argv[1] if len(sys.argv) > 1 else None

  if cmd == 'scan':
    dump_names(loop)
  else:
    ble2mqtt = Ble2Mqtt(CurrentConfig)
    ble2mqtt.prepare(loop)

  loop.run_forever()
