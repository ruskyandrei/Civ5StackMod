"""Replay preserved auto_275 through an already-running persistent tuner service.

This ignored development harness does not launch Civ V, start its socket service,
deploy binaries, save a game, change performance controls, or quit the process.
Arm Watch-CivCampaign.ps1 and Watch-CivCpuTemp.ps1 for the exact PID/start ticks
first, using this run directory and its fresh complete.signal; save their IDs in
watcher-manifest.json with Game, StartTicks, GpuMemoryWatcher and CpuWatcher.
The caller is responsible for preserving existing engine autosave slots before
launching a test game. This harness verifies the manually selected source save
has not changed, and never requests a save or writes in the game's save folders.

Example, after launcher/service/watchdogs are ready at the main menu:
  python work/run-performance-replay.py --run-dir work/test-runs/perf-new \
      --game-pid 12345 --start-ticks 639263635413699642

The archived 31/33/35 output establishes turn275, observer8, Summary1, both quick
options, cap2 returning to0, then stopped turn277/human0 and the census format.
The exact historical preparation command was not archived. Explicit (0,-1)
preserves observer8 while paused, unlike the convenience halt command returning
to a human. Source setAIAutoPlay confirms activating again from an existing
observer skips the human-to-AI slot change/production/diplomacy reseeding.

Only full turn276 is comparable to the earlier round timing. Turn275 resumes a
save and includes load/preparation;277 switches to a human. No mutations are
retried after errors/timeouts. On failure watchdogs remain armed unless the
expected safe stop has already been observed. On success the game stays open,
stopped on human0 at277, for caller-controlled inspection/normal shutdown.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import civ5_tuner as tuner

SAVE_SHA = "E61C8BD691E989A66068053A67819306A421BAE725EB5AF7317E2FBEF1235160"
DEFAULT_SAVE = Path(r"C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5\ModdedSaves\single\auto_275.Civ5Save")
DEFAULT_LOGS = Path(r"C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5\Logs")
SESSION_HEADER = re.compile(r"^STACKDIAG\|SESSION\|schema=\d+ run=([\w-]+) segment=(\d+) build=(.*?) level=", re.M)
CENSUS_ROW = re.compile(r"InGame: (PERF_UNIT|PERF_CITY)\s+(.*)")

STATUS = """
local active=Game.GetActivePlayer();local player=Players[active]
return {turn=Game.GetGameTurn(),activePlayer=active,autoplay=Game.GetAIAutoPlay(),
 diagnostics=Game.GetStackingDiagnosticsLevel(),quickCombat=PreGame.GetQuickCombat(),
 quickMovement=PreGame.GetQuickMovement(),pausePlayer=Game.GetPausePlayer(),
 human=player and player:IsHuman() or false,observer=player and player:IsObserver() or false,
 multiplayer=PreGame.IsMultiplayerGame()}
"""
PREPARE = """
assert(not PreGame.IsMultiplayerGame(),'Single-player replay only')
assert(Game.GetGameTurn()==275,'Expected preserved turn275 save')
assert(Game.GetActivePlayer()==8 and Players[8]:IsObserver(),'Expected observer8')
assert(Game.GetPausePlayer()==8,'Load screen must still pause observer8')
assert(Players[0] and Players[0]:IsAlive() and not Players[0]:IsMinorCiv()
 and not Players[0]:IsObserver() and not Players[0]:IsBarbarian(),'Return player0 unavailable')
assert(Game.SetStackingDiagnosticsLevel and Game.FlushStackingDiagnostics,'Diagnostics APIs required')
local restored=Game.GetAIAutoPlay()
Game.SetAIAutoPlay(0,-1)
assert(Game.GetAIAutoPlay()==0 and Game.GetActivePlayer()==8 and Players[8]:IsObserver(),
 'Stopping restored autoplay changed observer')
Game.SetStackingDiagnosticsLevel(1)
Game.SetOption('GAMEOPTION_QUICK_COMBAT',true)
Game.SetOption('GAMEOPTION_QUICK_MOVEMENT',true)
Game.SetAIAutoPlay(2,0)
assert(Game.GetAIAutoPlay()==2 and Game.GetActivePlayer()==8,'Could not arm bounded replay')
assert(Game.GetGameTurn()==275 and Game.GetPausePlayer()==8,'Preparation advanced/unpaused game')
assert(PreGame.GetQuickCombat() and PreGame.GetQuickMovement(),'Quick options did not apply')
Game.FlushStackingDiagnostics()
print('PERF_READY',Game.GetGameTurn(),Game.GetAIAutoPlay(),Game.GetActivePlayer(),
 Game.GetStackingDiagnosticsLevel(),PreGame.GetQuickCombat(),PreGame.GetQuickMovement())
return {restoredAutoplay=restored,turn=Game.GetGameTurn(),autoplay=Game.GetAIAutoPlay(),
 activePlayer=Game.GetActivePlayer(),pausePlayer=Game.GetPausePlayer(),
 diagnostics=Game.GetStackingDiagnosticsLevel(),quickCombat=PreGame.GetQuickCombat(),
 quickMovement=PreGame.GetQuickMovement(),observer=Players[8]:IsObserver()}
"""
CONTINUE = """
assert(not Controls.ActivateButton:IsHidden(),'Loading is not complete')
assert(not PreGame.IsMultiplayerGame(),'Single player only')
assert(Game.GetGameTurn()==275 and Game.GetAIAutoPlay()==2 and Game.GetActivePlayer()==8,
 'Prepared replay state changed')
assert(Game.GetPausePlayer()==8,'Game unpaused before continuation')
Events.LoadScreenClose();Game.SetPausePlayer(-1);UI.SetDontShowPopups(false)
return 'continued'
"""
CENSUS = """
assert(Game.GetGameTurn()==277 and Game.GetAIAutoPlay()==0 and Game.GetActivePlayer()==0,
 'Expected bounded stop277/counter0/active0')
assert(Players[0]:IsHuman() and not Players[0]:IsObserver(),'Return player0 is not human')
Game.FlushStackingDiagnostics()
print('PERF_STOP',Game.GetGameTurn(),Game.GetAIAutoPlay(),Game.GetActivePlayer())
local rows={}
for owner=0,63 do
 local player=Players[owner]
 if player and player:IsAlive() then
  for unit in player:Units() do
   local row={'PERF_UNIT',owner,unit:GetID(),unit:GetX(),unit:GetY(),unit:GetDamage(),unit:GetMoves()}
   rows[#rows+1]=row;print(unpack(row))
  end
  for city in player:Cities() do
   local row={'PERF_CITY',owner,city:GetID(),city:GetX(),city:GetY(),city:GetDamage(),city:GetPopulation()}
   rows[#rows+1]=row;print(unpack(row))
  end
 end
end
return rows
"""


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256") if hasattr(hashlib, "file_digest") else None
        if digest is None:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest().upper()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def census_rows(text):
    rows = []
    for line in text.splitlines():
        match = CENSUS_ROW.search(line)
        if match:
            values = [int(value) for value in match[2].split()]
            if len(values) != 6:
                raise ValueError("Unexpected PERF census field count")
            rows.append([match[1], *values])
    return rows


def stopped(status):
    return (status.get("turn") == 277 and status.get("autoplay") == 0
            and status.get("activePlayer") == 0 and status.get("human") is True
            and status.get("observer") is False)


def exact_process(game_pid, start_ticks, guard_pids):
    # Read process metadata only; this is neither GUI automation nor an input API.
    guards = ",".join(str(int(pid)) for pid in guard_pids)
    script = (f"$replayGame=Get-Process -Id {int(game_pid)} -ErrorAction Stop;"
              f"$replayGuards=@(Get-Process -Id {guards} -ErrorAction Stop);"
              "[pscustomobject]@{PID=$replayGame.Id;Name=$replayGame.ProcessName;"
              "StartTicks=$replayGame.StartTime.ToUniversalTime().Ticks;"
              "Modules=@($replayGame.Modules|Where-Object {$_.ModuleName -eq 'CvGameCore_Expansion2.dll'}|ForEach-Object {$_.FileName});"
              "Watchers=@($replayGuards|ForEach-Object {$_.Id})}|ConvertTo-Json -Compress")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True, check=True, timeout=20)
    proof = json.loads(result.stdout)
    if (proof.get("PID") != game_pid or proof.get("StartTicks") != start_ticks
            or proof.get("Name", "").lower() != "civilizationv_dx11"
            or set(proof.get("Watchers", [])) != set(guard_pids)):
        raise ValueError("Exact DX11 process/watchdog identity did not match")
    return proof


class Replay:
    def __init__(self, args):
        self.args = args
        self.run = args.run_dir.resolve()
        self.sequence = 0
        self.safe_stop = False
        self.manifest = {}

    def call(self, context, source, label, timeout=None):
        self.sequence += 1
        stem = f"{self.sequence:03d}-{label}"
        (self.run / (stem + ".lua")).write_text(source, encoding="utf-8")
        budget = self.args.command_timeout if timeout is None else timeout
        started = time.monotonic()
        result = tuner.call_service(self.args.session, "exec", {
            "context": context, "source": source, "timeout": budget}, budget)
        write_json(self.run / (stem + ".json"), {"utc": utc(), "seconds": time.monotonic() - started,
                                                "context": context, "result": result})
        if not result.get("ok"):
            raise tuner.TunerError(result.get("error", "Lua command failed"))
        return result.get("values", [])

    def states(self, label):
        self.sequence += 1
        result = tuner.call_service(self.args.session, "states", {"timeout": self.args.command_timeout},
                                    self.args.command_timeout)
        write_json(self.run / f"{self.sequence:03d}-{label}.json", {"utc": utc(), "result": result})
        if not result.get("ok"):
            raise tuner.TunerError(result.get("error", "Context query failed"))
        return {context["name"] for context in result.get("contexts", [])}

    def save_manifest(self):
        write_json(self.run / "replay-manifest.json", self.manifest)

    def archive_native(self):
        destination = self.run / "native-segments"
        destination.mkdir(exist_ok=True)
        run_ids = set()
        builds = set()
        count = 0
        for path in self.args.logs.glob(f"Stacking-*-p{self.args.game_pid}-r*.log"):
            text = path.read_text(encoding="utf-8-sig", errors="strict")
            header = SESSION_HEADER.search(text)
            if not header:
                continue
            run_ids.add(header[1]); builds.add(header[3]); count += 1
            # Same current PID can have several rolling segments, not several runs.
            shutil.copyfile(path, destination / path.name)
        if count == 0 or len(run_ids) != 1 or len(builds) != 1:
            raise ValueError(f"Expected one native diagnostic run/build for exact game PID; found {run_ids}/{builds}")
        self.manifest["NativeRun"] = next(iter(run_ids))
        self.manifest["Version"] = next(iter(builds))
        self.save_manifest()

    def execute(self):
        allowed = (ROOT / "work" / "test-runs").resolve()
        if not self.run.is_relative_to(allowed) or self.run == allowed:
            raise ValueError("Run directory must be below this project's work/test-runs")
        # Guards may already have created their evidence; harness output must be new.
        if self.run.exists() and any(self.run.glob("[0-9][0-9][0-9]-*")):
            raise ValueError("Harness output already exists; choose a fresh run directory")
        self.run.mkdir(parents=True, exist_ok=True)
        if (self.run / "replay-manifest.json").exists() or (self.run / "complete.signal").exists():
            raise ValueError("Manifest/completion signal already exists; choose a fresh run directory")
        watcher = json.loads((self.run / "watcher-manifest.json").read_text(encoding="utf-8-sig"))
        if watcher["Game"] != self.args.game_pid or watcher["StartTicks"] != self.args.start_ticks:
            raise ValueError("Watchdog manifest does not match requested exact game process")
        if Path(watcher["Signal"]).resolve() != self.run / "complete.signal":
            raise ValueError("Watchdogs must use this run's complete.signal")
        guard_pids = [int(watcher["GpuMemoryWatcher"]), int(watcher["CpuWatcher"])]
        if len(set(guard_pids)) != 2 or self.args.game_pid in guard_pids:
            raise ValueError("Watchdog PID identities are invalid")
        proof = exact_process(self.args.game_pid, self.args.start_ticks, guard_pids)
        write_json(self.run / "process-before.json", proof)
        save = self.args.save.resolve(strict=True)
        if save.suffix.lower() != ".civ5save" or sha(save) != SAVE_SHA:
            raise ValueError("Save does not match preserved auto_275 SHA256")
        self.manifest = {"Status": "preparing", "Save": str(save), "SaveSHA256": SAVE_SHA,
                         "PID": self.args.game_pid, "StartTicks": self.args.start_ticks,
                         "TurnLimit": 2, "ReturnPlayer": 0, "DiagnosticLevel": 1,
                         "QuickCombat": True, "QuickMovement": True, "StartedUTC": utc(),
                         "GameplayData": "Installed data unchanged by this harness; caller must verify deployment",
                         "Preparation": "Paused observer8; SetAIAutoPlay(0,-1), Summary1, quick string options, SetAIAutoPlay(2,0)",
                         "TimingLimits": "Compare full turn276 only; resumed275 and human-switch277 are partial"}
        self.save_manifest()
        states = self.states("initial-contexts")
        if "InGame" in states:
            raise ValueError("Start at the main menu outside a loaded game, with a fresh process/native run")
        self.call("LegalScreen", "UIManager:DequeuePopup(ContextPtr)", "dismiss-legal")
        enabled = self.call("ModsBrowser", "local mods=Modding.GetEnabledModsByActivationOrder();"
                            "assert(#mods>0,'No enabled mods');return mods", "enabled-mods")[0]
        if not isinstance(enabled, list):
            raise ValueError("Unexpected enabled mod list")
        # Engine UI ModsSinglePlayer.lua reads v.ModID, not v.ID.
        ids = {mod.get("ModID", "").lower() for mod in enabled}
        expected_mods = {"d1b6328c-ff44-4b0d-aad7-c657f83610cd": 151,
                         "8411a7a8-dad3-4622-a18e-fcc18324c799": 17,
                         "24923240-e4fb-4bf6-8f0e-6e5b6cf4d3c2": 1,
                         "3645dbca-bdfb-4d86-bdc5-46cb5a426cc2": 1}
        if ids != set(expected_mods) or any(int(mod["Version"]) != expected_mods[mod["ModID"].lower()] for mod in enabled):
            raise ValueError("Enabled mods must match archived31/33/35 CP151, VP17, EUI1 and Squads1")
        self.manifest["EnabledMods"] = enabled
        self.call("ModsBrowser", "OnNextButtonClicked();return 'activated'", "activate-enabled-mods")
        ready_deadline = time.monotonic() + self.args.load_timeout
        while "ModsSinglePlayer" not in self.states("activated-contexts"):
            if time.monotonic() >= ready_deadline:
                raise TimeoutError("VP menu activation did not complete within load budget")
            time.sleep(1)
        path_literal = tuner.lua_string(str(save).replace("\\", "/"))
        self.call("ModsSinglePlayer", "local path=" + path_literal + ";assert(PreGame.GetFileHeader(path),'Unreadable save');"
                  "Events.PlayerChoseToLoadGame(path);return 'requested'", "request-load")
        ready_deadline = time.monotonic() + self.args.load_timeout
        while True:
            states = self.states("loading-contexts")
            if "InGame" in states and "LoadScreen" in states:
                ready = self.call("LoadScreen", "return not Controls.ActivateButton:IsHidden()", "load-ready")[0]
                if ready:
                    break
            if time.monotonic() >= ready_deadline:
                raise TimeoutError("Save loading did not complete within load budget")
            time.sleep(1)
        prepared = self.call("InGame", PREPARE, "prepare-bounded-replay")[0]
        self.manifest["Prepared"] = prepared
        proof = exact_process(self.args.game_pid, self.args.start_ticks, guard_pids)
        modules = proof.get("Modules", [])
        if len(modules) != 1:
            raise ValueError("Expected exactly one loaded gamecore DLL")
        write_json(self.run / "loaded-dll.json", {"PID": self.args.game_pid, "StartTicks": self.args.start_ticks,
                                                   "Path": modules[0], "SHA256": sha(modules[0])})
        self.manifest["InstalledDLL"] = modules[0]
        self.manifest["SHA256"] = sha(modules[0])
        self.archive_native()
        shutil.copyfile(self.args.logs / "Lua.log", self.run / "Lua-start.log")
        self.manifest["Status"] = "armed"
        self.save_manifest()
        self.call("LoadScreen", CONTINUE, "continue-bounded-replay")
        self.manifest["ContinuedUTC"] = utc()
        self.manifest["Status"] = "running"
        self.save_manifest()
        deadline = time.monotonic() + self.args.maximum_seconds
        while True:
            status = self.call("InGame", STATUS, "status")[0]
            print(json.dumps({"utc": utc(), "status": status}), flush=True)
            if stopped(status):
                self.safe_stop = True
                # Disarm immediately: paused game is no longer expected to advance.
                (self.run / "complete.signal").write_text("Bounded replay stopped277/counter0/human0 " + utc() + "\n", encoding="utf-8")
                self.manifest["Stopped"] = status
                self.manifest["StoppedUTC"] = utc()
                self.manifest["Status"] = "stopped"
                self.save_manifest()
                break
            if status["turn"] > 277 or (status["turn"] == 277 and status["autoplay"] == 0):
                raise ValueError(f"Unexpected bounded replay stop: {status}")
            if time.monotonic() >= deadline:
                raise TimeoutError("Replay exceeded its monitoring budget; no ambiguous mutation retried")
            self.archive_native()
            time.sleep(min(self.args.poll_seconds, max(0, deadline - time.monotonic())))
        rows = self.call("InGame", CENSUS, "flush-and-census")[0]
        write_json(self.run / "paused-census.json", rows)
        self.archive_native()
        lua_path = self.args.logs / "Lua.log"
        # The structured result is complete even though ordinary output retains128
        # records. Real Lua.log must independently contain every printed census row.
        for attempt in range(20):
            text = lua_path.read_text(encoding="utf-8-sig")
            if census_rows(text) == rows:
                break
            if attempt == 19:
                raise ValueError("Lua.log census does not exactly match complete structured census")
            time.sleep(.1)
        shutil.copyfile(lua_path, self.run / "Lua-end.log")
        if sha(save) != SAVE_SHA:
            raise ValueError("Source manual save changed during replay")
        self.manifest["SaveSHA256After"] = sha(save)
        self.manifest["CensusCount"] = len(rows)
        self.manifest["UnitCount"] = sum(row[0] == "PERF_UNIT" for row in rows)
        self.manifest["CityCount"] = sum(row[0] == "PERF_CITY" for row in rows)
        self.manifest["Status"] = "completed_stopped_game_open"
        self.save_manifest()
        print(json.dumps({"ok": True, "run": str(self.run), "nativeRun": self.manifest["NativeRun"],
                          "censusRows": len(rows), "gameLeftOpen": True, "watchdogsDisarmedBySignal": True}), flush=True)


def self_test():
    # Offline checks exercise the actual helper logic without opening a socket,
    # invoking the game, launching a process, or writing another file.
    assert stopped({"turn": 277, "autoplay": 0, "activePlayer": 0, "human": True, "observer": False})
    for wrong in ({"turn": 278}, {"autoplay": 1}, {"activePlayer": 8}, {"human": False}, {"observer": True}):
        value = {"turn": 277, "autoplay": 0, "activePlayer": 0, "human": True, "observer": False}
        value.update(wrong)
        assert not stopped(value)
    sample = "[1.0] InGame: PERF_UNIT\t0\t1\t38\t18\t3\t0\n[1.1] InGame: PERF_CITY\t0\t2\t38\t18\t0\t11\n"
    assert census_rows(sample) == [["PERF_UNIT", 0, 1, 38, 18, 3, 0], ["PERF_CITY", 0, 2, 38, 18, 0, 11]]
    try:
        census_rows("InGame: PERF_UNIT 0 1 2 3 4")
    except ValueError:
        pass
    else:
        raise AssertionError("Malformed census accepted")
    header = SESSION_HEADER.search("STACKDIAG|SESSION|schema=1 run=Stacking-20260930T111924-637-p24992-r1 segment=0 build=Release-5.4.6-35-g91054ec4c Clean level=1 configFNV=00000000")
    assert header and header[3] == "Release-5.4.6-35-g91054ec4c Clean"
    baseline = ROOT / "work/test-runs/overnight-20260930/performance-reused35/Lua-end.log"
    if baseline.exists():
        rows = census_rows(baseline.read_text(encoding="utf-8-sig"))
        assert len(rows) == 766
        assert sum(row[0] == "PERF_UNIT" for row in rows) == 694
        assert sum(row[0] == "PERF_CITY" for row in rows) == 72
    assert "Game.SetAIAutoPlay(0,-1)" in PREPARE and "Game.SetAIAutoPlay(0,0)" not in PREPARE
    assert "Game.SetAIAutoPlay(2,0)" in PREPARE and "SetAIAutoPlay" not in CENSUS
    runtime = ROOT / "work/lua-validation"
    if runtime.exists():
        sys.path.insert(0, str(runtime))
        from lupa.lua51 import LuaRuntime
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("""
state={turn=275,active=8,auto=5000,pause=8,diag=0,observer=true,human=false,quickCombat=false,quickMovement=false,reseed=0}
calls={};printed={}
print=function(...) printed[#printed+1]={...} end
local alive=function() return true end
local no=function() return false end
Players={[0]={IsAlive=alive,IsMinorCiv=no,IsBarbarian=no,IsObserver=no,IsHuman=function() return state.human end},
 [8]={IsObserver=function() return state.observer end,IsHuman=no}}
PreGame={IsMultiplayerGame=no,GetQuickCombat=function() return state.quickCombat end,GetQuickMovement=function() return state.quickMovement end}
Game={GetGameTurn=function() return state.turn end,GetActivePlayer=function() return state.active end,
 GetAIAutoPlay=function() return state.auto end,GetPausePlayer=function() return state.pause end,
 GetStackingDiagnosticsLevel=function() return state.diag end,SetStackingDiagnosticsLevel=function(n) state.diag=n end,
 FlushStackingDiagnostics=function() end,SetOption=function(k,v) if k=='GAMEOPTION_QUICK_COMBAT' then state.quickCombat=v elseif k=='GAMEOPTION_QUICK_MOVEMENT' then state.quickMovement=v else error(k) end end,
 SetAIAutoPlay=function(n,p)
  calls[#calls+1]={n,p};local old=state.auto;state.auto=n
  if old>0 and n==0 and p>=0 then state.active=p;state.observer=false;state.human=true end
  if old==0 and n>0 and not state.observer then state.reseed=state.reseed+1 end
 end}
""")
        prepared = lua.execute(PREPARE)
        assert prepared["turn"] == 275 and prepared["activePlayer"] == 8 and prepared["autoplay"] == 2
        assert lua.globals().state["reseed"] == 0 and len(lua.globals().calls) == 2
        assert (lua.globals().calls[1][1], lua.globals().calls[1][2]) == (0, -1)
        assert (lua.globals().calls[2][1], lua.globals().calls[2][2]) == (2, 0)
        lua.execute("""
state.turn=277;state.active=0;state.auto=0;state.human=true;state.observer=false
local unit={GetID=function() return 1 end,GetX=function() return 38 end,GetY=function() return 18 end,GetDamage=function() return 3 end,GetMoves=function() return 0 end}
local city={GetID=function() return 2 end,GetX=function() return 38 end,GetY=function() return 18 end,GetDamage=function() return 0 end,GetPopulation=function() return 11 end}
local function single(v) local i=0;return function() i=i+1;if i==1 then return v end end end
Players[0].Units=function() return single(unit) end;Players[0].Cities=function() return single(city) end
Players[8].IsAlive=function() return false end
""")
        observed = lua.execute(CENSUS)
        assert [list(observed[i].values()) for i in range(1, len(observed)+1)] == census_rows(sample)
        assert len(lua.globals().calls) == 2  # Census is read-only except diagnostic flush.
        # Syntax checks for all game code and readiness expressions.
        check_syntax = lua.eval("function(source) assert(loadstring(source));return true end")
        for source in (STATUS, PREPARE, CONTINUE, CENSUS):
            assert check_syntax(source)
    print(json.dumps({"ok": True, "offline": True, "gameCommandsSent": 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--session", type=Path, default=tuner.DEFAULT_SESSION)
    parser.add_argument("--save", type=Path, default=DEFAULT_SAVE)
    parser.add_argument("--logs", type=Path, default=DEFAULT_LOGS)
    parser.add_argument("--game-pid", type=int)
    parser.add_argument("--start-ticks", type=int)
    parser.add_argument("--command-timeout", type=float, default=120)
    parser.add_argument("--load-timeout", type=float, default=240)
    parser.add_argument("--maximum-seconds", type=float, default=1800)
    parser.add_argument("--poll-seconds", type=float, default=15)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.run_dir is None or args.game_pid is None or args.start_ticks is None:
        parser.error("--run-dir, --game-pid and --start-ticks are required")
    if not 0 < args.command_timeout <= 120 or not 1 <= args.poll_seconds <= 60:
        parser.error("Command timeout must be(0,120]; polling must be1–60 seconds")
    if not 1 <= args.load_timeout <= 1800 or not 1 <= args.maximum_seconds <= 1800:
        parser.error("Load/replay monitoring budgets must be1–1800 seconds")
    replay = Replay(args)
    try:
        replay.execute()
        return 0
    except Exception as exc:
        failure = {"ok": False, "utc": utc(), "error": str(exc),
                   "safeStopObserved": replay.safe_stop, "watchdogsLeftArmed": not replay.safe_stop,
                   "mutationRetried": False, "gameLeftOpen": True}
        if replay.manifest:
            replay.manifest["Status"] = "failed"
            replay.manifest["Failure"] = failure
            replay.save_manifest()
        print(json.dumps(failure), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
