from .metric import *
from .data import Value, Reading, Labels, Path
from threading import RLock
import time

class Readings:
  def __init__(self, items, at=time.time()):
    self.items = items
    self.at = at

  def filtered(self, prefix):
    pp = Path.of(prefix)
    new_items = tuple(
      Reading(
        kind=r.kind,
        path=r.path.lstripped(r.path),
        val=r.val,
        desc=r.desc
      ) for r in self.items if r.path.startswith(pp)
    )
    return Readings(items=new_items, at=self.at)

  def as_dict(self):
    ret = {}
    for r in self.items:
      group = r.dir()
      key = r.om_name()
      ret.setdefault(group, {})
      ret[group][key] = r

    return ret

  def __iter__(self):
    return self.items.__iter__()


class Registry:
  def __init__(self):
    # stored as: :
    # { Path(the, path): { (): Metric, (label1, lablevalue1): Metric }
    # That is, `metrics` is a dict of dicts, where the key for the first
    # is the metric path, and the key for the second is the metric labels,
    # sorted and turned into a tuple of tuple (k, v).
    self.metrics = dict()

  def find_or_create(self, klass, reporter, path, desc, labels, **kwargs):
    if path not in self.metrics:
      self.metrics[path] = {}

    metric = self.metrics[path].get(labels)

    if metric:
      if klass != metric.__class__:
        raise Exception("Metric class mismatch")
      return metric

    metric = klass(reporter=reporter, path=path, desc=desc, labels=labels, **kwargs)

    self.metrics[path][labels] = metric
    return metric

  def read(self, prefix=None, after=0):
    return Readings(tuple(self._read_iter_(prefix, after)))

  def _read_iter_(self, prefix, after):
    """ Create an interator of all readings with options to filter by
        path prefix, timestamp or both
    """
    ppfx = Path.of(prefix)
    for path, group in sorted(self.metrics.items()):
      if path.startswith(ppfx):
        for metric in group.values():
          if metric.value_fn:
            metric.update()
          if metric.last_sample_at > after:
            yield Reading(
              kind=metric.kind,
              path=path.lstripped(ppfx),
              val=metric.to_value(),
              desc=metric.desc
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


class MetricReporter:
  def __init__(self, registry, path=Path(())):
    self.path = Path.of(path)
    self.registry = registry

  def _mk_(self, klass, name, desc, labels=Labels.Empty, **kwargs):
    return self.registry.find_or_create(
      klass=klass,
      reporter=self,sd
      path=self.path.plus(name),
      desc=desc,
      labels=labels,
      **kwargs,
    )

  def scoped(self, *new_path):
    return MetricReporter(self.registry, self.path.plus(*new_path))

  def with_labels(self, metric, labels):
    return self._mk_(
      klass=metric.__class__,
      name=metric.path.name(),
      desc=metric.desc,
      labels=labels,
      **metric.kwargs,
    )

  def counter(self, name, desc=""):
    return self._mk_(Counter, name, desc)

  def gauge(self, name, desc=""):
    return self._mk_(Gauge, name, desc)

  def stat(self, name, desc="", **kwargs):
    return self._mk_(Stat, name, desc, **kwargs)

  def state(self, name, desc="", state=None, states=set(), **kwargs):
    return self._mk_(State, name, desc, state=state, states=states, **kwargs)


class NullMetricReporter(MetricReporter):
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
