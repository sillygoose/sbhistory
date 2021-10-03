
""""""

import logging
import datetime

_LOGGER = logging.getLogger('sbhistory')


def process(inverter_results, start):
    for inverter in inverter_results:
        t = inverter[1]['t']
        dt = datetime.datetime.fromtimestamp(t)
        date = start.date()
        end_date = datetime.date(year=dt.year, month=dt.month, day=dt.day)
        delta = datetime.timedelta(days=1)

        # add missing dates as 0 Wh values
        while date < end_date:
            print('.', end='', flush=True)
            newtime = datetime.datetime.combine(date, datetime.time(0, 0))
            t = int(newtime.timestamp())
            inverter.append({'t': t, 'v': 0})
            date += delta

        # Sort the entries by date
        try:
            inv0 = inverter
            inv_name = inv0.pop(0)
            inv0.sort(key=lambda item: item.get('t'))
            inv0.insert(0, inv_name)
        except Exception as e:
            print(e)

        # normalize times to midnight
        midnight = datetime.time()
        for i in range(1, len(inverter)):
            t = inverter[i]['t']
            v = inverter[i]['v']
            dt = datetime.datetime.fromtimestamp(t)
            if dt.hour > 12:
                new_day = dt.date() + datetime.timedelta(days=1)
                new_dt = datetime.datetime.combine(new_day, midnight)
                inverter[i]['t'] = int(new_dt.timestamp())
            else:
                new_day = dt.date()
                new_dt = datetime.datetime.combine(new_day, midnight)
                inverter[i]['t'] = int(new_dt.timestamp())

    # Calculate the total
    total = {}
    count = {}
    for inverter in inverter_results:
        last_non_null = None
        for i in range(1, len(inverter)):
            print('.', end='', flush=True)
            t = inverter[i]['t']
            v = inverter[i]['v']
            if v is None:
                if not last_non_null:
                    continue
                v = last_non_null
                inverter[i]['v'] = last_non_null

            total[t] = v + total.get(t, 0)
            count[t] = count.get(t, 0) + 1
            last_non_null = v

    # Site output if multiple inverters
    if len(inverter_results) > 1:
        site_total = []
        for t, v in total.items():
            if count[t] == len(inverter_results):
                site_total.append({'t': t, 'v': v})
        site_total.insert(0, {'inverter': 'site'})
        inverter_results.append(site_total)

    print()
    return inverter_results
