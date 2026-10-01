"""Start a fresh same-map campaign with any installed DLL; hand control to the monitor.

Parameterized copy of start-offensive-campaign.py (which is pinned to DLL102).
Launch the game with start-short-performance-test.ps1, restore the mods with
ensure-benchmark-mods.py, run this, then work/monitor-live-campaign.py.

One startup per fresh process/run. No reconnection, resumed mutations or gameplay
edits. The extracted prefix ends immediately after the existing continuation;
the bounded replay's polling/shutdown controller is never started concurrently.
"""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,inspect,json,shutil,sys,textwrap
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('behavior_start',ROOT/'work/run-behavior-replay.py')
behavior=importlib.util.module_from_spec(spec);spec.loader.exec_module(behavior)
perf=behavior.perf
SOURCE=ROOT/'work/test-runs/campaign47-20260930-1735/Stack DLL47 Fresh T000.Civ5Save'
SOURCE_SHA='EA96E61517D6A579CB5DE5492C9DFC0E7D448CD506A9E61C5800CD856A41B461'

def startup_function():
    source=textwrap.dedent(inspect.getsource(behavior.BehaviorReplay.execute))
    tree=ast.parse(source);function=tree.body[0]
    indices=[i for i,n in enumerate(function.body) if isinstance(n,ast.Assign) and
        any(isinstance(t,ast.Attribute) and isinstance(t.value,ast.Name) and t.value.id=='self' and t.attr=='deadline' for t in n.targets)]
    assert len(indices)==1,'Existing startup boundary changed'
    function.body=function.body[:indices[0]]
    rendered=ast.unparse(function)
    assert rendered.count("'continue-bounded-behavior'")==1
    assert 'behavior-status' not in rendered and 'while True' in rendered # Existing load wait only.
    namespace=dict(vars(behavior));exec(compile(tree,'existing tested campaign startup','exec'),namespace)
    return namespace['execute'],hashlib.sha256(source.encode()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--dll-sha');p.add_argument('--save-prefix');p.add_argument('--source-commit')
    p.add_argument('--target-turn',type=int,default=350)
    p.add_argument('--self-test',action='store_true');a=p.parse_args()
    start,startup_sha=startup_function()
    if a.self_test:
        print(json.dumps({'startup_prefix_valid':True,'game_calls':0,'source_sha256':startup_sha}));return 0
    run=a.run_dir.resolve();assert run.is_relative_to(ROOT/'work/test-runs')
    assert a.dll_sha and a.save_prefix and a.source_commit,'--dll-sha, --save-prefix and --source-commit are required'
    DLL_SHA=a.dll_sha.upper()
    assert perf.sha(SOURCE)==SOURCE_SHA
    watcher=json.loads((run/'watcher-manifest.json').read_text(encoding='utf-8-sig'))
    assert watcher['ExpectedDLLSHA']==DLL_SHA
    assert not (run/'campaign-manifest.json').exists() and not (run/'status.json').exists()
    expected_rows=json.loads((run/'expected-mods.json').read_text())
    assert isinstance(expected_rows,list) and len(expected_rows)==5
    expected={row['ModID'].lower():int(row['Version']) for row in expected_rows}
    assert len(expected)==5
    args=SimpleNamespace(run_dir=run,save=SOURCE,save_sha=SOURCE_SHA,start_turn=0,stop_turn=a.target_turn,
        return_player=0,source_mode='human',view_mode='standard',tactical_sampling='off',
        watch_city='Panama City',game_pid=watcher['Game'],start_ticks=watcher['StartTicks'],
        expected_dll_sha=DLL_SHA,expected_mods=expected,session=behavior.tuner.DEFAULT_SESSION,
        command_timeout=120,load_timeout=240,maximum_seconds=28800,resume_prepared=False,
        quit_after_complete=False,logs=Path(r"C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5\Logs"))
    replay=behavior.BehaviorReplay(args)
    try:
        start(replay)
        assert perf.sha(SOURCE)==SOURCE_SHA
        manifest=dict(Status='running',CreatedUTC=perf.utc(),Game=args.game_pid,StartTicks=args.start_ticks,
            TargetTurn=a.target_turn,ReturnPlayer=0,DLLSHA256=DLL_SHA,SourceCommit=a.source_commit,
            SourceSave=str(SOURCE),SourceSaveSHA256=SOURCE_SHA,NativeRun=replay.manifest['NativeRun'],
            LoadedDLLPath=replay.manifest['InstalledDLL'],DiagnosticsLevel=1,PollingSeconds=60,
            SavePrefix=a.save_prefix,BaselineRun='campaign102-20261001-offense01',
            StartupSourceSHA256=startup_sha,Limits='Same source/map/roster as campaign102; all post-load AI choices use the installed DLL. Summary diagnostics; no per-turn Lua observer injection.')
        shutil.copyfile(ROOT/'work/test-runs/campaign47-20260930-1735/checkpoint.lua',run/'checkpoint.lua')
        perf.write_json(run/'campaign-manifest.json',manifest)
        print(json.dumps(manifest));return 0
    except Exception as error:
        replay.record_failure({'utc':perf.utc(),'error':str(error),'retried':False})
        raise

if __name__=='__main__':sys.exit(main())
