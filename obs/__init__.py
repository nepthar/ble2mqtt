from .registry import Registry
from .observer import Observer
from .data import ObsKey
from time import time

REGISTRY = Registry()
OBSERVER = Observer(ObsKey.Root, REGISTRY)

OBSERVER.gauge(
  "started_s", desc="Unix epoch timestamp of module initialization"
).set(round(time()))

def observer():
  return OBSERVER
