from .registry import MetricReporter, Registry

REGISTRY = Registry()
REPORTER = MetricReporter(REGISTRY)

def reporter():
  return REPORTER
