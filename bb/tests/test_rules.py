import unittest
from copy import deepcopy
from bb.domain import instant, span, check_input
from bb.validate import validate


def fixture():
    d=dict(schemaVersion=1,inputRevision=0,workplace=dict(name='Test',start='2026-09-07',end='2026-09-13',timezone='Europe/Stockholm'),customers=[dict(id='c1',code='Kund 1',active=True)],interventions=[dict(id='t1',customerId='c1',name='Stöd',type='fixed',start='09:00',latestEnd='10:00',minutes=60,doubleStaff=False,weekdays=[1],date='2026-09-07',skills=['Omsorg'])],employees=[dict(id='e1',code='M01',ssg=100,night=True,profiles=['D'],hourlyCost=None,status='active',skills=['Omsorg'])],templates=[dict(id='D',name='Dag',start='06:00',end='14:00',type='day',skills=['Omsorg'],breaks=[])],absences=[],boundaryShifts=[],boundaryAcknowledged=True,economy=dict(hourlyCost=250),rules=dict(minRestHours=11,fullTimeWeeklyHours=40,maxWeeklyHours=48,maxShiftHours=12,maxConsecutiveDays=5,nightFloor=0,flexibilityStep=15))
    s=dict(id='test',status='draft',basedOnRevision=0,shifts=[dict(id='s1',employeeId='e1',date='2026-09-07',start='06:00',end='14:00',type='day',skills=['Omsorg'],breaks=[])],assignments=[dict(occurrenceId='t1@2026-09-07',employeeId='e1',start=instant('2026-09-07','09:00'),end=instant('2026-09-07','10:00'))],solverStatus='NOT_RUN',explanation='',seconds=0,objective=None,bound=None)
    d['current']=s;d['proposal']=None;d['outcomes']=[]
    return d,s


class Rules(unittest.TestCase):
    def codes(self,d,s): return {e['rule'] for e in validate(d,s)['errors']}
    def test_valid(self):
        d,s=fixture();self.assertTrue(validate(d,s)['valid'])
    def test_double_requires_two_people(self):
        d,s=fixture();d['interventions'][0]['doubleStaff']=True;s['assignments']*=2
        self.assertIn('COVERAGE',self.codes(d,s));self.assertIn('TASK_OVERLAP',self.codes(d,s))
    def test_headcount_not_assignment(self):
        d,s=fixture();d['employees'].append(dict(**{**d['employees'][0],'id':'e2','code':'M02'}));s['shifts'].append({**s['shifts'][0],'id':'s2','employeeId':'e2'})
        d['interventions'].append({**d['interventions'][0],'id':'t2'});s['assignments'].append({**s['assignments'][0],'occurrenceId':'t2@2026-09-07'})
        self.assertIn('TASK_OVERLAP',self.codes(d,s))
    def test_absence(self):
        d,s=fixture();d['absences']=[dict(id='a',employeeId='e1',start='2026-09-07',end='2026-09-07')];self.assertIn('ABSENCE',self.codes(d,s))
    def test_competence(self):
        d,s=fixture();d['interventions'][0]['skills']=['Läkemedel'];self.assertIn('TASK_SKILL',self.codes(d,s))
    def test_break(self):
        d,s=fixture();s['shifts'][0]['breaks']=[dict(offset=180,minutes=30)];self.assertIn('ON_DUTY',self.codes(d,s))
    def test_previous_period_exact_rest(self):
        d,s=fixture();d['boundaryShifts']=[{**s['shifts'][0],'id':'before','date':'2026-09-06','start':'11:00','end':'19:00'}];self.assertNotIn('REST',self.codes(d,s))
        d['boundaryShifts'][0]['end']='20:00';self.assertIn('REST',self.codes(d,s))
    def test_next_period_rest(self):
        d,s=fixture();s['shifts'][0].update(date='2026-09-13',start='14:00',end='22:00');d['boundaryShifts']=[{**s['shifts'][0],'id':'after','date':'2026-09-14','start':'08:00','end':'16:00'}];self.assertIn('REST',self.codes(d,s))
    def test_dst_night(self):
        for day,minutes in [('2026-03-28',420),('2026-10-24',540)]:
            a,b=span(dict(date=day,start='22:00',end='06:00'));self.assertEqual(b-a,minutes)
        for day in ['2026-03-29','2026-10-25']:
            with self.assertRaises(ValueError): instant(day,'02:30')
    def test_night_eligibility_and_floor(self):
        d,s=fixture();s['shifts'][0].update(start='22:00',end='06:00');d['employees'][0]['night']=False;d['rules']['nightFloor']=1
        self.assertIn('NIGHT',self.codes(d,s));self.assertIn('NIGHT_FLOOR',self.codes(d,s))
    def test_duplicate_ids(self):
        d,s=fixture();s['shifts'].append(deepcopy(s['shifts'][0]));self.assertIn('DUPLICATE_SHIFT',self.codes(d,s))
    def test_fail_closed_rules(self):
        d,s=fixture();d['rules']['minRestHours']=10
        with self.assertRaises(ValueError): check_input(d)
