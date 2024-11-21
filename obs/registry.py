from .metric import *
from .data import Value, Reading, Labels, Path
from threading import RLock


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

  def _items_(self, prefix):
    paths = sorted(self.metrics.keys())
    if prefix:
      prefix = Path.make(prefix)
      for p in paths:
        if p.startswith(prefix):
          yield (p.lstripped(prefix), self.metrics[p])
    else:
      for p in paths:
        yield (p, self.metrics[p])

  def readings(self, prefix=None):
    for _, mgroup in self._items_(prefix):
      for metric in mgroup.values():
        # Skip the "unlabeled" metric in a labeled group
        if len(mgroup) > 1 and not metric.labels:
          continue
        yield metric.to_reading()

  def readings_groups(self, prefix=None):
    for path, mgroup in self._items_(prefix):
      yield (path, [v.to_reading() for v in mgroup.values()])

  def readings_tree(self, prefix=None):
    tree = {}
    for path, mgroup in self._items_(prefix):
      current_level = tree
      for key in path[:-1]:
        # Ensure the "path" exists in the tree structure
        current_level = current_level.setdefault(key, {})
      current_level[path[-1]] = [m.to_reading() for m in mgroup.values()]
    return tree


class ThreadsafeRegistry:
  def __init__(self):
    self._reg = Registry()
    self.lock = RLock()

  def find_or_create(self, klass, reporter, path, desc, labels, **kwargs):
    with self.lock:
      return self._reg.find_or_create(klass, reporter, path, desc, labels, **kwargs)

  def _items_(self, prefix=()):
    # Materialize items into a list right away and release the lock
    with self.lock:
      return list(self._reg._items_(prefix))


class MetricReporter:
  def __init__(self, registry, path=Path(())):
    self.path = Path.make(path)
    self.registry = registry

  def _mk_(self, klass, name, desc, labels=Labels.Empty, **kwargs):
    return self.registry.find_or_create(
      klass=klass,
      reporter=self,
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
    self.null_metric = NullMetric(reporter=self, path=Path.make("null"), desc="NullMetric")

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
