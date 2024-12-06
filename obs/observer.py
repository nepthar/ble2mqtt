from .data import Path, Labels

from .metric import Gauge, Counter, Stat, State

class Observer:
  def __init__(self, registry, path=Path(())):
    self.path = Path.of(path)
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
    return Observer(self.registry, self.path.plus(*new_path))

  def counter(self, name, desc=""):
    return self._mk_(Counter, name, desc)

  def gauge(self, name, desc=""):
    return self._mk_(Gauge, name, desc)

  def stat(self, name, desc="", **kwargs):
    return self._mk_(Stat, name, desc, **kwargs)

  def state(self, name, desc="", state=None, states=set(), **kwargs):
    return self._mk_(State, name, desc, state=state, states=states, **kwargs)


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
