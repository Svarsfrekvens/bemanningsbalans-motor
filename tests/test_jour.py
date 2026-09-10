import importlib.util
import unittest
from collections import defaultdict
from copy import deepcopy
from test_rules import fixture
from bb.domain import check_input, instant, jour_intervals, paid, span
from bb.validate import validate
from bb.solver import solve


def jour_mall():
    return dict(id='J', name='Sovande jour', start='23:00', end='06:30', type='jour', skills=[], breaks=[])


def with_jour(d, extra=0):
    d = deepcopy(d)
    d['templates'].append(jour_mall())
    d['employees'][0]['profiles'] = ['D', 'J']
    d['employees'][0]['night'] = True
    for i in range(extra):
        d['employees'].append({**d['employees'][0], 'id': f'e{i + 2}', 'code': f'M{i + 2:02d}'})
    return d


class SovandeJour(unittest.TestCase):
    def test_paid_work_excludes_jour(self):
        s = dict(id='j1', employeeId='e1', date='2026-09-07', start='23:00', end='06:30', type='jour', skills=[], breaks=[])
        self.assertEqual(paid(s), [])
        a, b = span(s)
        self.assertGreater(b - a, 7 * 60)
        self.assertLess(b - a, 9 * 60)

    def test_jour_is_not_awake_night_floor(self):
        d, s = fixture()
        d['templates'].append(jour_mall())
        d['rules']['nightFloor'] = 1
        s['shifts'] = [dict(id='j1', employeeId='e1', date='2026-09-07', start='23:00', end='06:30', type='jour', skills=[], breaks=[])]
        s['assignments'] = []
        codes = {e['rule'] for e in validate(d, s)['errors']}
        self.assertIn('NIGHT_FLOOR', codes)

    def test_jour_requires_night_eligibility(self):
        d, s = fixture()
        d['templates'].append(jour_mall())
        d['employees'][0]['night'] = False
        s['shifts'] = [dict(id='j1', employeeId='e1', date='2026-09-07', start='23:00', end='06:30', type='jour', skills=[], breaks=[])]
        s['assignments'] = []
        self.assertIn('NIGHT', {e['rule'] for e in validate(d, s)['errors']})

    def test_jour_does_not_count_toward_ssg(self):
        d, s = fixture()
        d['templates'].append(jour_mall())
        s['shifts'] = [
            dict(id='s1', employeeId='e1', date='2026-09-07', start='06:00', end='14:00', type='day', skills=['Omsorg'], breaks=[]),
            dict(id='j1', employeeId='e1', date='2026-09-07', start='23:00', end='06:30', type='jour', skills=[], breaks=[]),
        ]
        codes = {e['rule'] for e in validate(d, s)['errors']}
        self.assertNotIn('CONTRACT', codes)
        self.assertNotIn('WEEK_HOURS', codes)
        self.assertNotIn('REST', codes)

    def test_jour_over_48h_in_four_weeks_is_rejected(self):
        d, s = fixture()
        d['workplace']['end'] = '2026-10-04'
        d['templates'].append(jour_mall())
        s['shifts'] = [
            dict(id=f'j{i}', employeeId='e1', date=f'2026-09-{7 + i:02d}', start='23:00', end='06:30', type='jour', skills=[], breaks=[])
            for i in range(7)
        ]
        s['assignments'] = []
        self.assertIn('JOUR_4W', {e['rule'] for e in validate(d, s)['errors']})

    def test_jour_over_50h_in_calendar_month_is_rejected(self):
        d, s = fixture()
        d['workplace'].update(start='2026-09-01', end='2026-09-30')
        d['templates'].append(jour_mall())
        s['shifts'] = [
            dict(id=f'j{i}', employeeId='e1', date=f'2026-09-{i:02d}', start='23:00', end='06:30', type='jour', skills=[], breaks=[])
            for i in range(1, 8)
        ]
        s['assignments'] = []
        self.assertIn('JOUR_MONTH', {e['rule'] for e in validate(d, s)['errors']})

    def test_task_cannot_sit_on_sleeping_oncall(self):
        d, s = fixture()
        d['templates'].append(jour_mall())
        d['interventions'][0].update(start='23:30', latestEnd='00:30', minutes=60)
        s['shifts'] = [dict(id='j1', employeeId='e1', date='2026-09-07', start='23:00', end='06:30', type='jour', skills=[], breaks=[])]
        s['assignments'] = [dict(
            occurrenceId='t1@2026-09-07',
            employeeId='e1',
            start=instant('2026-09-07', '23:30'),
            end=instant('2026-09-08', '00:30'),
        )]
        self.assertIn('ON_DUTY', {e['rule'] for e in validate(d, s)['errors']})

    def test_jour_intervals_default_2300_0630(self):
        xs = list(jour_intervals('2026-09-07', '2026-09-07'))
        self.assertIn((instant('2026-09-07', '23:00'), instant('2026-09-08', '06:30')), xs)
        self.assertIn((instant('2026-09-06', '23:00'), instant('2026-09-07', '06:30')), xs)

    def test_jour_intervals_uses_rules_clock_and_weekdays(self):
        rules = dict(jour=dict(start='22:00', end='07:00', weekdays=[1]))
        xs = list(jour_intervals('2026-09-07', '2026-09-08', rules))
        self.assertIn((instant('2026-09-07', '22:00'), instant('2026-09-08', '07:00')), xs)
        self.assertNotIn(instant('2026-09-08', '22:00'), [a for a, _ in xs])

    def test_check_input_rejects_invalid_jour(self):
        d, _ = fixture()
        d['rules']['jour'] = dict(start='25:00', end='06:30', weekdays=[1, 2, 3, 4, 5, 6, 7])
        with self.assertRaises(ValueError):
            check_input(d)
        d['rules']['jour'] = dict(start='23:00', end='06:30', weekdays=[])
        with self.assertRaises(ValueError):
            check_input(d)

    def test_check_input_accepts_default_jour(self):
        d, _ = fixture()
        d['rules']['jour'] = dict(start='23:00', end='06:30', weekdays=[1, 2, 3, 4, 5, 6, 7])
        check_input(d)


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
class SovandeJourSolver(unittest.TestCase):
    def test_solver_covers_nights_with_jour_not_cost(self):
        d, _ = fixture()
        d = with_jour(d, extra=1)
        d['rules']['nightFloor'] = 0
        d['rules']['jourFloor'] = 1
        d['objectiveWeights'] = dict(continuitySek=0, spreadSekPerPermille=0)
        r = solve(d, 8)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        jour = [s for s in r['schedule']['shifts'] if s.get('type') == 'jour']
        self.assertGreaterEqual(len(jour), 1)
        br = r['schedule']['objectiveBreakdown']
        work = [s for s in r['schedule']['shifts'] if s.get('type') != 'jour']
        if not work:
            self.assertEqual(br['costOre'], 0)

    def test_solver_does_not_exceed_jour_cap(self):
        d, _ = fixture()
        d['workplace']['end'] = '2026-09-20'
        d = with_jour(d, extra=2)
        d['rules']['nightFloor'] = 0
        d['rules']['jourFloor'] = 1
        r = solve(d, 15)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertTrue(r['validation']['valid'])
        hours = defaultdict(float)
        for s in r['schedule']['shifts']:
            if s.get('type') != 'jour':
                continue
            a, b = span(s)
            hours[s['employeeId']] += (b - a) / 60
        for h in hours.values():
            self.assertLessEqual(h, 48.01)
