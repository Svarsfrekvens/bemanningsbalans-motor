import importlib.util
import unittest
from test_rules import fixture
from bb.solver import solve


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
class LexikografiskOptimering(unittest.TestCase):
    def tva_uppgifter(self):
        d, _ = fixture()
        d['rules']['nightFloor'] = 0
        d['interventions'] = [
            dict(id='t1', customerId='c1', name='Morgon', type='fixed', start='09:00',
                 latestEnd='10:00', minutes=60, doubleStaff=False, weekdays=[1],
                 date='2026-09-07', skills=['Omsorg']),
            dict(id='t2', customerId='c1', name='Eftermiddag', type='fixed', start='14:00',
                 latestEnd='15:00', minutes=60, doubleStaff=False, weekdays=[1],
                 date='2026-09-07', skills=['Omsorg']),
        ]
        d['templates'] = [
            dict(id='FM', name='Förmiddag', start='06:00', end='12:00', type='day', skills=['Omsorg'], breaks=[]),
            dict(id='HELA', name='Heldag', start='06:00', end='16:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        d['employees'] = [
            dict(id='billig', code='B', ssg=100, night=True, profiles=['FM'], hourlyCost=100, status='active', skills=['Omsorg']),
            dict(id='dyr', code='D', ssg=100, night=True, profiles=['HELA'], hourlyCost=400, status='active', skills=['Omsorg']),
        ]
        d['objectiveWeights'] = dict(continuitySek=0, spreadSekPerPermille=0, uncoveredSekPerMinute=0)
        return d

    def test_valjer_hogre_tackning_framfor_lagre_kostnad(self):
        d = self.tva_uppgifter()
        r = solve(d, 8)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        occ = {a['occurrenceId'] for a in r['schedule']['assignments']}
        self.assertIn('t1@2026-09-07', occ)
        self.assertIn('t2@2026-09-07', occ)
        self.assertEqual(r['schedule']['lexicographic']['uncoveredMinutes'], 0)

    def test_samma_tackning_valjer_lagre_kostnad(self):
        d, _ = fixture()
        d['rules']['nightFloor'] = 0
        d['employees'] = [
            dict(id='billig', code='B', ssg=100, night=True, profiles=['D'], hourlyCost=100, status='active', skills=['Omsorg']),
            dict(id='dyr', code='D', ssg=100, night=True, profiles=['D'], hourlyCost=400, status='active', skills=['Omsorg']),
        ]
        d['objectiveWeights'] = dict(continuitySek=0, spreadSekPerPermille=0)
        r = solve(d, 8)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        anstallda = {s['employeeId'] for s in r['schedule']['shifts']}
        self.assertEqual(anstallda, {'billig'})
        self.assertEqual(r['schedule']['lexicographic']['uncoveredMinutes'], 0)

    def test_samma_tackning_och_kostnad_kan_anvanda_kontinuitet(self):
        d, _ = fixture()
        d['rules']['nightFloor'] = 0
        d['customers'] = [
            dict(id='c1', code='Kund 1', active=True),
            dict(id='c2', code='Kund 2', active=True),
        ]
        d['interventions'] = [
            dict(id='t1', customerId='c1', name='Stöd', type='fixed', start='09:00',
                 latestEnd='10:00', minutes=60, doubleStaff=False, weekdays=[1],
                 date='2026-09-07', skills=['Omsorg']),
            dict(id='t2', customerId='c2', name='Stöd', type='fixed', start='10:00',
                 latestEnd='11:00', minutes=60, doubleStaff=False, weekdays=[1],
                 date='2026-09-07', skills=['Omsorg']),
        ]
        d['employees'] = [
            dict(id='e1', code='M01', ssg=100, night=True, profiles=['D'], hourlyCost=250, status='active', skills=['Omsorg']),
        ]
        d['objectiveWeights'] = dict(continuitySek=50, spreadSekPerPermille=0)
        r = solve(d, 8)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertEqual(len(r['schedule']['assignments']), 2)
        self.assertEqual({a['employeeId'] for a in r['schedule']['assignments']}, {'e1'})
