# This is a copy of Twitter's metrics merged with prometheus metrics.
# It enables some helpful stuff.

## TODO: Lables(?)


from enum import Enum
from dataclasses import dataclass
from typing import Optional
from threading import RLock
import time
#from cachetools import TTLCache

import prometheus_client as pm
import prometheus_client.core as pmc
import prometheus_client.registry as pmr

# If a metric has not had a sample in 1 day, evict it
METRIC_TLL = 1 * 24 * 60 * 60


class MetricKind(Enum):
  COUNTER = 1
  GAUGE = 2
  STATE = 3
  STAT = 4
  INFO = 5


@dataclass
class Reading:
  """ metric id -> value pair with a timestamp, exported """
  kind: MetricKind
  path: tuple[str]
  value: any
  labels: dict[str, str]
  timestamp: float


def _metric_id(path, labels):
  return path + (tuple(sorted(labels.items())),)


class Metric:

  __slots__ = (
    'path', 'desc', 'reporter', 'id', 'kwargs', 'labeles', 'submetrics' 'last_sample_at'
  )

  def __init__(self, reporter, path, desc='', labels=dict(), **kwargs):
    # TODO: Sanity check desc and path. Or not, yolo.

    if not path:
      raise ArgumentError("Path must not be empty")

    self.reporter = reporter
    self.path = path
    self.desc = desc
    self.id = _metric_id(path, labels)
    self.labels = labels
    self.submetrics = set()
    self.kwargs = kwargs
    self.last_sample_at = 0
    self._init_metric_(**kwargs)

  def _init_metric_(self, **kwargs):
    raise NotImplementedError

  def is_labeled(self):
    return not not self.labels

  def collect(self):
    yield from ()

  def labeled(self, label, label_val):
    return self.provider.labeled(self, label, label_val)

  def id_str(self):
    path_part = "/".join(self.path)
    label_part = ""
    if self.labels:
      label_part = "{" + ", ".join(f"{k}={v}" for k, v in self.id[-1]) + "}"

    return path_part + label_part

  def peek(self):
    """ Peek at the value of this """
    return "..."

  def __repr__(self):
    return f"{self.__class__}({self.id_str()}, value={self.peek()})"

  def __str__(self):
    return self.__repr__()


class NullMetric(Metric):
  """ Does nothing successfully """
  def inc(*args, **kwargs):
    pass

  def dec(*args, **kwargs):
    pass

  def set(*args, **kwargs):
    pass

  def set_fn(*args, **kwargs):
    pass

  def rec(*args, **kwargs):
    pass


class Counter(Metric):
  def _init_metric_(self, **kwargs):
    self.counter = 0

  def inc(self, amt=1):
    if self.is_labeled():
      raise Exception(f"{self} has submetrics - cannot inc directly")
    # TODO: Ensure positive. Meh, shoot yourself in the foot if you want.
    self.counter += amt

  def collect(self):
    if self.is_labeled():
      # Don't actually collect anything - the parent will handle this.
      return
    elif self.submetrics:
      # This is the parent metric, add a "_total" reading and collect from all
      # of the children.
      total = 0
      total_at = 0
      path = self.path
      for m in submetrics:
        total += m.counter
        total_at = max(total_at, m.last_sample_at)
        yield Reading(MetricKind.COUNTER, path, m.counter, m.labels, m.last_sample_at)

      yield Reading(MetricKind.COUNTER, path + ('total',), total, self.labels, total_at)
    else:
      yield Reading(MetricKind.COUNTER, self.path, self.counter, self.labels, self.last_sample_at)

  def peek(self):
    return self.counter


class Gauge(Metric):
  def _init_metric_(self, **kwargs):
    self.gauge = kwargs.get('value', 0.0)
    self.gauge_fn = None

  def inc(self, amt=1.0):
    self.last_sample_at = time.time()
    self.gauge += 1

  def dec(self, amt=1.0):
    self.last_sample_at = time.time()
    self.gauge -= amt

  def set(self, newval):
    self.last_sample_at = time.time()
    self.gauge = newval

  def set_fn(self, fn):
    self.last_sample_at = 0
    self.gauge_fn = fn

  def collect(self):
    if self.gauge_fn:
      yield Reading(MetricKind.GAUGE, self.path, self.gauge_fn(), (), time.time())
    else:
      yield Reading(MetricKind.GAUGE, self.path, self.gauge, (), self.last_sample_at)

  def peek(self):
    return self.gauge


class State(NullMetric):
  pass


class Stat(NullMetric):
  pass


class Registry:
  def __init__(self):
    self.metrics = dict()

  def register(self, metric):
    m_id = metric.id
    if m_id in self.metrics:
      raise Exception(f"Metric exists: {id}")

    self.metrics[m_id] = metric

  def unregister(self, metric):
    self.unregister_id(metric.id)

  def unregister_id(self, m_id):
    self.metrics.delete(m_id)

  def find(self, klass, metric_id):
    found = self.metrics.get(metric_id)
    if found:
      if klass != found.__class__:
        raise Exception(f"Found metric {new_m_id} with wrong type. Expected {klass} got {found.__class__}")
      return found

  def find_or_create(self, klass, provider, path, desc, labels, **kwargs):
    new_m_id = _metric_id(path, labels)

    new_metric = klass(
      provider=provider,
      path=metric.path,
      desc=metric.desc,
      labels=new_labels,
      **metric.kwargs
    )

    self.metrics[new_m_id] = new_metric
    return new_metric

  def value(self, path, labels=()):
    found = self.metrics.get(_metric_id(path, labels))
    return found.peek() if found else None

  def collect(self):
    for m in sorted(self.metrics.values()):
      yield from m.collect()


class ThreadsafeRegistry:

  def __init__(self):
    self._reg = Registry()
    self.lock = RLock()

  def register(self, metric):
    with self.lock:
      return self._reg.register(metric)

  def unregister_id(self, m_id):
    with self.lock:
      return self._reg.unregister_id(m_id)

  def find(self, klass, metric_id):
    with self.lock:
      return self._reg.find(klass, metric_id)

  def find_or_create(self, klass, provider, path, desc, labels, **kwargs):
    with self.lock:
      return self._reg.find_or_create(klass, provider, path, desc, labels, **kwargs)

  def collect(self):
    metrics = []
    with self.lock:
      metrics = sorted(self.metrics.values())
    for m in metrics:
      yield from m.collect()


class MetricReporter:
  def __init__(self, registry, path=()):
    self.path = path
    self.registry = registry

  def scoped(self, *new_path):
    return MetricReporter(self.registry, self.path + tuple(new_path))

  def labeled(self, metric, label, label_val):
    new_labels = metric.labels.copy()
    new_labels[label] = label_val
    new_m_id = _metric_id(metric.path, new_labels)

    if new_m_id == metric.id:
      return metric

    labeled_metric = self.registry.find_or_create(
      klass=metric.__class__,
      provider=self,
      path=metric.path,
      labels=new_labels,
      **metric.kwargs
    )

    metric.submetrics.add(labeled_metric)

    return labeled_metric

  def counter(self, name, desc=''):
    metric_path = self.path + (name,)
    return self.registry.find_or_create(Counter, self, metric_path, desc, dict())

  def gauge(self, name, desc=''):
    metric_path = self.path + (name,)
    return self.registry.find_or_create(Gauge, self, metric_path, desc, dict())

  def stat(self, name, desc='', **kwargs):
    metric_path = self.path + (name,)
    return self.registry.find_or_create(Stat, self, metric_path, desc, dict())

  def state(self, name, desc='', **kwargs):
    metric_path = self.path + (name,)
    return self.registry.find_or_create(State, self, metric_path, desc, dict())


class NullMetricReporter(MetricReporter):
  null_metric = NullMetric(('null',), 'NullMetric', dict(), None)

  def scoped(*args, **kwargs):
    return self.null_metric

  def labeled(*args, **kwargs):
    return self.null_metric

  def counter(*args, **kwargs):
    return self.null_metric

  def gauge(*args, **kwargs):
    return self.null_metric

  def enum(*args, **kwargs):
    return self.null_metric

  def stat(*args, **kwargs):
    return self.null_metric


class MqttExporter:
  def __init__(self, registry):
    self.registry = registry

  def export(self):
    pass


class PrometheusExporter(pmr.Collector):
  def __init__(self, port=8088, registry):
    self.port = port
    self.registry = registry

  def start(self):
    pmc.REGISTRY.register(self)
    pm.start_http_server(self.port)

  def collect(self):
    for metric in self.registry.metrics.values():
      for r in metric.collect():
        pc_metric_name = '_'.join(r.path)
        match r.kind:
          case MetricKind.COUNTER:
            yield pmc.CounterMetricFamily(pc_metric_name, metric.desc, value=r.value)
          case MetricKind.GAUGE:
            yield pmc.GaugeMetricFamily(pc_metric_name, metric.desc, value=r.value)
          case _:
            print(f"pc unhandled metric kind: {r.kind}")


REGISTRY = Registry()


def reporter():
  return MetricReporter(REGISTRY)


def null_reporeter():
  return NullMetricReporter()

