"""Pure scalar parser/censor/cadence/anchor fixtures; no game/source edits."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,tempfile,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--production',action='store_true');options=parser.parse_args()
p=module('pathprof',ROOT/'work/profile-path-queries.py');checks=0
def check(ok):
 global checks;checks+=1;assert ok
def row():
 value={k:0 for k in p.COUNTERS};value.update(unit=1,pathType=0,origin='search',serial=8,thread=7,nodeGeneration=13,flags=4,startX=0,startY=0,goalX=1,goalY=0,queryStride=8,queryPhase=0,callStride=16,callPhase=0,startTick=10,endTick=20,sourceEpochStart=1,sourceEpochEnd=1,eventFlags=0,trackingSlots=128,trackingProbeLimit=16,repeatCoverage='observed_lower_bound_if_untracked_nonzero',qpcFrequency=1000000,queryAvailable=1,queryTicks=10000,semantics='inclusive_same_thread_wall_samples',repeatSemantics='bounded_plot_scene_actor_HP_opportunities_not_validated_cache_hits',overlap='nested_queries_and_PLAN_not_additive')
 return dict(category='PATH_SAMPLE',turn=252,player=3,raw_tick=20,tick=20,origin='synthetic',values=value)
r=row();check(p.decode(r)[1]==[]);r['values'].update(rawDangerCalls=32,trackedDangerCalls=32,repeatedPlotCalls=20,sameSceneHPRepeats=18,dangerSelected=2,dangerSamples=2,dangerTicks=2000,dangerMaxTicks=1100)
parsed,errors=p.decode(r);check(not errors and parsed['parts']['danger']['approximate_inclusive_ms']==32);check(parsed['repeat_known_complete'] and parsed['repeat_lower_bound']==20)
r['values'].update(untrackedDangerCalls=8,trackedDangerCalls=24);check(not p.decode(r)[0]['repeat_known_complete']);check(p.decode(r)[0]['repeat_lower_bound']==20)
r['values'].update(dangerSamples=0,dangerTicks=0,dangerMaxTicks=0);check(p.decode(r)[0]['parts']['danger']['unknown'] and p.decode(r)[0]['parts']['danger']['approximate_inclusive_ms'] is None)
for key,value in [('qpcFrequency',0),('rawDangerCalls',-1),('queryAvailable',True),('serial',1<<32),('queryPhase',8),('callStride',64),('trackingProbeLimit',128),('dangerSelected',1),('dangerSamples',3),('origin','legacy'),('trackedDangerCalls',19),('sameSceneHPRepeats',21),('queryTicks',1<<64)]:
 current=row();current['values'].update(r['values']);current['values'][key]=value;check(bool(p.decode(current)[1]))
current=row();current['raw_message']='unit=1 unit=2';check(bool(p.decode(current)[1]));current['raw_message']='[message truncated]';check(bool(p.decode(current)[1]))
current=row();current['values'].update(queryAvailable=0,queryTicks=0);check(p.decode(current)[0]['query_ms'] is None);check(p.analyze([current])['groups'][0]['query_ms_known'] is None)
current=row();del current['values']['dangerSamples'];check(bool(p.decode(current)[1]))
current=row();current['values']['origin']='verify';check(p.analyze([row(),current])['groups'][0]['query_kind']=='search' and len(p.analyze([row(),current])['groups'])==2)
check(p.analyze([row()],turns=[251])['retained_valid_rows']==0)
# Anchor patch shared by the CPU profiler excludes leading/following new rows.
stage=ROOT/'work/path-query-profile-staged';anchor_base=ROOT/'work' if options.production else stage;binding={}
for name in ('profile-turn-phases.py','profile-phase-cpu.py'):
 actual=(anchor_base/name).read_text(encoding='utf-8-sig');expected=(stage/name).read_text(encoding='utf-8-sig')
 assert actual==expected,'Actual entire anchor helper differs from stage: '+name
 binding[name]=hashlib.sha256(actual.encode()).hexdigest()
wall=module('staged_wall',anchor_base/'profile-turn-phases.py');cpu=module('staged_cpu',anchor_base/'profile-phase-cpu.py')
check('PATH_SAMPLE' in wall.TIMING_CATEGORIES and 'PATH_SAMPLE' in cpu.wall.TIMING_CATEGORIES)
def event(tick,turn,kind):return dict(raw_tick=tick,tick=tick,turn=turn,player=3,category=kind,values={},origin='synthetic')
events=[event(100,7,'PATH_SAMPLE'),event(110,7,'SUMMARY'),event(120,7,'PATH_SAMPLE'),event(200,8,'PATH_SAMPLE'),event(250,8,'SUMMARY')]
profile=wall.analyze(events,7);check(profile['native_round_window']['duration_ms']==140 and profile['native_round_window']['first_category']=='SUMMARY' and profile['native_round_window']['next_first_category']=='SUMMARY');check(profile['native_all_event_window']['duration_ms']==100);check(cpu.analyze(events,7)['window']['duration_ms']==140)
with tempfile.TemporaryDirectory(prefix='path-profile-') as temp:
 directory=Path(temp);wire='STACKDIAG|SESSION|run=expected segment=0\nSTACKDIAG|20|turn=252|player=3|PATH_SAMPLE|'+' '.join(f'{k}={v}' for k,v in row()['values'].items())+'\n';(directory/'a.log').write_text(wire);(directory/'copy.log').write_text(wire[:-3]);output=directory/'report.json'
 command=[sys.executable,'-B',str(ROOT/'work/profile-path-queries.py'),str(directory),'--run','expected','--output',str(output)];result=subprocess.run(command,capture_output=True,text=True);check(result.returncode==0);report=json.loads(output.read_text());check(report['retained_valid_rows']==1 and len(report['archive_quality']['duplicate_segment_files_ignored'])==1)
 (directory/'a.log').write_text(wire.replace('qpcFrequency=1000000','qpcFrequency=0'));(directory/'copy.log').unlink();result=subprocess.run(command,capture_output=True,text=True);check(result.returncode==2)
(ROOT/'work/path-query-parser-fixture-result.json').write_text(json.dumps(dict(checks=checks,failures=0,production_bound=options.production,anchor_source_sha256=binding,parser_source_sha256=hashlib.sha256((ROOT/'work/profile-path-queries.py').read_bytes()).hexdigest(),scope='actual scalar PATH_SAMPLE validation/cadence/censor/unknown/CLI canonical copies plus phase/CPU legacy anchor exclusion'),indent=2)+'\n');print(str(checks)+' parser/anchor checks passed.')
