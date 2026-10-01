"""Monitor one already-started campaign; no reloads, observer injection or retries.

Reads compact city/status snapshots and bounded replay pages roughly once a
minute. The native guards archive logs independently. Only mutations are an
alive return-player correction if needed, final halt, flush and unique save.
"""
from pathlib import Path
import argparse, importlib.util, json, os, sys, time
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('perf_live',ROOT/'work/run-performance-replay.py')
perf=importlib.util.module_from_spec(spec);spec.loader.exec_module(perf)
tuner=perf.tuner
SAVE_ROOT=Path(r"C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5\ModdedSaves\single")
LOG_ROOT=Path(r"C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5\Logs")

def final_save_name(manifest,turn):
    if type(turn) is not int or turn<0:raise ValueError('Final save requires a nonnegative integer turn')
    if 'SavePrefix' not in manifest:
        return f'Stack DLL47 Campaign T{turn:03d} 20260930-1735'
    prefix=manifest['SavePrefix']
    if (not isinstance(prefix,str) or not prefix or prefix!=prefix.strip() or prefix.endswith('.')
            or any(ord(char)<32 or char in '<>:"/\\|?*' for char in prefix)):
        raise ValueError('SavePrefix must be a nonempty Windows filename prefix without path/control characters or trailing dots/spaces')
    return f'{prefix} T{turn:03d}'

def final_save_paths(run,manifest,turn):
    name=final_save_name(manifest,turn);path=SAVE_ROOT/(name+'.Civ5Save');archive=run/path.name
    if path.exists() or archive.exists():raise ValueError('Final save or archived save name exists; never overwrite')
    return name,path,archive

def utc(): return datetime.now(timezone.utc).isoformat()
def write(path,value):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--poll-seconds',type=int,default=60)
    args=parser.parse_args();run=args.run_dir.resolve()
    if not run.is_relative_to(ROOT/'work/test-runs') or not 15<=args.poll_seconds<=120:
        parser.error('Expected run below work/test-runs and polling15-120s')
    manifest=json.loads((run/'campaign-manifest.json').read_text(encoding='utf-8-sig'))
    final_save_name(manifest,0) # Validate an explicit prefix before any engine request.
    guards=json.loads((run/'watcher-manifest.json').read_text(encoding='utf-8-sig'))
    target=manifest['TargetTurn'];deadline=time.monotonic()+28800
    signal=Path(guards['Signal']);state_path=run/'status.json'
    if signal.exists() or state_path.exists(): raise ValueError('Fresh monitor required; no automatic resume')
    (run/'checkpoints').mkdir(exist_ok=True);(run/'replay-pages').mkdir(exist_ok=True)
    source=(run/'checkpoint.lua').read_text(encoding='utf-8')
    sequence=0;cursor=0;last_turn=-1;return_player=0;last_data=None
    write(run/'monitor-manifest.json',dict(pid=os.getpid(),startedUTC=utc(),target=target,pollSeconds=args.poll_seconds,
        savePrefix=manifest.get('SavePrefix'),saveNaming='manifest_prefix' if 'SavePrefix' in manifest else 'legacy_default'))
    def event(action,**values):
        row=dict(utc=utc(),action=action,**values)
        with (run/'monitor-events.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    def call(lua,label):
        nonlocal sequence
        sequence+=1;stem=f'{sequence:05d}-{label}'
        (run/(stem+'.lua')).write_text(lua,encoding='utf-8')
        started=time.monotonic()
        result=tuner.call_service(tuner.DEFAULT_SESSION,'exec',dict(context='InGame',source=lua,timeout=120),120)
        write(run/(stem+'.json'),dict(utc=utc(),seconds=time.monotonic()-started,result=result))
        if not result.get('ok'):raise RuntimeError(result.get('error','Lua call failed; not retried'))
        return result.get('values',[None])[0]
    def proof():
        return perf.exact_process(manifest['Game'],manifest['StartTicks'],[guards['GpuMemoryWatcher'],guards['CpuWatcher']])
    def pages(total):
        nonlocal cursor
        # Bound each checkpoint's historical work; never return every replay at once.
        for batch in range(8):
            if cursor>=total:break
            end=min(cursor+256,total)
            lua=f'local out={{start={cursor},next={end},total=Game.GetNumReplayMessages(),messages={{}}}};for i={cursor},{end-1} do local m=Game.GetReplayMessage(i);if m and (m.Type==1 or m.Type==3 or m.Type==4) then m.index=i;out.messages[#out.messages+1]=m end end;return out'
            data=call(lua,'replay-page')
            if not isinstance(data,dict) or data.get('start')!=cursor or data.get('next')!=end:raise ValueError('Replay cursor mismatch')
            write(run/'replay-pages'/f'{cursor:07d}-{end:07d}.json',dict(utc=utc(),data=data))
            cursor=end
    def save_and_finish(data,complete,reason):
        # Already human/stopped or explicitly halted beforehand; no unit orders.
        turn=data['turn'];name,path,save_archive=final_save_paths(run,manifest,turn)
        call("assert(Game.GetAIAutoPlay()==0 and not Players[Game.GetActivePlayer()]:IsObserver(),'Autoplay must be stopped');Game.FlushStackingDiagnostics();UI.SaveGame("+tuner.lua_string(name)+");return Game.GetGameTurn()",'final-save')
        if not path.is_file():raise ValueError('Final save absent')
        import shutil
        if save_archive.exists():raise ValueError('Archived final save name appeared; never overwrite')
        # Exclusive destination creation also covers a collision appearing
        # between the preflight and copy. Preserve existing archive bytes.
        with path.open('rb') as saved,save_archive.open('xb') as archived:
            shutil.copyfileobj(saved,archived)
        shutil.copystat(path,save_archive)
        # Preserve the final partial segment before guards disarm.
        logs=LOG_ROOT
        archive=run/'native-segments';archive.mkdir(exist_ok=True)
        import re
        for file in logs.glob(f'Stacking-*-p{manifest["Game"]}-*.log'):
            with file.open('rb') as stream:raw=stream.read()
            header=raw.split(b'\n',1)[0].decode('utf-8-sig',errors='replace')
            match=re.search(r'run=([^ ]+) segment=(\d+)',header)
            if match and match[1]==manifest['NativeRun']:
                dest=archive/f'{match[1]}-segment-{int(match[2]):06d}.log'
                if not dest.exists() or dest.stat().st_size<=len(raw):dest.write_bytes(raw)
        final=dict(utc=utc(),state='completed' if complete else 'stopped_early',reason=reason,data=data,replayCursor=cursor,save=str(path),saveSHA256=perf.sha(path))
        write(state_path,final);signal.write_text(reason+'\n',encoding='utf-8')
        event(final['state'],turn=turn,save=str(path),reason=reason)
    try:
        event('started',target=target)
        while time.monotonic()<deadline:
            if signal.exists():raise RuntimeError('Completion signal unexpectedly appeared')
            proof();data=call(source,'checkpoint');last_data=data
            if not isinstance(data,dict) or data.get('turn',-1)<last_turn:raise ValueError('Unexpected loaded game/turn regression')
            last_turn=data['turn'];now=utc()
            write(run/'checkpoints'/f'turn-{last_turn:06d}-{sequence:05d}.json',dict(utc=now,data=data))
            write(state_path,dict(utc=now,state='running',target=target,replayCursor=cursor,data=data))
            event('checkpoint',turn=last_turn,autoplay=data['autoplay'],cities=len(data.get('cities',[])),wars=len(data.get('wars',[])))
            pages(data['replayCount'])
            if data['diagnostics']!=1:raise ValueError('Summary diagnostics changed; no automatic override')
            majors=data.get('livingMajors',[])
            if last_turn>=target:
                if data['observer'] or data['autoplay']:
                    if not majors:raise ValueError('No living major available for stop')
                    player=return_player if return_player in majors else majors[0]
                    data=call(f'if Game.GetAIAutoPlay()==0 and Players[Game.GetActivePlayer()]:IsObserver() then Game.SetAIAutoPlay(1,{player}) end;Game.SetAIAutoPlay(0,{player});'+source,'target-stop')
                save_and_finish(data,True,'target_reached');return 0
            if not data['observer'] or data['autoplay']==0:
                if data['observer']:raise ValueError('Zero counter still observing below target')
                save_and_finish(data,False,'autoplay_stopped_before_target');return 0
            if data['pausePlayer']>=0:raise ValueError('Autoplay was paused; do not resume without user instruction')
            if return_player not in majors:
                if not majors:raise ValueError('No living major available')
                return_player=majors[0];remaining=target-last_turn
                call(f'assert(Players[Game.GetActivePlayer()]:IsObserver());if Game.GetAIAutoPlay()=={remaining} then Game.SetAIAutoPlay({remaining+1},{return_player}) end;Game.SetAIAutoPlay({remaining},{return_player});return Game.GetAIAutoPlay()','replace-dead-return-player')
                event('return_player_changed',player=return_player,remaining=remaining)
            time.sleep(args.poll_seconds)
        raise RuntimeError('Eight-hour monitor ceiling; guards also expire. Manual follow-up required')
    except Exception as error:
        write(state_path,dict(utc=utc(),state='failed',error=str(error),data=last_data,replayCursor=cursor))
        event('failed',error=str(error));return 1

if __name__=='__main__':sys.exit(main())
