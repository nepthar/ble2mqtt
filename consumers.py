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

    self.last_publish_at = time.time()

    rendered = []
    for group, values in readings.items():
      path_str = f"{prefix_str}/" + "/".join(group)
      for k in values.keys():
        values[k] = adjust_value(values[k].value)

      rendered.append((path_str, json.dumps(values)))

    async with self.mqtt_client as mqtt:
      for key, payload in rendered:
        await mqtt.publish(key, payload=payload)


class OpenMetricPublisher:
  def __init__(self,
      registry,
      aiohttp_app=web.Application(),
      port=8088,
      inc_help_type=True,
      om_strict=True
    ):
    self.registry = registry
    self.port = port
    self.app = aiohttp_app
    self.runner = None
    self.extras = inc_help_type

    async def handle_stats(request):
      return web.Response(text="\n".join(self.collect()))

    self.app.add_routes([web.get('/stats', handle_stats)])

  def setup_aiohttp(self, loop):
    # set up aiohttp - like run_app, but non-blocking
    runner = web.AppRunner(self.app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, port=self.port)
    loop.run_until_complete(site.start())

  async def stop(self):
    await self.runner.cleanup()

  def collect(self):
    readings = self.registry.read()
    prev_path = None
    for r in readings:
      # Output the TYPE/HELP if this is the first of this thing's path
      if self.extras:
        if prev_path != r.path:
          yield record_to_om_type(r)
          if r.desc:
            yield record_to_om_help(r)

      prev_path = r.path
      yield record_to_om_string(r)
