#!/usr/bin/env python3
import asyncio
import aiomqtt
import json
from enum import Enum, Flag
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from victron_ble.devices.base import OperationMode

from obs import reporter
from obs.exporter import PrometheusExporter, LinesExporter

from pprint import pp

  # async def publish_to_mqtt(self, to_publish):
  #   async with self.mqtt_client as mqtt:
  #     for devname, readings in to_publish.items():
  #       adjusted = { k: Ble2Mqtt.adjust_value(v) for k, v in readings.items() }
  #       await mqtt.publish(
  #         f"{self.mqtt_prefix}{devname}", payload=json.dumps(adjusted))


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

    self.pm_exporter = PrometheusExporter()
    # self.mqtt_exporter = MqttExporter(
    #   broker=config_map['mqtt_broker_addr'],
    #   username=config_map.get('mqtt_user'),
    #   password=config_map.get('mqtt_pass'),
    #   publish_interval_s=config_map['mqtt_pub_interval_s']
    # )

    self.queue = asyncio.Queue(maxsize=250)
    self.bs_callback = lambda dev, data: self.on_advertise(dev, data)

    ## TODO: Make this NOT per-device?
    for device in self.known_devices.values():
      device.throttle_s = config_map["ble_throttle_s"]

    self.reporter = reporter.scoped(*self.metric_path)

    self.queue_depth = reporter.gauge("queue_depth", "Beacon reading queue depth")
    self.queue_depth.set_fn(lambda: self.queue.qsize())

    bctr = self.reporter.counter('beacons', "How each beacon was processed")
    self.bc_h = bctr.labeled("action", "handled")
    self.bc_i = bctr.labeled("action", "ignored")
    self.bc_t = bctr.labeled("action", "throttled")
    self.bc_x = self.bc_t.labeled("path","500")
    self.bc_x.inc()

    self.unhandled_ctr = self.reporter.counter('unhandled', 'BLE Beacon data that could not become a metric')

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
    print(devname)
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
        await asyncio.sleep(self.mqtt_exporter.interval_s)

        #await self.mqtt_exporter.export()


    loop.create_task(scan())
    #loop.create_task(export_mqtt())

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
    print("\n")
    # #pp(LinesExporter().collect())

    # for x in LinesExporter().collect():
    #   pp(x)

    pp(LinesExporter().getob())
    print("\nBye")
    sys.exit(0)

  signal.signal(signal.SIGINT, ctrl_c)

  cmd = sys.argv[1] if len(sys.argv) > 1 else None

  if cmd == 'scan':
    dump_names(loop)
  else:
    ble2mqtt = Ble2Mqtt(CurrentConfig)
    ble2mqtt.prepare(loop)
    ble2mqtt.pm_exporter.start()
    #ble2mqtt.queue.put_nowait(('b2m', {"alive": "true"}))

  loop.run_forever()
