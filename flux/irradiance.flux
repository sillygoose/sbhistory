// InfluxDB2 Flux example
// Display clearsky irradiance and site production in a Graph visualization
// Irradiance is easy, the SMA inverters store production as total production in Wh, typically
// every 5 minutes.  To convert this data to Watts (W), you must find the difference between adjacent
// data points (Wh) and multiply by 3600 secs/hour (Ws) and then divide by the interval in seconds).
//
// Irradience is in W/m^2, multiply by the area of the array and panel efficiency to get the solar
// potental for the site.
//
// InfluxDB 1.8.x users should add the retention policy to the bucket name, ie, 'multisma2/autogen'
panel_area = 144.0
panel_efficency = 0.1725

from(bucket: "multisma2")
    |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
    |> filter(fn: (r) => r._measurement == "production" and r._inverter == "site" and r._field == "total_wh")
    |> elapsed(unit: 1s)
    |> difference(nonNegative: true, columns: ["_value"])
    |> filter(fn: (r) => r._value > 0)
    |> map(fn: (r) => ({r with _value: float(v: r._value) * 3600.0 / float(v: r.elapsed)}))
    |> drop(columns: [
        "elapsed",
        "_start",
        "_stop",
        "_field",
        "_inverter",
        "_measurement",
    ])
    |> yield(name: "production")

from(bucket: "multisma2")
    |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
    |> filter(fn: (r) => r._measurement == "sun" and r._field == "irradiance" and r._type == "modeled")
    |> map(fn: (r) => ({r with _value: float(v: r._value) * panel_area * panel_efficency}))
    |> yield(name: "irradiance")