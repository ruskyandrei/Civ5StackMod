"""Vanilla-VP autoplay benchmark: create a fresh T0 save, or autoplay a save to a target turn.

  vpbench.py newgame --run NAME --dll-sha SHA --save-name "VPBench T000"
  vpbench.py run     --run NAME --dll-sha SHA --save PATH --target-turn 250 --final-save-name "..."

Each command launches its own game process (CPU temperature guard + tuner service),
enables and activates the benchmark mods, and quits the game when finished.
Recording is read-only: a turn counter poll every few seconds, a compact
city/war snapshot when the turn changes, and the engine's own replay messages at the end.
"""
from pathlib import Path
import argparse, json, shutil, subprocess, sys, time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import civ5_tuner as tuner

PY = sys.executable
PWSH = r'C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
SAVES = Path(r"C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5\ModdedSaves\single")
MODS = ROOT / 'work/test-runs/c102-t269-source/expected-mods.json'
SESSION = tuner.DEFAULT_SESSION

NEWGAME = r'''
PreGame.SetLeaderName(0,"");PreGame.SetCivilizationDescription(0,"");PreGame.SetCivilizationShortDescription(0,"");PreGame.SetCivilizationAdjective(0,"")
for i=0,GameDefines.MAX_MAJOR_CIVS-1 do PreGame.SetCivilization(i,-1);PreGame.SetTeam(i,i) end
local world=GameInfo.Worlds.WORLDSIZE_STANDARD
PreGame.SetRandomWorldSize(false);PreGame.SetWorldSize(world.ID);PreGame.SetNumMinorCivs(world.DefaultMinorCivs)
PreGame.SetLoadWBScenario(false)
local map=GameInfo.MapScripts{FileName="Assets\\Maps\\Continents.lua"}()
assert(map,'Continents map script missing')
PreGame.SetRandomMapScript(false);PreGame.SetMapScript(map.FileName)
PreGame.SetGameSpeed(GameInfo.GameSpeeds.GAMESPEED_STANDARD.ID)
PreGame.SetEra(GameInfo.Eras.ERA_ANCIENT.ID)
PreGame.SetHandicap(0,GameInfo.HandicapInfos.HANDICAP_PRINCE.ID)
for row in GameInfo.Victories() do PreGame.SetVictory(row.ID,true) end
PreGame.SetMaxTurns(0);PreGame.ResetGameOptions();PreGame.ResetMapOptions()
PreGame.SetSlotStatus(0,SlotStatus.SS_TAKEN)
for i=1,GameDefines.MAX_MAJOR_CIVS-1 do
 if i<world.DefaultPlayers then PreGame.SetSlotStatus(i,SlotStatus.SS_COMPUTER) else PreGame.SetSlotStatus(i,SlotStatus.SS_CLOSED) end
end
PreGame.SetCivilization(1,GameInfo.Civilizations.CIVILIZATION_ZULU.ID)
PreGame.SetCivilization(2,GameInfo.Civilizations.CIVILIZATION_AZTEC.ID)
local out={world=world.Type,players=world.DefaultPlayers,minors=PreGame.GetNumMinorCivs(),map=PreGame.GetMapScript(),speed=PreGame.GetGameSpeed(),slots={}}
for i=0,world.DefaultPlayers do out.slots[#out.slots+1]={slot=i,status=PreGame.GetSlotStatus(i),civ=PreGame.GetCivilization(i)} end
return out
'''
START = "PreGame.SetPersistSettings(false);Events.SerialEventStartGame();UIManager:SetUICursor(1);return 'start requested'"
CONTINUE = "assert(not Controls.ActivateButton:IsHidden(),'Loading is not complete');assert(not PreGame.IsMultiplayerGame(),'Single player only');Events.LoadScreenClose();Game.SetPausePlayer(-1);UI.SetDontShowPopups(false);return 'continued'"
SETUP = r'''
local out={turn=Game.GetGameTurn(),activePlayer=Game.GetActivePlayer(),speed=GameInfo.GameSpeeds[Game.GetGameSpeedType()].Type,
 world=GameInfo.Worlds[Map.GetWorldSize()].Type,map=PreGame.GetMapScript(),plots=Map.GetNumPlots(),version=(Game.GetDLLVersion and Game.GetDLLVersion() or ''),diagnostics=(Game.GetStackingDiagnosticsLevel and Game.GetStackingDiagnosticsLevel() or -1),players={}}
for owner=0,63 do local p=Players[owner]
 if p and p:IsEverAlive() and not p:IsBarbarian() then local civ=GameInfo.Civilizations[p:GetCivilizationType()]
  out.players[#out.players+1]={owner=owner,civilization=civ and civ.Type or '',minor=p:IsMinorCiv(),human=p:IsHuman(),handicap=GameInfo.HandicapInfos[p:GetHandicapType()].Type} end end
return out
'''
TURN = "return {turn=Game.GetGameTurn(),autoplay=Game.GetAIAutoPlay(),pause=Game.GetPausePlayer()}"
CHECKPOINT = r'''
local active=Game.GetActivePlayer()
local out={turn=Game.GetGameTurn(),activePlayer=active,autoplay=Game.GetAIAutoPlay(),observer=Players[active]:IsObserver(),human=Players[active]:IsHuman(),pausePlayer=Game.GetPausePlayer(),replayCount=Game.GetNumReplayMessages(),players={},cities={},wars={},livingMajors={}}
for owner=0,63 do
 local p=Players[owner]
 if p and p:IsAlive() and not p:IsObserver() then
  local civ=GameInfo.Civilizations[p:GetCivilizationType()]
  out.players[#out.players+1]={owner=owner,team=p:GetTeam(),civilization=civ and civ.Type or '',minor=p:IsMinorCiv(),barbarian=p:IsBarbarian(),unitCount=p:GetNumUnits(),cityCount=p:GetNumCities(),military=p:GetNumMilitaryUnits(),score=(not p:IsMinorCiv() and not p:IsBarbarian()) and p:GetScore() or 0,techs=Teams[p:GetTeam()]:GetTeamTechs():GetNumTechsKnown()}
  if not p:IsMinorCiv() and not p:IsBarbarian() then out.livingMajors[#out.livingMajors+1]=owner end
  for city in p:Cities() do
   out.cities[#out.cities+1]={plot=city:Plot():GetPlotIndex(),owner=owner,name=city:GetName(),originalOwner=city:GetOriginalOwner(),foundedTurn=city:GetGameTurnFounded(),acquiredTurn=city:GetGameTurnAcquired(),hp=city:GetMaxHitPoints()-city:GetDamage(),maxHP=city:GetMaxHitPoints(),population=city:GetPopulation()}
  end
  if not p:IsBarbarian() then
   for other=owner+1,63 do local q=Players[other];if q and q:IsAlive() and not q:IsObserver() and not q:IsBarbarian() and Teams[p:GetTeam()]:IsAtWar(q:GetTeam()) then out.wars[#out.wars+1]={owner,other} end end
  end
 end
end
return out
'''


def utc(): return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


class Bench:
    def __init__(self, run):
        self.run = ROOT / 'work/test-runs' / run
        self.name = run
        self.seq = 0

    def log(self, action, **values):
        row = dict(utc=utc(), action=action, **values)
        with (self.run / 'events.jsonl').open('a', encoding='utf-8') as stream: stream.write(json.dumps(row) + '\n')
        print(json.dumps(row), flush=True)

    def call(self, context, lua, label, timeout=120, keep=True):
        started = time.monotonic()
        result = tuner.call_service(SESSION, 'exec', dict(context=context, source=lua, timeout=timeout), timeout)
        if keep:
            self.seq += 1
            write(self.run / 'calls' / f'{self.seq:05d}-{label}.json', dict(utc=utc(), seconds=time.monotonic() - started, result=result))
        if not result.get('ok'): raise RuntimeError(f"{label}: {result.get('error', 'Lua call failed')}")
        return (result.get('values') or [None])[0]

    def states(self):
        result = tuner.call_service(SESSION, 'states', dict(timeout=30), 30)
        return {c['name'] for c in result.get('contexts', [])}

    def launch(self, dll_sha, maximum):
        if not (self.run / 'watcher-manifest.json').exists():  # otherwise attach to the already launched run
            log = self.run.parent / (self.name + '-launch.log')
            with log.open('wb') as stream:
                code = subprocess.run([PWSH, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'work/vpbench/vpbench-launch.ps1'),
                                       '-RunName', self.name, '-ExpectedDLLSHA', dll_sha, '-MaximumSeconds', str(maximum)],
                                      stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT).returncode
            if code: raise RuntimeError(f'Launch failed; see {log}')
        (self.run / 'calls').mkdir(exist_ok=True)
        self.guards = json.loads((self.run / 'watcher-manifest.json').read_text(encoding='utf-8-sig'))
        self.log('launched', game=self.guards['Game'])
        if not (self.run / 'ensure-mods-result.json').exists():
            code = subprocess.run([PY, '-B', '-u', str(ROOT / 'work/ensure-benchmark-mods.py'), '--run-dir', str(self.run), '--expected-mods-json', str(MODS)],
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True)
            if code.returncode: raise RuntimeError('Benchmark mods could not be verified: ' + code.stdout[-400:])
            self.call('LegalScreen', 'UIManager:DequeuePopup(ContextPtr)', 'dismiss-legal')
        self.call('ModsBrowser', "assert(#Modding.GetEnabledModsByActivationOrder()>0,'No mods enabled');OnNextButtonClicked();return 'activated'", 'activate-mods')
        deadline = time.monotonic() + 240
        while 'ModsSinglePlayer' not in self.states():
            if time.monotonic() >= deadline: raise TimeoutError('Mod activation did not complete')
            time.sleep(1)
        self.log('mods_activated')

    def wait_loaded(self, timeout=420):
        deadline = time.monotonic() + timeout
        while True:
            names = self.states()
            if 'InGame' in names and 'LoadScreen' in names and self.call('LoadScreen', 'return not Controls.ActivateButton:IsHidden()', 'load-ready', keep=False):
                return
            if time.monotonic() >= deadline: raise TimeoutError('Game did not finish loading')
            time.sleep(1)

    def process(self):
        script = (f"$p=Get-Process -Id {int(self.guards['Game'])} -ErrorAction Stop;[pscustomobject]@{{CPUSeconds=$p.TotalProcessorTime.TotalSeconds;"
                  "PeakWorkingSet=$p.PeakWorkingSet64;PeakVirtual=$p.PeakVirtualMemorySize64;PrivateBytes=$p.PrivateMemorySize64;StartTicks=$p.StartTime.ToUniversalTime().Ticks}|ConvertTo-Json -Compress")
        result = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, text=True, timeout=20)
        if result.returncode: return None
        data = json.loads(result.stdout)
        return data if data['StartTicks'] == self.guards['StartTicks'] else None

    def quit(self):
        try:
            names = self.states()
            tuner.call_service(SESSION, 'exec', dict(context='InGame' if 'InGame' in names else 'MainMenu', source="UI.ExitGame();return 'quit requested'", timeout=30), 30)
        except Exception as error:
            self.log('quit_request_failed', error=str(error))
        deadline = time.monotonic() + 120
        while self.process() and time.monotonic() < deadline: time.sleep(2)
        gone = self.process() is None
        try: tuner.call_service(SESSION, 'stop', {}, 10)
        except Exception: pass
        time.sleep(2)
        if Path(SESSION).exists():
            subprocess.run(['taskkill', '/PID', str(self.guards['Service']), '/F'], capture_output=True)
            time.sleep(1)
            if Path(SESSION).exists(): Path(SESSION).unlink()
        Path(self.guards['Signal']).write_text('finished\n', encoding='utf-8')
        self.log('quit', gameExited=gone)

    def save(self, name):
        path = SAVES / (name + '.Civ5Save')
        if path.exists(): raise ValueError(f'Save already exists: {path}')
        self.call('InGame', 'UI.SaveGame(' + tuner.lua_string(name) + ');return Game.GetGameTurn()', 'save')
        deadline = time.monotonic() + 60
        while not path.is_file() or path.stat().st_size == 0:
            if time.monotonic() >= deadline: raise TimeoutError('Save file did not appear')
            time.sleep(1)
        time.sleep(2)
        shutil.copy2(path, self.run / path.name)
        return path


def newgame(args):
    b = Bench(args.run)
    b.launch(args.dll_sha, 1800)
    try:
        setup = b.call('ModsSinglePlayer', NEWGAME, 'pregame-setup')
        write(b.run / 'pregame.json', setup)
        b.call('ModsSinglePlayer', START, 'start-game')
        b.log('start_requested')
        b.wait_loaded()
        info = b.call('InGame', SETUP, 'setup-info')
        write(b.run / 'setup.json', info)
        assert info['turn'] == 0 and info['world'] == 'WORLDSIZE_STANDARD' and info['speed'] == 'GAMESPEED_STANDARD', info
        civs = {p['civilization'] for p in info['players']}
        assert {'CIVILIZATION_ZULU', 'CIVILIZATION_AZTEC'} <= civs, civs
        b.call('LoadScreen', CONTINUE, 'continue')
        time.sleep(5)
        path = b.save(args.save_name)
        b.log('saved', save=str(path), majors=[p['civilization'] for p in info['players'] if not p['minor']])
    finally:
        b.quit()
    return 0


def run(args):
    b = Bench(args.run)
    save = Path(args.save).resolve(strict=True)
    target = args.target_turn
    b.launch(args.dll_sha, args.maximum_seconds)
    status = dict(state='failed')
    try:
        path = tuner.lua_string(str(save).replace('\\', '/'))
        b.call('ModsSinglePlayer', 'local path=' + path + ";assert(PreGame.GetFileHeader(path),'Unreadable save');Events.PlayerChoseToLoadGame(path);return 'requested'", 'request-load')
        b.wait_loaded()
        info = b.call('InGame', SETUP, 'setup-info')
        write(b.run / 'setup.json', info)
        # Stacking DLL only: -1 means the API is absent (vanilla). Benchmarks run with diagnostics off.
        assert info.get('diagnostics', -1) <= 0, 'Stacking diagnostics are enabled; set DiagnosticsLevel to 0'
        start_turn = info['turn']
        turns = target - start_turn
        assert turns > 0
        b.call('InGame', f"assert(not PreGame.IsMultiplayerGame());local p=Players[0];assert(p and p:IsAlive() and not p:IsMinorCiv());Game.SetOption('GAMEOPTION_QUICK_COMBAT',true);Game.SetOption('GAMEOPTION_QUICK_MOVEMENT',true);Game.SetAIAutoPlay({turns},0);return Game.GetAIAutoPlay()", 'arm-autoplay')
        first = b.call('InGame', CHECKPOINT, 'checkpoint')
        (b.run / 'checkpoints').mkdir()
        write(b.run / 'checkpoints' / f'turn-{start_turn:04d}.json', dict(utc=utc(), data=first))
        b.call('LoadScreen', CONTINUE, 'continue')
        started = time.monotonic(); started_utc = utc()
        b.log('autoplay_started', turn=start_turn, target=target)
        turn_seen = {start_turn: 0.0}
        last_turn = start_turn; last_checkpoint_turn = start_turn; last_checkpoint_time = started; last_progress = started
        return_player = 0; final = first
        deadline = started + args.maximum_seconds
        while True:
            time.sleep(args.poll_seconds)
            now = time.monotonic()
            if now >= deadline: raise TimeoutError('Maximum run time reached')
            try:
                state = b.call('InGame', TURN, 'turn', keep=False)
            except Exception:
                if b.process() is None: raise RuntimeError(f'Game process is gone at turn {last_turn} (crash or guard stop)')
                raise
            turn = state['turn']
            if turn != last_turn:
                for t in range(last_turn + 1, turn + 1): turn_seen[t] = round(now - started, 1)
                last_turn = turn; last_progress = now
                with (b.run / 'turn-times.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(dict(turn=turn, seconds=round(now - started, 1))) + '\n')
            elif now - last_progress > 1800:
                raise RuntimeError(f'No turn progress for 30 minutes at turn {turn}')
            if turn >= target: break
            if turn != last_checkpoint_turn and now - last_checkpoint_time >= 30:
                final = b.call('InGame', CHECKPOINT, 'checkpoint', keep=False)
                write(b.run / 'checkpoints' / f"turn-{final['turn']:04d}.json", dict(utc=utc(), seconds=round(now - started, 1), data=final))
                last_checkpoint_turn = final['turn']; last_checkpoint_time = now
                if final['turn'] % 10 == 0 or final['turn'] - start_turn < 3:
                    b.log('checkpoint', turn=final['turn'], seconds=round(now - started), cities=len(final['cities']), wars=len(final['wars']))
                majors = final['livingMajors']
                if state['autoplay'] == 0 and not final['observer']: raise RuntimeError(f"Autoplay stopped early at turn {final['turn']}")
                if return_player not in majors:
                    if not majors: raise RuntimeError('No living major')
                    return_player = majors[0]; remaining = target - final['turn']
                    b.call('InGame', f'assert(Players[Game.GetActivePlayer()]:IsObserver());if Game.GetAIAutoPlay()=={remaining} then Game.SetAIAutoPlay({remaining + 1},{return_player}) end;Game.SetAIAutoPlay({remaining},{return_player});return Game.GetAIAutoPlay()', 'replace-return-player')
                    b.log('return_player_changed', player=return_player)
        elapsed = time.monotonic() - started
        b.log('target_reached', turn=last_turn, seconds=round(elapsed, 1))
        proc = b.process()
        final = b.call('InGame', f'if Game.GetAIAutoPlay()>0 or Players[Game.GetActivePlayer()]:IsObserver() then if Game.GetAIAutoPlay()==0 then Game.SetAIAutoPlay(1,{return_player}) end;Game.SetAIAutoPlay(0,{return_player}) end;' + CHECKPOINT, 'final-checkpoint')
        write(b.run / 'checkpoints' / f"turn-{final['turn']:04d}-final.json", dict(utc=utc(), seconds=round(elapsed, 1), data=final))
        messages = []; total = final['replayCount']; cursor = 0
        while cursor < total:
            end = min(cursor + 200, total)
            page = b.call('InGame', f'local out={{}};for i={cursor},{end - 1} do local m=Game.GetReplayMessage(i);if m and m.Type~=2 then m.index=i;m.Plots=nil;out[#out+1]=m end end;return out', 'replay-page', keep=False)
            if isinstance(page, list): messages.extend(page)
            cursor = end
        write(b.run / 'replay-messages.json', messages)
        status = dict(state='completed', startedUTC=started_utc, startTurn=start_turn, endTurn=last_turn, turns=last_turn - start_turn,
                      wallSeconds=round(elapsed, 1), secondsPerTurn=round(elapsed / (last_turn - start_turn), 2), process=proc,
                      pollSeconds=args.poll_seconds, dllSHA256=args.dll_sha, save=str(save), replayMessages=len(messages))
        write(b.run / 'turn-seen.json', turn_seen)
        try:
            saved = b.save(args.final_save_name)
            status['finalSave'] = str(saved)
        except Exception as error:
            status['finalSaveError'] = str(error)
        write(b.run / 'status.json', status)
        b.log('completed', **{k: status[k] for k in ('turns', 'wallSeconds', 'secondsPerTurn')})
        return 0
    except Exception as error:
        status.update(error=str(error), utc=utc())
        write(b.run / 'status.json', status)
        b.log('failed', error=str(error))
        return 1
    finally:
        b.quit()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    n = sub.add_parser('newgame'); n.add_argument('--run', required=True); n.add_argument('--dll-sha', required=True); n.add_argument('--save-name', required=True)
    r = sub.add_parser('run'); r.add_argument('--run', required=True); r.add_argument('--dll-sha', required=True); r.add_argument('--save', required=True)
    r.add_argument('--target-turn', type=int, default=250); r.add_argument('--final-save-name', required=True)
    r.add_argument('--poll-seconds', type=float, default=5); r.add_argument('--maximum-seconds', type=int, default=21600)
    args = p.parse_args()
    return newgame(args) if args.command == 'newgame' else run(args)


if __name__ == '__main__': sys.exit(main())
