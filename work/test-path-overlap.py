"""Small synthetic PATH/phase overlap fixtures; no native compile/game calls."""
import copy,importlib.util,json,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('path_overlap',root/'work/profile-path-overlap.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
checks=0
def check(name,yes):
 global checks
 checks+=1
 if not yes:raise AssertionError(name)
def record(tick,category,values=None,turn=7,player=3,origin='synthetic'):
 return dict(raw_tick=tick%p.wall.MOD,tick=tick,category=category,values=values or {},turn=turn,player=player,origin=origin)
def query(start=20,end=60,serial=8,thread=9,unit=1,kind='search',player=3,pathType=0,qpc=None):
 v={k:0 for k in p.paths.COUNTERS};v.update(unit=unit,pathType=pathType,origin=kind,serial=serial,thread=thread,nodeGeneration=13,flags=4,startX=0,startY=0,goalX=1,goalY=0,queryStride=8,queryPhase=0,callStride=16,callPhase=0,startTick=start%p.wall.MOD,endTick=end%p.wall.MOD,sourceEpochStart=1,sourceEpochEnd=1,eventFlags=0,trackingSlots=128,trackingProbeLimit=16,repeatCoverage='observed_lower_bound_if_untracked_nonzero',qpcFrequency=1000000,queryAvailable=1,queryTicks=qpc if qpc is not None else (end-start)*1000,semantics='inclusive_same_thread_wall_samples',repeatSemantics='bounded_plot_scene_actor_HP_opportunities_not_validated_cache_hits',overlap='nested_queries_and_PLAN_not_additive')
 v.update(rawDangerCalls=32,trackedDangerCalls=32,repeatedPlotCalls=20,sameSceneHPRepeats=18,dangerSelected=2,dangerSamples=2,dangerTicks=2000,dangerMaxTicks=1100)
 r=record(end,'PATH_SAMPLE',v,player=player,origin=f'query-{player}-{thread}-{serial}');r['raw_message']=' '.join(f'{k}={x}' for k,x in v.items());return r
def phase(start,end,name,thread=9,player=3,turn=7):
 return record(end,'TURN_PHASE',dict(startTick=start%p.wall.MOD,endTick=end%p.wall.MOD,elapsedMs=end-start,thread=thread,phase=name,semantics='inclusive'),turn,player,origin=name)
q=query();rows=[q,record(65,'PLAN_PERF',dict(target='1:1',finalizeMs=0,searchMs=50)),record(66,'PLAN',dict(target='1:1',milliseconds=50)),phase(0,100,'unit_ai_update'),phase(10,80,'tactical_ai'),phase(15,75,'stacking_offensive_moves'),record(200,'SUMMARY',turn=8)]
r=p.analyze(rows);a=r['whole_selection'];one=r['queries'][0]
check('exact player thread phases',len(one['phase_associations'])==3)
check('inclusive phase labels union once',a['coarse_phase_overlap_wall_union_ms']==40)
check('each nested label remains nonadditive',sum(x['wall_union_ms'] for x in a['coarse_overlap_by_phase'])==120)
check('PLAN candidate interval overlap',a['coarse_estimated_PLAN_candidate_overlap_wall_union_ms']==40)
check('PLAN thread explicitly unknown',one['PLAN_associations'][0]['qualification']=='player_time_candidate_thread_unknown_approximate_PLAN')
check('phase PLAN partition not additive',a['coarse_nonadditive_partition_ms']==dict(phase_and_estimated_PLAN=40,phase_only=0,estimated_PLAN_only=0,outside_recorded_phase_or_estimated_PLAN=0))
check('real selected QPC duration retained',a['query_qpc_ms_known']==40)
check('opportunities kept as observed counters',a['counters']['repeatedPlotCalls']==20 and a['counters']['sameSceneHPRepeats']==18)
extra=query(60,70,serial=16,kind='verify');r=p.analyze(rows+[extra]);a=r['whole_selection']
check('verify and search distinct groups',len(r['turn_player_query_kind'])==2)
check('adjacent query envelopes union',a['coarse_query_envelope_wall_union_ms']==50)
check('partial PLAN candidate clip',a['coarse_estimated_PLAN_candidate_overlap_wall_union_ms']==45)
check('partition real remainder',a['coarse_nonadditive_partition_ms']['phase_only']==5)
foreign=query(20,30,serial=24,thread=10);r=p.analyze(rows+[foreign]);f=r['queries'][-1]
check('foreign thread no phase attribution',not f['phase_associations'])
check('foreign thread PLAN only candidate',bool(f['PLAN_associations']))
other=query(100,150,serial=32,unit=2,player=4,pathType=2);r=p.analyze(rows+[other])
check('different player not attributed existing phase',not r['queries'][-1]['phase_associations'])
check('unit player type grouping explicit',len(r['turn_player_unit_type_query_kind'])==2 and r['turn_player_unit_type_query_kind'][1]['pathType']==2)
check('outside envelope retained',r['whole_selection']['coarse_nonadditive_partition_ms']['outside_recorded_phase_or_estimated_PLAN']==50)
point=query(55,55,serial=40,qpc=5000);r=p.analyze(rows+[point]);z=r['queries'][-1]
check('nonzero QPC zero coarse width',z['query_ms']==5 and z['interval']==(55,55))
check('point lists candidates no duration',len(z['phase_associations'])==3 and all(x['overlap_interval'] is None for x in z['phase_associations']))
check('point does not inflate coverage',r['whole_selection']['coarse_phase_overlap_wall_union_ms']==40 and r['whole_selection']['zero_width_query_envelopes']==1)
wrap=p.wall.MOD;qw=query(wrap-10,wrap+4,serial=48);rw=p.analyze([qw,phase(wrap-20,wrap+8,'wrapped')])
check('DWORD wrap correct interval',rw['queries'][0]['interval']==(wrap-10,wrap+4))
check('wrapped phase overlap',rw['whole_selection']['coarse_phase_overlap_wall_union_ms']==14)
bad=query();bad['values']['endTick']=90;rb=p.analyze([bad]);check('future endpoint rejects association',rb['queries'][0]['interval'] is None and rb['queries'][0]['interval_error']=='end_after_record_tick')
baseline=p.paths.analyze(rows);r=p.analyze(rows,base_report=baseline);check('existing parser report accepted',r['whole_selection']['retained_sampled_queries']==1)
partial=copy.deepcopy(baseline);partial['queries']=[];r=p.analyze(rows,base_report=partial);check('partial existing report coverage explicit',r['coverage']['native_query_identities_without_matched_report']==1 and bool(r['warnings']))
stale=copy.deepcopy(baseline);stale['queries'][0]['counters']['repeatedPlotCalls']+=1;r=p.analyze(rows,base_report=stale);check('stale report counters refuse join',r['invalid_associations'] and not r['queries'])
r=p.analyze(rows+[copy.deepcopy(q)]);check('duplicate query identity refuses both',len(r['invalid_associations'])==2 and not r['queries'])
wrong=copy.deepcopy(rows);wrong[3]['values']['thread']=10;wrong[4]['values']['thread']=10;wrong[5]['values']['thread']=10;check('all wrong phase threads no overlap',not p.analyze(wrong)['queries'][0]['phase_associations'])
adjacent=rows+[phase(20,60,'adjacent_source_turn',turn=8)];r=p.analyze(adjacent);check('adjacent sourceTurn provenance retained',any(x['sourceTurn']==8 for x in r['queries'][0]['phase_associations']))
filtered=p.analyze(rows,turns=[6]);check('missing sampled turn unknown',not filtered['queries'] and bool(filtered['warnings']))
check('no saved time/scaled count fields',not any('saved' in k or 'scaled' in k for k in a))
with tempfile.TemporaryDirectory(prefix='civ-path-overlap-') as temp:
 d=Path(temp);body='STACKDIAG|SESSION|run=exact-path segment=0\n'
 for row in sorted(rows,key=lambda x:x['tick']):
  body+=f"STACKDIAG|{row['raw_tick']}|turn={row['turn']}|player={row['player']}|{row['category']}|"+' '.join(f'{k}={v}' for k,v in row['values'].items())+'\n'
 (d/'full.log').write_text(body);(d/'short-copy.log').write_text(body[:-10])
 loaded,quality=p.load(d,'exact-path');check('canonical prefix copy once',len(loaded)==len(rows) and len(quality['duplicate_segment_files_ignored'])==1)
 base=p.paths.analyze(loaded,quality);base['run']='exact-path';report=d/'base.json';report.write_text(json.dumps(base));target=d/'overlap.json'
 cmd=[sys.executable,'-B',str(root/'work/profile-path-overlap.py'),str(d),'--run','exact-path','--path-report',str(report),'--output',str(target)]
 run=subprocess.run(cmd,capture_output=True,text=True);check('CLI existing report succeeds',run.returncode==0 and target.exists())
 base['run']='another-run';report.write_text(json.dumps(base));run=subprocess.run(cmd,capture_output=True,text=True);check('CLI wrong run refuses',run.returncode==2)
result=dict(checks=checks,failures=0,scope='sampled PATH report/native identity, coarse same-thread phase and estimated PLAN candidate overlap union, zero-width/wrap/partial/grouping/CLI; no saved-time/native cache-hit claim')
(root/'work/path-overlap-fixture-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
