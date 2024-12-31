from obs.observer import Observer
from obs.registry import Registry
from pprint import pp

reg = Registry()
obs = Observer(reg)

rep = obs.scoped("test")

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

log = rep.labeled("instance", "0").log('hi')

log.inf("hello there")
log.dbg("debug me")

#pp(observer().registry.collect().as_dict())


h = rep.hist("myhist")

h.rec(45)
h.rec(100)
for i in range(300, 400):
  h.rec(i)

h.rec(100000)


pp(h.read())


readings = reg.collect()

for r in readings:
  pp(r)

# def process_readings(readings):
#   if not readings:
#     return None

#   if len(readings) == 1:
#     return readings[0]

#   # otherwise build our labels
#   reading_dict = {}
#   for r in readings:
#     # Ignore readings without labels here
#     if r.labels:
#       flatkey = r.om_labels()
#       if flatkey:
#         reading_dict[flatkey] = r

#   return reading_dict


# def combine(prefix=()):
#   combined = {}
#   for reading in default_registry().readings(prefix):
#     group_key = reading.group("/")
#     key = reading.flatkey()

#     combined.setdefault(group_key, {})
#     combined[group_key][key] = process_readings([reading])

#   return combined


# pp(combine())

