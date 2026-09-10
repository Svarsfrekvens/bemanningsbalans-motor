"""Independent validator. It never imports solver.py or trusts solver status."""
from .domain import (check_input, occurrences, span, paid, overlap, intersect, instant,
                     add_days, days, parts, night_intervals, jour_intervals, is_night, monday)


def validate(data, schedule):
    errors, warnings = [], []

    def issue(rule, message, **more):
        errors.append(dict(rule=rule, message=message, **more))

    try:
        check_input(data)
        occ = occurrences(data)
    except (ValueError, KeyError, TypeError) as exc:
        return dict(valid=False, errors=[dict(rule='INPUT',message=str(exc))], warnings=[])
    employees = {e['id']:e for e in data['employees']}
    wp, r = data['workplace'], data['rules']
    lo, hi = instant(wp['start'],'00:00'), instant(add_days(wp['end'],1),'00:00')
    boundaries = {s['id'] for s in data['boundaryShifts']}
    processed = []
    try:
        ids = [s['id'] for s in schedule['shifts']] + list(boundaries)
        if len(ids) != len(set(ids)):
            issue('DUPLICATE_SHIFT','Ett pass-id förekommer flera gånger.')
        for s in schedule['shifts'] + data['boundaryShifts']:
            try:
                a,b = span(s)
                work = paid(s)
                processed.append(dict(**s,a=a,b=b,work=work))
                e = employees.get(s['employeeId'])
                if not e:
                    issue('EMPLOYEE','Medarbetare saknas.',shiftId=s['id']); continue
                meta = dict(employeeId=e['id'],shiftId=s['id'])
                if s['id'] not in boundaries and e['status'] != 'active':
                    issue('STATUS',f"{e['code']}: inte aktiv.",**meta)
                if not e['night'] and (s.get('type') == 'jour' or is_night(a,b)):
                    issue('NIGHT',f"{e['code']}: saknar nattbehörighet.",**meta)
                if not set(s['skills']) <= set(e['skills']):
                    issue('SKILL',f"{e['code']}: saknar passkompetens.",**meta)
                if b-a > r['maxShiftHours']*60:
                    issue('SHIFT_LENGTH',f"{e['code']}: för långt pass.",**meta)
                if any(v['employeeId']==e['id'] and overlap(a,b,instant(v['start'],'00:00'),instant(add_days(v['end'],1),'00:00')) for v in data['absences']):
                    issue('ABSENCE',f"{e['code']}: pass under frånvaro.",**meta)
            except (ValueError,KeyError,TypeError) as exc:
                issue('TIME',f'Ogiltigt arbetspass: {exc}')
        for e in employees.values():
            shifts = sorted((s for s in processed if s['employeeId']==e['id']),key=lambda x:x['a'])
            for i,s in enumerate(shifts):
                for previous in shifts[:i]:
                    gap = s['a']-previous['b']
                    if gap < 0:
                        issue('SHIFT_OVERLAP',f"{e['code']}: {gap/60:g} timmars vila före {s['date']} {s['start']}.",employeeId=e['id'],shiftId=s['id'])
                    elif previous['work'] and s['work'] and gap < r['minRestHours']*60:
                        issue('REST',f"{e['code']}: {gap/60:g} timmars vila före {s['date']} {s['start']}.",employeeId=e['id'],shiftId=s['id'])
            used = sum(intersect(a,b,lo,hi) for s in shifts for a,b in s['work'])
            cap = e['ssg']/100*r['fullTimeWeeklyHours']*60*len(list(days(wp['start'],wp['end'])))/7
            if used > cap+0.01:
                issue('CONTRACT',f"{e['code']}: fler timmar än periodkapaciteten enligt SSG.",employeeId=e['id'])
            for week in {monday(day) for day in days(wp['start'],wp['end'])}:
                wa,wb = instant(week,'00:00'),instant(add_days(week,7),'00:00')
                if sum(intersect(a,b,wa,wb) for s in shifts for a,b in s['work']) > r['maxWeeklyHours']*60:
                    issue('WEEK_HOURS',f"{e['code']}: för många timmar kalenderveckan {week}.",employeeId=e['id'])
            run = 0
            for day in days(add_days(wp['start'],-r['maxConsecutiveDays']),add_days(wp['end'],r['maxConsecutiveDays'])):
                a,b = instant(day,'00:00'),instant(add_days(day,1),'00:00')
                run = run+1 if any(any(overlap(x,y,a,b) for x,y in s['work']) for s in shifts) else 0
                if run==r['maxConsecutiveDays']+1:
                    issue('CONSECUTIVE',f"{e['code']}: för många kalenderdagar med arbete i följd.",employeeId=e['id'])
            jour = [s for s in shifts if s.get('type') == 'jour']
            sorterade = sorted(jour, key=lambda s: s['date'])
            for i, start in enumerate(sorterade):
                gransen = add_days(start['date'], 27)
                total = sum(s['b'] - s['a'] for s in sorterade[i:] if s['date'] <= gransen)
                if total > 48 * 60 + 0.01:
                    issue('JOUR_4W', f"{e['code']}: mer än 48 timmar jourtid under fyra veckor från {start['date']}.", employeeId=e['id'])
                    break
            per_manad = {}
            for s in sorterade:
                k = s['date'][:7]
                per_manad[k] = per_manad.get(k, 0) + (s['b'] - s['a'])
            for manad, total in per_manad.items():
                if total > 50 * 60 + 0.01:
                    issue('JOUR_MONTH', f"{e['code']}: mer än 50 timmar jourtid i {manad}.", employeeId=e['id'])
        assignments=schedule['assignments']
        known={o['id'] for o in occ}
        # Ett förslag får redovisa obemannat behov, men bara om det är öppet
        # deklarerat. Odeklarerad brist är fortfarande ett fel.
        declared={}
        for u in schedule.get('uncovered') or []:
            try:
                declared[u['occurrenceId']]=int(u['count'])
            except (KeyError,TypeError,ValueError):
                issue('UNCOVERED','Obemannat behov är felaktigt redovisat.')
        for a in assignments:
            if a['occurrenceId'] not in known:
                issue('UNKNOWN_TASK','Okänd insats i tilldelningen.',occurrenceId=a['occurrenceId'])
        for o in occ:
            rows=[a for a in assignments if a['occurrenceId']==o['id']]
            meta=dict(occurrenceId=o['id'])
            distinct=len({a['employeeId'] for a in rows})
            gap=declared.get(o['id'],0)
            if len(rows)!=distinct:
                issue('COVERAGE',f"{o['task']['name']} {o['date']}: samma medarbetare räknas flera gånger.",**meta)
            elif distinct+gap!=o['count']:
                issue('COVERAGE',f"{o['task']['name']} {o['date']}: kräver {o['count']} olika medarbetare.",**meta)
            elif gap:
                warnings.append(dict(rule='UNCOVERED',message=f"{o['task']['name']} {o['date']}: {gap} av {o['count']} insatstillfällen är obemannade i förslaget.",occurrenceId=o['id']))
            if len({a['start'] for a in rows})>1:
                issue('SIMULTANEOUS','Dubbelbemanningen startar inte samtidigt.',**meta)
            for a in rows:
                if type(a['start']) is not int or type(a['end']) is not int or not o['earliest']<=a['start']<=o['latest'] or a['end']!=a['start']+o['task']['minutes']:
                    issue('WINDOW','Insatsen har fel tid eller längd.',**meta)
                e=employees.get(a['employeeId'])
                if not e or e['status']!='active' or not set(o['task']['skills'])<=set(e['skills']):
                    issue('TASK_SKILL','Insatsen saknar behörig medarbetare.',**meta)
                if not any(s['employeeId']==a['employeeId'] and any(x<=a['start'] and y>=a['end'] for x,y in s['work']) for s in processed):
                    issue('ON_DUTY','Medarbetaren är inte i tjänst hela insatsen.',**meta)
        for e in employees.values():
            rows=sorted((a for a in assignments if a['employeeId']==e['id']),key=lambda x:x['start'])
            for i,a in enumerate(rows):
                for b in rows[i+1:]:
                    if b['start']>=a['end']: break
                    issue('TASK_OVERLAP',f"{e['code']}: dubbelbokad på {a['occurrenceId']} och {b['occurrenceId']}.",employeeId=e['id'])
        for a,b in night_intervals(wp['start'],wp['end']):
            a,b=max(a,lo),min(b,hi)
            if a>=b: continue
            work=[(x,y,s['employeeId']) for s in processed if employees.get(s['employeeId'],{}).get('night') and employees[s['employeeId']]['status']=='active' for x,y in s['work']]
            points=sorted({a,b}|{t for x,y,_ in work for t in (x,y) if a<t<b})
            for t in points[:-1]:
                if len({e for x,y,e in work if x<=t<y})<r['nightFloor']:
                    issue('NIGHT_FLOOR',f"Vaken natt saknar täckning {' '.join(parts(t))}."); break
        jour_floor = int(r.get('jourFloor') or 0)
        if jour_floor:
            for a,b in jour_intervals(wp['start'],wp['end'],r):
                a,b=max(a,lo),min(b,hi)
                if a>=b: continue
                covering=[(s['a'],s['b'],s['employeeId']) for s in processed if s.get('type')=='jour' and employees.get(s['employeeId'],{}).get('night') and employees[s['employeeId']]['status']=='active']
                points=sorted({a,b}|{t for x,y,_ in covering for t in (x,y) if a<t<b})
                for t in points[:-1]:
                    if len({e for x,y,e in covering if x<=t<y})<jour_floor:
                        issue('JOUR_FLOOR',f"Sovande jour saknar täckning {' '.join(parts(t))}."); break
    except (KeyError,TypeError,ValueError) as exc:
        issue('STRUCTURE',f'Schemat kunde inte läsas: {exc}')
    if not data['boundaryAcknowledged']:
        warnings.append(dict(rule='BOUNDARIES',message='Passen före och efter perioden har inte bekräftats.'))
    warnings.append(dict(rule='SCOPE',message='Kontrollen omfattar implementerade regler, inte hela kollektivavtalet.'))
    return dict(valid=not errors,errors=errors,warnings=warnings)
