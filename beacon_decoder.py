import time
import struct
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData


class BeaconDecoder:
  """Decodes the BLE advertisement data into a key-value dict"""

  def __init__(self, name):
    self.throttle_expire = 0
    self.throttle_s = 0
    self.name = name

  def should_throttle(self):
    now = time.time()
    if now > self.throttle_expire:
      self.throttle_expire = now + self.throttle_s
      return False
    return True

  def decode(self, device: BLEDevice, adv_data: AdvertisementData):
    """Decode the advertisement data from the device into a dict"""
    raise NotImplementedError


class VTDecoder(BeaconDecoder):
  VT_MFG_HEX = 0x02E1
  VT_DATA_PREFIX = b"\x10"

  def __init__(self, name, vt_device_class, key):
    super().__init__(name)
    self.vt_ble = vt_device_class(key)

  def decode(self, device: BLEDevice, adv_data: AdvertisementData):
    vt_data = adv_data.manufacturer_data.get(self.VT_MFG_HEX)
    if vt_data and vt_data.startswith(self.VT_DATA_PREFIX):
      data_dict = self.vt_ble.parse(vt_data)._data
      # why tf doesn't it do this automatically?
      if "current" and "voltage" in data_dict:
        data_dict["power"] = float(data_dict["current"]) * float(data_dict["voltage"])
      return data_dict

    return {}


class MokoH4Decoder(BeaconDecoder):
  SVC_DATA_KEY = "0000feab-0000-1000-8000-00805f9b34fb"
  DATA_PREFIX = b"\x70"

  def __init__(self, name):
    super().__init__(name)

  def decode(self, device: BLEDevice, adv_data: AdvertisementData):
    sd = adv_data.service_data.get(self.SVC_DATA_KEY)
    if sd and sd.startswith(self.DATA_PREFIX):
      t = round(struct.unpack(">H", sd[3:5])[0] / 10.0, 1)
      h = round(struct.unpack(">H", sd[5:7])[0] / 10.0, 1)
      tf = (t * 1.8) + 32.0

      return {"temperature_c": t, "humidity_pc": h, "temperature_f": tf}

    return {}
