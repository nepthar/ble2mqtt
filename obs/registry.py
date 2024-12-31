from .metric import *
from .data import Reading, to_scope
from .logger import TextLogger, ObsLevel
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
    self.level = ObsLevel.INF

  def find_or_create_log(self, key, level):
    if key not in self.logs:
      self.logs[key] = self.logger(key=key, registry=self)

    log = self.logs[key]
    log.set_level(level)

    return log

  def peek(self, key):
    if key in self.metrics:
      return self.metrics[key].peek()

  def get(self, klass, key):
    metric = self.metric.get(key)
    if metric and klass != metric.__class__:
      raise Exception("Metric class mismatch")

    return metric

  def find_or_create(self, klass, observer, key, desc, level, **kwargs):
    if key not in self.metrics:
      self.metrics[key] = klass(
        key=key,
        observer=observer,
        level=level,
        desc=desc,
        **kwargs
      )

    metric = self.metrics[key]

    if klass != metric.__class__:
      raise Exception("Metric class mismatch")

    return metric

  def collect(self):
    return Readings(tuple(self.readings()))

  def readings(self, level=ObsLevel.INF, prefix=(), after=0):
    """ Gather all readings in this registry, optionally filtering """
    lv = level.value
    prefix = to_scope(prefix)

    for key, metric in sorted(self.metrics.items()):
      if lv >= metric.level.value and key.scope_startswith(prefix):
        metric.update()
        if metric.last_sample_at >= after:
          yield Reading(
            value=metric.value,
            scope=key.scope_lstripped(prefix),
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

  def collect(self):
    # Materialize items into a list right away and release the lock
    with self.lock:
      return self._reg.collect()

