"""Read-only native PATH_SAMPLE analysis; opportunities are not cache hits."""
from __future__ import annotations
import argparse,importlib.util,json,math,re
from collections import Counter,defaultdict
from pathlib import Path
spec=importlib.util.spec_from_file_location('wall',Path(__file__).with_name('profile-turn-phases.py'));wall=importlib.util.module_from_spec(spec);spec.loader.exec_module(wall)
U32=(1<<32)-1;U64=(1<<64)-1
COUNTERS=('qpcReads','clockFailures','queryTicks','nestedQueries','nodeCacheHits','nodeCacheBuilds','rawDangerCalls','trackedDangerCalls','untrackedDangerCalls','repeatedPlotCalls','sameSceneHPRepeats','dirtyDangerCalls','actorMismatches','dangerSelected','dangerSamples','dangerTicks','dangerMaxTicks','terrainCalls','terrainSelected','terrainSamples','terrainTicks','terrainMaxTicks')
METADATA=('turnRowLimit','turnRowOrdinal','capAfterThisRow','previousCapTurn','previousCappedSelectedQueries','rowCoverage','unit','pathType','origin','serial','thread','nodeGeneration','flags','startX','startY','goalX','goalY','queryStride','queryPhase','callStride','callPhase','startTick','endTick','sourceEpochStart','sourceEpochEnd','eventFlags','trackingSlots','trackingProbeLimit','repeatCoverage','qpcFrequency','queryAvailable','semantics','repeatSemantics','overlap')
def decode(row):
 value=row['values'];errors=[]
 wire=row.get('raw_message','');duplicate=[k for k,v in Counter(k for k,v in wall.FIELD.findall(wire)).items() if v>1 and k in COUNTERS+METADATA]
 if duplicate:errors.append('duplicate_fields:'+','.join(sorted(duplicate)))
 if '[message truncated]' in wire:errors.append('truncated_message')
 for key in COUNTERS:
  if type(value.get(key)) is not int or not 0<=value[key]<=U64:errors.append(key+':invalid_u64')
 for key in ('serial','thread','nodeGeneration','flags','startTick','endTick'):
  if type(value.get(key)) is not int or not 0<=value[key]<=U32:errors.append(key+':invalid_u32')
 for key in ('unit','pathType','startX','startY','goalX','goalY','sourceEpochStart','sourceEpochEnd'):
  if type(value.get(key)) is not int or not -(1<<31)<=value[key]<(1<<31):errors.append(key+':invalid_i32')
 for key in ('origin','repeatCoverage','semantics','repeatSemantics','overlap'):
  if not isinstance(value.get(key),str):errors.append(key+':missing_text')
 if value.get('origin') not in ('search','verify'):errors.append('origin:unknown')
 if value.get('semantics')!='inclusive_same_thread_wall_samples':errors.append('unsupported_semantics')
 if value.get('queryStride') not in (8,128):errors.append('queryStride:unsupported')
 for key,expected in (('callStride',16),('trackingSlots',128),('trackingProbeLimit',16)):
  if value.get(key)!=expected:errors.append(key+':unsupported')
 for key,bound in (('queryPhase',value.get('queryStride',0) if type(value.get('queryStride')) is int else 0),('callPhase',16),('eventFlags',64)):
  if type(value.get(key)) is not int or not 0<=value[key]<bound:errors.append(key+':invalid')
 if value.get('queryStride')==128:
  for key,bound in (('turnRowLimit',128),):
   if value.get(key)!=bound:errors.append(key+':invalid')
  if type(value.get('turnRowOrdinal')) is not int or not 1<=value['turnRowOrdinal']<=128:errors.append('turnRowOrdinal:invalid')
  if type(value.get('capAfterThisRow')) is not int or value['capAfterThisRow']!=int(value.get('turnRowOrdinal')==128):errors.append('capAfterThisRow:invalid')
  if type(value.get('previousCapTurn')) is not int or not -(1<<31)<=value['previousCapTurn']<(1<<31):errors.append('previousCapTurn:invalid')
  if type(value.get('previousCappedSelectedQueries')) is not int or not 0<=value['previousCappedSelectedQueries']<=U64:errors.append('previousCappedSelectedQueries:invalid')
  if value.get('rowCoverage')!='earliest_completed_selected_queries_after_cap_later_unknown':errors.append('rowCoverage:unsupported')
 if value.get('queryAvailable') not in (0,1) or type(value.get('queryAvailable')) is not int:errors.append('queryAvailable:invalid')
 if type(value.get('qpcFrequency')) is not int or not 0<value['qpcFrequency']<=U64:errors.append('frequency:invalid')
 if errors:return None,errors
 if (value['serial']+value['queryPhase'])%value['queryStride']:errors.append('query_not_on_reported_cadence')
 if value['trackedDangerCalls']+value['untrackedDangerCalls']+value['actorMismatches']!=value['rawDangerCalls']:errors.append('danger_accounting_mismatch')
 if not 0<=value['sameSceneHPRepeats']<=value['repeatedPlotCalls']<=value['trackedDangerCalls']<=value['rawDangerCalls']:errors.append('repeat_count_mismatch')
 if value['dirtyDangerCalls']>value['trackedDangerCalls']+value['untrackedDangerCalls']:errors.append('dirty_count_mismatch')
 if not value['queryAvailable'] and value['queryTicks']:errors.append('unavailable_query_duration_nonzero')
 part_rows={}
 for index,name in enumerate(('danger','terrain')):
  calls=value['rawDangerCalls' if name=='danger' else 'terrainCalls'];selected=value[name+'Selected'];samples=value[name+'Samples'];ticks=value[name+'Ticks'];maximum=value[name+'MaxTicks']
  expected=(calls+((value['callPhase']+index*7)&15))//16
  if selected!=expected or not 0<=samples<=selected<=calls:errors.append(name+':cadence_counts_mismatch')
  if maximum>ticks or not samples and (ticks or maximum):errors.append(name+':sample_tick_mismatch')
  sampled_ms=ticks*1000/value['qpcFrequency'] if samples else None
  part_rows[name]=dict(calls=calls,selected=selected,samples=samples,sampled_ms=sampled_ms,maximum_sample_ms=maximum*1000/value['qpcFrequency'] if samples else None,approximate_inclusive_ms=sampled_ms*calls/samples if samples else None,low_sample=samples<32,unknown=bool(calls and not samples))
 if errors:return None,errors
 return dict(query_stride=value['queryStride'],row_cap={k:value[k] for k in ('turnRowLimit','turnRowOrdinal','capAfterThisRow','previousCapTurn','previousCappedSelectedQueries','rowCoverage') if k in value},turn=row['turn'],player=row['player'],origin=row.get('origin'),query_kind=value['origin'],unit=value['unit'],pathType=value['pathType'],flags=value['flags'],serial=value['serial'],thread=value['thread'],nodeGeneration=value['nodeGeneration'],start=[value['startX'],value['startY']],goal=[value['goalX'],value['goalY']],eventFlags=value['eventFlags'],scene_changed=value['sourceEpochStart']!=value['sourceEpochEnd'],query_ms=value['queryTicks']*1000/value['qpcFrequency'] if value['queryAvailable'] else None,parts=part_rows,counters={k:value[k] for k in COUNTERS},repeat_known_complete=value['untrackedDangerCalls']==0 and value['actorMismatches']==0,repeat_lower_bound=value['repeatedPlotCalls'],same_scene_HP_repeat_lower_bound=value['sameSceneHPRepeats']),[]
NOTES=[
 'Stride128 rows are capped at128 earliest completed selected queries per native-run turn across threads. Reaching the cap biases coverage toward earlier work. Later selected query counts remain unknown until a following-turn row reports previousCappedSelectedQueries; no query timings are extrapolated past the cap.',
 'Only retained systematic sampled queries are analyzed. Query/part samples can alias workload; no extrapolated complete-turn sum or saved-time claim.',
 'Part wall samples include diagnostic timing overhead. Inclusive parent/nested/PLAN time overlaps and must not be added as CPU or disjoint turn costs.',
 'Plot/scene/actor/HP repeats are opportunities, not validated cache hits. Source/hazard/promotion/city/HP semantics still need a memo proof; eventFlags do not exclude legacy loading listeners.',
 'Bounded tracking with16 probes may censor repeats before128 distinct slots are used. Untracked/mismatched queries have observed lower bounds; unseen repeats remain unknown, not zero.',
 'Zero successful samples for nonzero calls means unknown timing. Few samples and clock failures limit estimated cost rankings.',
 'VerifyPath is a separate live-world validation context; do not reuse normal-search cached node data or raw danger there.',
]
def analyze(records,quality=None,turns=None):
 decoded=[];invalid=[]
 for record in records:
  if record['category']!='PATH_SAMPLE' or turns is not None and record['turn'] not in turns:continue
  row,errors=decode(record)
  if errors:invalid.append(dict(origin=record.get('origin'),errors=errors))
  else:decoded.append(row)
 groups=defaultdict(list)
 for row in decoded:groups[(row['turn'],row['player'],row['query_kind'])].append(row)
 summaries=[]
 for (turn,player,kind),rows in sorted(groups.items()):
  parts={}
  for name in ('danger','terrain'):
   known=[r['parts'][name] for r in rows if r['parts'][name]['samples']]
   parts[name]=dict(calls=sum(r['parts'][name]['calls'] for r in rows),successful_samples=sum(r['parts'][name]['samples'] for r in rows),unknown_query_timings=sum(r['parts'][name]['unknown'] for r in rows),sampled_ms=sum(p['sampled_ms'] for p in known) if known else None,known_approximate_inclusive_ms=sum(p['approximate_inclusive_ms'] for p in known) if known else None,maximum_sample_ms=max((p['maximum_sample_ms'] for p in known),default=None))
  known=[r['query_ms'] for r in rows if r['query_ms'] is not None]
  summaries.append(dict(turn=turn,player=player,query_kind=kind,retained_sampled_queries=len(rows),query_ms_known=sum(known) if known else None,query_ms_unknown=sum(r['query_ms'] is None for r in rows),parts=parts,counters={k:sum(r['counters'][k] for r in rows) for k in COUNTERS if not k.endswith('Ticks')},tracking_censored_queries=sum(not r['repeat_known_complete'] for r in rows)))
 caps=[]
 for turn in sorted({r['turn'] for r in decoded}):
  rows=[r for r in decoded if r['turn']==turn and r['row_cap']]
  if not rows:continue
  previous=defaultdict(set)
  for r in rows:previous[r['row_cap']['previousCapTurn']].add(r['row_cap']['previousCappedSelectedQueries'])
  caps.append(dict(turn=turn,maximum_retained_ordinal=max(r['row_cap']['turnRowOrdinal'] for r in rows),cap_reached=any(r['row_cap']['capAfterThisRow'] for r in rows),later_selected_query_count='unknown_until_following_turn_report',previous_turn_selected_censor_reports=[dict(turn=t,counts=sorted(c),consistent=len(c)==1) for t,c in sorted(previous.items()) if t!=-1]))
 return dict(schema='native_PATH_SAMPLE_v1',row_cap_coverage=caps,archive_quality=quality or {},measurement_notes=NOTES,retained_valid_rows=len(decoded),invalid_rows=invalid,groups=summaries,queries=decoded,diagnostic_drop_rows=[r for r in records if r['category'] in ('TRUNCATED','DIAGNOSTIC_COST') and (turns is None or r['turn'] in turns)])
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--run',required=True);parser.add_argument('--turn',type=int,action='append');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 if args.output.suffix.lower()!='.json':parser.error('output must be JSON')
 if any(args.output.resolve()==p.resolve() for p in args.directory.glob('*.log')):parser.error('output cannot overwrite native input')
 records,quality=wall.load(args.directory,args.run)
 if not quality['headers']:parser.error('No matching native run')
 messages={}
 for header in quality['headers']:
  path=Path(header['path'])
  with path.open(encoding='utf-8-sig',errors='replace') as stream:
   for line_number,line in enumerate(stream,1):
    if '|PATH_SAMPLE|' in line:messages[f'{path.name}:{line_number}']=line.split('|PATH_SAMPLE|',1)[1]
 for record in records:
  if record['category']=='PATH_SAMPLE':record['raw_message']=messages.get(record['origin'],'')
 report=analyze(records,quality,args.turn);report['run']=args.run;args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(valid=report['retained_valid_rows'],invalid=len(report['invalid_rows']),output=str(args.output))));return 2 if report['invalid_rows'] else 0
if __name__=='__main__':raise SystemExit(main())
