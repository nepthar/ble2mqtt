import array
import time
import threading

from .data import ObsKey, ObsKind
from .metric import Metric


class Timeseries(Metric):

  kind: ObsKind = None

  def _init_timeseries_(self, sample_count, time_window_s):
    self.count = int(sample_count)
    self.samples = array.array('L', (0 for _ in range(sample_count)))
    self.timestamps = array.array('L', (0 for _ in range(sample_count)))
    self.lock = threading.RLock()
    self.time_window_s = time_window_s
    self.index = self.count

  def rec(self, sample):
    i = 0

    with self.lock:
      self.index = (self.index + 1) % self.count
      i = self.index

    self.samples[i] = sample
    self.timestamps[i] = round(time.time())

  def timeseries(self):
    cutoff = round(time.time()) - self.time_window_s

    return (
      self.samples[i] for i in range(self.count) if self.timestamps[i] > cutoff
    )


class BucketCounters(Timeseries):
  kind: ObsKind = ObsKind.BCOUNTER

  buckets = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 1e9]

  def _init_metric_(self, sample_count, time_window_s):
    self._init_timeseries_(sample_count, time_window_s)
    self.bc = len(self.buckets)

  def read(self):
    counts = [0 for _ in self.buckets]

    ts = list(self.timeseries())
    total = len(ts)
    minv = ts[0]
    maxv = ts[0]

    for t in ts:
      minv = min(minv, t)
      maxv = max(maxv, t)

      for i in range(self.bc):
        if t < self.buckets[i]:
          counts[i] += 1
          break

    ret = {str(self.buckets[i]): round(counts[i]/total, 2) for i in range(self.bc - 1)}

    ret["top"] = counts[-1]
    ret["min"] = minv
    ret["max"] = maxv
    ret["count"] = total

    return ret


class Histogram(Timeseries):
  kind: ObsKind = ObsKind.HIST

  def _init_metric_(self, sample_count, time_window_s):
    self._init_timeseries_(sample_count, time_window_s)

  def read(self):
    ts = sorted(self.timeseries())
    l = len(ts) - 1

    i999 = round(l * 0.999)
    i99 = round(l * 0.99)
    i95 = round(l * 0.95)
    i90 = round(l * 0.90)
    i50 = round(l * 0.50)

    return {
      "max": ts[l],
      "p999": ts[i999],
      "p99": ts[i99],
      "p95": ts[i95],
      "p90": ts[i90],
      "p50": ts[i50],
      "min": ts[0],
      "count": l + 1
    }



