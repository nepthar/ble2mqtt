from enum import Enum
from collections import namedtuple
import time
import sys

from .data import ObsKey, to_scope, ObsLevel


LogEntry = namedtuple('LogEntry', ('level', 'at', 'key', 'text', 'values'))


class BaseLogger:
  def __init__(self, key=ObsKey.Root, registry=None):
    self.registry = registry
    self.key = key
    self._level_val = registry.level.value if registry else ObsLevel.INF.value

  def set_level(self, new_level):
    self._level_val = new_level.value

  def handle(self, level, at, text, values):
    pass

  def __call__(self, msg, *vals):
    self.info(text, values)

  def dbg(self, msg, *vals):
    if self._level_val >= ObsLevel.DBG.value:
      self.handle(ObsLevel.DBG, time.time(), msg, vals)

  def inf(self, msg, *vals):
    if self._level_val >= ObsLevel.INF.value:
      self.handle(ObsLevel.INF, time.time(), msg, vals)

  def err(self, msg, *vals):
    if self._level_val >= ObsLevel.ERR.value:
      self.handle(ObsLevel.ERR, time.time(), msg, vals)


class EntryLogger(BaseLogger):

  def on_entry(self, entry):
    pass

  def handle(self, level, at, msg, vals):
    self.on_entry(LogEntry(level, at, self.key, msg, vals))


class TextLogger(BaseLogger):

  FORMAT = "{level} {hh:02d}:{mm:02d}:{ss:02d}{tag} {text}\n"

  def __init__(self, writeable=sys.stderr, key=ObsKey.Root, registry=None):
    self.writeable = writeable
    self.tag = f" [{key.om_name()}]" if key.scope else ""
    super().__init__(key=key, registry=registry)

  def handle(self, level, at, text, values):
    message_text = text.format(values)
    ts = time.localtime(at)
    self.writeable.write(self.FORMAT.format(
      level=level.name,
      hh=ts.tm_hour, mm=ts.tm_min, ss=ts.tm_sec,
      tag=self.tag,
      text=message_text
    ))


