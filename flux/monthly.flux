// InfluxDB2 Flux example: last 31 days production
//
// Display the past 30 days production along with the current day production to date.  This requires two
// queries, the first to extract the last 30 days of production and a second query to calculate
// the production to date for the current day.
//
// Because the production for a given day requires that the total at the beginning of the day be
// subtracted from the total at the beginning of the following day, a sort is done to reverse the table
// so the time field will be the 1st of the month for the months production (otherwise it would tagged with
// the start of the following month).  So the results are sorted, differences taken, and sorted back to build
// the table for display.  Since the table will be in Watt-hours (Wh) and negative from the initial sort, the
// values are adjusted by -1000 to fix the sign and convert to kiloWatt-hours (kWh).
//
// The second query is similar but two fields are needed, 'today' will find the production at the start of
// the day and 'total' will extract the last reported production, subtract and adjust for the current
// days production.
//
// InfluxDB 1.8.x users should add the retention policy to the bucket name, ie, 'multisma2/autogen'

import "date"

timeAxisShift = 12h

// Collect the past 30 days production
from(bucket: "multisma2")
  |> range(start: -32d)
  |> filter(fn: (r) => r._measurement == "production" and r._inverter == "site" and r._field == "midnight")
  |> sort(columns: ["_time"], desc: true)
  |> difference(nonNegative: false, columns: ["_value"])
  |> map(fn: (r) => ({ _time: r._time, _value: float(v: r._value) / -1000.0 }))
  |> sort(columns: ["_time"], desc: false)
  |> timeShift(duration: timeAxisShift, columns: ["_time"])
  |> yield(name: "past_production")

// Collect the current days production  
from(bucket: "multisma2")
  |> range(start: -1d)
  |> filter(fn: (r) => r._measurement == "production" and r._inverter == "site")
  |> filter(fn: (r) => r._field == "midnight" or r._field == "daily")
  |> last()
  |> map(fn: (r) => ({ _time: r._time, _value: float(v: r._value) / -1000.0 }))
  |> sort(columns: ["_time"], desc: true)
  |> difference(nonNegative: false, columns: ["_value"])
  |> timeShift(duration: timeAxisShift, columns: ["_time"])
  |> yield(name: "today_production")