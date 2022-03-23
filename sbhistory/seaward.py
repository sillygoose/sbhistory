"""Process Seaward irradiance meter CSV files."""

import logging
import os
import csv
import datetime


_LOGGER = logging.getLogger('sbhistory')


def process(directory, tzinfo, influxdb):
    try:
        _LOGGER.info(f"Processing files from {directory}")
        for entry in os.scandir(directory):
            if not entry.is_file():
                continue
            if not entry.path.endswith('.csv'):
                continue

            csv_indices = {}
            lp_points = []
            with open(entry.path, newline='') as csvfile:
                _LOGGER.info(f"Processing file {entry.name}")
                reader = csv.reader(csvfile, delimiter=',', quotechar='|')
                for row in reader:
                    if len(row) == 0:
                        break
                    if reader.line_num == 1:
                        to_find = ['Date', 'Time', 'Tpv', 'Ta', 'Irr', 'Irr Unit', 'Temp Unit']
                        for heading in to_find:
                            index = row.index(heading)
                            csv_indices[heading] = index
                    else:
                        irradiance = row[csv_indices['Irr']]
                        if irradiance.startswith('<'):
                            irradiance = '0'
                        irradiance = float(irradiance)

                        date = row[csv_indices['Date']]
                        date_dmy = date.split('.')
                        d = datetime.date(
                            year=int('20' + date_dmy[2]), month=int(date_dmy[1]), day=int(date_dmy[0])
                        )

                        time = row[csv_indices['Time']]
                        time_hms = time.split(':')
                        t = datetime.time(hour=int(time_hms[0]), minute=int(time_hms[1]))
                        dt = datetime.datetime.combine(date=d, time=t, tzinfo=tzinfo)
                        ts = int(dt.timestamp())

                        tpv = row[csv_indices['Tpv']]
                        if tpv == 'ERR':
                            tpv = None
                        ta = row[csv_indices['Ta']]
                        if ta == 'ERR':
                            ta = None

                        # sample: sun,_type=measured irradiance=800 1556813561098
                        lp_points.append(f"sun,_type=measured irradiance={irradiance} {ts}")
                        if tpv:
                            # sample: sun,_type=working temperature=10 1556813561098
                            lp_points.append(f"sun,_type=working temperature={float(ta)} {ts}")
                        if ta:
                            # sample: sun,_type=ambient temperature=8 1556813561098
                            lp_points.append(f"sun,_type=ambient temperature={float(tpv)} {ts}")
                        print('.', end='', flush=True)

                print()
                influxdb.write_points(lp_points)

    except FileNotFoundError as e:
        _LOGGER.error(f"{e}")
        return None

    except Exception as e:
        print()
        _LOGGER.error(f"An error occurred in {entry.name}, line {reader.line_num}: {e}")
        return None

    print()
