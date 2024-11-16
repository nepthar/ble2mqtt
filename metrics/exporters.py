from . import registry, MetricKind

import prometheus_client.core as pmc
import prometheus_client.registry as pmr
import prometheus_client as pm
from prometheus_client.samples import Sample, Timestamp


class MqttExporter:
  def __init__(self, broker, username, password, publish_interval_s, registry=registry()):
    self.registry = registry
    self.broker = broker
    self.username = username
    self.password = password
    self.interval_s = publish_interval_s

  def export(self):
    pass

class ProMetricHelper:

  def __init__(self, r, type):
    ts = Timestamp(r.timestamp, 0.0) if r.timestamp else None
    self.name = "_".join(r.path)
    self.type = type
    self.documentation = r.desc
    self.samples = [
      Sample(
        name=self.name,
        labels=r.labels,
        value=r.value,
        timestamp=ts,
        exemplar=None
      )
    ]

class PrometheusExporter(pmr.Collector):
  def __init__(self, registry=registry(), port=8088):
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
        case _:
          print(f"pc unhandled metric kind: {r.kind}")


class LinesExporter:
  def __init__(self, registry=registry()):
    self.registry = registry

  def collect(self):
    return (r.as_line(ts=False) for r in self.registry.collect())

