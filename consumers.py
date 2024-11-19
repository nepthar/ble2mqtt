from obs import default_registry
from obs.metric import Reading

import json
import aiomqtt
from aiohttp import web

from enum import Enum, Flag

from pprint import pp

def adjust_value(val):
  match val:
    case float():
      return round(val, 2)
    case Enum() | Flag():
      return val.name.lower()
    case _:
      return val


class MqttPublisher:
  def __init__(self, broker, username, password, prefix, registry):
    self.registry = registry
    self.mqtt_client = aiomqtt.Client(
      hostname=broker,
      username=username,
      password=password,
    )
    self.prefix = prefix

  async def publish(self):
    to_publish = {}
    for r in self.registry.readings(self.prefix):
      group = r.group('/')
      key = r.flatkey()

      to_publish.setdefault(group, {})
      to_publish[group][key] = adjust_value(r.value)

    rendered = [(k, json.dumps(v)) for k, v in to_publish.items()]

    async with self.mqtt_client as mqtt:
      for key, payload in rendered:
        await mqtt.publish(key, payload=payload)


class OpenMetricPublisher:
  def __init__(self, registry, aiohttp_app=web.Application(), port=8088):
    self.registry = registry
    self.port = port
    self.app = aiohttp_app
    self.runner = None

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
    return (r.om_str() for r in self.registry.readings())
