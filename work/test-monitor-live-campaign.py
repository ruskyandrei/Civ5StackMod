"""Offline campaign-monitor prefix/collision and unchanged stop/failure checks.

All engine/process services are replaced with explicit mocks before main runs.
No game, tuner service, controller, UI or subprocess is used.
"""
from pathlib import Path
import importlib.util,json,sys,tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('campaign_monitor',ROOT/'work/monitor-live-campaign.py')
monitor=importlib.util.module_from_spec(spec);spec.loader.exec_module(monitor)
checks=0
def check(ok,name):
    global checks
    if not ok:raise AssertionError(name)
    checks+=1
check(monitor.final_save_name({},350)=='Stack DLL47 Campaign T350 20260930-1735','exact legacy default')
prefix='Stack DLL102 Campaign 20261001-1540'
check(monitor.final_save_name({'SavePrefix':prefix},350)==prefix+' T350','manifest prefix')
for value in ('','../other','x\\y','C:other','x\nnext',' x','x ','x.','x*',None,False):
    try:monitor.final_save_name({'SavePrefix':value},350)
    except ValueError:checks+=1
    else:raise AssertionError('unsafe prefix accepted: '+repr(value))

with tempfile.TemporaryDirectory(prefix='campaign-monitor-fixture-',dir=ROOT/'work/test-runs') as temporary:
    base=Path(temporary);monitor.SAVE_ROOT=base/'saves';monitor.SAVE_ROOT.mkdir();monitor.LOG_ROOT=base/'logs';monitor.LOG_ROOT.mkdir()
    pure_run=base/'paths';pure_run.mkdir();manifest={'SavePrefix':prefix}
    name,path,archive=monitor.final_save_paths(pure_run,manifest,350)
    path.write_bytes(b'original-user-save')
    try:monitor.final_save_paths(pure_run,manifest,350)
    except ValueError:checks+=1
    else:raise AssertionError('existing game save accepted')
    check(path.read_bytes()==b'original-user-save','game collision preserved');path.unlink();archive.write_bytes(b'original-archive')
    try:monitor.final_save_paths(pure_run,manifest,350)
    except ValueError:checks+=1
    else:raise AssertionError('existing archive accepted')
    check(archive.read_bytes()==b'original-archive','archive collision preserved');archive.unlink()

    def scenario(label,checkpoints,fail_session=False,collision=False,bad_prefix=False,proof_failure=False):
        run=base/label;run.mkdir();signal=run/'complete.signal'
        data=dict(Game=111,StartTicks=222,NativeRun='Stacking-fixture-p111-r1',TargetTurn=350,SavePrefix='Fixture '+label)
        if bad_prefix:data['SavePrefix']='../escape'
        guards=dict(Signal=str(signal),GpuMemoryWatcher=333,CpuWatcher=444)
        (run/'campaign-manifest.json').write_text(json.dumps(data));(run/'watcher-manifest.json').write_text(json.dumps(guards));(run/'checkpoint.lua').write_text('return fixture_checkpoint')
        calls=[];pending=list(checkpoints)
        if collision:(run/(monitor.final_save_name(data,350)+'.Civ5Save')).write_bytes(b'preserved')
        def proof(game,start,watchers):
            check((game,start,watchers)==(111,222,[333,444]),'original exact process/guard proof')
            if proof_failure:raise RuntimeError('exact guard lost')
            return dict(PID=111,StartTicks=222)
        def service(session,action,request,timeout):
            calls.append(request['source']);check(session==monitor.tuner.DEFAULT_SESSION and action=='exec','sole existing client/session')
            if fail_session:return dict(ok=False,error='session lost')
            lua=request['source']
            if 'UI.SaveGame(' in lua:
                file=monitor.SAVE_ROOT/(monitor.final_save_name(data,350)+'.Civ5Save');file.write_bytes(b'new-fixture-save');return dict(ok=True,values=[350])
            if 'replace-dead' in lua:raise AssertionError('labels must not be Lua')
            if 'Game.SetAIAutoPlay' in lua and 'fixture_checkpoint' not in lua:return dict(ok=True,values=[1])
            require=pending.pop(0);return dict(ok=True,values=[require])
        monitor.perf.exact_process=proof;monitor.tuner.call_service=service;monitor.time.sleep=lambda seconds:None
        old_argv=sys.argv;sys.argv=['monitor','--run-dir',str(run),'--poll-seconds','60']
        try:
            try:result=monitor.main()
            except ValueError:
                if not bad_prefix:raise
                result='rejected_before_engine'
        finally:sys.argv=old_argv
        return run,signal,calls,result
    def status(turn,observer=False,autoplay=0,majors=None):
        return dict(turn=turn,observer=observer,autoplay=autoplay,pausePlayer=-1,diagnostics=1,livingMajors=[0] if majors is None else majors,replayCount=0,cities=[],wars=[])
    run,signal,calls,result=scenario('complete',[status(350)])
    check(result==0 and signal.is_file(),'normal target stop/completion')
    final=json.loads((run/'status.json').read_text());check(final['state']=='completed' and 'Fixture complete T350' in final['save'],'prefix used for final save')
    check((run/'Fixture complete T350.Civ5Save').read_bytes()==b'new-fixture-save','new save archived')
    run,signal,calls,result=scenario('session-lost',[status(350)],fail_session=True)
    check(result==1 and len(calls)==1 and not signal.exists(),'session failure no reconnect/retry/save')
    run,signal,calls,result=scenario('guard-lost',[status(350)],proof_failure=True)
    check(result==1 and not calls and not signal.exists(),'guard failure before engine call')
    run,signal,calls,result=scenario('collision',[status(350)],collision=True)
    check(result==1 and len(calls)==1 and not any('UI.SaveGame(' in row for row in calls),'archive collision before save mutation')
    check((run/'Fixture collision T350.Civ5Save').read_bytes()==b'preserved','archive collision not overwritten')
    run,signal,calls,result=scenario('bad-prefix',[status(350)],bad_prefix=True)
    check(result=='rejected_before_engine' and not calls,'invalid prefix before engine call')
    run,signal,calls,result=scenario('dead-return',[status(349,True,1,[1]),status(350,False,0,[1])])
    check(result==0 and any('Game.SetAIAutoPlay(1,1)' in row for row in calls),'living-major correction preserved')
print(json.dumps(dict(self_test='passed',checks=checks,game_calls=0,service_calls='mocked_only'),indent=2))
