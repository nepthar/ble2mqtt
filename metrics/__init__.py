from enum import Enum
from dataclasses import dataclass
from typing import Optional
from threading import RLock
import time


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
  desc: str
  timestamp: float

  def as_line(self, ts=True):
    """ Convert this reading to a basic Prometheus/OpenMetric line """
    ts_part = f" {self.timestamp}" if ts and self.timestamp > 1 else ""
    return f"{metric_id_str(self.path, self.labels)} {self.value}{ts_part}"


def _metric_id(path, labels):
  return path + (tuple(sorted(labels.items())),)


def metric_id_str(path, labels):
  path_part = "/".join(path)
  label_part = ""
  if labels:
    label_part = "{" + ", ".join(f"{k}={v}" for k, v in sorted(labels.items())) + "}"
  return path_part + label_part


class Metric:

  __slots__ = (
    'id',
    'path',
    'desc',
    'value',
    'value_fn',
    'reporter',
    'kwargs',
    'labeles',
    'children',
    'last_sample_at'
  )

  # The kind of metric used to generate Record
  kind: MetricKind

  # Whether or not this metric allows `value_fn`
  allow_fn: True

  def __init__(self, reporter, path, desc='', labels=dict(), **kwargs):
    # TODO: Sanity check desc and path. Or not, yolo.

    if not path:
      raise ArgumentError("Path must not be empty")

    self.reporter = reporter
    self.path = path
    self.desc = desc
    self.id = metric_id_str(path, labels)
    self.labels = labels
    self.children = set()
    self.kwargs = kwargs
    self.last_sample_at = 0
    self.value = None
    self.value_fn = None
    self._init_metric_(**kwargs)

  def _init_metric_(self, **kwargs):
    raise NotImplementedError

  def is_labeled(self):
    return not not self.labels

  def collect(self):
    raise NotImplementedError

  def labeled(self, label, label_val):
    return self.reporter.labeled(self, label, label_val)

  def peek(self):
    """ Peek at the value of this metric. Sometimes this is not possible
        Like in histograms, etc.
    """
    return self.value if self.value else "n/a"

  def _update_(self):
    if self.value_fn:
      self.set(self.value_fn())

  def set_fn(self, value_fn):
    """ Have this metric use `value_fn` to retrieve the value when collected """
    self.last_sample_at = 0
    self.value_fn = value_fn

  def reading(self):
    self._update_()
    return Reading(
      self.kind, self.path, self.value, self.labels, self.desc, self.last_sample_at
    )

  def __repr__(self):
    return f"{self.__class__.__name__}({self.id}, value={self.peek()})"

  def __str__(self):
    return self.__repr__()


class NullMetric(Metric):
  """ Does nothing successfully """
  def _init_metric_(*args, **kwargs):
    pass

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

  def collect(self):
    yield from ()


class Counter(Metric):
  kind = MetricKind.COUNTER

  def _init_metric_(self, **kwargs):
    self.value = 0

  def set_fn(self, value_fn):
    raise NotImplementedError("Counters do not use functions")

  def inc(self, amt=1):
    if self.children:
      raise Exception(f"{self} has children - cannot inc directly")
    # TODO: Ensure positive. Meh, shoot yourself in the foot if you want.
    self.last_sample_at = time.time()
    self.value += amt

  def collect(self):
    if self.is_labeled():
      # Don't actually collect anything - the parent will handle this.
      return
    elif self.children:
      # This is the parent metric, add a "_total" reading and collect from all
      # of the children.
      total = 0
      total_at = 0
      path = self.path
      for m in self.children:
        total += m.value
        total_at = max(total_at, m.last_sample_at)
        yield Reading(MetricKind.COUNTER, path, m.value, m.labels, self.desc, m.last_sample_at)

      yield Reading(MetricKind.COUNTER, path, total, self.labels, self.desc, total_at)
    else:
      yield self.reading()


class Gauge(Metric):
  kind = MetricKind.GAUGE
  def _init_metric_(self, **kwargs):
    self.value = kwargs.get('value', 0.0)
    self.value_fn = None

  def inc(self, amt=1.0):
    self.last_sample_at = time.time()
    self.value += 1

  def dec(self, amt=1.0):
    self.last_sample_at = time.time()
    self.value -= amt

  def set(self, newval):
    self.last_sample_at = time.time()
    self.value = newval

  def collect(self):
    self._update_()
    yield self.reading()


class State(Metric):
  kind = MetricKind.STATE

  def _init_metric_(self, state=None, states=[], state_fn=None, **kwargs):
    self.value = None
    self.state_fn = state_fn
    self.states = set(states)
    self.restrict = bool(states)

    if state:
      self.set(state)

  def set(self, new_state):
    assert isinstance(new_state, str)

    if self.restrict and new_state not in self.states:
      raise Exception(f"State {new_state} is not in {self.states}")

    self.value = new_state
    self.states.add(new_state)
    self.last_sample_at = time.time()

  def set_fn(self, fn):
    self.state_fn = fn

  def _update_(self):
    if self.state_fn:
      self.set(self.state_fn())

  def collect(self):
    if self.children:
      return
    else:
      yield self.reading()


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

  def find_or_create(self, klass, reporter, path, desc, labels, **kwargs):
    new_m_id = metric_id_str(path, labels)

    metric = self.find(klass, new_m_id)
    if metric:
      return metric

    metric = klass(
      reporter=reporter,
      path=path,
      desc=desc,
      labels=labels,
      **kwargs
    )

    self.metrics[new_m_id] = metric
    return metric

  def value(self, path, labels=()):
    found = self.metrics.get(metric_id_str(path, labels))
    return found.peek() if found else None

  def collect(self):
    for m in sorted(self.metrics.values(), key=lambda x: x.id):
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

  def find_or_create(self, klass, reporter, path, desc, labels, **kwargs):
    with self.lock:
      return self._reg.find_or_create(klass, reporter, path, desc, labels, **kwargs)

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

  def _mk_(self, klass, name, desc, labels=dict(), **kwargs):
    return self.registry.find_or_create(
      klass=klass,
      reporter=self,
      path=self.path + (name,),
      desc=desc,
      labels=labels,
      **kwargs
    )

  def scoped(self, *new_path):
    return MetricReporter(self.registry, self.path + tuple(new_path))

  def labeled(self, metric, label, label_val):
    new_labels = metric.labels.copy()
    new_labels[label] = label_val
    new_m_id = _metric_id(metric.path, new_labels)

    if new_m_id == metric.id:
      return metric

    labeled_metric = self._mk_(
      klass=metric.__class__,
      name=metric.path[-1],
      desc=metric.desc,
      labels=new_labels,
      **metric.kwargs
    )

    metric.children.add(labeled_metric)

    return labeled_metric

  def counter(self, name, desc=''):
    return self._mk_(Counter, name, desc)

  def gauge(self, name, desc=''):
    return self._mk_(Gauge, name, desc)

  def stat(self, name, desc='', **kwargs):
    return self_mk_(Stat, name, desc, **kwargs)

  def state(self, name, desc='', state=None, states=set(), **kwargs):
    return self._mk_(State, name, desc, state=state, states=states, **kwargs)


class NullMetricReporter(MetricReporter):
  def __init__(self):
    self.null_metric = NullMetric(
      reporter=self,
      path=("null",),
      desc="NullMetric")

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

  def state(*args, **kwargs):
    return self.null_metric


REGISTRY = Registry()
NULL_REPORTER = NullMetricReporter()


def registry():
  return REGISTRY


def reporter():
  return MetricReporter(REGISTRY)


def null_reporeter():
  return NULL_REPORTER

