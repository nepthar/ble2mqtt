import time
from enum import Enum
from dataclasses import dataclass
from collections import namedtuple

from .data import Reading, Value, Labels, Path, MetricKind

class Metric:
  __slots__ = (
    "path",
    "desc",
    "value",
    "value_fn",
    "reporter",
    "kwargs",
    "labeles",
    "last_sample_at",
  )

  # The kind of metric used to generate Record
  kind: MetricKind

  # Whether or not this metric allows `value_fn`
  allow_fn: True

  def __init__(
    self, reporter, path, desc="", labels=dict(), value=None, value_fn=None, **kwargs
  ):
    if not path:
      raise Exception("Path must not be empty")

    self.reporter = reporter
    self.path = path
    self.desc = desc
    self.labels = labels
    self.kwargs = kwargs
    self.last_sample_at = 0
    self.value = value
    self.value_fn = value_fn

    self._init_metric_(**kwargs)

  def name(self):
    return self.path.name()

  def _init_metric_(self, **kwargs):
    pass

  def labeled(self, label, label_val):
    new_labels = self.labels.labeled(label, label_val)
    return self.reporter.with_labels(self, new_labels)

  def peek(self):
    """Peek at the value of this metric. Sometimes this is not possible
    Like in histograms, etc.
    """
    if self.value:
      return self.value

    if self.value_fn:
      return "fn()"

    return "n/a"

  def set_fn(self, value_fn):
    """Have this metric use `value_fn` to retrieve the value when collected"""
    assert self.last_sample_at == 0, "Cannot set a function once a metric has been used"
    self.last_sample_at = 0
    self.value_fn = value_fn

  def set(self, value, at=time.time()):
    print(f"set {self.name()}")
    assert self.value_fn is None, "Cannot set a metric with a value_fn"
    self.value = value
    self.last_sample_at = at

  def update(self, at=time.time()):
    assert self.value_fn is not None, "Cannot update a metric without a value_fn"
    self.value = self.value_fn()
    self.last_sample_at = at

  def to_value(self):
    return Value(self.value, self.labels, self.last_sample_at)

  def __repr__(self):
    return f"{self.__class__.__name__}({self.name()}, value={self.peek()})"

  def __str__(self):
    return self.__repr__()

  def __lt__(self, other):
    if self.path < other.path:
      return True
    elif self.path == other.path:
      return tuple(self.labels.keys()) < tuple(other.labels.keys())
    else:  # self.path > other.path
      return False

  def __eq__(self, other):
    return self.path == other.path and self.labels == other.labels


class Counter(Metric):
  kind = MetricKind.COUNTER

  def _init_metric_(self, **kwargs):
    if self.value is None:
      self.value = 0

  def set_fn(self, value_fn):
    raise NotImplementedError("Counters do not use functions")

  def inc(self, amt=1, at=time.time()):
    self.last_sample_at = at
    self.value += amt


class Gauge(Metric):
  kind = MetricKind.GAUGE

  def inc(self, amt=1.0, at=time.time()):
    self.set(self.value + amt, at)

  def dec(self, amt=1.0, at=time.time()):
    self.set(self.value - amt, at)


class State(Metric):
  kind = MetricKind.STATE

  def _init_metric_(self, states=[], **kwargs):
    self.states = set(states)
    self.restrict = bool(states)

  def set(self, new_state, at=time.time()):
    assert isinstance(new_state, str)

    if self.restrict and new_state not in self.states:
      raise Exception(f"State {new_state} is not in {self.states}")

    self.states.add(new_state)
    super().set(new_state, at)


class Stat(Metric):
  pass


class NullMetric(Metric):
  """Does nothing successfully"""

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
