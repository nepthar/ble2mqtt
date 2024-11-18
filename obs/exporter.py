from . import default_registry
from .metric import MetricKind

import prometheus_client.core as pmc
import prometheus_client.registry as pmr
import prometheus_client as pm
from prometheus_client.samples import Sample, Timestamp

import json
import aiomqtt

from enum import Enum, Flag

def adjust_value(val):
  match val:
    case float():
      return round(val, 2)
    case Enum() | Flag():
      return val.name
    case _:
      return val


# class MqttExporter:
#   def __init__(self, broker, username, password, publish_interval_s, registry=registry()):
#     self.registry = registry
#     self.interval_s = publish_interval_s

#     self.mqtt_client = aiomqtt.Client(
#       hostname=broker,
#       username=username,
#       password=password,
#     )

#   async def export(self):
#     readings = list(self.registry.collect())
#     singles = []
#     dics = {}

#     for r in readings:
#       last_path = r.path[-1]
#       if ':' in last_path:
#         # This is a dict thingy.
#         k, _, v = last_path.partition(':')

#         key = '/'.join(r.path[:-1]) + '/' + k
#         collection = dics.get(key, list())
#         collection.append((v, r.value))
#         dics[key] = collection
#       else:
#         singles.append((r.path, r.value))

#     to_publish = []
#     for k, collection in dics.items():
#       values_json = {v[0]: v[1] for v in collection}
#       values_json = json.dumps(values_json)
#       to_publish.append((k, values_json))

#     for i in singles:
#       keyname = '/'.join(i[0])
#       value = str(adjust_value(i[1]))
#       to_publish.append((keyname, value))

#     async with self.mqtt_client as mqtt:
#       for key, value in to_publish:
#         await mqtt.publish(key, payload=value)


class ProMetricHelper:
  """ We're just going to do this ourselves one day. God damn prometheus """

  def __init__(self, r, type):
    ts = Timestamp(r.value.timestamp, 0.0) if r.value.timestamp else None
    self.name = "_".join(r.path)
    self.type = type
    self.documentation = r.desc
    self.samples = [
      Sample(
        name=self.name,
        labels=r.value.labels,
        value=r.value.val,
        timestamp=ts,
        exemplar=None
      )
    ]


class PrometheusExporter(pmr.Collector):
  def __init__(self, registry=default_registry(), port=8088):
    self.port = port
    self.registry = registry

  def start(self):
    pmc.REGISTRY.register(self)
    pm.start_http_server(self.port)

  def collect(self):
    for r in self.registry.collect():
      match r.kind:
        case MetricKind.COUNTER:
          yield ProMetricHelper(r, 'counter')
        case MetricKind.GAUGE:
          yield ProMetricHelper(r, 'gauge')
        case MetricKind.STATE:
          pass
          #yield ProMetricHelper(r, 'gauge')
        case _:
          print(f"pc unhandled metric kind: {r.kind}")


class LinesExporter:
  def __init__(self, registry=default_registry()):
    self.registry = registry

  def collect(self):
    return (r.as_line(ts=False) for r in self.registry.collect())

  def getob(self):
    return self.registry.as_dict()


