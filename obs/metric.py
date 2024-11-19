import time
from enum import Enum
from dataclasses import dataclass


class MetricKind(Enum):
  COUNTER = 1
  GAUGE = 2
  STATE = 3
  STAT = 4
  INFO = 5


@dataclass
class Value:
  value: any
  labels: dict[str, str]
  at: float


@dataclass
class Reading:
  kind: MetricKind
  path: tuple[str]
  val: Value
  desc: str

  @property
  def value(self):
    return self.val.value

  @property
  def labels(self):
    return self.val.labels

  @property
  def at(self):
    return self.val.at

  def group(self, join_char=None):
    return join_char.join(self.path[:-1]) if join_char else self.path[:-1]

  def flatkey(self):
    oml = self.om_labels()
    name = self.path[-1]
    return name + ''.join(['{', oml, '}']) if oml else name

  def om_labels(self):
    """ OpenMetrics representation of the labels """
    return ", ".join(f"{k}=\"{v}\"" for k, v in sorted(self.labels.items()))

  def om_help(self):
    """ OpenMetrics render of the help with this reading """
    return f"# HELP {self.desc}"

  def om_str(self):
    """ OpenMetrics rendering of this reading """
    parts = [self.group('_'), '_', self.flatkey(), ' ', str(self.value)]
    if self.val.at:
      parts.append(' ')
      parts.append(str(round(self.val.at)))

    return ''.join(parts)


class Metric:

  __slots__ = (
    'path',
    'desc',
    'value',
    'value_fn',
    'reporter',
    'kwargs',
    'labeles',
    'last_sample_at'
  )

  # The kind of metric used to generate Record
  kind: MetricKind

  # Whether or not this metric allows `value_fn`
  allow_fn: True

  def __init__(self,
      reporter,
      path,
      desc='',
      labels=dict(),
      value=None,
      value_fn=None,
      **kwargs
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

    if value:
      self.set(value)

  def name(self):
    return self.path[-1]

  def _init_metric_(self, **kwargs):
    raise NotImplementedError

  def labeled(self, label, label_val):
    new_labels = self.labels.copy()
    new_labels[label] = label_val
    return self.reporter.with_labels(self, new_labels)

  def peek(self):
    """ Peek at the value of this metric. Sometimes this is not possible
        Like in histograms, etc.
    """
    if self.value:
      return self.value

    if self.value_fn:
      return "fn()"

    return "n/a"

  def set_fn(self, value_fn):
    """ Have this metric use `value_fn` to retrieve the value when collected """
    assert self.last_sample_at == 0, "Cannot set a function once a metric has been used"
    self.last_sample_at = 0
    self.value_fn = value_fn

  def set(self, value, at=time.time()):
    assert self.value_fn is None, "Cannot set a metric with a value_fn"
    self.value = value
    self.last_sample_at = at

  def to_value(self):
    if self.value_fn:
      self.value = self.value_fn()
      self.last_sample_at = time.time()
    return Value(self.value, self.labels, self.last_sample_at)

  def to_reading(self):
    return Reading(
      self.kind,
      self.path,
      self.to_value(),
      self.desc,
    )

  def __repr__(self):
    return f"{self.__class__.__name__}({self.name()}, value={self.peek()})"

  def __str__(self):
    return self.__repr__()

  def __lt__(self, other):
    if self.path < other.path:
      return True
    elif self.path == other.path:
      return tuple(self.labels.keys()) < tuple(other.labels.keys())
    else: # self.path > other.path
      return False

  def __eq__(self, other):
    return self.path == other.path and self.labels == other.labels


class Counter(Metric):
  kind = MetricKind.COUNTER

  def _init_metric_(self, value=0, **kwargs):
    self.value = value

  def set_fn(self, value_fn):
    raise NotImplementedError("Counters do not use functions")

  def inc(self, amt=1):
    self.last_sample_at = time.time()
    self.value += amt


class Gauge(Metric):
  kind = MetricKind.GAUGE
  def _init_metric_(self, value=0.0, value_fn=None, **kwargs):
    self.value = value
    self.value_fn = value_fn

  def inc(self, amt=1.0):
    self.set(self.value + amt)

  def dec(self, amt=1.0):
    self.set(self.value - amt)


class State(Metric):
  kind = MetricKind.STATE

  def _init_metric_(self, states=[], value=None, **kwargs):
    self.value = None
    self.states = set(states)
    self.restrict = bool(states)

    if value:
      self.set(value)

  def set(self, new_state):
    assert isinstance(new_state, str)

    if self.restrict and new_state not in self.states:
      raise Exception(f"State {new_state} is not in {self.states}")

    self.value = new_state
    self.states.add(new_state)
    self.last_sample_at = time.time()


class Stat(Metric):
  pass


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
