"""Lightweight synthetic validation of the offline packet probe reader."""
import copy,importlib.util,json
from pathlib import Path
import subprocess,sys,tempfile
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('packet_profile',root/'work/profile-packet-probes.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
checks=0
def check(name,okay):
 global checks
 checks+=1
 if not okay:raise AssertionError(name)
def record(category,values=None,tick=0,turn=252,player=1,origin='synthetic'):
 value=values or {};message=' '.join(f'{k}={v}' for k,v in value.items())
 return dict(category=category,values=value,tick=tick,raw_tick=tick,turn=turn,player=player,origin=origin,raw_message=message)
def probe(**change):
 value={k:0 for k in p.COUNTS+p.BYTES}
 value.update(targetPlot=92,serial=7,thread=23,version=1,prefilterBits=2,cohortBits=3,slots=128,maxKeyWords=512,metadataBytes=269568,
  misses=100,prefiltered=25,cohortQueries=10,groups=2,repeats=7,sameMember=3,crossMember=4,
  freshQueries=7,batchReuseQueries=2,freshRepeatQueries=5,freshCrossMemberQueries=3,
  rawCalls=5,outcomeBuildAttempts=3,fieldGroups=1,cityGroups=1,invalidated=1,
  keyBytes=120,peakKeyBytes=200,outputUpperBytes=80,peakOutputUpperBytes=96)
 value.update(change);return record('PLAN_PACKET_PROBE',value,30)
def sample(**change):
 zeros=','.join('0' for x in p.samples.PARTS);calls=','.join('2' for x in p.samples.PARTS)
 values=dict(targetPlot=92,serial=7,thread=23,stride=4096,phase=0,qpcFrequency=10000000,qpcFrequencyCalls=1,qpcReads=0,clockFailures=0,
  parts=','.join(p.samples.PARTS),calls=calls,selected=zeros,samples=zeros,ticks=zeros,maxTicks=zeros,semantics=p.samples.SEMANTICS)
 values.update(change);return record('PLAN_SAMPLE',values,31)
def plan():return record('PLAN',dict(target='4:1',milliseconds=18,states=97),29)
def perf():return record('PLAN_PERF',dict(target='4:1',dangerMisses=100,searchMs=17),28)

decoded,errors=p.decode(probe());check('valid v1 fields',not errors and decoded['finished_probe_observations']==9)
check('group/member introductions qualified',decoded['observed_group_member_introductions']==6)
check('retained groups current known without clears',decoded['current_metadata_groups']==2)
for field,value in [('misses',-1),('rawCalls',True),('groups',1<<64),('thread',0),('serial',1<<32),('targetPlot',-1),
 ('version',3),('slots',129),('maxKeyWords',511),('prefilterBits',3),('cohortBits',2),('metadataBytes',3*1024*1024+1),
 ('sameMember',4),('freshRepeatQueries',8),('freshCrossMemberQueries',6),('rawCalls',8),('fieldGroups',2),('freshQueries',8),
 ('cohortQueries',8),('prefiltered',101),('evictions',3),('keyBytes',204),('peakKeyBytes',262148),('keyBytes',119),
 ('outputUpperBytes',97),('peakOutputUpperBytes',163841),('outcomeBuildAttempts',0)]:
 _,bad=p.decode(probe(**{field:value}));check('reject inconsistent '+field+str(value),bool(bad))
for field in p.COUNTS+p.BYTES:
 if field=='packetResultReuseQueries':continue # This field is absent in v1.
 r=probe();del r['values'][field];_,errors=p.decode(r);check('required metric '+field,bool(errors))
check('v1 absent shared-packet metric defaults to zero',p.decode(probe())[0]['packetResultReuseQueries']==0)
v2=probe(version=2,metadataBytes=269576,packetResultReuseQueries=1,batchReuseQueries=1)
check('v2 distinguishes packet result from local batch',not p.decode(v2)[1] and p.decode(v2)[0]['packetResultReuseQueries']==1)
del v2['values']['packetResultReuseQueries'];check('v2 requires packet result metric',bool(p.decode(v2)[1]))
check('v1 shared result metric forbidden',bool(p.decode(probe(packetResultReuseQueries=1,batchReuseQueries=1))[1]))
row=probe();row['raw_message']+=' [message truncated]';check('explicit truncation rejected',bool(p.decode(row)[1]))
row=probe();row['raw_message']+=' serial=8';check('duplicate field rejected',bool(p.decode(row)[1]))
row=probe();row['raw_message']='STACKDIAG|30|turn=252|player=1|PLAN_PACKET_PROBE|'+row['raw_message']+' targetPlot=93';check('wire first-field duplicate rejected',bool(p.decode(row)[1]))
row=p.decode(probe(clears=1))[0];check('cleared FIFO occupancy unknown',row['current_metadata_groups'] is None)
row=p.decode(probe(cohortQueries=11))[0];check('unaccounted selected query warned',row['unaccounted_selected_queries']==1 and row['warnings'])

rows=[perf(),plan(),probe(),sample()];report=p.analyze(rows,map_width=88)
check('sample exact identity association',report['coverage']['probe_sample_identity_matches']==1)
check('PLAN/PERF target association stays candidate',report['legacy_association_counts']=={'target_verified_adjacent_candidate':1})
check('attached matching perf remains candidate',report['plans'][0]['legacy_plan_association']['preceding_perf_candidate']['fields']['dangerMisses']==100)
check('target coordinates use supplied width',report['plans'][0]['target_coordinates']==[4,1])
check('field and city admissions retained separately',report['whole_selection']['counts']['fieldGroups']==report['whole_selection']['counts']['cityGroups']==1)
check('no stride-scaled saved work keys',not any('saved' in k or 'estimated' in k for k in report['whole_selection']))
check('zero called samples carry zero measured ticks only',all(x['sampled_wall_ms']==0 for x in report['plans'][0]['sample_association']['parts']))
unverified=p.analyze(rows)['plans'][0]['legacy_plan_association'];check('no inferred map width',unverified['status']=='target_unverified_adjacent_candidate')
for field,value in [('thread',24),('serial',8),('targetPlot',93)]:
 r=p.analyze([perf(),plan(),probe(),sample(**{field:value})],map_width=88)
 check('different '+field+' never joins',r['coverage']['probe_sample_identity_matches']==0 and r['coverage']['samples_without_probe']==1)
wrong=[perf(),record('PLAN',dict(target='5:1'),29),probe(),sample()]
check('different legacy target rejected',p.analyze(wrong,map_width=88)['legacy_association_counts']=={'target_mismatch':1})
check('unrelated preceding row does not borrow stale PLAN',p.analyze([plan(),record('COMBAT',{},29),probe(),sample()],map_width=88)['legacy_association_counts']=={'unmatched':1})
check('explicit legacy serial mismatch rejected',p.analyze([record('PLAN',dict(targetPlot=92,serial=8,thread=23),29),probe()],map_width=88)['legacy_association_counts']=={'identity_mismatch':1})
check('explicit legacy full identity supported',p.analyze([record('PLAN',dict(targetPlot=92,serial=7,thread=23),29),probe()],map_width=88)['legacy_association_counts']=={'identity_and_target_verified':1})
check('duplicate probes all rejected',p.analyze([probe(),probe(),sample()])['coverage']['valid_probe_rows']==0)
check('duplicate samples never authorized',p.analyze([probe(),sample(),sample()])['coverage']['probe_sample_identity_matches']==0)
check('missing probe remains unknown',p.analyze([sample()])['warnings'] and p.analyze([])['whole_selection']['observed_fresh_cross_member_fraction'] is None)
check('turn filter precise',p.analyze(rows,turn=251)['coverage']['valid_probe_rows']==0)
check('player filter precise',p.analyze(rows,player=2)['coverage']['valid_probe_rows']==0)
both=rows+[dict(probe(),turn=253),dict(sample(),turn=253)];r=p.analyze(both,map_width=88)
check('turn identities not merged',r['coverage']['probe_sample_identity_matches']==2 and len(r['turn_player_target_groups'])==2)
check('peaks are max not sum',r['whole_selection']['per_plan_max_bytes']['peakKeyBytes']==200)
cost=record('DIAGNOSTIC_COST',dict(dropped=2),35);drop=record('TRUNCATED',{},34)
check('native row drops warned',p.analyze(rows+[drop,cost])['diagnostic_drop_rows'] and p.analyze(rows+[drop,cost])['warnings'])
check('partial archive warned',p.analyze(rows,dict(gaps=[[1,2]]))['warnings'])
check('conflicting archive warned',p.analyze(rows,dict(conflicting_segment_files=[{}]))['warnings'])
check('clock reversal warned',p.analyze(rows,dict(clock_reversals=['x']))['warnings'])

with tempfile.TemporaryDirectory(prefix='civ-packet-profile-') as temp:
 directory=Path(temp)
 def wire(r):return f"STACKDIAG|{r['raw_tick']}|turn={r['turn']}|player={r['player']}|{r['category']}|{r['raw_message']}\n"
 body='STACKDIAG|SESSION|run=NativeRun-74 segment=0\n'+''.join(map(wire,rows))
 (directory/'a.log').write_text(body,encoding='utf-8');(directory/'short-copy.log').write_text(body[:-10],encoding='utf-8')
 (directory/'other-run.log').write_text(body.replace('NativeRun-74','NativeRun-old'),encoding='utf-8')
 loaded,quality=p.load(directory,'NativeRun-74');check('exact native run selected',len(loaded)==4)
 check('prefix segment copy deduplicated',len(quality['duplicate_segment_files_ignored'])==1 and not quality['conflicting_segment_files'])
 check('raw probe message retained',loaded[2]['raw_message'].startswith('STACKDIAG|'))
 check('loader + association output valid',p.analyze(loaded,quality,map_width=88)['invalid_row_count']==0)
 output=directory/'report.json';run=subprocess.run([sys.executable,'-B',str(root/'work/profile-packet-probes.py'),str(directory),'--run','NativeRun-74','--turn','252','--map-width','88','--output',str(output)],capture_output=True,text=True)
 check('CLI succeeds and writes only supplied output',run.returncode==0 and output.exists())
 saved=json.loads(output.read_text());check('CLI output exact selected identity',saved['run']=='NativeRun-74' and saved['coverage']['probe_sample_identity_matches']==1)
 (directory/'conflict.log').write_text(body.replace('misses=100','misses=101'),encoding='utf-8');_,quality=p.load(directory,'NativeRun-74')
 check('conflicting copies recorded not silently combined',bool(quality['conflicting_segment_files']))
 absent=subprocess.run([sys.executable,'-B',str(root/'work/profile-packet-probes.py'),str(directory),'--run','absent','--output',str(directory/'absent.json')],capture_output=True,text=True)
 check('no matching run fails explicitly',absent.returncode!=0 and not (directory/'absent.json').exists())
 invalid_path=directory/'bad';invalid_path.mkdir();bad=probe(version=3);(invalid_path/'one.log').write_text('STACKDIAG|SESSION|run=bad segment=0\n'+wire(bad),encoding='utf-8');badout=invalid_path/'report.json'
 rejected=subprocess.run([sys.executable,'-B',str(root/'work/profile-packet-probes.py'),str(invalid_path),'--run','bad','--output',str(badout)],capture_output=True,text=True)
 check('invalid schema emits diagnostic report with exit2',rejected.returncode==2 and json.loads(badout.read_text())['invalid_row_count']==1)

result=dict(checks=checks,failures=0,scope='Lightweight synthetic parser, exact identities, canonical native-run/segment-copy loader, bounds and count equations; no native overlap/speed claim.')
(root/'work/packet-probe-profile-fixture-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
