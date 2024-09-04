from beacon_decoder import VTDecoder, MokoH4Decoder
from victron_ble.devices import BatteryMonitor, SolarCharger

SampleConfig = {
  # A dictionary of devices keyed off of their address (or UUID if it's a mac)
  'devices': {
    "FB:23:8C:6C:8C:B0": MokoH4Decoder("h4_8cb0"),
    "D3:EF:7F:F0:46:3D": MokoH4Decoder("h4_463d"),
    "AA:BB:CC:DD:EE:FF": VTDecoder("solar", SolarCharger, "00000000000000000000000000000000"),
    "AA:BB:CC:DD:EE:00": VTDecoder("bms", BatteryMonitor, "11111111111111111111111111111111"),
  },

  # If a device broadcasts faster than this, the reading is discarded
  "ble_throttle_s": 5,

  # The prefix on the MQTT broadcast to apply to all messages
  "mqtt_prefix": "room/sensor/",

  # MQTT Broker address
  "mqtt_broker_addr": "mqtt.broker.address.com",

  # Broker username (can be None)
  "mqtt_user": "mosquitto",

  # Broker password (can be None)
  "mqtt_pass": "hunter2",

  # Publish a batch of MQTT messages on this interval
  "mqtt_pub_interval_s": 30
}

CurrentConfig = SampleConfig
