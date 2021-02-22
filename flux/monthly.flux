// InfluxDB2 Flux example: last 31 days production
//
// Display the past 30 days production along with the current day production to date.  This requires multiple
// queries, the first to extract the last 30 days of production and a second set of queries to calculate
// the production to date for the current day.  These are then combined to produce the data set for display.
//
// InfluxDB 1.8.x users should add the retention policy to the bucket name, ie, 'multisma2/autogen'

import "experimental"
import "date"

local_time = experimental.addDuration(d: -5h, to: now())

// This can be used to align results with x-axis labels
timeAxisShift = 0h

past_30 = from(bucket: "multisma2")
  |> range(start: -32d)
  |> filter(fn: (r) => r._measurement == "production" and r._inverter == "site" and r._field == "midnight")
  |> sort(columns: ["_time"], desc: true)
  |> difference()
  |> map(fn: (r) => ({ _time: r._time, _kwh: float(v: r._value) * -0.001 }))
  |> sort(columns: ["_time"], desc: false)
  |> yield(name: "past_30")

midnight = from(bucket: "multisma2")
  |> range(start: -1d)
  |> filter(fn: (r) => r._measurement == "production" and r._inverter == "site" and r._field == "midnight")
  |> filter(fn: (r) => date.monthDay(t: r._time) == date.monthDay(t: local_time))
  |> map(fn: (r) => ({ _time: r._time, _total_wh: r._value }))
  |> yield(name: "midnight")

right_now = from(bucket: "multisma2")
  |> range(start: -1d)
  |> filter(fn: (r) => r._measurement == "production" and r._inverter == "site" and r._field == "total_wh")
  |> last()
  |> map(fn: (r) => ({ _time: r._time, _total_wh: r._value }))
  |> yield(name: "right_now")

this_day = union(tables: [midnight, right_now])
  |> sort(columns: ["_time"], desc: true)
  |> difference(nonNegative: false, columns: ["_total_wh"])
  |> map(fn: (r) => ({ _time: r._time, _kwh: float(v: r._total_wh) * -0.001 }))
  |> yield(name: "this_day")

union(tables: [past_30, this_day])
  |> sort(columns: ["_time"], desc: false)
  |> map(fn: (r) => ({ _time: r._time, _value: r._kwh }))
  |> timeShift(duration: timeAxisShift, columns: ["_time"])
  |> yield(name: "combined")