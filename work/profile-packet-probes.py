"""Offline PLAN_PACKET_PROBE counts. Writes only the requested JSON report.

No sampled overlap is extrapolated to saved simulations, CPU time or seconds.
The canonical native-run loader deduplicates segment copies. Probe/SAMPLE share
exact identity fields; old PLAN/PERF adjacency remains a qualified candidate.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import importlib.util
import json
from pathlib import Path
import re

spec=importlib.util.spec_from_file_location('plan_samples',Path(__file__).with_name('profile-plan-samples.py'))
samples=importlib.util.module_from_spec(spec);spec.loader.exec_module(samples)
wall=samples.wall
MAX_U64=(1<<64)-1
COUNTS=('misses','prefiltered','cohortQueries','groups','repeats','sameMember','crossMember',
 'freshQueries','batchReuseQueries','freshRepeatQueries','freshCrossMemberQueries','rawCalls','outcomeBuildAttempts',
 'fieldGroups','cityGroups','fallback','oversized','sourceUnavailable','invalidated','reentrant','evictions','clears','packetResultReuseQueries')
BYTES=('keyBytes','peakKeyBytes','outputUpperBytes','peakOutputUpperBytes')
IDENTITY=('turn','player','targetPlot','thread','serial')
NOTES=[
 'These are retained diagnostic observations, not estimated saved simulations or time. No stride scaling is applied.',
 'Both deterministic filters are group-consistent for supported exact inputs; censoring, finite metadata FIFO, bounds and scene clears can omit valuable groups.',
 'freshQueries counts queries which called raw danger or attempted an outcome build. Attempts can fail; rawCalls and outcomeBuildAttempts may both occur for one query.',
 'batchReuseQueries used the existing local outcome batch; v2 reports shared result-packet hits separately as packetResultReuseQueries. v1 predates the shared result cache.',
 'crossMember is the first observation of a new member after another member in the retained group; subsequent visits to that member are sameMember.',
 'freshCrossMemberQueries is the first fresh-work visit by a new member after earlier fresh work; the member may previously have used the local batch.',
 'outputUpperBytes is the first retained group\'s logical injury-pair union proxy, not actual retained vector capacity, inline/container/node cost or a future global cache budget.',
 'Source owners/order/duplicates, full numerical friendly injuries including off-stack AA, candidate order and projected enemy injuries are included within the locked native preview scene.',
 'PLAN_PACKET_PROBE and PLAN_SAMPLE can share exact turn/player/target/thread/serial identity. Legacy PLAN/PERF lack serial/thread; adjacency and verified target provide only candidate associations.',
 'Peak bytes are summarized with maxima, not sums. Field/city group counts distinguish admissions only; repeat/query counts are not split by domain in this emitter.',
 'A missing probe row can mean unsupported scope, allocation failure, reset, disabled sampling or a dropped row. Missing data is never interpreted as zero overlap.',
]

def unsigned(value,maximum=MAX_U64):return type(value) is int and 0<=value<=maximum
def identity(row):return tuple(row[k] for k in IDENTITY)
def decode(record):
 value=dict(record['values']);errors=[];warnings=[]
 if value.get('version')==1 and 'packetResultReuseQueries' not in value:value['packetResultReuseQueries']=0
 if '[message truncated]' in record.get('raw_message',''):errors.append('explicit_message_truncation')
 raw_message=record.get('raw_message','');wire=wall.RECORD.fullmatch(raw_message.rstrip('\r\n'))
 raw_pairs=wall.FIELD.findall(wire.group(5) if wire else raw_message)
 duplicates=[k for k,c in Counter(k for k,v in raw_pairs).items() if c>1 and k in COUNTS+BYTES+('targetPlot','thread','serial','version','prefilterBits','cohortBits','slots','maxKeyWords','metadataBytes')]
 if duplicates:errors.append('duplicate_fields:'+','.join(sorted(duplicates)))
 for k in COUNTS+BYTES+('targetPlot','serial','thread','version','prefilterBits','cohortBits','slots','maxKeyWords','metadataBytes'):
  if not unsigned(value.get(k)):errors.append(k+':missing_or_invalid_unsigned_integer')
 if errors:return None,errors
 if value['version'] not in (1,2):errors.append('unsupported_version')
 if value['version']==1 and value['packetResultReuseQueries']!=0:errors.append('v1_cannot_report_shared_packet_result_reuse')
 if value['serial']==0 or value['thread']==0 or value['serial']>(1<<32)-1 or value['thread']>(1<<32)-1:errors.append('invalid_native_identity')
 if value['targetPlot']>(1<<31)-1:errors.append('invalid_native_plot_index')
 expected={'prefilterBits':2,'cohortBits':3,'slots':128,'maxKeyWords':512}
 for k,want in expected.items():
  if value[k]!=want:errors.append('unsupported_'+k)
 if not 128*512*4<=value['metadataBytes']<=3*1024*1024:errors.append('invalid_metadata_footprint')
 relations=[('cohortQueries','prefiltered'),('prefiltered','misses'),('freshCrossMemberQueries','freshRepeatQueries'),
  ('freshRepeatQueries','freshQueries'),('rawCalls','freshQueries'),('evictions','groups')]
 for a,b in relations:
  if value[a]>value[b]:errors.append(a+'_exceeds_'+b)
 observations=value['groups']+value['repeats']
 if value['sameMember']+value['crossMember']!=value['repeats']:errors.append('repeat_classes_do_not_sum')
 if value['freshQueries']+value['batchReuseQueries']+value['packetResultReuseQueries']!=observations:errors.append('work_classes_do_not_sum')
 if value['fieldGroups']+value['cityGroups']!=value['groups']:errors.append('field_city_groups_do_not_sum')
 if value['freshQueries']>value['rawCalls']+value['outcomeBuildAttempts']:errors.append('fresh_queries_without_raw_or_build_attempt')
 if observations+value['invalidated']>value['cohortQueries']:errors.append('finished_and_invalidated_exceed_selected_queries')
 unaccounted=value['cohortQueries']-observations-value['invalidated']
 if unaccounted>0:warnings.append('selected_queries_without_retained_finish_or_invalidation:'+str(unaccounted))
 if value['keyBytes']>value['peakKeyBytes'] or value['peakKeyBytes']>128*512*4:errors.append('key_payload_bound_or_peak_invalid')
 if value['keyBytes']%4 or value['peakKeyBytes']%4:errors.append('key_bytes_not_native_word_multiple')
 if value['outputUpperBytes']>value['peakOutputUpperBytes'] or value['peakOutputUpperBytes']>128*(128+32)*8:errors.append('logical_output_proxy_bound_or_peak_invalid')
 if errors:return None,errors
 row={k:value[k] for k in COUNTS+BYTES+('targetPlot','serial','thread','version','prefilterBits','cohortBits','slots','maxKeyWords','metadataBytes')}
 row.update(turn=record['turn'],player=record['player'],tick=record['tick'],origin=record.get('origin'),warnings=warnings,
  finished_probe_observations=observations,unaccounted_selected_queries=unaccounted,
  observed_group_member_introductions=value['groups']+value['crossMember'],
  current_metadata_groups=value['groups']-value['evictions'] if value['clears']==0 else None)
 return row,[]

def aggregate(rows):
 totals={k:sum(r[k] for r in rows) for k in COUNTS}
 totals.update(finished_probe_observations=sum(r['finished_probe_observations'] for r in rows),
  unaccounted_selected_queries=sum(r['unaccounted_selected_queries'] for r in rows),
  observed_group_member_introductions=sum(r['observed_group_member_introductions'] for r in rows))
 return dict(plan_probe_rows=len(rows),counts=totals,
  metadata_max_bytes=max((r['metadataBytes'] for r in rows),default=None),
  per_plan_max_bytes={k:max((r[k] for r in rows),default=None) for k in BYTES},
  observed_fresh_cross_member_fraction=totals['freshCrossMemberQueries']/totals['freshQueries'] if totals['freshQueries'] else None,
  observed_cross_member_repeat_fraction=totals['crossMember']/totals['repeats'] if totals['repeats'] else None,
  fraction_scope='Retained selected observations only; no unsampled, uncensored or end-turn extrapolation.')

def analyze(records,quality=None,turn=None,player=None,map_width=None):
 selected=lambda r:(turn is None or r['turn']==turn) and (player is None or r['player']==player)
 invalid=[];probe_candidates=[];sample_candidates=[]
 for position,record in enumerate(records):
  if not selected(record):continue
  if record['category']=='PLAN_PACKET_PROBE':
   row,errors=decode(record)
   if errors:invalid.append(dict(category=record['category'],origin=record.get('origin'),turn=record['turn'],player=record['player'],errors=errors))
   else:row['position']=position;probe_candidates.append(row)
  elif record['category']=='PLAN_SAMPLE':
   row,errors=samples.decode(record)
   if errors:invalid.append(dict(category=record['category'],origin=record.get('origin'),turn=record['turn'],player=record['player'],errors=errors))
   else:row['position']=position;sample_candidates.append(row)
 def unique(rows,kind):
  counts=Counter(identity(r) for r in rows);good=[]
  for row in rows:
   if counts[identity(row)]!=1:invalid.append(dict(category=kind,origin=row.get('origin'),turn=row['turn'],player=row['player'],errors=['duplicate_identity'],identity=identity(row)))
   else:good.append(row)
  return good
 probes=unique(probe_candidates,'PLAN_PACKET_PROBE');timed=unique(sample_candidates,'PLAN_SAMPLE')
 timed_by_id={identity(r):r for r in timed};probes_by_id={identity(r):r for r in probes}
 for probe in probes:
  other=timed_by_id.get(identity(probe))
  probe['sample_association']=dict(status='identity_verified' if other else 'unmatched',
   origin=other['origin'] if other else None,
   parts=[dict(part=p['part'],calls=p['calls'],samples=p['samples'],sampled_wall_ms=p['sampled_wall_ms']) for p in other['parts']] if other else None)
  # The probe is emitted immediately before SAMPLE. Its own preceding record
  # is the correct bounded legacy PLAN/PERF candidate, with no stale search scan.
  probe['legacy_plan_association']=samples.associate_plan(records,probe.pop('position'),probe,map_width)
  if map_width:probe['target_coordinates']=[probe['targetPlot']%map_width,probe['targetPlot']//map_width]
 groups=defaultdict(list)
 for probe in probes:groups[(probe['turn'],probe['player'],probe['targetPlot'])].append(probe)
 costs=[dict(origin=r.get('origin'),turn=r['turn'],player=r['player'],fields=r['values']) for r in records if selected(r) and r['category']=='DIAGNOSTIC_COST']
 truncated=[dict(origin=r.get('origin'),turn=r['turn'],player=r['player'],fields=r['values']) for r in records if selected(r) and r['category']=='TRUNCATED']
 quality=quality or {};warnings=[]
 if not probes:warnings.append('No valid probe rows: packet overlap is unknown, not zero.')
 if quality.get('conflicting_segment_files'):warnings.append('Conflicting copies of native segments were found; completeness is uncertain.')
 if quality.get('gaps') or quality.get('earlier_segments_missing') or quality.get('incomplete_tails_skipped'):warnings.append('Native archive is partial; counts cover retained complete records only.')
 if quality.get('clock_reversals'):warnings.append('Native clock order contains reversals; legacy timing adjacency is unreliable.')
 if truncated or any(r['fields'].get('dropped',0) for r in costs):warnings.append('Diagnostic row drops are reported; absent probe/SAMPLE records can be budget-censored.')
 unmatched_samples=[dict(identity=identity(r),origin=r['origin']) for r in timed if identity(r) not in probes_by_id]
 return dict(schema='native_PLAN_PACKET_PROBE_v1_v2',filters=dict(turn=turn,player=player,map_width=map_width),
  measurement_notes=NOTES,warnings=warnings,archive_quality=quality,
  coverage=dict(valid_probe_rows=len(probes),valid_sample_rows=len(timed),
   probe_sample_identity_matches=sum(identity(r) in timed_by_id for r in probes),
   probes_without_sample=sum(identity(r) not in timed_by_id for r in probes),samples_without_probe=len(unmatched_samples),
   retained_native_PLAN_rows=sum(selected(r) and r['category']=='PLAN' for r in records),
   retained_native_PLAN_PERF_rows=sum(selected(r) and r['category']=='PLAN_PERF' for r in records),
   identity_matched_probe_fraction_of_valid_samples=sum(identity(r) in timed_by_id for r in probes)/len(timed) if timed else None),
  invalid_rows=invalid,invalid_row_count=len(invalid),whole_selection=aggregate(probes),
  legacy_association_counts=dict(Counter(r['legacy_plan_association']['status'] for r in probes)),
  diagnostic_drop_rows=truncated,diagnostic_cost_rows=costs,samples_without_probe=unmatched_samples,
  turn_player_target_groups=[dict(turn=k[0],player=k[1],targetPlot=k[2],
   target_coordinates=[k[2]%map_width,k[2]//map_width] if map_width else None,**aggregate(v)) for k,v in sorted(groups.items())],
  plans=probes)

def load(directory,run):
 records,quality=wall.load(directory,run);messages={}
 for header in quality['headers']:
  path=Path(header['path'])
  with path.open(encoding='utf-8-sig',errors='replace') as stream:
   for index,line in enumerate(stream,1):
    if '|PLAN_PACKET_PROBE|' in line or '|PLAN_SAMPLE|' in line:messages[f'{path.name}:{index}']=line
 for record in records:
  if record['category'] in ('PLAN_PACKET_PROBE','PLAN_SAMPLE'):record['raw_message']=messages.get(record['origin'],'')
 return records,quality

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('native_directory',type=Path)
 parser.add_argument('--run',required=True,help='Exact native session run ID; never combine sessions')
 parser.add_argument('--turn',type=int);parser.add_argument('--player',type=int)
 parser.add_argument('--map-width',type=int,help='Optional independently verified map width; never inferred')
 parser.add_argument('--output',type=Path,required=True);options=parser.parse_args()
 if not options.native_directory.is_dir():parser.error('native_directory must exist')
 if options.map_width is not None and options.map_width<=0:parser.error('--map-width must be positive')
 records,quality=load(options.native_directory,options.run)
 if not quality['headers']:parser.error('No matching native run segments found')
 result=analyze(records,quality,options.turn,options.player,options.map_width)
 result.update(native_directory=str(options.native_directory.resolve()),run=options.run)
 options.output.parent.mkdir(parents=True,exist_ok=True);options.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(output=str(options.output.resolve()),coverage=result['coverage'],invalid_row_count=result['invalid_row_count'],counts=result['whole_selection']['counts'])))
 return 2 if result['invalid_row_count'] else 0
if __name__=='__main__':raise SystemExit(main())
