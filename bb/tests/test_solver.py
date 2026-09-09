import importlib.util
import unittest
from copy import deepcopy
from test_rules import fixture
from bb.validate import validate
from bb.solver import solve


@unittest.skipUnless(importlib.util.find_spec('ortools'),'OR-Tools saknas: solver-tester är INTE körda')
class SolverTests(unittest.TestCase):
    def test_real_solver_produces_valid_solution(self):
        d,_=fixture();r=solve(d,5)
        self.assertIn(r['schedule']['solverStatus'],['OPTIMAL','FEASIBLE']);self.assertTrue(validate(d,r['schedule'])['valid']);self.assertEqual(len(r['schedule']['assignments']),1);self.assertEqual(r['schedule']['uncovered'],[])
    def test_no_qualified_staff_leaves_need_uncovered(self):
        d,_=fixture();d['employees'][0]['skills']=[];r=solve(d,5)
        self.assertIn(r['schedule']['solverStatus'],['OPTIMAL','FEASIBLE']);self.assertEqual(r['schedule']['assignments'],[]);self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']),1);self.assertTrue(r['validation']['valid'])
    def test_double_staff_with_one_person_reports_half_uncovered(self):
        d,_=fixture();d['interventions'][0]['doubleStaff']=True;r=solve(d,5)
        self.assertIn(r['schedule']['solverStatus'],['OPTIMAL','FEASIBLE']);self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']),1);self.assertTrue(r['validation']['valid'])
    def test_two_distinct_staff_and_simultaneous_double(self):
        d,_=fixture();d['interventions'][0]['doubleStaff']=True;d['employees'].append({**d['employees'][0],'id':'e2','code':'M02'});r=solve(d,5);a=r['schedule']['assignments'];self.assertEqual(len({x['employeeId'] for x in a}),2);self.assertEqual(len({x['start'] for x in a}),1);self.assertTrue(r['validation']['valid']);self.assertEqual(r['schedule']['uncovered'],[])
    def test_absent_employee_cannot_be_used(self):
        d,_=fixture();d['absences']=[dict(id='a',employeeId='e1',start='2026-09-07',end='2026-09-13')];r=solve(d,5)
        self.assertEqual(r['schedule']['assignments'],[]);self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']),1)
    def test_rest_boundary_is_not_relaxed(self):
        d,s=fixture();d['boundaryShifts']=[{**s['shifts'][0],'id':'before','date':'2026-09-06','start':'13:00','end':'21:00'}];r=solve(d,5)
        self.assertEqual(r['schedule']['shifts'],[]);self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']),1)
    def test_fixed_schedule_input_is_unchanged(self):
        d,_=fixture();old=deepcopy(d);solve(d,5);self.assertEqual(d,old)
    def test_overlap_reports_one_uncovered_instead_of_breaking_rules(self):
        d,_=fixture();d['interventions'].append({**d['interventions'][0],'id':'t2'});r=solve(d,5)
        self.assertEqual(len(r['schedule']['assignments']),1);self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']),1);self.assertTrue(r['validation']['valid'])
    def test_flexible_tasks_can_be_sequenced(self):
        d,_=fixture();d['interventions'][0].update(type='flexible',latestEnd='11:00');d['interventions'].append({**d['interventions'][0],'id':'t2'});r=solve(d,5);self.assertIn(r['schedule']['solverStatus'],['OPTIMAL','FEASIBLE']);self.assertTrue(r['validation']['valid']);self.assertEqual(r['schedule']['uncovered'],[])
