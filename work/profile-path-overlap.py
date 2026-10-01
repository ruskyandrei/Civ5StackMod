"""Offline sampled PATH query/phase overlap, building on profile-path-queries.

Coarse GetTickCount envelopes and estimated PLAN intervals are location
evidence, not CPU attribution. Repeated danger inputs are opportunities, not
validated memo hits. No sampled-query stride scaling is performed.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import importlib.util,json
from pathlib import Path

spec=importlib.util.spec_from_file_location('path_profile',Path(__file__).with_name('profile-path-queries.py'))
paths=importlib.util.module_from_spec(spec);spec.loader.exec_module(paths);wall=paths.wall
NOTES=[
 'All query counts/durations cover retained systematically selected PATH_SAMPLE rows only. No query-stride extrapolation or saved-time estimate.',
 'QPC query and part timings are inclusive sampled wall durations, not CPU time. Nested queries are included in their outer query.',
 'GetTickCount query envelopes and TURN_PHASE bounds are coarse. Zero-width query envelopes can have nonzero QPC duration; their overlap duration is unknown.',
 'TURN_PHASE associations require exact player/thread and intersecting recorded bounds. Source-turn provenance is preserved for scopes emitted at adjacent turn boundaries.',
 'PLAN bounds retain the existing emission/finalization estimate. Legacy PLAN records lack thread identity; player/time intersections are candidates, not proven same-thread search ownership.',
 'Envelope coverage is unioned, never added across nested phase labels, queries or PLAN. Per-label phase coverage overlaps and must not be summed.',
 'Part approximate_inclusive_ms is the existing per-selected-query call-sample estimate. Low sample counts, clock failures and systematic aliasing limit rankings.',
 'Plot/scene/actor/HP repeats are observed opportunities, not validated cache hits. Event masks do not exclude legacy loading listeners or prove complete raw-danger dependencies.',
 'Metadata tracking, invalid/missing rows, archive gaps and diagnostic budgets censor coverage. Absence means unknown work, not zero.',
]

def load(directory,run):
 records,quality=wall.load(directory,run)
 if not quality['headers']:raise ValueError('No exact native run: '+run)
 messages={}
 for header in quality['headers']:
  file=Path(header['path'])
  with file.open(encoding='utf-8-sig',errors='replace') as stream:
   for line_number,line in enumerate(stream,1):
    if '|PATH_SAMPLE|' in line:messages[f'{file.name}:{line_number}']=line.split('|PATH_SAMPLE|',1)[1]
 for row in records:
  if row['category']=='PATH_SAMPLE':row['raw_message']=messages.get(row['origin'],'')
 return records,quality

def identity(row):return tuple(row[k] for k in ('turn','player','thread','serial'))
def query_interval(record):
 start,end=record['values']['startTick'],record['values']['endTick'];duration=(end-start)%wall.MOD
 if duration>=wall.HALF:return None,'query_bounds_exceed_supported_duration'
 adjusted=dict(record,values=dict(record['values'],elapsedMs=duration))
 return wall.phase_interval(adjusted)

def overlap_interval(a,b):
 start,end=max(a[0],b[0]),min(a[1],b[1]);return (start,end) if end>start else None
def point_candidate(point,interval):return interval[0]<=point<=interval[1]

def aggregate(rows):
 parts={}
 for name in ('danger','terrain'):
  known=[r['parts'][name] for r in rows if r['parts'][name]['samples']]
  parts[name]=dict(calls=sum(r['parts'][name]['calls'] for r in rows),
   successful_samples=sum(r['parts'][name]['samples'] for r in rows),
   unknown_query_timings=sum(r['parts'][name]['unknown'] for r in rows),
   low_sample_queries=sum(r['parts'][name]['low_sample'] for r in rows),
   sampled_ms=sum(p['sampled_ms'] for p in known) if known else None,
   known_approximate_inclusive_ms=sum(p['approximate_inclusive_ms'] for p in known) if known else None,
   maximum_sample_ms=max((p['maximum_sample_ms'] for p in known),default=None))
 intervals=[r['interval'] for r in rows if r['interval'] is not None]
 phases=[span for r in rows for span in r['phase_overlap_spans']]
 plans=[span for r in rows for span in r['PLAN_candidate_overlap_spans']]
 phase_plan=wall.intersection(phases,plans);phase_ms=wall.length(phases);plan_ms=wall.length(plans)
 envelope_ms=wall.length(intervals);both_ms=wall.length(phase_plan)
 by_phase=defaultdict(list)
 for row in rows:
  for candidate in row['phase_associations']:
   if candidate['overlap_interval'] is not None:by_phase[candidate['phase']].append(candidate['overlap_interval'])
 known=[r['query_ms'] for r in rows if r['query_ms'] is not None]
 return dict(retained_sampled_queries=len(rows),query_qpc_ms_known=sum(known) if known else None,
  query_qpc_unknown=sum(r['query_ms'] is None for r in rows),parts=parts,
  counters={k:sum(r['counters'][k] for r in rows) for k in paths.COUNTERS if not k.endswith('Ticks')},
  tracking_censored_queries=sum(not r['repeat_known_complete'] for r in rows),
  scene_changed_queries=sum(r['scene_changed'] for r in rows),
  event_flags_counts=dict(Counter(r['eventFlags'] for r in rows)),
  invalid_query_intervals=sum(r['interval'] is None for r in rows),
  zero_width_query_envelopes=sum(r['interval'] is not None and r['interval'][0]==r['interval'][1] for r in rows),
  coarse_query_envelope_wall_union_ms=envelope_ms,
  coarse_phase_overlap_wall_union_ms=phase_ms,coarse_estimated_PLAN_candidate_overlap_wall_union_ms=plan_ms,
  coarse_phase_or_PLAN_union_ms=wall.length(phases+plans),
  coarse_nonadditive_partition_ms=dict(phase_and_estimated_PLAN=both_ms,phase_only=phase_ms-both_ms,
   estimated_PLAN_only=plan_ms-both_ms,outside_recorded_phase_or_estimated_PLAN=envelope_ms-wall.length(phases+plans)),
  coarse_overlap_by_phase=[dict(phase=k,wall_union_ms=wall.length(v)) for k,v in sorted(by_phase.items())],
  query_association_counts=dict(phase_matches=sum(bool(r['phase_associations']) for r in rows),
   PLAN_candidates=sum(bool(r['PLAN_associations']) for r in rows),
   phase_unmatched=sum(not r['phase_associations'] for r in rows),
   PLAN_unmatched=sum(not r['PLAN_associations'] for r in rows)))

def analyze(records,quality=None,turns=None,base_report=None):
 quality=quality or {};fresh=paths.analyze(records,quality,turns)
 if base_report is None:base_report=fresh
 canonical={};invalid=[]
 for record in records:
  if record['category']!='PATH_SAMPLE':continue
  parsed,errors=paths.decode(record)
  if not errors:canonical.setdefault(identity(parsed),[]).append((record,parsed))
 rows=[]
 for query in base_report['queries']:
  if turns is not None and query['turn'] not in turns:continue
  candidates=canonical.get(identity(query),[])
  if len(candidates)!=1:
   invalid.append(dict(origin=query.get('origin'),identity=identity(query),error='missing_or_duplicate_canonical_query_identity'));continue
  record,parsed=candidates[0]
  # A precomputed report is accepted only when its original decoded fields
  # match the selected native run. Never attach intervals to stale counters.
  if any(query.get(k)!=value for k,value in parsed.items() if k!='origin'):
   invalid.append(dict(origin=query.get('origin'),identity=identity(query),error='path_report_values_do_not_match_native_run'));continue
  interval,error=query_interval(record)
  rows.append(dict(query,canonical_origin=record.get('origin'),interval=interval,interval_error=error,
   phase_associations=[],PLAN_associations=[],phase_overlap_spans=[],PLAN_candidate_overlap_spans=[]))
 phases=[];invalid_phases=[];plans=[];plan_warnings=[]
 for record in records:
  if record['category']!='TURN_PHASE':continue
  values=record['values'];interval,error=wall.phase_interval(record)
  if error or values.get('semantics')!='inclusive' or not isinstance(values.get('phase'),str) or type(values.get('thread')) is not int or values['thread']<=0:
   invalid_phases.append(dict(origin=record.get('origin'),error=error or 'invalid_phase_metadata'));continue
  phases.append(dict(sourceTurn=record['turn'],player=record['player'],thread=values['thread'],phase=values['phase'],interval=interval,origin=record.get('origin')))
 for turn in sorted(set(r['turn'] for r in rows)):
  profile=wall.analyze(records,turn,quality=quality);plans.extend(dict(p,sourceTurn=turn) for p in profile['PLAN_intervals'])
  plan_warnings.extend(dict(turn=turn,warning=w) for w in profile['warnings'])
 phase_index=defaultdict(list);plan_index=defaultdict(list)
 for phase in phases:phase_index[(phase['player'],phase['thread'])].append(phase)
 for plan in plans:plan_index[plan['player']].append(plan)
 for row in rows:
  if row['interval'] is None:continue
  interval=row['interval'];zero=interval[0]==interval[1]
  for phase in phase_index[(row['player'],row['thread'])]:
   overlap=overlap_interval(interval,phase['interval'])
   if overlap is None and not(zero and point_candidate(interval[0],phase['interval'])):continue
   row['phase_associations'].append(dict(phase,overlap_interval=overlap,
    qualification='same_player_thread_coarse_point_candidate' if zero else 'same_player_thread_coarse_interval_overlap'))
   if overlap is not None:row['phase_overlap_spans'].append(overlap)
  for plan in plan_index[row['player']]:
   overlap=overlap_interval(interval,plan['interval'])
   if overlap is None and not(zero and point_candidate(interval[0],plan['interval'])):continue
   row['PLAN_associations'].append(dict(plan,overlap_interval=overlap,
    qualification='player_time_candidate_thread_unknown_approximate_PLAN'))
   if overlap is not None:row['PLAN_candidate_overlap_spans'].append(overlap)
 groups=defaultdict(list);units=defaultdict(list);types=defaultdict(list)
 for row in rows:
  groups[(row['turn'],row['player'],row['query_kind'])].append(row)
  units[(row['turn'],row['player'],row['unit'],row['pathType'],row['query_kind'])].append(row)
  types[(row['turn'],row['player'],row['pathType'],row['query_kind'])].append(row)
 warnings=[]
 matched={identity(r) for r in rows}
 omitted=[dict(identity=identity(r),origin=r.get('origin')) for r in fresh['queries'] if identity(r) not in matched]
 if not rows:warnings.append('No valid matched PATH_SAMPLE rows: work and repeat opportunities are unknown.')
 if omitted:warnings.append('The input path report omits selected valid native query identities; aggregates cover its matched subset only.')
 if invalid or fresh['invalid_rows']:warnings.append('Invalid or mismatched path rows excluded; coverage is incomplete.')
 if quality.get('gaps') or quality.get('earlier_segments_missing') or quality.get('incomplete_tails_skipped'):warnings.append('Native archive is partial.')
 if quality.get('conflicting_segment_files') or quality.get('clock_reversals'):warnings.append('Conflicting segments or clock reversals limit temporal associations.')
 drops=base_report.get('diagnostic_drop_rows',[])
 if any(r['category']=='TRUNCATED' or r['values'].get('dropped',0) for r in drops):warnings.append('Diagnostic drops can censor query and phase coverage.')
 return dict(schema='native_sampled_PATH_overlap_v1',measurement_notes=NOTES,archive_quality=quality,
  warnings=warnings,invalid_associations=invalid,invalid_base_rows=fresh['invalid_rows'],invalid_phase_rows=invalid_phases,
  coverage=dict(valid_native_PATH_rows_selected=fresh['retained_valid_rows'],matched_queries=len(rows),
   native_query_identities_without_matched_report=len(omitted)),native_queries_without_matched_report=omitted,
  PLAN_location_warnings=plan_warnings,whole_selection=aggregate(rows),
  turn_player_query_kind=[dict(turn=k[0],player=k[1],query_kind=k[2],**aggregate(v)) for k,v in sorted(groups.items())],
  turn_player_pathType_query_kind=[dict(turn=k[0],player=k[1],pathType=k[2],query_kind=k[3],**aggregate(v)) for k,v in sorted(types.items())],
  turn_player_unit_type_query_kind=[dict(turn=k[0],player=k[1],unit=k[2],pathType=k[3],query_kind=k[4],**aggregate(v)) for k,v in sorted(units.items())],
  queries=rows,diagnostic_drop_rows=drops)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--run',required=True)
 parser.add_argument('--turn',type=int,action='append');parser.add_argument('--path-report',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 if args.output.suffix.lower()!='.json':parser.error('output must be JSON')
 inputs=list(args.directory.glob('*.log'))+([args.path_report] if args.path_report else [])
 if any(args.output.resolve()==p.resolve() or args.output.exists() and args.output.samefile(p) for p in inputs):parser.error('output must not replace an input or alias')
 try:
  records,quality=load(args.directory,args.run);base=json.loads(args.path_report.read_text(encoding='utf-8-sig')) if args.path_report else None
  if base is not None and base.get('run')!=args.run:raise ValueError('Path report does not name the exact selected native run')
  report=analyze(records,quality,args.turn,base)
 except (ValueError,KeyError) as error:parser.error(str(error))
 report.update(run=args.run,path_report=str(args.path_report) if args.path_report else None,selected_turns=args.turn)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(queries=report['whole_selection']['retained_sampled_queries'],invalid_base_rows=len(report['invalid_base_rows']),invalid_associations=len(report['invalid_associations']),output=str(args.output))))
 return 2 if report['invalid_base_rows'] or report['invalid_associations'] else 0

if __name__=='__main__':raise SystemExit(main())
