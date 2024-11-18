import time
from enum import Enum
from dataclasses import dataclass

# Canonicalize labels
def label_id(label_dict):
  return tuple(sorted(label_dict.items())) if label_dict else ()

class MetricKind(Enum):
  COUNTER = 1
  GAUGE = 2
  STATE = 3
  STAT = 4
  INFO = 5

@dataclass
class Value:
  val: any
  labels: dict[str, str]
  timestamp: float

@dataclass
class ReadingX:
  """ metric id -> value pair with a timestamp, exported """
  kind: MetricKind
  path: tuple[str]
  value: any
  desc: str

  def as_line(self, ts=True):
    """ Convert this reading to a basic Prometheus/OpenMetric line """
    ts_part = f" {self.timestamp}" if ts and self.timestamp > 1 else ""
    return f"{_metric_id_str(self.path, self.labels)} {self.value}{ts_part}"


@dataclass
class Reading:
  kind: MetricKind
  path: tuple[str]
  value: Value
  desc: str


@dataclass
class Thing:
  kind: MetricKind
  path: tuple[str]
  reading: Reading
  desc: desc

def _metric_id(path, labels):
  return path + tuple(sorted(labels.items()))

def _metric_id_str(path, labels):
  path_part = "/".join(path)
  label_part = ""
  if labels:
    label_part = "{" + ",".join(f"{k}={v}" for k, v in label_id(labels)) + "}"
  return path_part + label_part

# @dataclass
# class Path:
#   metric_id: tuple

#   def path(self):
#     return path[:-1]

#   def name(self):
#     return path[-2:-1]

#   def labels(self):
#     return dict(path[-1])

#   def __lt__(self, other):
#     return self.metric_id < other.metric_id

#   def __hash__(self):
#     return hash(self.metric_id)



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

  def __init__(self,
      reporter,
      path,
      desc='',
      labels=dict(),
      parent=None,
      value=None,
      value_fn=None,
      **kwargs
    ):

    if not path:
      raise ArgumentError("Path must not be empty")

    self.reporter = reporter
    self.path = path
    self.desc = desc
    self.id = _metric_id(path, labels)
    self.labels = labels
    self.children = set()
    self.kwargs = kwargs
    self.last_sample_at = 0
    self.parent = parent
    self.value = value
    self.value_fn = value_fn

    self._init_metric_(**kwargs)

    if value:
      self.set(value)

  def name(self):
    return self.path[-1]

  def _init_metric_(self, **kwargs):
    raise NotImplementedError

  def is_labeled(self):
    return bool(self.labels)

  def is_parent(self):
    return bool(self.children)

  def collect(self):
    if self.is_parent():
      return

    if self.value_fn:
      self.value = self.value_fn()
      self.last_sample_at = time.time()
    yield self.reading()

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

  def readingx(self):
    return Reading(
      self.kind,
      self.path,
      self.value,
      self.labels,
      self.desc,
      self.last_sample_at
    )

  def reading(self):
    return Reading(
      self.kind,
      self.path,
      self.value_2(),
      self.desc
    )

  def value_2(self):
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
