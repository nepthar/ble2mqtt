# This is a copy of Twitter's metrics merged with prometheus metrics.
# It enables some helpful stuff.

## TODO: Lables

import prometheus_client as pc

class Metric:
  def __init__(self, scope, desc, **kwargs):
    self.scope = scope
    self.desc = desc
    self.setup(**kwargs)

  def setup(self, **kwargs):
    pass

  def rec(self, value):
    raise NotImplementedError

  def inc(self, amt=1):
    raise NotImplementedError

  def dec(self, amt=1):
    raise NotImplementedError

  def set(self, value):
    raise NotImplementedError

  def set_function(self, fn):
    raise NotImplementedError

  def collect(self):
    raise NotImplementedError


class NullMetric(Metric):
  """ NullMetric does not collect anything """

  def rec(self, value):
    pass

  def inc(self, amt=1):
    pass

  def dec(self, amt=1):
    pass

  def set(self, value):
    pass

  def set_function(self, fn):
    pass

  def collect(self):
    yield from ()


class PrometheusMetric(Metric):
  # The underlying Prometheus metric
  pm_metric = None

  def pm_name(self):
    return '_'.join(self.scope)


class Counter(PrometheusMetric):
  def setup(self, **kwargs):
    self.pm_metric = pm.Counter(
      self.pm_name(), kwargs.get('desc', ' '))

  def inc(self, amt=1):
    self.pm_metric.inc(amt)


class Gauge(PrometheusMetric):
  def setup(self, **kwargs):
    self.pm_metric = pm.Gauge(self.pm_name(), kwargs.get('desc', ' '))

  def inc(self, amt=1):
    self.pm_metric.inc(amt)

  def dec(self, amt=1):
    self.pm_metric.dec(amt)

  def set(self, val):
    self.pm_metric.set(val)

  def set_function(self, fn):
    self.pm_metric.set_function(fn)


class State(PrometheusMetric):
  """ An enumeration or known state """

  def setup(self, **kwargs):
    self.pm_metric = pm.Enum(
      self.pm_name(), kwargs.get('desc', ' '), states=kwargs['states'])


class Reporter:
  def __init__(self, scope=tuple()):
    self.scope = scope

  def scoped(self, scope):
    return Reporter(self.scope + (scope,))

  def _mk(self, klass, name, desc, **kwargs):
    return klass(self.scope + (name,), desc, **kwargs)

  def counter(self, name, desc=' '):
    return self._mk(pc.Counter, name, desc)

  def gauge(self, name, desc=' '):
    return self._mk(pc.Gauge, name, desc)

  def state(self, name, desc=' ', **kwargs):
    return self._mk(pc.State, name, desc, **kwargs)

  def enum(self, name, desc=' ', **kwargs):
    return self._mk(pc.State, name, desc, **kwargs)


class NullReporter(Reporter):
  NULL_METRIC = NullMetric(("null_metric",), "Ignored")

  def _mk(self, klass, name, desc, **kwargs):
    return self.NULL_METRIC
