"""Pure domain/time helpers. No solver or web-framework dependency.

All instants are integer UTC minutes. Ambiguous/nonexistent wall times are
rejected explicitly; night shifts across a DST change keep their real duration.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from math import isfinite

TZ = ZoneInfo('Europe/Stockholm')


def add_days(day, n):
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def days(start, end):
    if (date.fromisoformat(end) - date.fromisoformat(start)).days > 100:
        raise ValueError('För lång period.')
    while start <= end:
        yield start
        start = add_days(start, 1)


def instant(day, clock):
    naive = datetime.fromisoformat(f'{day}T{clock}:00')
    found = set()
    for fold in (0, 1):
        aware = naive.replace(tzinfo=TZ, fold=fold)
        utc = aware.astimezone(timezone.utc)
        if utc.astimezone(TZ).replace(tzinfo=None) == naive:
            found.add(int(utc.timestamp() // 60))
    if len(found) != 1:
        raise ValueError(f'{day} {clock}: tiden saknas eller är tvetydig vid sommartidsomställningen.')
    return found.pop()


def parts(t):
    value = datetime.fromtimestamp(t * 60, TZ)
    return value.date().isoformat(), value.strftime('%H:%M')


def span(shift):
    day, start, end = shift['date'], shift['start'], shift['end']
    return instant(day, start), instant(add_days(day, 1) if end <= start else day, end)


def intersect(a, b, c, d):
    return max(0, min(b, d) - max(a, c))


def overlap(a, b, c, d):
    return a < d and c < b


def paid(shift):
    # Sovande jour är inte arbetstid: den ingår inte i SSG, veckotimmar,
    # kostnad eller insatsbemanning. Spännvidden (span) används fortfarande
    # så att jour inte kan överlappa ett arbetspass.
    if shift.get('type') == 'jour':
        span(shift)
        return []
    a, b = span(shift)
    cursor, result = a, []
    for br in sorted(shift['breaks'], key=lambda x: x['offset']):
        x, y = a + br['offset'], a + br['offset'] + br['minutes']
        if x < cursor or y > b or br['minutes'] <= 0:
            raise ValueError('Ogiltig eller överlappande rast.')
        if cursor < x:
            result.append((cursor, x))
        cursor = y
    if cursor < b:
        result.append((cursor, b))
    return result


def night_intervals(start, end):
    for day in days(add_days(start, -1), end):
        yield instant(day, '22:00'), instant(add_days(day, 1), '06:00')


def jour_intervals(start, end):
    """Sovande jour enligt styrande villkor: 23:00–06:30."""
    for day in days(add_days(start, -1), end):
        yield instant(day, '23:00'), instant(add_days(day, 1), '06:30')


def is_night(a, b):
    return any(overlap(a, b, x, y) for x, y in night_intervals(parts(a)[0], parts(b)[0]))


def monday(day):
    return add_days(day, -date.fromisoformat(day).weekday())


def occurrences(data):
    active = {c['id'] for c in data['customers'] if c['active']}
    lo, hi = instant(data['workplace']['start'], '00:00'), instant(add_days(data['workplace']['end'], 1), '00:00')
    out = []
    for day in days(add_days(data['workplace']['start'], -1), data['workplace']['end']):
        wd = date.fromisoformat(day).isoweekday()
        for task in data['interventions']:
            if task['customerId'] not in active or (task['date'] != day if task['date'] else wd not in task['weekdays']):
                continue
            earliest = instant(day, task['start'])
            latest = earliest if task['type'] == 'fixed' else instant(add_days(day, 1) if task['latestEnd'] <= task['start'] else day, task['latestEnd']) - task['minutes']
            if latest < earliest:
                raise ValueError(f"{task['name']}: insatsen ryms inte i tidsfönstret.")
            if overlap(earliest, latest + task['minutes'], lo, hi):
                out.append(dict(id=task['id']+'@'+day, task=task, date=day, earliest=earliest, latest=latest, count=2 if task['doubleStaff'] else 1))
    return out


def check_input(d):
    """Fail closed on malformed data, supported size limits and rule values."""
    def require(ok, message):
        if not ok:
            raise ValueError(message)

    def numeric(value, lo, hi, integer=False):
        return type(value) in (int, float) and isfinite(value) and lo <= value <= hi and (not integer or int(value) == value)

    import re
    try:
        require(d['schemaVersion'] == 1, 'Okänd dataversion.')
        wp = d['workplace']
        require(wp['timezone'] == 'Europe/Stockholm', 'Använd svensk tidszon.')
        n = (date.fromisoformat(wp['end']) - date.fromisoformat(wp['start'])).days + 1
        require(1 <= n <= 42, 'Perioden ska vara 1–42 dagar.')
        require(numeric(d['inputRevision'], 0, 10**10, True), 'Ogiltig revision.')
        for key, limit in [('customers',100),('employees',80),('interventions',4000),('templates',12),('boundaryShifts',2000),('absences',2000)]:
            require(isinstance(d[key], list) and len(d[key]) <= limit, f'Ogiltig storlek: {key}.')
            require(len({x['id'] for x in d[key]}) == len(d[key]), f'Dubbla id i {key}.')
        require(1 <= len(d['templates']) <= 12, 'Passmallar saknas.')
        customers = {c['id'] for c in d['customers']}
        employees = {e['id'] for e in d['employees']}
        profiles = {p['id'] for p in d['templates']}
        require(len({c['code'] for c in d['customers']}) == len(customers), 'Dubbla kundkoder.')
        require(len({e['code'] for e in d['employees']}) == len(employees), 'Dubbla medarbetarkoder.')
        for c in d['customers']:
            require(bool(re.fullmatch(r'Kund \d+', c['code'])) and type(c['active']) is bool, 'Ogiltig kundkod/status.')
        for e in d['employees']:
            require(bool(re.fullmatch(r'[A-ZÅÄÖ0-9-]{1,8}', e['code'])), 'Använd medarbetarkoder.')
            require(numeric(e['ssg'],0,100) and type(e['night']) is bool, 'Ogiltig SSG/nattbehörighet.')
            require(e['status'] in ['active','vacant','inactive'], 'Ogiltig personalstatus.')
            require(e['profiles'] and set(e['profiles']) <= profiles, 'Ogiltiga passprofiler.')
            require(e['hourlyCost'] is None or numeric(e['hourlyCost'],0,100000), 'Ogiltig timkostnad.')
            require(isinstance(e['skills'],list) and all(isinstance(k,str) for k in e['skills']), 'Ogiltig kompetens.')
        for t in d['interventions']:
            require(t['customerId'] in customers and t['type'] in ['fixed','flexible'], 'Ogiltig insats/kund.')
            require(numeric(t['minutes'],1,480,True) and type(t['doubleStaff']) is bool, 'Ogiltig insatslängd eller dubbelbemanning.')
            require(t['weekdays'] and set(t['weekdays']) <= set(range(1,8)), 'Ogiltiga veckodagar.')
            require(all(isinstance(k,str) for k in t['skills']), 'Ogiltig kompetens.')
            if t['date']:
                date.fromisoformat(t['date'])
            for value in [t['start'],t['latestEnd']]:
                require(bool(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value)), 'Ogiltig tid.')
        for a in d['absences']:
            require(a['employeeId'] in employees and a['start'] <= a['end'], 'Ogiltig frånvaro.')
            instant(a['start'],'00:00'); instant(a['end'],'00:00')
        for key, lo, hi, integer in [('minRestHours',11,48,False),('fullTimeWeeklyHours',1,60,False),('maxWeeklyHours',1,60,False),('maxShiftHours',1,16,False),('maxConsecutiveDays',1,7,True),('nightFloor',0,10,True),('flexibilityStep',1,60,True)]:
            require(numeric(d['rules'][key],lo,hi,integer), f'Ogiltig regel: {key}.')
        if 'jourFloor' in d['rules']:
            require(numeric(d['rules']['jourFloor'], 0, 10, True), 'Ogiltig regel: jourFloor.')
        require(numeric(d['economy']['hourlyCost'],0,100000), 'Ogiltig timkostnad.')
        ow = d.get('objectiveWeights') or {}
        require(isinstance(ow, dict), 'Ogiltiga målviktningar.')
        for key in ('continuitySek', 'spreadSekPerPermille'):
            if key in ow:
                require(numeric(ow[key], 0, 10000), f'Ogiltig målvikt: {key}.')
        require(type(d['boundaryAcknowledged']) is bool,'Periodgränser måste bekräftas explicit.')
        for s in d['boundaryShifts']:
            require(s['employeeId'] in employees, 'Gränspass saknar medarbetare.')
            paid(s)
        for t in d['templates']:
            require(t['type'] in ['day','evening','night','jour'], 'Ogiltig passtyp.')
            require(isinstance(t['skills'],list), 'Passkompetens saknas.')
            for day in days(wp['start'],wp['end']):
                paid({**t,'date':day})
        require(len(occurrences(d)) <= 1600, 'Högst 1 600 insatstillfällen per beräkning. Förkorta perioden.')
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('Grunduppgifter saknas eller har fel format.') from exc
    return d
