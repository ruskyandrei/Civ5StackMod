"""Offline AI-followup replay performance gate; no game or controller calls.

Exit0: timing passes under all recorded matching controls (engine INI caveat).
Exit1: valid candidate exceeds the strict ceiling. Exit2: missing/invalid proof.
AI semantic differences are reported for review, never treated as cache failures.
"""
from __future__ import annotations
import argparse, copy, importlib.util, json, re, tempfile
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
REPLAY=module('behavior_replay_comparison',ROOT/'work/compare-behavior-performance-replays.py')
PHASE=module('native_phase_profile',ROOT/'work/profile-turn-phases.py')
InvalidEvidence=REPLAY.InvalidEvidence
ACCEPTED_BASELINE_MS=Decimal('57517')
OBSERVED_BASELINE_MS=57515
CEILING_MS=ACCEPTED_BASELINE_MS*Decimal('1.10')
NEW_SETTINGS=dict(AIAssaultEssentialSiegeUnits=2,AIAssaultFirstWaveMaximumTurns=1,
    AIAssaultWaveMaximumRecords=64,AIAssaultIncompleteDamagePercent=125,
    AIOffensiveProductionRoleRepairUnits=2,AIOffensiveProductionRecommendationSlack=2,
    AIOffensiveContributionRadius=2,AIAssaultAttackProgressStallTurns=24)
SETUP_FIELDS=('sourceSaveSHA256','turn','width','height','worldSize','worldType','gameSpeed','gameSpeedType','aliveMajorCount')

def require(condition,message):
    if not condition:raise InvalidEvidence(message)

def json_lines(path):
    try:
        raw=path.read_text(encoding='utf-8-sig')
        require(raw.endswith('\n'),f'{path.name}: incomplete health tail')
        rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
    except (OSError,UnicodeError,json.JSONDecodeError) as error:raise InvalidEvidence(f'{path}: {error}') from error
    require(bool(rows) and all(isinstance(row,dict) for row in rows),f'{path.name}: invalid health rows')
    return rows

def closure(folder,manifest):
    normal=REPLAY.read_json(folder/'normal-exit.json');watch=REPLAY.read_json(folder/'watcher-manifest.json')
    loaded=REPLAY.read_json(folder/'loaded-dll.json')
    require(manifest['Status']=='completed_game_closed_service_stopped','normal complete-game/service status missing')
    require(normal==manifest.get('NormalExit'),'normal-exit and manifest proof differ')
    require(normal.get('status')=='completed' and all(normal.get(key) is True for key in
        ('requested','quitDispatched','quitAcknowledged','gameExitConfirmed','serviceStopDispatched','serviceExitConfirmed','sessionFileAbsent')),'normal game/service closure not confirmed')
    require(normal.get('forcedTermination') is False and normal.get('mutationRetried') is False,'forced/retried closure cannot qualify')
    require(normal.get('GamePID')==manifest.get('PID')==watch.get('Game')==loaded.get('PID') and
        normal.get('GameStartTicks')==manifest.get('StartTicks')==watch.get('StartTicks')==loaded.get('StartTicks'),'game identity proofs differ')
    require(normal.get('ServicePID')==watch.get('Service') and type(normal.get('ServiceStartTicks')) is int and normal['ServiceStartTicks']>0,'service identity missing')
    guards=normal.get('GuardPIDs');ticks=normal.get('GuardStartTicks')
    require(isinstance(guards,list) and len(guards)==2 and len(set(guards))==2 and
        set(guards)=={watch.get('CpuWatcher'),watch.get('GpuMemoryWatcher')}==set(loaded.get('Watchers',[])), 'exact guard identity proof missing')
    require(isinstance(ticks,list) and len(ticks)==2 and all(type(value) is int and value>0 for value in ticks),'guard start proofs missing')
    require(str(loaded.get('SHA256','')).upper()==manifest['SHA256'].upper()==str(watch.get('ExpectedDLLSHA','')).upper(),'loaded native DLL proof differs')
    require(isinstance(loaded.get('Modules'),list) and loaded.get('Path') in loaded['Modules'],'loaded DLL module identity missing')
    require((folder/'complete.signal').is_file(),'verified completion signal missing')
    health={}
    for name,pid_key in (('cpu-temperature-health.jsonl','process'),('campaign-health.jsonl','pid')):
        rows=json_lines(folder/name)
        require(rows[0].get('event')=='armed' and rows[0].get(pid_key)==manifest['PID'] and rows[0].get('startTicks')==manifest['StartTicks'],f'{name}: original guarded game identity missing')
        require(rows[-1].get('event')=='disarmed' and rows[-1].get('reason')=='completion_signal',f'{name}: guard did not disarm on completion')
        require(not any(row.get('event') in ('kill','terminated','termination','stop','stopping','error','failed') for row in rows),f'{name}: abnormal guard event')
        health[name]=dict(rows=len(rows),last_event=rows[-1]['event'],reason=rows[-1]['reason'])
    return dict(normal=True,gamePID=manifest['PID'],startTicks=manifest['StartTicks'],guardPIDs=guards,health=health)

def setup(folder,manifest):
    record=REPLAY.read_json(folder/'game-setup.json')
    require(record==manifest.get('GameSetup'),'game-setup and manifest proof differ')
    require(all(key in record for key in SETUP_FIELDS),'game-setup fields missing')
    require(record['sourceSaveSHA256'].upper()==manifest['SaveSHA256'].upper() and record['turn']==manifest['StartTurn'],'setup source/turn mismatch')
    for key in ('width','height','aliveMajorCount'):require(type(record[key]) is int and record[key]>0,f'setup invalid {key}')
    for key in ('worldSize','gameSpeed'):require(type(record[key]) is int and record[key]>=0,f'setup invalid {key}')
    for key in ('worldType','gameSpeedType'):require(isinstance(record[key],str) and record[key],f'setup invalid {key}')
    return {key:record[key] for key in SETUP_FIELDS}

def timing(records,quality,turn):
    for key in ('gaps','conflicting_segment_files','incomplete_tails_skipped','clock_reversals'):
        require(not quality.get(key),f'native quality: {key}')
    require(quality.get('malformed_records')==0 and not quality.get('earlier_segments_missing'),'incomplete native archive')
    profile=PHASE.analyze(records,turn,quality=quality)
    require(profile['complete_native_boundary'],'dense turn lacks following native boundary')
    window=profile['native_round_window'];require(type(window.get('duration_ms')) is int and window['duration_ms']>0,'invalid full-turn duration')
    require(profile['coverage']['PLAN_calls']>0,'dense turn lacks native planner evidence')
    return dict(turn=turn,window=window,full_turn_ms=window['duration_ms'],PLAN_ms=profile['coverage']['PLAN_milliseconds_sum'],
        PLAN_calls=profile['coverage']['PLAN_calls'],complete=True,
        all_event_window=profile['native_all_event_window'],phase_warnings=profile.get('warnings',[]))

def native_configuration(records,quality):
    # Include tech/combat/class/promotion/building/domain rows as well as
    # settings. The phase reader's convenience configuration keeps settings
    # only; comparing that subset would miss changed combat configuration.
    raw={};config=[];job_values=set();raw_rows=0
    for selected in quality['headers']:
        with Path(selected['path']).open(encoding='utf-8-sig') as stream:
            next(stream)
            for line in stream:
                match=PHASE.RECORD.fullmatch(line.rstrip('\r\n'))
                if match and match[4]=='CONFIG_RAW':
                    value=re.fullmatch(r'([A-Za-z][A-Za-z0-9_:]*)=(-?\d+)',match[5])
                    require(value is not None,'malformed CONFIG_RAW payload')
                    key=value[1];require(key not in raw,'duplicate native configuration key');raw[key]=int(value[2]);raw_rows+=1
    for row in records:
        if row['category']=='CONFIG':config.append(row['values'])
        if 'JOBMANAGER_THREADS' in row['values']:job_values.add(row['values']['JOBMANAGER_THREADS'])
    require(bool(raw) and raw_rows==len(raw) and len(config)==1,'missing/duplicate/ambiguous native Summary configuration')
    require(all(type(value) is int for value in raw.values()),'noninteger CONFIG_RAW value')
    require({'setting:'+key for key in ('Enabled','DiagnosticsCategoryMask','DiagnosticsLevel','DiagnosticsSummaryInterval','DiagnosticsTacticalSampling')}.issubset(raw),'incomplete recorded diagnostic controls')
    require(config[0].get('effectiveLevel')==1,'native effective diagnostics not Summary')
    require(len(job_values)<=1,'native JOBMANAGER_THREADS changed')
    effective={key:value for key,value in config[0].items() if key!='fnv1a'}
    return dict(raw=raw,effective=effective,jobmanager_threads=next(iter(job_values)) if job_values else None)

def read(folder):
    folder=Path(folder);data=REPLAY.read(folder);manifest=data['manifest']
    require((manifest['StartTurn'],manifest['StopTurn'],manifest['ReturnPlayer'],manifest['DiagnosticLevel'])==(251,255,0,1),'wrong bounded Summary replay window')
    require(manifest['QuickCombat'] is True and manifest['QuickMovement'] is True,'quick controls differ from accepted fixture')
    require(data['view']['recorded'] and data['view']['strategic'] is False,'actual standard view proof missing')
    require(data['sampling']['recorded'] and data['sampling']['enabled'] is False,'actual tactical sampling-off proof missing')
    records,quality=PHASE.load(folder/'native-segments',manifest['NativeRun'])
    return dict(data=data,records=records,quality=quality,closure=closure(folder,manifest),setup=setup(folder,manifest),
        timing=timing(records,quality,253),config=native_configuration(records,quality))

def config_comparison(before,after):
    left,right=before['raw'],after['raw'];added=set(right)-set(left);removed=set(left)-set(right)
    require(added=={'setting:'+key for key in NEW_SETTINGS} and not removed,'unexpected XML configuration additions/removals')
    require(all(right['setting:'+key]==value for key,value in NEW_SETTINGS.items()),'new AI XML controls differ from approved values')
    require(all(right[key]==value for key,value in left.items()),'existing XML control changed')
    require(before['effective']==after['effective'],'effective Summary configuration differs')
    a,b=before['jobmanager_threads'],after['jobmanager_threads']
    require(a is None or b is None or a==b,'native JOBMANAGER_THREADS differs')
    return dict(existing_settings_equal=True,existing_count=len(left),intentional_new_settings=NEW_SETTINGS,
        effective_summary_equal=True,JOBMANAGER_THREADS=dict(baseline=a,candidate=b,equal=a==b if a is not None and b is not None else None),
        engine_INI_archived=False,engine_configuration_equality='unknown',
        caveat='Game-setup proves map/speed; prepared manifests prove quick/view/sampling. Engine INI and logging/threading snapshots were not archived for baseline; equality is not inferred. No intended INI changes are evidence of intent, not an archived control proof.')

def performance_accept(milliseconds):return Decimal(str(milliseconds))<=CEILING_MS

def compare(baseline,candidate,expected_candidate_dll=None):
    left,right=read(baseline),read(candidate)
    require(left['data']['metadata']==right['data']['metadata'],'source/window/mod/preparation controls differ')
    require(left['setup']==right['setup'],'game setup map/speed/census metadata differs')
    require(left['data']['snapshots']['before']==right['data']['snapshots']['before'],'initial nonempty world census differs')
    require(left['timing']['full_turn_ms']==OBSERVED_BASELINE_MS,'baseline native timing is not the accepted fresh control')
    if expected_candidate_dll:require(right['data']['manifest']['SHA256'].upper()==expected_candidate_dll.upper(),'candidate loaded DLL is not the expected build')
    controls=config_comparison(left['config'],right['config'])
    semantics=REPLAY.compare(baseline,candidate)
    passed=performance_accept(right['timing']['full_turn_ms'])
    return dict(schema=1,status='performance_pass_with_engine_configuration_caveat' if passed else 'performance_regression',performance_pass=passed,
        baseline=str(Path(baseline).resolve()),candidate=str(Path(candidate).resolve()),
        native_runs=[left['data']['manifest']['NativeRun'],right['data']['manifest']['NativeRun']],
        loaded_DLL_SHA256=[left['data']['manifest']['SHA256'],right['data']['manifest']['SHA256']],
        source_and_before_census_equal=True,recorded_controls=controls,normal_closure=[left['closure'],right['closure']],
        timing=dict(accepted_baseline_ms=str(ACCEPTED_BASELINE_MS),observed_baseline_ms=left['timing']['full_turn_ms'],
            accepted_minus_observed_ms=str(ACCEPTED_BASELINE_MS-left['timing']['full_turn_ms']),strict_ceiling_ms=str(CEILING_MS),
            candidate_ms=right['timing']['full_turn_ms'],regression_percent_vs_accepted=float((Decimal(right['timing']['full_turn_ms'])/ACCEPTED_BASELINE_MS-1)*100),
            baseline=left['timing'],candidate=right['timing']),
        semantic_review=dict(expected_AI_changes=True,review_required=True,acceptance_failure=False,
            all_compared_semantics_equal=semantics['all_compared_semantics_equal'],after_census_equal=semantics['after_census_equal'],native_semantics=semantics['native_semantics']),
        limits='Timing uses identical legacy-comparable event boundaries, not CPU/exclusive phase cost. Accepted57.517s differs from archived57.515s by2ms; strict63.2687s ceiling retained explicitly. Engine INI equality is unknown. One replay can qualify timing under recorded controls, not establish AI efficacy, long-run conquest or general performance.')

def self_test():
    checks=0
    def check(ok,label):
        nonlocal checks
        if not ok:raise AssertionError(label)
        checks+=1
    with tempfile.TemporaryDirectory(prefix='civ5-ai-followup-gate-') as temporary:
        root=Path(temporary);a=root/'baseline';b=root/'candidate'
        def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value)+'\n',encoding='utf-8')
        def fixture(folder,run,duration,new):
            pid=100 if not new else 200;dll=('B' if not new else 'C')*64
            prepared=dict(turn=251,autoplay=4,observer=True,activePlayer=8,pausePlayer=8,diagnostics=1,quickCombat=True,quickMovement=True,
                sourceMode='human',sourceActivePlayer=0,restoredAutoplay=0,viewAPIAvailable=True,strategicView=False,viewModeOriginal=False,
                tacticalSamplingRequested='off',tacticalSamplingAPIAvailable=True,tacticalSamplingValueValid=True,tacticalSampling=False,tacticalSamplingOriginal=False)
            stopped=dict(turn=255,autoplay=0,activePlayer=0,human=True,observer=False,returnPlayerAlive=True,
                tacticalSamplingAPIAvailable=True,tacticalSamplingValueValid=True,tacticalSampling=False)
            normal=dict(status='completed',requested=True,quitDispatched=True,quitAcknowledged=True,gameExitConfirmed=True,serviceStopDispatched=True,
                serviceExitConfirmed=True,sessionFileAbsent=True,forcedTermination=False,mutationRetried=False,GamePID=pid,GameStartTicks=123,
                ServicePID=pid+1,ServiceStartTicks=456,GuardPIDs=[pid+2,pid+3],GuardStartTicks=[457,458])
            setup=dict(utc='fixture',sourceSaveSHA256='A'*64,turn=251,width=88,height=58,worldSize=3,worldType='WORLDSIZE_STANDARD',gameSpeed=2,gameSpeedType='GAMESPEED_STANDARD',aliveMajorCount=8)
            manifest=dict(Status='completed_game_closed_service_stopped',SaveSHA256='A'*64,SaveSHA256After='A'*64,StartTurn=251,StopTurn=255,ReturnPlayer=0,
                DiagnosticLevel=1,QuickCombat=True,QuickMovement=True,SHA256=dll,ExpectedDLLSHA256=dll,SourceMode='human',ViewMode='standard',TacticalSamplingMode='off',
                NativeRun=run,EnabledMods=[dict(ModID='fixture',Version=1)],Prepared=prepared,Stopped=stopped,PID=pid,StartTicks=123,NormalExit=normal,GameSetup=setup)
            write(folder/'replay-manifest.json',manifest);write(folder/'normal-exit.json',normal);write(folder/'game-setup.json',setup)
            write(folder/'watcher-manifest.json',dict(Game=pid,StartTicks=123,Service=pid+1,CpuWatcher=pid+2,GpuMemoryWatcher=pid+3,ExpectedDLLSHA=dll))
            write(folder/'loaded-dll.json',dict(PID=pid,StartTicks=123,SHA256=dll,Path='fixture.dll',Modules=['fixture.dll'],Watchers=[pid+2,pid+3]))
            (folder/'complete.signal').write_text('complete\n')
            for name,key in (('cpu-temperature-health.jsonl','process'),('campaign-health.jsonl','pid')):
                (folder/name).write_text(json.dumps(dict(event='armed',startTicks=123,**{key:pid}))+'\n'+json.dumps(dict(event='disarmed',reason='completion_signal'))+'\n')
            for tag,turn in (('before',251),('after',255)):
                snapshot=dict(expectedTurn=turn,unitColumns=list(REPLAY.UNIT_COLUMNS),cityColumns=list(REPLAY.CITY_COLUMNS),players=[dict(owner=0,civilization='CIV0',team=0,human=tag=='after',minor=False,barbarian=False,units=[[1,3,2,4,5,100,120,2,10,0]],cities=[[7,'Fixture',0,2,4,0,400,2500,9]],wars=[])])
                write(folder/f'world-{tag}.json',snapshot)
            raw=dict(Enabled=1,DiagnosticsCategoryMask=63,DiagnosticsLevel=0,DiagnosticsSummaryInterval=1,DiagnosticsTacticalSampling=0)
            if new:raw.update(NEW_SETTINGS)
            lines=[f'STACKDIAG|SESSION|run={run} segment=0 build=fixture level=1']
            for key,value in raw.items():lines.append(f'STACKDIAG|100|turn=251|player=-1|CONFIG_RAW|setting:{key}={value}')
            lines.extend(['STACKDIAG|100|turn=251|player=-1|CONFIG|fnv1a=AAAA map=88x58 effectiveLevel=1 summaryEvery=1 detailEvery=10 playerFilter=-1',
                'STACKDIAG|1000|turn=253|player=0|CITY_DEFENSE|fixture=1','STACKDIAG|1001|turn=253|player=0|PLAN|target=1:1 states=2 assignments=1 milliseconds=1',
                f'STACKDIAG|{1000+duration}|turn=254|player=0|CITY_DEFENSE|fixture=2'])
            path=folder/'native-segments/fixture.log';path.parent.mkdir(exist_ok=True);path.write_text('\n'.join(lines)+'\n')
        fixture(a,'Stacking-baseline',57515,False);fixture(b,'Stacking-candidate',63268,True)
        check(compare(a,b)['performance_pass'],'last whole-ms below strict ceiling')
        check(performance_accept('63268.7') and not performance_accept('63268.7001'),'exact+10% decimal boundary')
        fixture_log=b/'native-segments/fixture.log';original_log=fixture_log.read_text();fixture_log.write_text(original_log.replace('64268','64269'))
        check(not compare(a,b)['performance_pass'],'first whole-ms above strict ceiling');fixture_log.write_text(original_log)
        original=(b/'normal-exit.json').read_bytes();(b/'normal-exit.json').unlink()
        try:compare(a,b)
        except InvalidEvidence:checks+=1
        else:raise AssertionError('missing closure admitted')
        (b/'normal-exit.json').write_bytes(original)
        fixture_log.write_text(original_log[:original_log.rindex('STACKDIAG|64268')])
        try:compare(a,b)
        except InvalidEvidence:checks+=1
        else:raise AssertionError('partial dense turn admitted')
        fixture_log.write_text(original_log)
        setup=REPLAY.read_json(b/'game-setup.json');setup['width']=90;write(b/'game-setup.json',setup)
        manifest=REPLAY.read_json(b/'replay-manifest.json');manifest['GameSetup']=setup;write(b/'replay-manifest.json',manifest)
        try:compare(a,b)
        except InvalidEvidence:checks+=1
        else:raise AssertionError('changed game setup admitted')
        fixture(b,'Stacking-candidate',63268,True)
        after=REPLAY.read_json(b/'world-after.json');after['players'][0]['units'][0][4]=10;write(b/'world-after.json',after)
        result=compare(a,b);check(result['performance_pass'] and not result['semantic_review']['after_census_equal'],'expected AI semantic difference does not fail timing')
        (b/'campaign-health.jsonl').write_text(json.dumps(dict(event='armed',pid=200,startTicks=123))+'\n')
        try:compare(a,b)
        except InvalidEvidence:checks+=1
        else:raise AssertionError('armed guard without disarm admitted')
    return dict(self_test='passed',checks=checks,game_calls=0)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline',type=Path);parser.add_argument('--candidate',type=Path)
    parser.add_argument('--expected-candidate-dll');parser.add_argument('--output',type=Path);parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:print(json.dumps(self_test(),indent=2));return 0
    if not args.baseline or not args.candidate:parser.error('--baseline and --candidate required')
    try:result=compare(args.baseline,args.candidate,args.expected_candidate_dll);code=0 if result['performance_pass'] else 1
    except (InvalidEvidence,ValueError,OSError) as error:result=dict(schema=1,status='invalid_or_incomplete_evidence',performance_pass=None,error=str(error));code=2
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],performance_pass=result['performance_pass'],timing=result.get('timing'),error=result.get('error')),indent=2));return code

if __name__=='__main__':raise SystemExit(main())
