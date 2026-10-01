"""Lightweight synthetic tests for actual native cache-counter comparison."""
import importlib.util,json,os,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cache_counters',root/'work/compare-plan-cache-counters.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
checks=0
def check(name,ok):
 global checks
 checks+=1
 if not ok:raise AssertionError(name)
def rec(values=None,turn=253,player=3,category='PLAN_PERF'):
 v=dict(target='25:25',dangerHits=100,dangerMisses=20,dangerEvictions=4,outcomeBuilds=2,outcomeReuses=5,outcomeBypasses=0,searchMs=30,entries=6,payloadBytes=80)
 if values:v.update(values)
 return dict(values=v,category=category,turn=turn,player=player,raw_tick=20,tick=20,origin='synthetic',raw_message=' '.join(f'{k}={x}' for k,x in v.items()))
baseline=p.analyze([rec(),rec(dict(dangerHits=200,dangerMisses=10,entries=2,payloadBytes=120))],map_width=88)
trial=p.analyze([rec(dict(dangerHits=250,dangerMisses=15,packetHits=5,packetBuilds=2,packetBypasses=10))],map_width=88)
r=p.compare(baseline,trial,88)
check('actual sums',baseline['whole_selection']['counters']['dangerHits']['complete']==300)
check('peak snapshot max not sum',baseline['whole_selection']['maxima']['entries']['complete']==6 and baseline['whole_selection']['maxima']['payloadBytes']['complete']==120)
check('missing baseline packet unknown',baseline['whole_selection']['counters']['packetHits']['complete'] is None)
check('delta unknown when baseline absent',r['whole_selection']['deltas']['counters']['packetHits'] is None)
check('actual known delta',r['whole_selection']['deltas']['counters']['dangerHits']==-50)
check('plot derived only explicit width',r['turn_player_targets'][0]['targetPlot']==2225)
check('target/player comparison aggregate',r['turn_player_targets'][0]['baseline']['retained_valid_PLAN_PERF_rows']==2)
check('unverified width keeps plot unknown',p.analyze([rec()])['plans'][0]['targetPlot'] is None)
missing=rec();del missing['values']['dangerHits']
partial=p.analyze([rec(),missing])['whole_selection']['counters']['dangerHits']
check('partial metric known retained sum',partial['observed_known']==100 and partial['missing_rows']==1)
check('partial metric complete unknown',partial['complete'] is None)
empty=p.analyze([],turns=[253]);check('missing whole turn remains unknown',empty['turns'][0]['counters']['dangerHits']['complete'] is None)
check('empty rows warned',bool(empty['warnings']))
zero=rec(dict(packetHits=0));check('explicit zero is known',p.analyze([zero])['whole_selection']['counters']['packetHits']['complete']==0)
for key,value in [('dangerHits',-1),('packetHits',True),('outcomeBuilds',1<<32),('target','25'),('target',25),('target','88:25')]:
 row,errors=p.decode(rec({key:value}),88);check('reject invalid '+key+str(value),row is None and bool(errors))
x=rec();x['raw_message']+=' dangerHits=9';check('duplicate metric rejected',bool(p.decode(x,88)[1]))
x=rec();x['raw_message']='STACKDIAG|20|turn=253|player=3|PLAN_PERF|'+x['raw_message']+' target=26:25';check('wire target duplicate rejected',bool(p.decode(x,88)[1]))
x=rec();x['raw_message']+=' [message truncated]';check('truncated metric row rejected',bool(p.decode(x)[1]))
invalid=p.analyze([rec(dict(dangerHits=-1))]);check('invalid omitted and censored',invalid['invalid_row_count']==1 and invalid['whole_selection']['retained_valid_PLAN_PERF_rows']==0)
mixed=p.analyze([rec(),rec(turn=252),rec(player=4)]);check('turn and player target separate',len(mixed['turns'])==2 and len(mixed['turn_player_targets'])==3)
filtered=p.analyze([rec(),rec(turn=252)],turns=[252]);check('explicit turn filter',len(filtered['plans'])==1 and filtered['plans'][0]['turn']==252)
only=p.compare(p.analyze([rec()]),p.analyze([rec(dict(target='26:25'))]));check('different target not falsely paired',len(only['turn_player_targets'])==2 and all(x['baseline'] is None or x['candidate'] is None for x in only['turn_player_targets']))
drop=rec(dict(dropped=1),category='DIAGNOSTIC_COST');check('row drops cautioned',bool(p.analyze([rec(),drop])['warnings']))
check('partial archive cautioned',bool(p.analyze([rec()],dict(gaps=[[1,2]]))['warnings']))
check('no scaling or predicted savings',not any('saved' in k or 'scaled' in k for k in r['whole_selection']))
with tempfile.TemporaryDirectory(prefix='civ-cache-counter-') as temp:
 d=Path(temp);a=d/'baseline';b=d/'candidate';a.mkdir();b.mkdir()
 def wire(row):return f"STACKDIAG|{row['raw_tick']}|turn={row['turn']}|player={row['player']}|{row['category']}|{row['raw_message']}\n"
 body='STACKDIAG|SESSION|run=exact-control segment=0\n'+wire(rec())
 (a/'0.log').write_text(body);(a/'copy.log').write_text(body[:-5]);(a/'other.log').write_text('STACKDIAG|SESSION|run=other-run segment=0\n'+wire(rec(dict(dangerHits=999))))
 (b/'0.log').write_text('STACKDIAG|SESSION|run=exact-trial segment=0\n'+wire(rec(dict(packetHits=5,packetBuilds=2,packetBypasses=0))))
 records,quality=p.load(a,'exact-control');check('canonical prefix dedup',len(records)==1 and len(quality['duplicate_segment_files_ignored'])==1)
 check('exact run filter',records[0]['values']['dangerHits']==100)
 failed=False
 try:p.load(a,'missing')
 except ValueError:failed=True
 check('unknown exact run refuses',failed)
 report=d/'report.json';cmd=[sys.executable,'-B',str(root/'work/compare-plan-cache-counters.py'),str(a),str(b),'--baseline-run','exact-control','--candidate-run','exact-trial','--turn','253','--map-width','88','--output',str(report)]
 completed=subprocess.run(cmd,capture_output=True,text=True);check('CLI report succeeds',completed.returncode==0 and report.exists())
 check('CLI baseline packet stays unknown',json.loads(report.read_text())['whole_selection']['baseline']['counters']['packetHits']['complete'] is None)
 (b/'0.log').write_text('STACKDIAG|SESSION|run=exact-trial segment=0\n'+wire(rec(dict(packetHits=-1))))
 invalid=subprocess.run(cmd,capture_output=True,text=True);check('CLI invalid retained row returns2',invalid.returncode==2)
 alias=d/'input-alias.json';os.link(b/'0.log',alias);before=(b/'0.log').read_bytes()
 blocked=subprocess.run(cmd[:-1]+[str(alias)],capture_output=True,text=True)
 check('CLI refuses output alias of input log',blocked.returncode==2 and 'alias' in blocked.stderr)
 check('blocked alias preserves input bytes',(b/'0.log').read_bytes()==before)
result=dict(checks=checks,failures=0,scope='actual-counter aggregation, missing-as-unknown, target/player matching, canonical run/segment dedup, invalid/drop coverage and CLI; no scaling/native ROI')
(root/'work/plan-cache-counter-fixture-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
