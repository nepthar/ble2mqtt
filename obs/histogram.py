from metric import Metric, MetricKind


@dataclass
class TimeSlice:


class TimeSamples(Metric):

  sample_count = 1000
  sample_ttl_s = 60

  ... List of samples



class ApproxHist(Metric):
  kind = MetricKind.HISTOGRAM

  intervals = (
    2, 5, 10,
    25, 50, 100,
    250, 500, 1000,
    2500, 5000, 10_000
  )

  unit = 1.0

  slice_time_s = 10
  slice_count = 6

  ... a bunch of time slices, each with their own bucket

  def __init__(self):
    self.slices =
