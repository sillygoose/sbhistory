// InfluxDB2 Flux example: last 13 months production
//
// Display the past 12 month production along with the current month to date.  This requires two
// queries, the first to extract the last 12 months of production and a second query to calculate
// the production the current month.
//
// InfluxDB 1.8.x users should add the retention policy to the bucket name, ie, 'multisma2/autogen'

import "date"

// This can be used to align results with x-axis labels
timeAxisShift = 0d

// Extract the last 12 months of production
past_12 = from(bucket: "multisma2")
  |> range(start: -13mo)
  |> filter(fn: (r) => r._measurement == "production" and r._inverter == "site" and r._field == "midnight")
  |> filter(fn: (r) => date.monthDay(t: r._time) == 1)
  |> sort(columns: ["_time"], desc: true)
  |> difference()
  |> map(fn: (r) => ({ _time: r._time, _kwh: float(v: r._value) * -0.001 }))
  |> sort(columns: ["_time"], desc: false)
  |> yield(name: "past_12")

// Extract the current months of production
first_of_month = from(bucket: "multisma2")
  |> range(start: -32d)
  |> filter(fn: (r) => r._measurement == "production" and r._inverter == "site" and r._field == "midnight")
  |> filter(fn: (r) => date.monthDay(t: r._time) == 1 )
  |> map(fn: (r) => ({ _time: r._time, _total_wh: r._value }))
  |> yield(name: "first_of_month")

today = from(bucket: "multisma2")
  |> range(start: -1d)
  |> filter(fn: (r) => r._measurement == "production" and r._inverter == "site" and r._field == "total_wh")
  |> last()
  |> map(fn: (r) => ({ _time: r._time, _total_wh: r._value }))
  |> yield(name: "today")

this_month = union(tables: [first_of_month, today])
  |> sort(columns: ["_time"], desc: true)
  |> difference(nonNegative: false, columns: ["_total_wh"])
  |> map(fn: (r) => ({ _time: r._time, _kwh: float(v: r._total_wh) * -0.001 }))
  |> yield(name: "this_month")

// Combine the results in to a single table with '_value' and '_time' as the axes
union(tables: [past_12, this_month])
  |> sort(columns: ["_time"], desc: false)
  |> map(fn: (r) => ({ _time: r._time, _value: r._kwh }))
  |> timeShift(duration: timeAxisShift, columns: ["_time"])
  |> yield(name: "combined")