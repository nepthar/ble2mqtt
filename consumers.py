import json
import aiomqtt

from obs.data import MetricKind
from aiohttp import web
from enum import Enum, Flag
import time

from pprint import pp

def adjust_value(val):
  match val:
    case float():
      return round(val, 2)
    case Enum() | Flag():
      return val.name.lower()
    case _:
      return val


def record_to_om_name(rec):
  om_name = '_'.join(rec.path.parts)
  if rec.kind == MetricKind.COUNTER and not om_name.endswith('_total'):
    om_name = om_name + "_total"
  return om_name


def record_to_om_string(rec):
  om_name = record_to_om_name(rec)
  value = str(rec.value)
  ts = f" {round(rec.at)}" if rec.at > 1 else ""
  labels = rec.labels

  match rec.kind:
    case MetricKind.COUNTER:
      pass
    case MetricKind.GAUGE:
      pass
    case MetricKind.STATE:
      labels = labels.labeled('state', value)
      value = "1"
    case MetricKind.STAT:
      pass
    case MetricKind.INFO:
      for k, v in rec.items():
        labels = labels.labeled(k, v)
      value = "1"
    case _ :
      pass

  labels_part = labels.as_str()

  return ''.join((om_name, labels_part, ' ', value, ts))

def record_to_om_help(rec):
  return f"# HELP {rec.desc}"

def record_to_om_type(rec):
  typestr = 'unknown'
  match rec.kind:
    case MetricKind.COUNTER:
      typestr = "counter"
    case MetricKind.GAUGE:
      typestr = "gauge"
    case MetricKind.STATE:
      typestr = "stateset"
    case MetricKind.STAT:
      typestr = "histogram"
    case MetricKind.INFO:
      typestr = "info"
    case _ :
      pass

  return f"# TYPE {typestr}"


class MqttPublisher:
  def __init__(self, broker, username, password, prefix, registry):
    self.registry = registry
    self.mqtt_client = aiomqtt.Client(
      hostname=broker,
      username=username,
      password=password,
    )
    self.prefix = prefix
    self.last_publish_at = 0

  async def publish(self):
    prefix_str = "/".join(self.prefix)
    readings = self.registry.read(
      prefix=self.prefix,
      after=self.last_publish_at
    ).as_dict()

    pp(readings)

    print("\n")

    self.last_publish_at = time.time()



    # rendered = []
    # for path, group in readings.items():
    #   pathstr = '/'.join(path)
    #   for k in group.keys():
    #     group[k] = adjust_value(group[k].value)

    #   rendered.append((prefix_str + pathstr, json.dumps(group)))

    # async with self.mqtt_client as mqtt:
    #   for key, payload in rendered:
    #     await mqtt.publish(key, payload=payload)


class OpenMetricPublisher:
  def __init__(self,
      registry,
      aiohttp_app=web.Application(),
      port=8088,
      inc_help_type=False
    ):
    self.registry = registry
    self.port = port
    self.app = aiohttp_app
    self.runner = None
    self.extras = inc_help_type

    async def handle_stats(request):
      return web.Response(text="\n".join(self.collect_lines()))

    self.app.add_routes([web.get('/stats', handle_stats)])

  def setup(self, loop):
    # set up aiohttp - like run_app, but non-blocking
    runner = web.AppRunner(self.app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, port=self.port)
    loop.run_until_complete(site.start())

  async def stop(self):
    await self.runner.cleanup()

  def collect_lines(self):
    return (record_to_om_string(r) for r in self.registry.readings())
