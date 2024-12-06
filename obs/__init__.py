from .registry import Registry
from .observer import Observer
from time import time

REGISTRY = Registry()
REPORTER = Observer(REGISTRY)

REPORTER.gauge(
  "started_s", desc="Unix epoch timestamp of module initialization"
).set(round(time()))

def reporter():
  return REPORTER
