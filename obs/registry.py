from .metric import *
from .data import Reading
from .logger import TextLogger, Level
from threading import RLock
import time


class Readings:
  def __init__(self, items, at=time.time()):
    self.items = items
    self.at = at

  def filtered(self, prefix=(), after=0):
    if not prefix or after:
      return self

    def inc(scope, at):
      return at > after and scope_startswith(scope, prefix)

    prefix = to_scope(prefix)
    new_items = tuple(
      Reading(
        value=r.value,
        scope=scope_lstrip(r.scope, prefix),
        labels=r.labels,
        kind=r.kind,
        desc=r.desc,
        at=r.at
      ) for r in self.items if inc(r.scope, r.at)
    )
    return Readings(items=new_items, at=self.at)

  def grouped(self):
    pass

  def as_dict(self):
    ret = {}
    for r in self.items:
      group = r.scope
      ret.setdefault(group, {})
      ret[group][r.labels] = r

    return ret

  def __iter__(self):
    return self.items.__iter__()


class Registry:
  def __init__(self, logger=TextLogger):
    # stored as: :
    # { Path(the, path): { (): Metric, (label1, lablevalue1): Metric }
    # That is, `metrics` is a dict of dicts, where the key for the first
    # is the metric path, and the key for the second is the metric labels,
    # sorted and turned into a tuple of tuple (k, v).
    self.metrics = dict()
    self.logs = dict()
    self.logger = logger
    self.level = Level.INF

  def find_or_create_log(self, key):
    if key not in self.logs:
      self.logs[key] = self.logger(key=key, registry=self)

    return self.logs[key]

  def find_or_create(self, klass, key, obs, desc, **kwargs):
    if key not in self.metrics:
      self.metrics[key] = klass(
        key=key,
        observer=obs,
        desc=desc,
        **kwargs
      )

    metric = self.metrics[key]

    if klass != metric.__class__:
      raise Exception("Metric class mismatch")

    return metric

  def collect(self):
    return Readings(tuple(self._readings_()))

  def _readings_(self):
    for key, metric in sorted(self.metrics.items()):
      if metric.value_fn:
        metric.update()

      yield Reading(
        value=metric.value,
        scope=key.scope,
        labels=key.labels,
        kind=metric.kind,
        desc=metric.desc,
        at=metric.last_sample_at
      )


class ThreadsafeRegistry:
  def __init__(self):
    self._reg = Registry()
    self.lock = RLock()

  def find_or_create(self, klass, reporter, path, desc, labels, **kwargs):
    with self.lock:
      return self._reg.find_or_create(klass, reporter, path, desc, labels, **kwargs)

  def read(self):
    # Materialize items into a list right away and release the lock
    with self.lock:
      return self._reg.read()

