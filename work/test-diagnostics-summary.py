"""Offline schema regression fixtures; no live logs or game state required."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('summary',Path(__file__).with_name('summarize-stacking-diagnostics.py'))
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def header(run='Stacking-test-p1-r1',segment=0,schema=1):
 return f'STACKDIAG|SESSION|schema={schema} run={run} segment={segment} build=5.4.6-test level=2 configFNV=00000123\n'
def row(category,message,turn=10,player=1,tick=123):
 return f'STACKDIAG|{tick}|turn={turn}|player={player}|{category}|{message}\n'
class ParserTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def write(self,name,body):
  p=self.root/name;p.write_text(body,encoding='utf-8');return p
 def parse(self):return mod.summarize(mod.discover(self.root))
 def test_metrics_counts_and_wrapping_tick(self):
  self.write('Stacking-test-00.log',header()+row('MEMORY','committedKB=100 reservedKB=20 freeKB=80 largestFreeKB=30',player=-1,tick=4294967290)+row('MEMORY','committedKB=120 reservedKB=10 freeKB=70 largestFreeKB=12',turn=11,player=-1,tick=5)+row('SUMMARY','units=12 countedCombat=8',turn=11)+row('SUMMARY','units=9',turn=11,player=2))
  r=self.parse()['runs'][0];self.assertEqual(r['record_count'],4);self.assertEqual(r['counts_by_category'],{'MEMORY':2,'SUMMARY':2})
  self.assertEqual(r['counts_by_turn']['11']['players'],{'-1':1,'1':1,'2':1});self.assertEqual(r['counts_by_player']['1']['total'],1)
  self.assertEqual(r['memory']['peaks_KB']['committedPlusReservedKB']['value'],130)
  self.assertEqual(r['memory']['minimum_free_KB']['largestFreeKB']['value'],12)
  self.assertEqual(r['files'][0]['header']['configFNV'],'00000123');self.assertEqual(r['turn_rewinds'],[])
 def test_combat_role_duplicates_and_incomplete_brackets(self):
  text=header()+row('COMBAT_BEGIN','combat=1 members=1')
  text+=row('COMBAT_MEMBER','combat=1 owner=1 id=4 role=attacker')+row('COMBAT_MEMBER','combat=1 owner=2 id=7 role=defender')+row('COMBAT_MEMBER','combat=1 owner=2 id=7 role=secondary_or_garrison')
  text+=row('COMBAT_CITY_BEFORE','combat=1 owner=2 id=20 damage=100')+row('COMBAT_AFTER','combat=1 owner=1 id=4 present=1 delayedDeath=0 hpBefore=100 hpAfter=70')+row('COMBAT_AFTER','combat=1 owner=2 id=7 present=0 delayedDeath=0 hpBefore=1 hpAfter=0')
  text+=row('COMBAT_CITY_AFTER','combat=1 owner=1 id=21 damage=50')+row('COMBAT_END','combat=1')+row('COMBAT_BEGIN','combat=2')
  self.write('Stacking-combat-00.log',text);c=self.parse()['runs'][0]['combat'];e=c['events'][0]
  self.assertEqual(c['counts']['COMBAT_MEMBER'],3);self.assertEqual(c['counts']['COMBAT_AFTER'],2)
  self.assertEqual(e['unique_units_before'],2);self.assertTrue(e['unit_identity_sets_match']);self.assertEqual(e['after_absent_records'],1)
  self.assertEqual(c['bracketed_once'],1);self.assertEqual(c['unbracketed_or_duplicate_serials'],[2]);self.assertEqual(c['unit_identity_mismatch_serials'],[])
 def test_rolling_header_order_gaps_and_lost_prefix(self):
  self.write('Stacking-roll-02.log',header(segment=10)+row('SUMMARY','units=10',turn=12))
  self.write('Stacking-roll-00.log',header(segment=8)+row('SUMMARY','units=8',turn=10))
  r=self.parse()['runs'][0];self.assertEqual(r['retained_segment_numbers'],[8,10]);self.assertEqual(r['missing_segment_ranges'],[[9,9]]);self.assertTrue(r['earlier_segments_absent']);self.assertEqual(r['turn_rewinds'],[])
 def test_duplicate_segments_ignored_and_conflicts_warned(self):
  text=header()+row('SUMMARY','units=1')
  self.write('Stacking-a.log',text);self.write('Stacking-b.log',text)
  self.assertEqual(self.parse()['runs'][0]['record_count'],1)
  self.write('Stacking-b.log',header()+row('SUMMARY','units=2'));r=self.parse()['runs'][0]
  self.assertEqual(r['record_count'],2);self.assertTrue(any('Conflicting' in x for x in r['warnings']))
 def test_long_plan_truncation_malformed_and_rewind(self):
  self.write('Stacking-records.log',header()+row('LONG_PLAN','generation=200 length=256 capacity=312 unit=9 type=1 movesBefore=60 movesAfter=60')+row('TRUNCATED','per-turn diagnostic row budget reached; gameplay unaffected')+row('PLAN_ASSIGN','unit=9 [message truncated]')+'bad diagnostic row\n'+row('LEVEL','summary',turn=2))
  r=self.parse()['runs'][0];self.assertEqual(r['long_plans'][0]['fields']['length'],256);self.assertEqual(len(r['row_budget_truncations']),1);self.assertEqual(len(r['message_truncations']),1)
  self.assertEqual(r['malformed_record_count'],1);self.assertEqual(len(r['turn_rewinds']),1)
 def test_partial_final_line_is_excluded(self):
  self.write('Stacking-partial.log',header()+row('SUMMARY','units=10')+row('MEMORY','committedKB=900')[:-1])
  r=self.parse()['runs'][0];self.assertEqual(r['record_count'],1);self.assertEqual(r['memory']['sample_count'],0);self.assertTrue(any('Unterminated' in w for w in r['warnings']))
 def test_run_isolation(self):
  self.write('Stacking-one.log',header(run='run-one')+row('COMBAT_BEGIN','combat=1'))
  self.write('Stacking-two.log',header(run='run-two')+row('COMBAT_END','combat=1'))
  result=self.parse();self.assertEqual(len(result['runs']),2)
  for r in result['runs']:self.assertEqual(r['combat']['bracketed_once'],0)
 def test_unknown_schema_and_locator(self):
  self.write('StackingDiagnostics-path.log','')
  self.write('Stacking-future.log',header(schema=2)+row('SUMMARY','units=10'))
  r=self.parse();self.assertEqual(len(r['ignored_files_without_valid_session_header']),1);self.assertEqual(r['runs'][0]['record_count'],0);self.assertTrue(any('Unsupported' in x for x in r['runs'][0]['warnings']))
 def test_output_cannot_overwrite_input_log(self):
  p=self.write('Stacking-protected.log',header()+row('SUMMARY','units=1'));original=p.read_bytes()
  with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as c:mod.main([str(self.root),'--output',str(p)])
  self.assertEqual(c.exception.code,2);self.assertEqual(p.read_bytes(),original)
 def test_full_build_label_and_configuration_provenance(self):
  text=header().replace('build=5.4.6-test level=', 'build=Release-093917 Clean level=')+row('CONFIG','fnv1a=00000123 map=128x80 effectiveLevel=2')
  self.write('Stacking-build.log',text);r=self.parse()['runs'][0]
  self.assertEqual(r['files'][0]['header']['build'],'Release-093917 Clean')
  self.assertIn('Clean level=',r['files'][0]['raw_session_header'])
  self.assertEqual(r['configuration_records'][0]['fields']['fnv1a'],'00000123')
 def test_output_cannot_overwrite_hardlinked_input(self):
  p=self.write('Stacking-link.log',header()+row('SUMMARY','units=1'));target=self.root/'looks-safe.json';original=p.read_bytes()
  os.link(p,target)
  with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as c:mod.main([str(self.root),'--output',str(target)])
  self.assertEqual(c.exception.code,2);self.assertEqual(p.read_bytes(),original)
 def test_duplicate_after_identity_is_explicit(self):
  self.write('Stacking-duplicate-after.log',header()+row('COMBAT_BEGIN','combat=1')+row('COMBAT_MEMBER','combat=1 owner=1 id=4')+row('COMBAT_AFTER','combat=1 owner=1 id=4 present=1')*2+row('COMBAT_END','combat=1'))
  c=self.parse()['runs'][0]['combat'];self.assertEqual(c['duplicate_after_identity_serials'],[1]);self.assertEqual(len(c['events'][0]['duplicate_after_identities']),1)
 def test_stdout_json_and_explicit_output(self):
  self.write('Stacking-normal.log',header()+row('SUMMARY','units=1'))
  out=io.StringIO()
  with redirect_stdout(out):self.assertEqual(mod.main([str(self.root)]),0)
  self.assertIn('"summary_schema": 1',out.getvalue());self.assertEqual(len(list(self.root.iterdir())),1)
  target=self.root/'summary.json'
  with redirect_stdout(io.StringIO()):self.assertEqual(mod.main([str(self.root),'--output',str(target)]),0)
  self.assertTrue(target.is_file())
 def test_military_outcomes_are_movements_not_attempts(self):
  text=header()+row('REINFORCEMENT','unit=4 from=1 after=2 goal=9 status=moving')+row('REINFORCEMENT','unit=4 from=2 after=8 goal=9 status=arrived',turn=11)
  text+=row('REINFORCEMENT','unit=5 reason=unsafe_endpoint')+row('REINFORCEMENT','unit=6 status=no_progress')+row('REINFORCEMENT','unit=7 status=removed_during_move')
  text+=row('GARRISON_ASSIGN','city=2 unit=5 from=2 after=2 present=1')+row('GARRISON_ASSIGN','city=2 unit=6 from=3 after=2 present=1')+row('GARRISON_ASSIGN','city=2 unit=7 from=3 after=-1 present=0')
  self.write('Stacking-military.log',text);p=self.parse()['runs'][0]['military']['players']['1']
  self.assertEqual(p['reinforcement_units'],[4]);self.assertEqual(p['arriving_units'],[4]);self.assertEqual(p['reinforcement_outcomes']['no_progress'],1)
  self.assertEqual(p['garrison_outcomes'],{'absent_after_order':1,'moved':1,'unchanged_position':1})
 def test_military_city_and_operation_player_identity(self):
  text=header()+row('CITY_DEFENSE','city=2 needStrength=0')+row('CITY_DEFENSE','city=2 needStrength=99',player=2)
  text+=row('CITY_DEFENSE','city=2 needStrength=20',turn=11)+row('OPERATION_ASSEMBLY','operation=6 stageAge=15 idle=12 recover=1')
  text+=row('ASSEMBLY_STALL','army=6 unit=4 action=repath')+row('ASSEMBLY_STALL','army=6 unit=4 action=release')
  text+=row('OP_RECRUIT_FILTER','unit=4 reason=failed_assignment_cooldown')+row('OPERATION_READINESS','operation=8 ready=0')+row('OPERATION_READINESS','operation=8 ready=1')
  text+=row('DECISION_SUMMARY','phase=after_first_unit_AI_pass combat=40 inCities=6')+row('UNIT_DECISION','unit=4 unassigned=1')
  self.write('Stacking-military.log',text);players=self.parse()['runs'][0]['military']['players'];p=players['1']
  self.assertEqual(p['latest_city_defense']['2']['fields']['needStrength'],20);self.assertEqual(players['2']['latest_city_defense']['2']['fields']['needStrength'],99)
  self.assertEqual(p['maximum_assembly_idle'],12);self.assertEqual(p['maximum_assembly_age'],15);self.assertEqual(p['assembly_actions'],{'operation_recovery':1,'release':1,'repath':1})
  self.assertEqual(p['readiness_outcomes'],{'not_ready':1,'ready':1});self.assertEqual(p['recruitment_reasons']['failed_assignment_cooldown'],1)
  self.assertEqual(len(p['decision_samples']),1);self.assertEqual(p['unit_decision_samples'],1)
 def test_old_logs_have_no_invented_military_observations(self):
  self.write('Stacking-old.log',header()+row('SUMMARY','units=12'))
  m=self.parse()['runs'][0]['military'];self.assertEqual(m['players'],{});self.assertIn('not final end-turn',m['interpretation'])
 def test_offensive_support_outcomes(self):
  text=header()+row('OFFENSIVE_SUPPORT','unit=4 target=20 action=travelling')+row('OFFENSIVE_SUPPORT','unit=4 target=20 action=front_arrival')
  text+=row('OFFENSIVE_SUPPORT','unit=4 operation=8 action=joined_formation')+row('OFFENSIVE_SUPPORT','unit=5 target=20 action=release_stale')
  text+=row('CAPTURE_PLAN','target=20 unit=-1 known=0')+row('CAPTURE_PLAN','target=20 unit=4 known=1')+row('CAPTURE_PLAN','target=20 unit=-1 known=1')
  text+=row('OPERATION_ROUTE','operation=8 action=cooldown')+row('OPERATION_ROUTE','operation=9 repaired=1')
  text+=row('OPERATION_PROGRESS','operation=8 idle=12')+row('WAR_READINESS','operation=8 ready=0')+row('SIEGE_REASSESS','target=20 action=skip_futile_city_fire')
  self.write('Stacking-offensive.log',text);p=self.parse()['runs'][0]['military']['players']['1']
  self.assertEqual(p['formation_join_units'],[4]);self.assertEqual(p['offensive_support_units'],[4,5])
  self.assertEqual(p['offensive_support_actions'],{'travelling':1,'front_arrival':1,'joined_formation':1,'release_stale':1})
  self.assertEqual(p['capture_plan_outcomes'],{'unknown_budget':1,'viable':1,'missing':1})
  self.assertEqual(p['route_actions'],{'cooldown':1,'repaired':1});self.assertEqual(p['maximum_march_idle'],12)
  self.assertEqual(p['war_readiness_outcomes'],{'not_ready':1})
if __name__=='__main__':unittest.main(verbosity=2)
