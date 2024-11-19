from .registry import Registry, MetricReporter, NullMetricReporter


REGISTRY = Registry()
NULL_REPORTER = NullMetricReporter()


def default_registry():
  return REGISTRY


def reporter():
  return MetricReporter(REGISTRY)


def null_reporter():
  return NULL_REPORTER
