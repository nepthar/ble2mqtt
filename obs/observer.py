from .data import ObsKey, ObsLevel

from .timeseries import Histogram, BucketCounters
from .metric import Gauge, Counter, Stat, State


class Observer:
  def __init__(self, registry, key=ObsKey.Root):
    self.key = key
    self.registry = registry
    self.level = ObsLevel.INF
    self.children = set()

  def _get_(self, klass, key, desc, level, **kwargs):
    metric = self.registry.find_or_create(
      klass=klass,
      observer=self,
      key=key,
      desc=desc,
      level=level,
      **kwargs
    )

    self.children.add(metric)
    return metric

  def set_level(new_level):
    self.level = new_level
    for c in self.children:
      c.set_level(new_level)

  def labeled(self, lname, lval):
    new_key = self.key.labeled(lname, lval)
    if new_key == self.key:
      return self
    else:
      new_obs = Observer(self.registry, new_key)
      self.children.add(new_obs)
      return new_obs

  def scoped(self, *scope):
    new_key = self.key.scoped(*scope)
    if new_key == self.key:
      return self
    else:
      new_obs = Observer(self.registry, new_key)
      self.children.add(new_obs)
      return new_obs

  def counter(self, name, desc=""):
    key = self.key.scoped(name)
    return self._get_(Counter, key, desc, self.level)

  def gauge(self, name, desc=""):
    key = self.key.scoped(name)
    return self._get_(Gauge, key, desc, self.level)

  def stat(self, name, desc="", **kwargs):
    key = self.key.scoped(name)
    return self._get_(Stat, key, desc, self.level, **kwargs)

  def state(self, name, desc="", state=None, states=set(), **kwargs):
    key = self.key.scoped(name)
    return self._get_(State, key, desc, self.level, state=state, states=states, **kwargs)

  def hist(self, name, desc="", sample_count=5000, time_window_s=60, **kwargs):
    key = self.key.scoped(name)
    return self._get_(BucketCounters,
      key, desc, self.level,
      sample_count=sample_count,
      time_window_s=time_window_s,
      **kwargs
    )

  def log(self, name):
    key = self.key.scoped(name)
    return self.registry.find_or_create_log(key, self.level)


class NullObserver(Observer):
  def __init__(self):
    self.null_metric = NullMetric(reporter=self, path=Path.of("null"), desc="NullMetric")

  def scoped(self, *args, **kwargs):
    return self.null_metric

  def labeled(self, *args, **kwargs):
    return self.null_metric

  def counter(self, *args, **kwargs):
    return self.null_metric

  def gauge(self, *args, **kwargs):
    return self.null_metric

  def enum(self, *args, **kwargs):
    return self.null_metric

  def stat(self, *args, **kwargs):
    return self.null_metric

  def state(self, *args, **kwargs):
    return self.null_metric
