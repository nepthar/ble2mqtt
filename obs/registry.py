from enum import Enum
from dataclasses import dataclass
from .metric import *
from typing import Optional
from threading import RLock
import time



class Registry:
  def __init__(self):
    # stored as: :
    #{ (the, path): { (): Metric, (label1, lablevalue1): Metric }
    # That is, `metrics` is a dict of dicts, where the key for the first
    # is the metric path, and the key for the second is the metric labels,
    # sorted and turned into a tuple of tuple (k, v).
    self.metrics = dict()

  def get(self, path, labels):
    found_group = self.metrics.get(path)
    if found_group:
      return self.found_group.get(label_id(labels))

  def find_or_create(self, klass, reporter, path, desc, labels, **kwargs):
    if path not in self.metrics:
      self.metrics[path] = {}

    l_id = label_id(labels)
    metric = self.metrics[path].get(l_id)

    if metric:
      if klass != metric.__class__:
        raise Exception("Metric class mismatch")
      return metric

    metric = klass(
      reporter=reporter,
      path=path,
      desc=desc,
      labels=labels,
      **kwargs
    )

    self.metrics[path][l_id] = metric
    return metric

  def value(self, path, labels=()):
    found = self.get(path, labels)
    return found.peek() if found else None

  def metrics(self):
    yield from (m for m in sorted(self.metrics.values()) if not m.is_parent())

  def collect(self):
    for group in self.metrics.values():
      for m in group.values():
        yield from m.collect()

  def as_dict(self):
    nested_dict = {}
    as_list = sorted(self.metrics.items(), key=lambda x: x[0])

    for path, group in as_list:
      current_level = nested_dict
      for key in path[:-1]:
        current_level = current_level.setdefault(key, {})

      collected = []
      for metric in group.values():
        collected.append(metric.value_2())

      current_level[path[-1]] = collected

    return nested_dict


class ThreadsafeRegistry:

  def __init__(self):
    self._reg = Registry()
    self.lock = RLock()

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
    print(kwargs)
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


  def with_labels(self, metric, labels):
    return self._mk_(
      klass=metric.__class__,
      name=metric.path[-1],
      desc=metric.desc,
      labels=labels,
      **metric.kwargs
    )

  # def labeled_old(self, metric, labels):
  #   if metric.parent:
  #     return self.labeled(metric.parent, labels)

  #   new_m_id = _metric_id(metric.path, labels)

  #   if new_m_id == metric.id:
  #     return metric

  #   labeled_metric = self._mk_(
  #     klass=metric.__class__,
  #     name=metric.path[-1],
  #     desc=metric.desc,
  #     labels=labels,
  #     **metric.kwargs
  #   )

  #   labeled_metric.parent = metric
  #   metric.children.add(labeled_metric)

  #   return labeled_metric

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
