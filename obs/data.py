from dataclasses import dataclass
from enum import Enum


class ObsLevel(Enum):
  OFF = 0
  DBG = 2
  INF = 3
  ERR = 5


class ObsKind(Enum):
  LOG = 0
  COUNTER = 1
  GAUGE = 2
  STATE = 3
  STAT = 4
  INFO = 5
  GROUP = 6
  HIST = 7
  BCOUNTER = 8
  UNKNOWN = 100


def to_scope(x):
  if x:
    match x:
      case tuple() if all(isinstance(i, str) for i in x):
        return x
      case str():
        return (x,)
      case None:
        return ()

    raise ValueError(f"Cannot make a scope path from {x}")
  else:
    return ()


def scope_startswith(scope, prefix):
  if not prefix:
    return True

  if not scope:
    return False

  l_prefix = len(prefix)
  l_scope = len(scope)

  if l_prefix > l_scope:
    return False

  return all(scope[i] == prefix[i] for i in range(l_prefix))


def scope_lstrip(scope, prefix):
  if scope_startswith(scope, prefix):
    return scope[len(prefix):]
  return scope


@dataclass(frozen=True)
class ObsKey:
  scope: tuple[str]
  labels: tuple[tuple[str]]

  def scoped(self, *new_scope):
    new_scope = self.scope + to_scope(new_scope)
    if self.scope == new_scope:
      return self

    return ObsKey(new_scope, self.labels)

  def labeled(self, lname, lval):
    d = dict(self.labels)
    d[lname] = lval
    new_labels = tuple(sorted(d.items()))

    if new_labels == self.labels:
      return self

    return ObsKey(self.scope, new_labels)

  def scope_startswith(self, prefix):
    prefix = to_scope(prefix)
    # This is always true - an empty prefix matches any scope
    if not prefix:
      return True

    if not self.scope:
      return False

    l_prefix = len(prefix)
    l_scope = len(self.scope)

    return \
      l_prefix > l_scope and \
      all(scope[i] == prefix[i] for i in range(l_prefix))

  def scope_lstripped(self, prefix):
    if self.scope_startswith(prefix):
      return self.scope[len(prefix):]

  def __eq__(self, other):
    return \
      self.scope == other.scope and \
      self.labels == other.labels

  def __lt__(self, other):
    return \
      self.scope < other.scope or \
      self.labels < other.labels

  def scope_str(self, joiner='/'):
    return joiner.join(self.scope)

  def om_name(self):
    """OpenMetrics name of this metric key with the labels if any"""
    oml = self.om_labels()
    name = self.scope_str('_')
    return name + "".join(["{", oml, "}"]) if oml else name

  def om_labels(self):
    """OpenMetrics representation of the labels"""
    return ", ".join(f'{k}="{v}"' for k, v in self.labels)

  def __repr__(self):
    pth = "/".join(self.scope)
    lbls = labels_as_str(self.labels)

    return f"{pth}{lbls}"

ObsKey.Root = ObsKey((), ())


@dataclass(frozen=True)
class Reading:
  kind: ObsKind
  scope: tuple[str]
  labels: tuple[str]
  value: any
  desc: str
  at: float

  @property
  def dir(self):
    return self.scope[:-1]

  @property
  def name(self):
    return self.scope[-1]
