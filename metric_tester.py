from metrics import *
from metrics.exporters import LinesExporter

def test_counters():
  print("Counter test: ")
  r = reporter()

  c1 = r.counter('counter1')
  c2 = r.counter('counter2')
  c3 = r.counter('counter1')

  if c1 is not c3:
    raise Exception("Metric lookup failed")

  c1.inc()
  c2l = c2.labeled('key', 'value')

  print(c2l)
  c2l.inc()

  # Gauges
  g1 = r.scoped('scope1', 'scope2').gauge('mygauge')

  g1.set(4)

  g2 = g1.labeled('my', 'tacos')
  g3 = g1.labeled('my', 'other')

  g2.set(44)
  g3.set(45)

  rs = r.scoped('states')

  s1 = rs.state('some_state', "This is some state")
  s2 = rs.state('known_state', "these are known", state='starting', states=['starting', 'ending'])

  s1.set('state1')
  s2.set('ending')

  le = LinesExporter()
  print("\nExport of all metrics:")
  for line in le.collect():
    print(line)

  print(r.registry.metrics)

if __name__ == "__main__":
  test_counters()
