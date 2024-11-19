from obs import reporter, default_registry
from pprint import pp

rep = reporter().scoped("test")

c1 = rep.counter("c1")
c1.inc()
c1.inc()


r2 = rep.scoped("inner")

c2 = r2.counter("test2")
c3 = r2.counter("test3")
c2.inc()

c3l = c3.labeled("key", "value")
c3l2 = c3.labeled("key", "value2")

c3l3 = c3l2.labeled("other", "nonsense")


c3l.inc()
c3l2.inc()
c3l3.inc()

c3l2.inc()
c3l3.inc()


def process_readings(readings):
  if not readings:
    return None

  if len(readings) == 1:
    return readings[0]

  # otherwise build our labels
  reading_dict = {}
  for r in readings:
    # Ignore readings without labels here
    if r.labels:
      flatkey = r.om_labels()
      if flatkey:
        reading_dict[flatkey] = r

  return reading_dict


def combine(prefix=()):
  combined = {}
  for reading in default_registry().readings(prefix):
    group_key = reading.group("/")
    key = reading.flatkey()

    combined.setdefault(group_key, {})
    combined[group_key][key] = process_readings([reading])

  return combined


pp(combine())
