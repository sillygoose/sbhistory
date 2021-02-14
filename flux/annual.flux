// InfluxDB2 Flux example: last 13 months production
//
// Display the past 12 month production along with the current month to date.  This requires two
// queries, the first to extract the last 12 months of production and a second query to calculate
// the production to date for the current month.
//
// Because the production for a given month requires that the total at the beginning of the month be
// subtracted from the total at the beginning of the following month, a sort is done to reverse the table
// so the time field will be the 1st of the month for the months production (otherwise it would tagged with
// the start of the following month).  So the results are sorted, differences taken, and sorted back to build
// the table for display.  Since the table will be in Watt-hours (Wh) and negative from the initial sort, the
// values are adjusted by -1000 to fix the sign and convert to kiloWatt-hours (kWh).
//
// The second query is similar but two fields are needed, 'today'will find the production at the start of
// the month and 'total' will extract the last reported production, subtract and adjust for the current
// month production.
//
// InfluxDB 1.8.x users should add the retention policy to the bucket name, ie, 'multisma2/autogen'

import "date"

timeAxisShift = 15d

// Collect the past 12 months production
from(bucket: "multisma2")
  |> range(start: -13mo)
  |> filter(fn: (r) => r._measurement == "production" and r.inverter == "site")
  |> filter(fn: (r) => r._field == "today" and date.monthDay(t: r._time) == 1)
  |> sort(columns: ["_time"], desc: true)
  |> difference(nonNegative: false, columns: ["_value"])
  |> map(fn: (r) => ({ _time: r._time, _value: float(v: r._value) / -1000.0 }))
  |> sort(columns: ["_time"], desc: false)
  |> timeShift(duration: timeAxisShift, columns: ["_time"])
  |> yield(name: "production_past")
  
// Collect the current month production
from(bucket: "multisma2")
  |> range(start: -1mo)
  |> filter(fn: (r) => r._measurement == "production" and r.inverter == "site")
  |> filter(fn: (r) => r._field == "total" or (r._field == "today" and date.monthDay(t: r._time) == 1))
  |> last()
  |> map(fn: (r) => ({ _time: r._time, _value: float(v: r._value) / -1000.0 }))
  |> sort(columns: ["_time"], desc: true)
  |> difference(nonNegative: false, columns: ["_value"])
  |> timeShift(duration: timeAxisShift, columns: ["_time"])
  |> yield(name: "production_today")