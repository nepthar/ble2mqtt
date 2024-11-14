# This is a copy of Twitter's metrics merged with prometheus metrics.
# It enables some helpful stuff.

## TODO: Lables(?)

from dataclasses import dataclass
from typing import Optional
import time
#from cachetools import TTLCache
#import prometheus_client as pc

# If a metric has not had a sample in 1 day, evict it
METRIC_TLL = 1 * 24 * 60 * 60
REGISTRY = None

@dataclass
class Reading:
  """ metric id -> value pair with a timestamp """
  path: tuple[str]
  value: any
  labels: dict[str, str]
  timestamp: float


def _metric_id(path, labels):
  return path + (tuple(sorted(labels.items())),)

class Metric:

  def __init__(self, path, desc, labels, reporter, **kwargs):
    # TODO: Sanity check desc and path. Or not, yolo.

    if not path:
      raise ArgumentError("Path must not be empty")

    self.path = path
    self.desc = desc
    self.last_sample_at = 0
    self.labels = labels
    self.reporter = reporter
    self.id = _metric_id(path, labels)
    self.kwargs = kwargs
    self._init_metric_(**kwargs)

  def _init_metric_(self, **kwargs):
    pass

  def collect(self):
    yield from ()

  def labeled(self, label, label_val):
    return self.reporter.labeled(self, label, label_val)


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


class SimpleCounter(Metric):

  def _init_metric_(self, **kwargs):
    self.counter = 0

  def inc(self, amt=1):
    # TODO: Ensure positive?
    self.counter += amt

  def collect(self):
    yield Reading(self.path, self.counter, self.labels, time.time())


class SimpleGauge(Metric):
  def _init_metric_(self, **kwargs):
    self.gauge = kwargs.get('value', 0.0)
    self.gauge_fn = None

  def inc(self, amt=1.0):
    self.timestamp = time.time()
    self.gauge += 1

  def dec(self, amt=1.0):
    self.timestamp = time.time()
    self.gauge -= amt

  def set(self, newval):
    self.timestamp = time.time()
    self.gauge = newval

  def set_fn(self, fn):
    self.timestamp = None
    self.gauge_fn = fn

  def collect(self):
    if self.gauge_fn:
      yield Reading(self.path, self.gauge_fn(), self.labels, time.time())
    else:
      yield Reading(self.path, self.gauge, self.labels, time.time())


class Registry:
  def __init__(self):
    self.metrics = dict()

  def register(self, metric):
    m_id = metric.id
    if m_id in self.metrics:
      raise Exception(f"Metric already exists: {id}")

    self.metrics[m_id] = metric

  def find(self, m_id):
    return self.metrics.get(m_id)

REGISTRY = Registry()

class Reporter:
  def __init__(self, path=(), registry=REGISTRY):
    self.path = path
    self.registry = registry

  def scoped(self, new_path):
    return Reporter(self.path + (path,), registery=self.registry)

  def labeled(self, metric, label, label_val):
    new_labels = metric.labels.copy()
    new_labels[label] = label_val
    new_m_id = _metric_id(metric.path, new_labels)

    if new_m_id == metric.id:
      return metric

    labeled_metric = self.registry.find(new_m_id)
    if labeled_metric:
      return labeled_metric

    klass = metric.__class__
    new_metric = klass(metric.path, metric.desc, new_labels, self, **metric.kwargs)
    self.registry.register(new_metric)
    return new_metric

  def counter(self, name, desc):
    return SimpleCounter(self.path + (name,), desc, dict(), self)

NULL_METRIC = NullMetric()

class NullReporter(Reporter):

  def __init__(self):
    pass

  def scoped(*args, **kwargs):
    return NULL_METRIC

  def labeled(*args, **kwargs):
    return NULL_METRIC

  def counter(*args, **kwargs):
    return NULL_METRIC

  def gauge(*args, **kwargs):
    return NULL_METRIC

  def enum(*args, **kwargs):
    return NULL_METRIC

  def stat(*args, **kwargs):
    return NULL_METRIC

NULL_REPORTER = NullReporter()
