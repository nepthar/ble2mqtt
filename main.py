#!/usr/bin/env python3
import asyncio
import aiomqtt
import json
from enum import Enum
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

OUTPUT = False

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

  def __init__(self, config_map):
    self.known_devices = config_map['devices']
    self.mqtt_addr = config_map['mqtt_broker_addr']
    self.mqtt_pub_interval_s = config_map['mqtt_pub_interval_s']
    self.mqtt_prefix = config_map['mqtt_prefix']
    self.mqtt_user = config_map.get('mqtt_user')
    self.mqtt_pass = config_map.get('mqtt_pass')
    self.queue = asyncio.Queue(maxsize=250)
    self.bs_callback = lambda dev, data: self.on_advertise(dev, data)

    for device in self.known_devices.values():
      device.throttle_s = config_map["ble_throttle_s"]

  def _queue_putall(self, items):
    try:
      for i in items:
        self.queue.put_nowait(i)
    except asyncio.QueueFull:
      pass

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
        #print(f"{found_device.name}: {readings_json}")
        self.queue.put_nowait((found_device.name, readings_json))
        #self.queue.put_nowait(found_device.name, )
        #self._queue_putall((f"{found_device.name}/{k}", v) for k, v in readings_dict.items())

  async def mqtt_publish(self):
    while True:
      await asyncio.sleep(self.mqtt_pub_interval_s)

      # Ensure that we only keep the most recent value for each key
      to_publish = { k: v for k, v in self._queue_getall() }
      if to_publish:
        async with aiomqtt.Client(self.mqtt_addr, username=self.mqtt_user, password=self.mqtt_pass) as mqtt:
          for item in to_publish.items():
            await mqtt.publish(f"{self.mqtt_prefix}{item[0]}", payload=str(item[1]))

  def prepare(self, loop):
    async def scan():
      scanner = BleakScanner(detection_callback=self.bs_callback)
      await scanner.start()

    loop.create_task(scan())
    loop.create_task(self.mqtt_publish())


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

  def ctrl_c(sig, frame):
    loop.stop()
    print("\nBye")
    sys.exit(0)

  signal.signal(signal.SIGINT, ctrl_c)

  if sys.argv[1] == 'scan':
    dump_names(loop)
  else:
    ble2mqtt = Ble2Mqtt(CurrentConfig)
    ble2mqtt.prepare(loop)
    ble2mqtt.queue.put_nowait(('b2m/alive', "true"))


  loop.run_forever()
