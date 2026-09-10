import importlib.util
import json
import os
import unittest
from copy import deepcopy
from test_rules import fixture
from bb.domain import check_input, occurrences
from bb.solver import solve


def relationer(data, schedule):
    kund = {}
    for o in occurrences(data):
        kund[o['id']] = o['task']['customerId']
    return {(kund.get(a['occurrenceId']), a['employeeId']) for a in schedule['assignments'] if kund.get(a['occurrenceId'])}


def vecka_galaxen_lik():
    """Sju dagar, flera kunder och medarbetare – samma struktur som en Galaxen-vecka."""
    d, _ = fixture()
    d['workplace'] = dict(name='Galaxen', start='2026-08-03', end='2026-08-09', timezone='Europe/Stockholm')
    d['customers'] = [
        dict(id='c1', code='Kund 1', active=True),
        dict(id='c2', code='Kund 2', active=True),
        dict(id='c3', code='Kund 3', active=True),
    ]
    d['employees'] = [
        dict(id='e1', code='M01', ssg=100, night=True, profiles=['D'], hourlyCost=None, status='active', skills=['Omsorg']),
        dict(id='e2', code='M02', ssg=100, night=True, profiles=['D'], hourlyCost=None, status='active', skills=['Omsorg']),
        dict(id='e3', code='M03', ssg=100, night=True, profiles=['D'], hourlyCost=None, status='active', skills=['Omsorg']),
    ]
    dagar = ['2026-08-03', '2026-08-04', '2026-08-05', '2026-08-06', '2026-08-07', '2026-08-08', '2026-08-09']
    veckodag = [1, 2, 3, 4, 5, 6, 7]
    interventions = []
    n = 0
    for i, dag in enumerate(dagar):
        for cid in ('c1', 'c2', 'c3'):
            n += 1
            interventions.append(dict(
                id=f't{n}', customerId=cid, name='Stöd', type='fixed', start='09:00',
                latestEnd='10:00', minutes=60, doubleStaff=False, weekdays=[veckodag[i]],
                date=dag, skills=['Omsorg'],
            ))
    d['interventions'] = interventions
    d['current'] = None
    d['proposal'] = None
    d['outcomes'] = []
    return d


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
class ObjectiveWeights(unittest.TestCase):
    def test_zero_continuity_makes_objective_equal_cost(self):
        d, _ = fixture()
        d['objectiveWeights'] = dict(continuitySek=0, spreadSekPerPermille=0)
        r = solve(d, 5)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        br = r['schedule']['objectiveBreakdown']
        self.assertEqual(br['continuityOre'], 0)
        self.assertEqual(br['spreadOre'], 0)
        self.assertEqual(r['schedule']['objective'], br['costOre'])

    def test_weight_out_of_range_is_rejected(self):
        d, _ = fixture()
        d['objectiveWeights'] = dict(continuitySek=10001, spreadSekPerPermille=2.5)
        with self.assertRaises(ValueError):
            check_input(d)

    def test_tenfold_continuity_reduces_relations_on_galaxen_week(self):
        path = os.path.join(os.path.dirname(__file__), 'galaxen_7d.json')
        base = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else vecka_galaxen_lik()
        low = deepcopy(base)
        high = deepcopy(base)
        low['objectiveWeights'] = dict(continuitySek=50, spreadSekPerPermille=2.5)
        high['objectiveWeights'] = dict(continuitySek=500, spreadSekPerPermille=2.5)
        a = solve(low, 20)
        b = solve(high, 20)
        self.assertIn(a['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertIn(b['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertLessEqual(len(relationer(high, b['schedule'])), len(relationer(low, a['schedule'])))
