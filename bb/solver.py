"""CP-SAT solver. Hard rules are constraints, never penalty terms.

Optimality is relative to supplied shift templates and the configured start grid.
The objective is integer cents for paid time + 50 SEK per customer/employee
relationship + 2.50 SEK per permille of workload-utilisation spread.
"""
from math import floor
from uuid import uuid4
from .domain import (check_input, occurrences, span, paid, overlap, intersect,
                     instant, add_days, days, night_intervals, jour_intervals, is_night, monday)
from .validate import validate


def ssg_for_day(e, day):
    ssg = e['ssg']
    for w in e.get('ssgWindows') or []:
        if w['start'] <= day <= w['end']:
            ssg = w['ssg']
    return ssg


def ssg_cap_minutes(e, period_days, rules):
    return sum(ssg_for_day(e, day) / 100 * rules['fullTimeWeeklyHours'] * 60 / 7 for day in period_days)


def solve(data, seconds=30):
    from ortools.sat.python import cp_model
    check_input(data)
    seconds = min(300, max(1, float(seconds)))
    wp, rules = data['workplace'], data['rules']
    lo,hi = instant(wp['start'],'00:00'),instant(add_days(wp['end'],1),'00:00')
    period_days=list(days(wp['start'],wp['end']))
    employees=[e for e in data['employees'] if e['status']=='active']
    templates={t['id']:t for t in data['templates']}
    occ=occurrences(data)
    jour_floor=int(rules.get('jourFloor') or 0)
    model=cp_model.CpModel()
    candidates=[]
    boundaries=[]
    for s in data['boundaryShifts']:
        a,b=span(s)
        boundaries.append(dict(shift=s,a=a,b=b,work=paid(s),x=1))
    for e in employees:
        boundary=[b for b in boundaries if b['shift']['employeeId']==e['id']]
        absences=[(instant(a['start'],'00:00'),instant(add_days(a['end'],1),'00:00')) for a in data['absences'] if a['employeeId']==e['id']]
        for day in days(add_days(wp['start'],-1),wp['end']):
            for profile in e['profiles']:
                t=templates[profile]
                if t['type']=='jour' and not jour_floor: continue
                s=dict(id=f"{e['id']}:{day}:{profile}",employeeId=e['id'],date=day,start=t['start'],end=t['end'],type=t['type'],skills=t['skills'],breaks=t['breaks'])
                a,b=span(s)
                if b<=lo or a>=hi or b-a>rules['maxShiftHours']*60: continue
                if not set(t['skills'])<=set(e['skills']) or (is_night(a,b) and not e['night']): continue
                if any(overlap(a,b,x,y) for x,y in absences): continue
                work=paid(s)
                if any(overlap(a,b,v['a'],v['b']) for v in boundary): continue
                if work and any(v['work'] and not (a-v['b']>=rules['minRestHours']*60 or v['a']-b>=rules['minRestHours']*60) for v in boundary): continue
                x=model.new_bool_var('shift:'+s['id'])
                candidates.append(dict(shift=s,a=a,b=b,work=work,x=x))
    if len(candidates)>10000:
        raise ValueError('För många passalternativ. Begränsa personal, passmallar eller period.')

    def min_period(c):
        return sum(intersect(a,b,lo,hi) for a,b in c['work'])

    utilisations=[]
    for e in employees:
        rows=sorted((c for c in candidates if c['shift']['employeeId']==e['id']),key=lambda c:c['a'])
        fixed=[b for b in boundaries if b['shift']['employeeId']==e['id']]
        for i,a in enumerate(rows):
            for b in rows[i+1:]:
                if overlap(a['a'],a['b'],b['a'],b['b']):
                    model.add(a['x']+b['x']<=1)
                    continue
                if a['work'] and b['work']:
                    if b['a']-a['b']>=rules['minRestHours']*60: break
                    model.add(a['x']+b['x']<=1)
        cap=floor(ssg_cap_minutes(e,period_days,rules)+1e-7)
        used=sum(min_period(c)*c['x'] for c in rows)+sum(min_period(c) for c in fixed)
        model.add(used<=cap)
        if cap>0:
            util=model.new_int_var(0,1000,'util:'+e['id'])
            used_var=model.new_int_var(0,cap,'paid_minutes:'+e['id'])
            model.add(used_var==used)
            model.add_division_equality(util,used_var*1000,cap)
            utilisations.append(util)
        for week in {monday(day) for day in period_days}:
            wa,wb=instant(week,'00:00'),instant(add_days(week,7),'00:00')
            model.add(sum(sum(intersect(a,b,wa,wb) for a,b in c['work'])*c['x'] for c in rows+fixed)<=floor(rules['maxWeeklyHours']*60))
        flags=[]
        for day in days(add_days(wp['start'],-rules['maxConsecutiveDays']),add_days(wp['end'],rules['maxConsecutiveDays'])):
            a,b=instant(day,'00:00'),instant(add_days(day,1),'00:00')
            flag=model.new_bool_var('workday:'+e['id']+day)
            covering=[c['x'] for c in rows+fixed if any(overlap(x,y,a,b) for x,y in c['work'])]
            if covering: model.add_max_equality(flag,covering)
            else: model.add(flag==0)
            flags.append(flag)
        window=rules['maxConsecutiveDays']+1
        for i in range(len(flags)-window+1):
            model.add(sum(flags[i:i+window])<=rules['maxConsecutiveDays'])
        jour_rows=[c for c in rows+fixed if c['shift'].get('type')=='jour']
        for start_day in sorted({c['shift']['date'] for c in jour_rows}):
            limit=add_days(start_day,27)
            model.add(sum((c['b']-c['a'])*c['x'] for c in jour_rows if start_day<=c['shift']['date']<=limit)<=48*60)
        per_manad={}
        for c in jour_rows:
            per_manad.setdefault(c['shift']['date'][:7],[]).append(c)
        for grupp in per_manad.values():
            model.add(sum((c['b']-c['a'])*c['x'] for c in grupp)<=50*60)

    # Awake-night floor counts on-duty, eligible people. Rest constraints prevent
    # a person from being counted through two simultaneous candidate shifts.
    for a,b in night_intervals(wp['start'],wp['end']):
        a,b=max(a,lo),min(b,hi)
        if a>=b or not rules['nightFloor']: continue
        valid_ids={e['id'] for e in employees if e['night']}
        coverage=[(u,v,c['x']) for c in candidates+boundaries if c['shift']['employeeId'] in valid_ids for u,v in c['work']]
        edges=sorted({a,b}|{t for u,v,_ in coverage for t in (u,v) if a<t<b})
        for edge in edges[:-1]:
            model.add(sum(x for u,v,x in coverage if u<=edge<v)>=rules['nightFloor'])

    if jour_floor:
        valid_ids={e['id'] for e in employees if e['night']}
        for a,b in jour_intervals(wp['start'],wp['end'],rules):
            a,b=max(a,lo),min(b,hi)
            if a>=b: continue
            coverage=[(c['a'],c['b'],c['x']) for c in candidates+boundaries if c['shift'].get('type')=='jour' and c['shift']['employeeId'] in valid_ids]
            edges=sorted({a,b}|{t for u,v,_ in coverage for t in (u,v) if a<t<b})
            for edge in edges[:-1]:
                model.add(sum(x for u,v,x in coverage if u<=edge<v)>=jour_floor)

    task_vars=[]
    # Ge CP-SAT en omedelbart giltig startpunkt: inga valda pass och allt
    # kundbehov öppet redovisat som obemannat. Utan denna startpunkt kunde den
    # stora Galaxen-modellen använda hela tidsgränsen i presolve/sökning och
    # svara UNKNOWN trots att den mjuka täckningsmodellen alltid har en lösning.
    # Motorn förbättrar därefter startpunkten genom att välja pass och bemanna.
    shift_hints=[]
    support_hints=[]
    per_employee={e['id']:[] for e in employees}
    customer_links={}
    supports_count=0
    gaps=[]
    for o in occ:
        # Start times are real integer minutes. Duration is never rounded.
        starts=list(range(o['earliest']-lo,o['latest']-lo+1,rules['flexibilityStep']))
        start=model.new_int_var_from_domain(cp_model.Domain.from_values(starts),'start:'+o['id'])
        duration=o['task']['minutes']
        end=model.new_int_var(starts[0]+duration,starts[-1]+duration,'end:'+o['id'])
        model.add(end==start+duration)
        assigns=[]
        for e in employees:
            if not set(o['task']['skills'])<=set(e['skills']): continue
            krav = o['task'].get('requiredEmployeeId')
            if krav and e['id'] != krav: continue
            candidates_for_e=[c for c in candidates+boundaries if c['shift']['employeeId']==e['id']]
            options=[]
            for c in candidates_for_e:
                for a,b in c['work']:
                    if b-a<duration or b<o['earliest']+duration or a>o['latest']: continue
                    z=model.new_bool_var('support:'+str(supports_count));supports_count+=1
                    support_hints.append(z)
                    if supports_count>120000:
                        raise ValueError('För många möjliga insatstilldelningar. Förkorta perioden.')
                    model.add(z<=c['x'])
                    model.add(start>=a-lo).only_enforce_if(z)
                    model.add(end<=b-lo).only_enforce_if(z)
                    options.append(z)
            if not options: continue
            selected=model.new_bool_var('assign:'+o['id']+':'+e['id'])
            support_hints.append(selected)
            model.add(sum(options)==selected)
            interval=model.new_optional_interval_var(start,duration,end,selected,'task:'+o['id']+':'+e['id'])
            per_employee[e['id']].append(interval)
            assigns.append((e['id'],selected))
            customer_links.setdefault((o['task']['customerId'],e['id']),[]).append(selected)
        # Coverage is a strongly weighted goal, never a silent relaxation of the
        # hard rules: an unstaffed intervention is reported back explicitly.
        gap=model.new_int_var(0,o['count'],'uncovered:'+o['id'])
        model.add(sum(x for _,x in assigns)+gap==o['count'])
        gaps.append((o,gap))
        task_vars.append((o,start,end,assigns))
    for intervals in per_employee.values():
        model.add_no_overlap(intervals)

    wages={e['id']:e['hourlyCost'] if e['hourlyCost'] is not None else data['economy']['hourlyCost'] for e in employees}
    cost=sum(round(min_period(c)/60*wages[c['shift']['employeeId']]*100)*c['x'] for c in candidates)
    links=[]
    for (customer,employee),xs in customer_links.items():
        used=model.new_bool_var('continuity:'+customer+':'+employee)
        model.add_max_equality(used,xs); links.append(used)
    spread=0
    if utilisations:
        mx=model.new_int_var(0,1000,'max_util');mn=model.new_int_var(0,1000,'min_util')
        model.add_max_equality(mx,utilisations);model.add_min_equality(mn,utilisations)
        spread=mx-mn
    ow=data.get('objectiveWeights') or {}
    continuity_ore=int(round(float(ow.get('continuitySek',50))*100))
    spread_ore=int(round(float(ow.get('spreadSekPerPermille',2.5))*100))
    # Default 500 kr per obemannad insatsminut (samma styrka som tidigare 50 000 öre).
    # Täckning går före kostnad, kontinuitet och jämn belastning. Hårda villkor lättas aldrig.
    uncovered_ore=int(round(float(ow.get('uncoveredSekPerMinute',500))*100))
    uncovered_minutes=sum(o['task']['minutes']*gap for o,gap in gaps)
    model.minimize(cost+continuity_ore*sum(links)+spread_ore*spread+uncovered_ore*uncovered_minutes)
    for c in candidates:
        model.add_hint(c['x'],0)
    for x in support_hints:
        model.add_hint(x,0)
    for o,start,end,_ in task_vars:
        first=o['earliest']-lo
        model.add_hint(start,first)
        model.add_hint(end,first+o['task']['minutes'])
    for o,gap in gaps:
        model.add_hint(gap,o['count'])
    solver=cp_model.CpSolver()
    solver.parameters.max_time_in_seconds=seconds
    solver.parameters.num_search_workers=8
    solver.parameters.random_seed=41
    status=solver.solve(model)
    code=solver.status_name(status)
    explanations={
        'OPTIMAL':'Bevisat optimal inom valda passmallar, tidssteg och viktade mål. Granska förslaget innan du godkänner.',
        'FEASIBLE':'En giltig lösning hittades. Bästa möjliga lösning är inte bevisad inom tidsgränsen.',
        'INFEASIBLE':'Ingen lösning uppfyller alla hårda villkor inom valda passmallar och tidssteg. Kontrollera behov, kompetens, tillgänglighet och passmallar. Inga regler har lättats.',
        'UNKNOWN':'Sökningen avbröts vid tidsgränsen utan en hittad lösning. Detta bevisar inte att problemet är olösbart.',
        'MODEL_INVALID':'Optimeringsmodellen är ogiltig. Inget schemaförslag kan användas.'}
    schedule=dict(id=str(uuid4()),status='draft',basedOnRevision=data['inputRevision'],shifts=[],assignments=[],uncovered=[],solverStatus=code,explanation=explanations.get(code,'Okänd beräkningsstatus.'),seconds=solver.wall_time,objective=None,bound=None)
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        schedule['shifts']=[c['shift'] for c in candidates if solver.value(c['x'])]
        schedule['assignments']=[dict(occurrenceId=o['id'],employeeId=e,start=solver.value(start)+lo,end=solver.value(end)+lo) for o,start,end,assigns in task_vars for e,x in assigns if solver.value(x)]
        schedule['uncovered']=[dict(occurrenceId=o['id'],name=o['task']['name'],date=o['date'],minutes=o['task']['minutes'],count=solver.value(gap)) for o,gap in gaps if solver.value(gap)]
        schedule['objective']=solver.objective_value
        schedule['bound']=solver.best_objective_bound
        cost_val=int(round(sum(round(min_period(c)/60*wages[c['shift']['employeeId']]*100)*solver.value(c['x']) for c in candidates)))
        cont_val=continuity_ore*sum(solver.value(x) for x in links)
        spread_val=spread_ore*(solver.value(spread) if utilisations else 0)
        schedule['objectiveBreakdown']=dict(costOre=cost_val,continuityOre=int(cont_val),spreadOre=int(spread_val))
        result=validate(data,schedule)
        if not result['valid']:
            schedule.update(solverStatus='MODEL_INVALID',shifts=[],assignments=[],explanation='Förslaget stoppades av den fristående kontrollen: '+result['errors'][0]['message'])
        return dict(schedule=schedule,validation=result,modelScope=dict(candidateShifts=len(candidates),occurrences=len(occ),startStep=rules['flexibilityStep']))
    return dict(schedule=schedule,validation=None,modelScope=dict(candidateShifts=len(candidates),occurrences=len(occ),startStep=rules['flexibilityStep']))
