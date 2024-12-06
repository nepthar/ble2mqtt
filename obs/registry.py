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
    self.logs = dict()

  def find_or_create_log(self):
    pass

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

