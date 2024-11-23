from .registry import MetricReporter, Registry
from time import time

REGISTRY = Registry()
REPORTER = MetricReporter(REGISTRY)

REPORTER.gauge(
  "started_s", desc="Unix epoch timestamp of module initialization"
).set(round(time()))

def reporter():
  return REPORTER
