from dataclasses import dataclass
from enum import Enum


class MetricKind(Enum):
  COUNTER = 1
  GAUGE = 2
  STATE = 3
  STAT = 4
  INFO = 5
  GROUP = 6
  UNKNOWN = 7


@dataclass(frozen=True)
class Path:

  @staticmethod
  def of(x):
    match x:
      case Path():
        return x
      case tuple():
        return Path(x)
      case str():
        return Path((x,))
      case None:
        return Path.Root
      case _:
        raise ValueError(f"Cannot make a Path from {x}")
    return

  # TODO: Some kind of validation?

  parts: tuple[str]

  def plus(self, *others):
    if others:
      return Path(self.parts + tuple(others))
    else:
      return self

  def __lt__(self, other):
    return self.parts < other.parts

  def __bool__(self):
    return bool(self.parts)

  def __iter__(self):
    return self.parts.__iter__()

  def name(self):
    return self.parts[-1] if self.parts else ""

  def dir(self):
    return Path(tuple(self.parts[:-1]))

  def startswith(self, other):
    if not other:
      return True

    l_other = len(other.parts)

    if l_other > len(self.parts):
      return False

    for i in range(l_other):
      if self.parts[i] != other.parts[i]:
        return False

    return True

  def lstripped(self, prefix):
    if self.startswith(prefix):
      lp = len(prefix.parts)
      return Path(self.parts[lp:])
    return self

  def to_str(self, joiner='/'):
    return joiner.join(self.parts)

  def __repr__(self):
    return f'P({self.to_str()})'


Path.Root = Path(())


@dataclass(frozen=True)
class Labels:
  # TODO: Length & number limitations?

  keys: tuple[str]
  vals: tuple[str]

  def __iter__(self):
    return zip(self.keys, self.vals)

  def dict(self):
    return dict(zip(self.keys, self.vals))

  def labeled(self, labelname, labelval):
    d = self.dict()
    d[labelname] = labelval
    nk, nv = list(zip(*sorted(d.items())))
    return Labels(keys=nk, vals=nv)

  def as_str(self):
    if not self.keys:
      return ""

    kvs = ", ".join(f"{k}=\"{v}\"" for k, v in zip(self.keys, self.vals))
    return ''.join(('{', kvs, '}'))

  def __repr__(self):
    return f"Labels({self.as_str()})"

  def __lt__(self, other):
    if self.keys == other.keys:
      return self.vals < other.vals
    else:
      return self.keys < other.keys


Labels.Empty = Labels((), ())


@dataclass(frozen=True)
class Value:
  value: any
  labels: Labels
  at: float


@dataclass(frozen=True)
class Reading:
  kind: MetricKind
  path: Path
  val: Value
  desc: str

  @property
  def value(self):
    return self.val.value

  @property
  def labels(self):
    return self.val.labels

  @property
  def at(self):
    return self.val.at

  def dir(self):
    return self.path.dir()

  def om_name(self):
    """ The "Key" of this metric, with the labels if any """
    oml = self.om_labels()
    name = self.path.name()
    return name + "".join(["{", oml, "}"]) if oml else name

  def om_labels(self):
    """OpenMetrics representation of the labels"""
    return ", ".join(f'{k}="{v}"' for k, v in self.labels)

  def om_str(self):
    """OpenMetrics rendering of this reading"""
    parts = [self.group("_"), "_", self.om_name(), " ", str(self.value)]
    if self.val.at:
      parts.append(" ")
      parts.append(str(round(self.val.at)))

    return "".join(parts)
