import time
from enum import Enum
from dataclasses import dataclass
from collections import namedtuple

from .data import Reading, ObsKey, ObsKind


class Metric:

  kind: ObsKind = ObsKind.UNKNOWN

  default = None

  __slots__ = (
    'key',
    'observer',
    'desc',
    'value',
    'value_fn',
    'last_sample_at',
    'level',
    'kwargs'
  )

  def __init__(self, key, observer, level, desc="", **kwargs):
    self.key = key
    self.observer = observer
    self.desc = desc
    self.kwargs = kwargs
    self.level = level

    self.value = None
    self.value_fn = None
    self.last_sample_at = 0

    self._init_metric_(**kwargs)

  def _init_metric_(self, **kwargs):
    pass

  def labeled(self, lname, lval):
    new_key = self.key.labeled(lname, lval)
    return self.observer._get_(
      klass=self.__class__,
      key=new_key,
      desc=self.desc,
      level=self.level,
      **self.kwargs
    )

    return ret

  def peek(self):
    """Peek at the value of this metric. Sometimes this is not possible
    Like in histograms, etc.
    """
    if self.last_sample_at:
      if self.value:
        return self.value

      if self.value_fn:
        return f"fn()->{self.value}"

    return self.default

  def set_fn(self, value_fn):
    """Have this metric use `value_fn` to retrieve the value when collected"""
    assert self.last_sample_at == 0, "Cannot set a function once a metric has been used"
    self.last_sample_at = 0
    self.value_fn = value_fn

  def set(self, value):
    assert self.value_fn is None, "Cannot set a metric with a value_fn"
    self.value = value
    self.last_sample_at = time.time()

  def update(self):
    """ Update this metric from the given function if it has one. Noop if not """
    if self.value_fn:
      self.value = self.value_fn()
      self.last_sample_at = time.time()

  def read(self):
    self.update()
    return self.value, self.last_sample_at


class Counter(Metric):
  kind = ObsKind.COUNTER
  default = 0

  def _init_metric_(self, value=0, **kwargs):
    self.value = value

  def set_fn(self, value_fn):
    raise NotImplementedError("Counters do not use functions")

  def inc(self, amt=1):
    assert amt > 0, "Amount must be positive"
    self.set(self.value + amt)


class Gauge(Metric):
  kind = ObsKind.GAUGE

  def _init_metric_(self, value=None, **kwargs):
    self.value = value

  def inc(self, amt=1.0):
    self.set(self.value + amt)

  def dec(self, amt=1.0):
    self.set(self.value - amt)


class State(Metric):
  kind = ObsKind.STATE

  def _init_metric_(self, states=[], **kwargs):
    self.allowed_states = set(states) if states else None

  def set(self, new_state):
    assert isinstance(new_state, str)

    if self.allowed_states and new_state not in self.allowed_states:
      raise Exception(f"State {new_state} is not in {self.states}")

    super().set(new_state)


class Stat(Metric):
  kind = ObsKind.STAT
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

  def get(self):
    return (None, 0)

  def collect(self):
    yield from ()
