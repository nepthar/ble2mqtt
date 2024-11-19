from .metric import *
from threading import RLock


# Canonicalize labels
def label_id(label_dict):
  return tuple(sorted(label_dict.items())) if label_dict else ()


def list_starts_with(lst, prefix_lst):
  if len(lst) < len(prefix_lst):
    return False

  for i in range(len(prefix_lst)):
    if lst[i] != prefix_lst[i]:
      return False

  return True


class Registry:
  def __init__(self):
    # stored as: :
    # { (the, path): { (): Metric, (label1, lablevalue1): Metric }
    # That is, `metrics` is a dict of dicts, where the key for the first
    # is the metric path, and the key for the second is the metric labels,
    # sorted and turned into a tuple of tuple (k, v).
    self.metrics = dict()

  def find_or_create(self, klass, reporter, path, desc, labels, **kwargs):
    if path not in self.metrics:
      self.metrics[path] = {}

    l_id = label_id(labels)
    metric = self.metrics[path].get(l_id)

    if metric:
      if klass != metric.__class__:
        raise Exception("Metric class mismatch")
      return metric

    metric = klass(reporter=reporter, path=path, desc=desc, labels=labels, **kwargs)

    self.metrics[path][l_id] = metric
    return metric

  def _items_(self, path_filter):
    keys = self.metrics.keys()
    lenpf = len(path_filter)

    if path_filter:

      def include(key):
        lk = len(key)
        if lk < lenpf:
          return False
        for i in range(lenpf):
          if key[i] != path_filter[i]:
            return False
        return True

      keys = filter(include, keys)

    # Guarantee sorted items
    for key in sorted(keys):
      # Remove the prefix given by the filter
      path = key[lenpf:]
      yield (path, self.metrics[key])

  def readings(self, path_filter=()):
    for _, mgroup in self._items_(path_filter):
      for metric in mgroup.values():
        # Skip the "unlabeled" metric in a labeled group
        if len(mgroup) > 1 and not metric.labels:
          continue
        yield metric.to_reading()

  def readings_groups(self, path_filter=()):
    for path, mgroup in self._items_(path_filter):
      yield (path, [v.to_reading() for v in mgroup.values()])

  def readings_tree(self, path_filter=()):
    tree = {}
    for path, mgroup in self._items_(path_filter):
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

  def _items_(self, path_filter=()):
    # Materialize items into a list right away and release the lock
    with self.lock:
      return list(self._reg._items_(path_filter))


class MetricReporter:
  def __init__(self, registry, path=()):
    self.path = path
    self.registry = registry

  def _mk_(self, klass, name, desc, labels=dict(), **kwargs):
    return self.registry.find_or_create(
      klass=klass,
      reporter=self,
      path=self.path + (name,),
      desc=desc,
      labels=labels,
      **kwargs,
    )

  def scoped(self, *new_path):
    return MetricReporter(self.registry, self.path + tuple(new_path))

  def with_labels(self, metric, labels):
    return self._mk_(
      klass=metric.__class__,
      name=metric.path[-1],
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
    self.null_metric = NullMetric(reporter=self, path=("null",), desc="NullMetric")

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
