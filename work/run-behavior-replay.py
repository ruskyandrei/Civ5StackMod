"""Bounded saved-campaign behavior replay through the persistent Civ V service.

The default is preserved campaign01 T215 -> T230, Summary diagnostics, quick
combat/movement, returning to alive major player0. Start with a fresh DX11
process at the main menu and its persistent tuner service. Arm the exact-PID
campaign/CPU watchdogs and write watcher-manifest.json in a fresh run directory.
Back up existing engine autosave slots before launch; this script never requests
a save, changes source saves, creates units, grants technology or issues orders.

Example (caller supplies the freshly deployed DLL hash):
 python -B work/run-behavior-replay.py --run-dir work/test-runs/behavior-capture \
   --game-pid 12345 --start-ticks 639263679154066891 --expected-dll-sha <SHA256>

Unlike run-performance-replay.py this is not an exact 275/277 benchmark fixture.
Its preparation requires an observer save and preserves that observer while
stopping a restored counter. Expected start/stop/return and save/hash can be
supplied explicitly. T215 and the return-player switch atT230 are partial turns.
The explicit --source-mode human alternative verifies a paused, non-autoplay
return-player source, then enters observer mode. This performs VP's slot-change
AI decisions; compare only identical human source/preparation pairs, not the
original uninterrupted campaign or an existing observer-source control.
Read-only per-player snapshots before/after include unit identity/type/position,
HP/movement, city name/original owner/HP/strength/population and active wars.
Per-player calls avoid the tuner's10,000-value result limit for whole campaigns.
The named watch city (defaultAbernethy) is sampled during status polling too.
--view-mode preserves the current view by default. Explicit standard/strategic
requests validate the engine globals before preparation mutates game settings,
then apply the view in a separate late InGame request after the census while
paused. This lets deferred active-player restoration run first. A further
InGame status verifies final mode before continuation. Actual view is recorded
even for preserve when the API exists; old archives have unknown view.

Commands and structured responses are archived with numbered files, alongside
Lua.log, rolling native segments, save/DLL identities, snapshots and analyzer
JSON. The expected human stop signals guards immediately, before final snapshots.
The game is left open for caller-controlled inspection/normal shutdown. Unsafe
stop states are paused when the socket remains usable, then reported as failures;
they never silently qualify as a successful expected stop. No dispatched mutation
is retried after a timeout. --resume-prepared only recovers verified paused
preparation before any continuation was dispatched, preserving prior evidence.

Shared transport/process/archive helpers are imported from the existing replay
harness; its benchmark semantics/defaults are not modified by this script.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("performance_replay", ROOT / "work/run-performance-replay.py")
perf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(perf)
tuner = perf.tuner
DEFAULT_SAVE = ROOT / "work/test-runs/overnight-20260930/campaign-01/Stack D29 Campaign01 T215 20260930.Civ5Save"
DEFAULT_SAVE_SHA = "9E3F9C6656B2C060FD0A33A568E14CE3BB29978B6656C3D0236FA02971005457"
EXPECTED_MODS = {"d1b6328c-ff44-4b0d-aad7-c657f83610cd": 151, "8411a7a8-dad3-4622-a18e-fcc18324c799": 17,
                 "24923240-e4fb-4bf6-8f0e-6e5b6cf4d3c2": 1, "3645dbca-bdfb-4d86-bdc5-46cb5a426cc2": 1}


def view_matches(status, mode):
    return mode == "preserve" or (status.get("viewAPIAvailable") is True
        and status.get("strategicView") is (mode == "strategic"))


def prepared(status, start, count, view_mode="preserve"):
    return (status.get("turn") == start and status.get("autoplay") == count
            # VP observer slots can report IsHuman()==true or false. The
            # observer/pause/counter checks establish paused preparation.
            and status.get("observer") is True
            and status.get("pausePlayer") == status.get("activePlayer")
            and isinstance(status.get("activePlayer"), int) and status["activePlayer"] >= 0
            and status.get("diagnostics") == 1 and status.get("quickCombat") is True
            and status.get("quickMovement") is True and status.get("multiplayer") is False
            and view_matches(status, view_mode))


def stopped(status, stop, player):
    return (status.get("turn") == stop and status.get("autoplay") == 0
            and status.get("activePlayer") == player and status.get("human") is True
            and status.get("observer") is False and status.get("returnPlayerAlive") is True)


def lua_sources(args):
    start, stop, player = args.start_turn, args.stop_turn, args.return_player
    count = stop - start
    source_mode = getattr(args, "source_mode", "observer")
    view_mode = getattr(args, "view_mode", "preserve")
    if source_mode not in ("observer", "human"):
        raise ValueError("Unknown replay source mode")
    if view_mode not in ("preserve", "standard", "strategic"):
        raise ValueError("Unknown replay view mode")
    view_literal = tuner.lua_string(view_mode)
    view_check = f"""local requestedView={view_literal}
local originalView=nil
if type(InStrategicView)=='function' then originalView=InStrategicView() end
if requestedView~='preserve' then
 assert(type(InStrategicView)=='function' and type(ToggleStrategicView)=='function'
  and type(originalView)=='boolean','Strategic view APIs unavailable')
end"""
    view_continue = "" if view_mode == "preserve" else f"""
assert(type(InStrategicView)=='function' and InStrategicView()=={str(view_mode == 'strategic').lower()},
 'Prepared view changed')"""
    if source_mode == "observer":
        source_check = """assert(Players[active] and Players[active]:IsObserver(),'Behavior source must be an observer save')
assert(Game.GetPausePlayer()==active,'Load screen must still pause the original observer')"""
        stop_restored = """Game.SetAIAutoPlay(0,-1)
assert(Game.GetActivePlayer()==active and Players[active]:IsObserver() and Game.GetAIAutoPlay()==0,
 'Stopping restored autoplay changed the observer')"""
        after_arm = ""
    else:
        source_check = f"""assert(active=={player} and Players[active] and Players[active]:IsHuman()
 and not Players[active]:IsObserver(),'Explicit human source must be the return player')
assert(Game.GetPausePlayer()==active and Game.GetAIAutoPlay()==0,'Human source must be paused without autoplay')"""
        stop_restored = ""
        after_arm = """active=Game.GetActivePlayer()
assert(active~=sourceActive and Players[active] and Players[active]:IsObserver(),
 'Human source did not switch to an observer')
Game.SetPausePlayer(active)"""
    status = perf.STATUS.replace("return {", "local result={", 1) + f"""
result.returnPlayerAlive=Players[{player}] and Players[{player}]:IsAlive() or false
result.viewModeRequested={view_literal}
result.viewAPIAvailable=type(InStrategicView)=='function'
if result.viewAPIAvailable then result.strategicView=InStrategicView() end
result.watchCities={{}}
local watched={tuner.lua_string(args.watch_city)}
for owner=0,63 do local p=Players[owner];if p and p:IsAlive() and not p:IsObserver() then
 for city in p:Cities() do if city:GetName()==watched then
  result.watchCities[#result.watchCities+1]={{owner=owner,id=city:GetID(),name=city:GetName(),
   originalOwner=city:GetOriginalOwner(),x=city:GetX(),y=city:GetY(),damage=city:GetDamage(),
   maximumHP=city:GetMaxHitPoints(),strength=city:GetStrengthValue(),population=city:GetPopulation()}}
 end end
end end
return result
"""
    prepare = f"""
assert(not PreGame.IsMultiplayerGame(),'Single-player replay only')
assert(Game.GetGameTurn()=={start},'Unexpected loaded turn')
local active=Game.GetActivePlayer()
local sourceActive=active
{source_check}
local returning=Players[{player}]
assert(returning and returning:IsAlive() and not returning:IsMinorCiv() and not returning:IsObserver()
 and not returning:IsBarbarian(),'Return civilization must be alive major')
assert(Game.SetStackingDiagnosticsLevel and Game.FlushStackingDiagnostics,'Diagnostics APIs unavailable')
{view_check}
local restored=Game.GetAIAutoPlay()
{stop_restored}
Game.SetStackingDiagnosticsLevel(1)
Game.SetOption('GAMEOPTION_QUICK_COMBAT',true)
Game.SetOption('GAMEOPTION_QUICK_MOVEMENT',true)
Game.SetAIAutoPlay({count},{player})
{after_arm}
assert(Game.GetGameTurn()=={start} and Game.GetAIAutoPlay()=={count} and Game.GetActivePlayer()==active
 and Game.GetPausePlayer()==active,'Preparation advanced or changed the original observer')
assert(PreGame.GetQuickCombat() and PreGame.GetQuickMovement(),'Quick settings did not apply')
Game.FlushStackingDiagnostics()
print('BEHAVIOR_READY',Game.GetGameTurn(),Game.GetAIAutoPlay(),Game.GetActivePlayer())
local ready=(function(){status}end)();ready.restoredAutoplay=restored
ready.sourceMode='{source_mode}';ready.sourceActivePlayer=sourceActive
ready.viewModeOriginal=originalView;ready.viewModeResult=ready.strategicView;return ready
"""
    continuation = f"""
assert(not Controls.ActivateButton:IsHidden(),'Load screen not ready')
assert(not PreGame.IsMultiplayerGame(),'Single-player replay only')
local active=Game.GetActivePlayer()
assert(Game.GetGameTurn()=={start} and Game.GetAIAutoPlay()=={count} and Players[active]:IsObserver()
 and Game.GetPausePlayer()==active,'Prepared observer replay changed')
assert(Game.GetStackingDiagnosticsLevel()==1 and PreGame.GetQuickCombat() and PreGame.GetQuickMovement(),
 'Prepared diagnostics/options changed')
{view_continue}
Events.LoadScreenClose();Game.SetPausePlayer(-1);UI.SetDontShowPopups(false);return 'continued'
"""
    return status, prepare, continuation


def lua_view_preparation(args):
    """Run after source normalization/census callbacks, before continuation."""
    mode = getattr(args, "view_mode", "preserve")
    if mode not in ("preserve", "standard", "strategic"):
        raise ValueError("Unknown replay view mode")
    return f"""
assert(not PreGame.IsMultiplayerGame(),'Single-player replay only')
local active=Game.GetActivePlayer()
assert(Game.GetGameTurn()=={args.start_turn} and Game.GetAIAutoPlay()=={args.stop_turn-args.start_turn}
 and Players[active] and Players[active]:IsObserver() and Game.GetPausePlayer()==active,
 'Late view preparation must remain paused at the original turn')
assert(Game.GetStackingDiagnosticsLevel()==1 and PreGame.GetQuickCombat() and PreGame.GetQuickMovement(),
 'Prepared diagnostics/options changed')
local requested={tuner.lua_string(mode)}
local available=type(InStrategicView)=='function'
local before=nil
if available then before=InStrategicView() end
local toggled=false
if requested~='preserve' then
 assert(available and type(ToggleStrategicView)=='function' and type(before)=='boolean',
  'Strategic view APIs unavailable')
 local desired=requested=='strategic'
 if before~=desired then ToggleStrategicView();toggled=true end
 assert(InStrategicView()==desired,'Requested strategic view did not apply')
end
local after=nil
if available then after=InStrategicView() end
return {{turn=Game.GetGameTurn(),activePlayer=active,pausePlayer=Game.GetPausePlayer(),
 autoplay=Game.GetAIAutoPlay(),viewModeRequested=requested,viewAPIAvailable=available,
 before=before,strategicView=after,toggled=toggled,semantics='late_paused_view_preparation'}}
"""


OWNER_LIST = """
local owners={}
for owner=0,63 do local player=Players[owner]
 if player and player:IsAlive() and not player:IsObserver() then owners[#owners+1]=owner end
end
return owners
"""
OWNER_SNAPSHOT = """
local owner=OWNER_ARGUMENT;local player=assert(Players[owner]);assert(player:IsAlive() and not player:IsObserver())
local civilization=GameInfo.Civilizations[player:GetCivilizationType()]
local out={owner=owner,civilization=civilization and civilization.Type or '',team=player:GetTeam(),
 human=player:IsHuman(),minor=player:IsMinorCiv(),barbarian=player:IsBarbarian(),units={},cities={},wars={}}
for unit in player:Units() do
 out.units[#out.units+1]={unit:GetID(),unit:GetUnitType(),unit:GetX(),unit:GetY(),unit:GetDamage(),
  unit:GetMaxHitPoints(),unit:GetMoves(),unit:GetDomainType(),unit:GetBaseCombatStrength(),unit:GetBaseRangedCombatStrength()}
end
for city in player:Cities() do
 out.cities[#out.cities+1]={city:GetID(),city:GetName(),city:GetOriginalOwner(),city:GetX(),city:GetY(),
  city:GetDamage(),city:GetMaxHitPoints(),city:GetStrengthValue(),city:GetPopulation()}
end
for other=0,63 do local p=Players[other]
 if p and p:IsAlive() and not p:IsObserver() and other~=owner and Teams[player:GetTeam()]:IsAtWar(p:GetTeam()) then
  out.wars[#out.wars+1]=other
 end
end
return out
"""
FLUSH = "Game.FlushStackingDiagnostics();return Game.GetStackingDiagnosticsStatus()"
PAUSE_UNEXPECTED = "local active=Game.GetActivePlayer();Game.SetPausePlayer(active);return {turn=Game.GetGameTurn(),pausePlayer=Game.GetPausePlayer(),activePlayer=active}"


class BehaviorReplay(perf.Replay):
    def __init__(self, args):
        super().__init__(args)
        self.status_source, self.prepare_source, self.continue_source = lua_sources(args)
        self.view_source = lua_view_preparation(args)
        self.deadline = None

    def snapshot(self, stage):
        owners = self.call("InGame", OWNER_LIST, f"{stage}-snapshot-owners")[0]
        if not isinstance(owners, list) or any(not isinstance(owner, int) or not 0 <= owner <= 63 for owner in owners):
            raise ValueError("Unexpected alive player list")
        snapshots = []
        for owner in owners:
            snapshots.append(self.call("InGame", OWNER_SNAPSHOT.replace("OWNER_ARGUMENT", str(owner)),
                                       f"{stage}-snapshot-player-{owner:02d}")[0])
        value = {"utc": perf.utc(), "expectedTurn": self.args.start_turn if stage == "before" else self.args.stop_turn,
                 "unitColumns": ["id", "type", "x", "y", "damage", "maximumHP", "moves", "domain", "baseMelee", "baseRanged"],
                 "cityColumns": ["id", "name", "originalOwner", "x", "y", "damage", "maximumHP", "strength", "population"],
                 "players": snapshots}
        perf.write_json(self.run / f"world-{stage}.json", value)
        return value

    def analyze(self):
        segment_directory = self.run / "native-segments"
        for script, output in (("summarize-stacking-diagnostics.py", "diagnostics-summary.json"),
                               ("analyze-assault-campaign.py", "assault-summary.json"),
                               ("profile-campaign-log.py", "performance-final.json")):
            self.progress("offline-analyzer", script=script)
            result = subprocess.run([sys.executable, "-B", str(ROOT / "work" / script), str(segment_directory),
                                     "--run", self.manifest["NativeRun"], "--output", str(self.run / output)],
                                    capture_output=True, text=True, timeout=90)
            perf.write_json(self.run / (script + ".result.json"), {"exitCode": result.returncode,
                                                                    "stdout": result.stdout, "stderr": result.stderr})
            if result.returncode:
                raise RuntimeError(f"Offline analyzer failed: {script}; raw evidence retained")

    def execute(self):
        allowed = (ROOT / "work/test-runs").resolve()
        if not self.run.is_relative_to(allowed) or self.run == allowed:
            raise ValueError("Run directory must be below project work/test-runs")
        self.sequence = perf.numbered_sequence(path.name for path in self.run.iterdir()) if self.run.exists() else 0
        self.run.mkdir(parents=True, exist_ok=True)
        manifest_path = self.run / "replay-manifest.json"
        if (self.run / "complete.signal").exists():
            raise ValueError("Completion signal already exists")
        if self.args.resume_prepared:
            self.manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        elif self.sequence or manifest_path.exists():
            raise ValueError("Behavior output already exists; use fresh run directory or explicit safe resume")
        self.progress("validating-behavior-replay", sourceTurn=self.args.start_turn, stopTurn=self.args.stop_turn)
        watcher = json.loads((self.run / "watcher-manifest.json").read_text(encoding="utf-8-sig"))
        if watcher["Game"] != self.args.game_pid or watcher["StartTicks"] != self.args.start_ticks:
            raise ValueError("Exact game identity does not match guards")
        if Path(watcher["Signal"]).resolve() != self.run / "complete.signal":
            raise ValueError("Guard completion signal does not match this run")
        guards = [int(watcher["GpuMemoryWatcher"]), int(watcher["CpuWatcher"])]
        if len(set(guards)) != 2 or self.args.game_pid in guards:
            raise ValueError("Invalid guard identities")
        perf.exact_process(self.args.game_pid, self.args.start_ticks, guards)
        save = self.args.save.resolve(strict=True)
        if save.suffix.lower() != ".civ5save" or perf.sha(save) != self.args.save_sha:
            raise ValueError("Source save SHA does not match expected preserved source")
        count = self.args.stop_turn - self.args.start_turn
        if self.args.resume_prepared:
            expected = {"SaveSHA256": self.args.save_sha, "PID": self.args.game_pid, "StartTicks": self.args.start_ticks,
                        "StartTurn": self.args.start_turn, "StopTurn": self.args.stop_turn, "ReturnPlayer": self.args.return_player,
                        "ExpectedDLLSHA256": self.args.expected_dll_sha}
            if self.manifest.get("SourceMode", "observer") != self.args.source_mode:
                raise ValueError("Resume source mode changed")
            if self.manifest.get("ViewMode", "preserve") != self.args.view_mode:
                raise ValueError("Resume view mode changed")
            if any(self.manifest.get(key) != value for key, value in expected.items()) or Path(self.manifest["Save"]).resolve() != save:
                raise ValueError("Resume source/process/behavior settings changed")
            if self.manifest.get("ContinuedUTC") or self.manifest.get("Stopped") or self.manifest.get("Status") not in ("preparing", "armed", "failed"):
                raise ValueError("Resume is only permitted before any continuation")
            if any(re.match(r"^\d+-continue-bounded-behavior\.lua$", path.name) for path in self.run.iterdir()):
                raise ValueError("Continuation was previously dispatched; never repeat it")
            records = list(self.run.glob("*-prepare-bounded-behavior.json"))
            if len(records) != 1 or records[0].with_suffix(".lua").read_text(encoding="utf-8") != self.prepare_source:
                raise ValueError("Exact original behavior preparation source/result is required")
            result = json.loads(records[0].read_text(encoding="utf-8-sig"))["result"]
            if not result.get("ok") or not prepared(result.get("values", [{}])[0], self.args.start_turn, count):
                raise ValueError("Original preparation did not establish exact bounded paused state")
            snapshot_path = self.run / f"manifest-before-resume-{self.sequence+1:03d}.json"
            with snapshot_path.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(self.manifest, indent=2)+"\n")
            failure = self.manifest.pop("Failure", None)
            if failure and failure not in self.manifest.setdefault("FailureHistory", []):
                self.manifest["FailureHistory"].append(failure)
            live = self.call("InGame", self.status_source, "resume-paused-behavior-state")[0]
            if not prepared(live, self.args.start_turn, count) or not live["returnPlayerAlive"]:
                raise ValueError("Live paused state is unsafe to resume")
            self.manifest["ViewModeOriginal"] = result.get("values", [{}])[0].get("viewModeOriginal")
            self.manifest["ViewModePrepared"] = live.get("strategicView")
            if self.call("LoadScreen", "return not Controls.ActivateButton:IsHidden()", "resume-load-ready")[0] is not True:
                raise ValueError("Load-screen activation button must remain visible")
            self.manifest.setdefault("ResumeAttempts", []).append({"utc": perf.utc(), "verified": live})
        else:
            self.manifest = {"Status": "preparing", "Save": str(save), "SaveSHA256": self.args.save_sha,
                             "StartTurn": self.args.start_turn, "StopTurn": self.args.stop_turn, "TurnLimit": count,
                             "SourceMode": self.args.source_mode,
                             "ViewMode": self.args.view_mode,
                             "ReturnPlayer": self.args.return_player, "DiagnosticLevel": 1, "QuickCombat": True, "QuickMovement": True,
                             "PID": self.args.game_pid, "StartTicks": self.args.start_ticks, "StartedUTC": perf.utc(),
                             "ExpectedDLLSHA256": self.args.expected_dll_sha, "WatchCity": self.args.watch_city,
                             "Limits": "First/return turns partial; human-source mode explicitly performs VP slot-change diplomacy/production/research/policy decisions; compare identical source/preparation only"}
            self.save_manifest()
            if "InGame" in self.states("initial-contexts"):
                raise ValueError("Begin from a fresh game's main menu")
            self.call("LegalScreen", "UIManager:DequeuePopup(ContextPtr)", "dismiss-legal")
            enabled = self.call("ModsBrowser", "return Modding.GetEnabledModsByActivationOrder()", "enabled-mods")[0]
            if {mod["ModID"].lower(): int(mod["Version"]) for mod in enabled} != self.args.expected_mods:
                raise ValueError("Enabled mods do not match the explicitly expected activation set")
            self.manifest["EnabledMods"] = enabled
            self.call("ModsBrowser", "OnNextButtonClicked();return 'activated'", "activate-mods")
            load_deadline = time.monotonic() + self.args.load_timeout
            while "ModsSinglePlayer" not in self.states("activation-contexts"):
                if time.monotonic() >= load_deadline:
                    raise TimeoutError("Mod activation budget expired")
                time.sleep(1)
            literal = tuner.lua_string(str(save).replace("\\", "/"))
            self.call("ModsSinglePlayer", "local path="+literal+";assert(PreGame.GetFileHeader(path),'Unreadable save');Events.PlayerChoseToLoadGame(path);return 'requested'", "load-behavior-save")
            load_deadline = time.monotonic() + self.args.load_timeout
            while True:
                states = self.states("loading-contexts")
                if {"InGame", "LoadScreen"}.issubset(states) and self.call("LoadScreen", "return not Controls.ActivateButton:IsHidden()", "load-ready")[0]:
                    break
                if time.monotonic() >= load_deadline:
                    raise TimeoutError("Save load budget expired")
                time.sleep(1)
            ready = self.call("InGame", self.prepare_source, "prepare-bounded-behavior")[0]
            if not prepared(ready, self.args.start_turn, count):
                raise ValueError("Behavior preparation failed ready-state validation")
            self.manifest["Prepared"] = ready
            self.manifest["ViewModeOriginal"] = ready.get("viewModeOriginal")
            self.manifest["ViewModePrepared"] = ready.get("strategicView")
            self.save_manifest()
        proof = perf.gamecore_metadata(lambda: perf.exact_process(self.args.game_pid, self.args.start_ticks, guards),
                                       lambda **fields: self.progress("loaded-dll-metadata", **fields))
        module = proof["Modules"][0]
        if perf.sha(module) != self.args.expected_dll_sha:
            raise ValueError("Loaded gamecore path's DLL file does not match expected deployment SHA")
        self.manifest.update(InstalledDLL=module, SHA256=perf.sha(module))
        perf.write_json(self.run / "loaded-dll.json", {**proof, "Path": module, "SHA256": perf.sha(module)})
        self.archive_native()
        if not (self.run / "world-before.json").exists():
            self.snapshot("before")
        shutil.copyfile(self.args.logs / "Lua.log", self.run / "Lua-start.log")
        # A delayed WorldView active-player callback can reset the immediate
        # preparation's view after its Lua returns. Set the explicit view only
        # after the census requests, then verify from another InGame request.
        # Never retry a dispatched late mutation after an unknown result.
        prior_view = list(self.run.glob("*-prepare-replay-view.lua"))
        if prior_view:
            if (len(prior_view) != 1 or prior_view[0].read_text(encoding="utf-8") != self.view_source
                    or not prior_view[0].with_suffix(".json").exists()):
                raise ValueError("Previous late view preparation is not safely recoverable; never repeat it")
            previous = json.loads(prior_view[0].with_suffix(".json").read_text(encoding="utf-8-sig"))["result"]
            if not previous.get("ok") or not previous.get("values"):
                raise ValueError("Previous late view preparation did not succeed; never repeat it")
            view_proof = previous["values"][0]
        else:
            view_proof = self.call("InGame", self.view_source, "prepare-replay-view")[0]
        final_ready = self.call("InGame", self.status_source, "verify-final-prepared-view")[0]
        if (not prepared(final_ready, self.args.start_turn, count, self.args.view_mode)
                or not final_ready["returnPlayerAlive"] or not isinstance(view_proof, dict)
                or view_proof.get("semantics") != "late_paused_view_preparation"
                or view_proof.get("viewModeRequested") != self.args.view_mode
                or view_proof.get("strategicView") != final_ready.get("strategicView")):
            raise ValueError("Final paused view preparation failed validation")
        initial_ready = self.manifest.get("Prepared", result["values"][0] if self.args.resume_prepared else {})
        self.manifest.setdefault("PreparedInitial", initial_ready.copy())
        self.manifest["Prepared"] = {**initial_ready, **final_ready, "viewModeResult": final_ready.get("strategicView")}
        self.manifest["ViewPreparation"] = view_proof
        self.manifest["ViewModePrepared"] = final_ready.get("strategicView")
        self.manifest["Status"] = "armed"
        self.save_manifest()
        self.call("LoadScreen", self.continue_source, "continue-bounded-behavior")
        self.manifest.update(Status="running", ContinuedUTC=perf.utc())
        self.save_manifest()
        self.deadline = time.monotonic() + self.args.maximum_seconds
        while True:
            status = self.call("InGame", self.status_source, "behavior-status")[0]
            self.progress("behavior-progress", status=status)
            if stopped(status, self.args.stop_turn, self.args.return_player):
                self.safe_stop = True
                (self.run / "complete.signal").write_text("Expected behavior replay stopped "+perf.utc()+"\n", encoding="utf-8")
                self.manifest.update(Status="stopped", Stopped=status, StoppedUTC=perf.utc())
                self.manifest["ViewModeStopped"] = status.get("strategicView")
                self.save_manifest()
                break
            if (status["turn"] > self.args.stop_turn or status["autoplay"] == 0 or not status["returnPlayerAlive"]
                    or not view_matches(status, self.args.view_mode) or time.monotonic() >= self.deadline):
                # A dead return player can leave observer autoplay advancing at
                # counter0. Pause once while the channel is known usable; fail
                # visibly instead of silently switching another civilization.
                pause = self.call("InGame", PAUSE_UNEXPECTED, "pause-unexpected-behavior-stop")[0]
                self.manifest["UnexpectedStopPaused"] = pause
                raise ValueError(f"Unexpected/expired behavior replay paused: {status}")
            self.archive_native()
            time.sleep(min(self.args.poll_seconds, max(0, self.deadline-time.monotonic())))
        self.call("InGame", FLUSH, "flush-behavior-diagnostics")
        after = self.snapshot("after")
        self.archive_native()
        shutil.copyfile(self.args.logs / "Lua.log", self.run / "Lua-end.log")
        if perf.sha(save) != self.args.save_sha:
            raise ValueError("Original preserved source save changed")
        self.manifest.update(SaveSHA256After=perf.sha(save), Status="completed_stopped_game_open",
                             UnitCount=sum(len(p["units"]) for p in after["players"]), CityCount=sum(len(p["cities"]) for p in after["players"]))
        self.save_manifest()
        self.analyze()
        self.progress("behavior-replay-complete", run=str(self.run), nativeRun=self.manifest["NativeRun"], gameLeftOpen=True)


def self_test():
    args = argparse.Namespace(start_turn=215, stop_turn=230, return_player=0, watch_city="Abernethy")
    status, preparation, continuation = lua_sources(args)
    ready = {"turn": 215, "autoplay": 15, "activePlayer": 8, "pausePlayer": 8, "observer": True,
             "human": True, "diagnostics": 1, "quickCombat": True, "quickMovement": True, "multiplayer": False}
    assert prepared(ready, 215, 15)
    assert prepared({**ready, "human": False}, 215, 15)
    for change in ({"turn": 216}, {"autoplay": 14}, {"pausePlayer": -1}, {"observer": False},
                   {"diagnostics": 2}, {"quickCombat": False}):
        assert not prepared({**ready, **change}, 215, 15)
    end = {"turn": 230, "autoplay": 0, "activePlayer": 0, "human": True, "observer": False, "returnPlayerAlive": True}
    assert stopped(end, 230, 0)
    for change in ({"turn": 231}, {"autoplay": 1}, {"activePlayer": 8}, {"human": False}, {"observer": True}, {"returnPlayerAlive": False}):
        assert not stopped({**end, **change}, 230, 0)
    assert "Game.SetAIAutoPlay(0,-1)" in preparation and "Game.SetAIAutoPlay(15,0)" in preparation
    runtime = ROOT / "work/lua-validation"
    if runtime.exists():
        sys.path.insert(0, str(runtime))
        from lupa.lua51 import LuaRuntime
        lua = LuaRuntime(unpack_returned_tuples=True)
        syntax = lua.eval("function(s) assert(loadstring(s));return true end")
        for source in (status, preparation, continuation, OWNER_LIST, OWNER_SNAPSHOT.replace("OWNER_ARGUMENT", "0"), PAUSE_UNEXPECTED):
            assert syntax(source)
        # Execute real generated preparation/status on a source-derived mock:
        # existing observer must survive stop/rearm without human->AI reseeding.
        lua.execute("""
state={turn=215,auto=785,active=8,pause=8,diag=0,quickCombat=false,quickMovement=false};calls={}
print=function() end
local yes=function() return true end;local no=function() return false end
local p0={IsAlive=yes,IsObserver=no,IsMinorCiv=no,IsBarbarian=no,IsHuman=no,Cities=function() return function() end end}
local p8={IsAlive=no,IsObserver=yes,IsHuman=yes,Cities=function() return function() end end}
Players={[0]=p0,[8]=p8}
PreGame={IsMultiplayerGame=no,GetQuickCombat=function() return state.quickCombat end,GetQuickMovement=function() return state.quickMovement end}
Game={GetGameTurn=function() return state.turn end,GetActivePlayer=function() return state.active end,
 GetPausePlayer=function() return state.pause end,GetAIAutoPlay=function() return state.auto end,
 GetStackingDiagnosticsLevel=function() return state.diag end,SetStackingDiagnosticsLevel=function(n) state.diag=n end,
 FlushStackingDiagnostics=function() end,SetAIAutoPlay=function(n,p) calls[#calls+1]={n,p};state.auto=n;assert(state.active==8) end,
 SetOption=function(k,v) if k=='GAMEOPTION_QUICK_COMBAT' then state.quickCombat=v elseif k=='GAMEOPTION_QUICK_MOVEMENT' then state.quickMovement=v else error(k) end end}
""")
        observed = lua.execute(preparation)
        assert prepared(dict(observed.items()), 215, 15)
        assert observed["observer"] is True and observed["human"] is True
        assert prepared({**dict(observed.items()), "human": False}, 215, 15)
        assert observed["restoredAutoplay"] == 785 and observed["returnPlayerAlive"] is True
        assert len(lua.globals().calls) == 2
        assert tuple(lua.globals().calls[1].values()) == (0, -1) and tuple(lua.globals().calls[2].values()) == (15, 0)
        lua.execute(status)
        assert len(lua.globals().calls) == 2
        lua.execute("""
local function one(value) local used=false;return function() if not used then used=true;return value end end end
local unit={GetID=function() return 12 end,GetUnitType=function() return 101 end,
 GetX=function() return 20 end,GetY=function() return 34 end,GetDamage=function() return 66 end,
 GetMaxHitPoints=function() return 100 end,GetMoves=function() return 120 end,GetDomainType=function() return 0 end,
 GetBaseCombatStrength=function() return 20 end,GetBaseRangedCombatStrength=function() return 0 end}
local city={GetID=function() return 44 end,GetName=function() return 'Abernethy' end,
 GetOriginalOwner=function() return 1 end,GetX=function() return 21 end,GetY=function() return 34 end,
 GetDamage=function() return 549 end,GetMaxHitPoints=function() return 550 end,
 GetStrengthValue=function() return 6200 end,GetPopulation=function() return 11 end}
Players[0].GetCivilizationType=function() return 0 end;Players[0].GetTeam=function() return 0 end
Players[0].Units=function() return one(unit) end;Players[0].Cities=function() return one(city) end
Players[1]={IsAlive=function() return true end,IsObserver=function() return false end,GetTeam=function() return 1 end,
 Cities=function() return function() end end}
Teams={[0]={IsAtWar=function(self,team) return team==1 end}}
GameInfo={Civilizations={[0]={Type='CIVILIZATION_AZTEC'}}}
Game.SetPausePlayer=function(n) state.pause=n end
""")
        initial = lua.execute(OWNER_SNAPSHOT.replace("OWNER_ARGUMENT", "0"))
        assert initial["civilization"] == "CIVILIZATION_AZTEC" and initial["team"] == 0
        assert list(initial["units"][1].values()) == [12,101,20,34,66,100,120,0,20,0]
        assert list(initial["cities"][1].values()) == [44,"Abernethy",1,21,34,549,550,6200,11]
        assert list(initial["wars"].values()) == [1]
        watched = lua.execute(status)["watchCities"][1]
        assert watched["owner"] == 0 and watched["damage"] == 549 and watched["maximumHP"] == 550
        assert len(lua.globals().calls) == 2
        paused = lua.execute(PAUSE_UNEXPECTED)
        assert paused["pausePlayer"] == paused["activePlayer"] == 8 and paused["turn"] == 215
        # A human source must fail before any autoplay/options mutation.
        lua.execute("state.active=0;state.pause=0;Players[0].IsHuman=function() return true end")
        try:
            lua.execute(preparation)
        except Exception as exc:
            assert "observer save" in str(exc)
        else:
            raise AssertionError("Human source was silently converted/reseeded")
        assert len(lua.globals().calls) == 2
        # Human normalization is explicit; validate the real generated branch,
        # including its paused source contract and newly active observer.
        human_args = argparse.Namespace(start_turn=215, stop_turn=230, return_player=0,
                                        watch_city="Abernethy", source_mode="human")
        _, human_prepare, _ = lua_sources(human_args)
        assert syntax(human_prepare)
        human_reset = """
state={turn=215,auto=0,active=0,pause=0,diag=0,quickCombat=false,quickMovement=false};calls={}
Players[0].IsHuman=function() return true end
Players[0].IsAlive=function() return true end
Game.SetStackingDiagnosticsLevel=function(n) calls[#calls+1]={'diag',n};state.diag=n end
Game.SetOption=function(k,v) calls[#calls+1]={k,v};if k=='GAMEOPTION_QUICK_COMBAT' then state.quickCombat=v else state.quickMovement=v end end
Game.SetAIAutoPlay=function(n,p)
 assert(state.active==0 and state.auto==0 and n==15 and p==0)
 calls[#calls+1]={'auto',n,p};state.auto=n;state.active=8
 Players[0].IsHuman=function() return false end
end
Game.SetPausePlayer=function(n) assert(n==8);calls[#calls+1]={'pause',n};state.pause=n end
"""
        lua.execute(human_reset)
        human_ready = dict(lua.execute(human_prepare).items())
        assert prepared(human_ready,215,15) and human_ready['sourceMode']=='human'
        assert human_ready['sourceActivePlayer']==0 and human_ready['restoredAutoplay']==0
        assert len(lua.globals().calls)==5
        for invalid in ("state.active=8;state.pause=8", "state.auto=7", "state.pause=-1",
                        "Players[0].IsHuman=function() return false end",
                        "Players[0].IsAlive=function() return false end", "state.turn=216"):
            lua.execute(human_reset+"\n"+invalid)
            try: lua.execute(human_prepare)
            except Exception: pass
            else: raise AssertionError("Invalid human source was normalized")
            assert len(lua.globals().calls)==0
        # View APIs must be validated before autoplay/options/diagnostics mutate.
        # Preserve queries an available API but never toggles; human normalization
        # may restore another player's view, so apply the request afterwards.
        view_args = argparse.Namespace(**vars(human_args), view_mode="strategic")
        _, strategic_prepare, strategic_continue = lua_sources(view_args)
        strategic_late = lua_view_preparation(view_args)
        assert syntax(strategic_prepare) and syntax(strategic_continue) and syntax(strategic_late)
        for unavailable in ("InStrategicView=nil;ToggleStrategicView=nil",
                            "InStrategicView=function() return false end;ToggleStrategicView=nil",
                            "InStrategicView=function() return 1 end;ToggleStrategicView=function() end"):
            lua.execute(human_reset+"\n"+unavailable)
            try: lua.execute(strategic_prepare)
            except Exception as exc: assert "Strategic view APIs unavailable" in str(exc)
            else: raise AssertionError("Missing/invalid view API admitted")
            assert len(lua.globals().calls)==0
        view_mock = """
state.strategic=ORIGINAL_VIEW;state.toggles=0
InStrategicView=function() return state.strategic end
ToggleStrategicView=function()
 assert(state.active==8 and state.pause==8,'Toggle outside paused observer')
 state.toggles=state.toggles+1;state.strategic=not state.strategic
end
"""
        for mode, original, expected, toggles in (("preserve",False,False,0),("preserve",True,True,0),
                ("strategic",False,True,1),("strategic",True,True,0),
                ("standard",False,False,0),("standard",True,False,1)):
            configured = argparse.Namespace(**vars(human_args), view_mode=mode)
            _, source, _ = lua_sources(configured)
            lua.execute(human_reset+"\n"+view_mock.replace("ORIGINAL_VIEW",str(original).lower()))
            initial = dict(lua.execute(source).items())
            assert initial['strategicView'] is original and lua.globals().state.toggles==0
            proof = dict(lua.execute(lua_view_preparation(configured)).items())
            status_for_view, _, _ = lua_sources(configured)
            got = {**initial, **dict(lua.execute(status_for_view).items()), 'viewModeResult':proof['strategicView']}
            assert prepared(got,215,15,mode) and got['strategicView'] is expected
            assert got['viewModeOriginal'] is original and got['viewModeResult'] is expected
            assert got['viewModeRequested']==mode and lua.globals().state.toggles==toggles
            assert len(lua.globals().calls)==5
        # Model the engine's delayed per-player restoration after preparation
        # returned and the census was sampled. Immediate view is not final proof.
        lua.execute(human_reset+"\n"+view_mock.replace("ORIGINAL_VIEW","true")+"""
state.delayedViewReset=false
""")
        initial = dict(lua.execute(strategic_prepare).items())
        assert initial['viewModeOriginal'] is True and initial['strategicView'] is True and lua.globals().state.toggles==0
        lua.execute("state.strategic=state.delayedViewReset")
        proof = dict(lua.execute(strategic_late).items())
        final_status, _, _ = lua_sources(view_args)
        got = {**initial, **dict(lua.execute(final_status).items()), 'viewModeResult':proof['strategicView']}
        assert prepared(got,215,15,"strategic") and proof['before'] is False and proof['strategicView'] is True
        assert got['viewModeOriginal'] is True and lua.globals().state.toggles==1
        lua.execute(human_reset+"\n"+view_mock.replace("ORIGINAL_VIEW","false")+"""
ToggleStrategicView=function() assert(state.active==8 and state.pause==8);state.toggles=state.toggles+1 end
""")
        lua.execute(strategic_prepare)
        try: lua.execute(strategic_late)
        except Exception as exc: assert "Requested strategic view did not apply" in str(exc)
        else: raise AssertionError("Unapplied view silently continued")
        assert lua.globals().state.toggles==1 and lua.globals().state.pause==8 and lua.globals().state.turn==215
        lua.execute(human_reset+"\n"+view_mock.replace("ORIGINAL_VIEW","true"))
        lua.execute(strategic_prepare)
        lua.execute(strategic_late)
        lua.execute("state.strategic=false")
        status_source, _, _ = lua_sources(view_args)
        changed = dict(lua.execute(status_source).items())
        assert changed['viewModeRequested']=='strategic' and changed['strategicView'] is False
        assert not prepared(changed,215,15,"strategic") and not view_matches(changed,"strategic")
        lua.execute("""
state.continued=0
Controls={ActivateButton={IsHidden=function() return false end}}
Events={LoadScreenClose=function() state.continued=state.continued+1 end}
UI={SetDontShowPopups=function() end}
Game.SetPausePlayer=function(n) assert(n==8 or n==-1);state.pause=n end
""")
        try: lua.execute(strategic_continue)
        except Exception as exc: assert "Prepared view changed" in str(exc)
        else: raise AssertionError("Changed view continued")
        assert lua.globals().state.continued==0 and lua.globals().state.pause==8
        lua.execute("state.strategic=true")
        assert lua.execute(strategic_continue)=='continued' and lua.globals().state.continued==1
        assert lua.globals().state.pause==-1
        # Preserve still works when engine view globals are absent.
        lua.execute(human_reset+"\nInStrategicView=nil;ToggleStrategicView=nil")
        preserved = dict(lua.execute(human_prepare).items())
        assert prepared(preserved,215,15) and preserved['viewAPIAvailable'] is False and 'strategicView' not in preserved
        preserve_late = dict(lua.execute(lua_view_preparation(human_args)).items())
        assert preserve_late['viewAPIAvailable'] is False and preserve_late['toggled'] is False
    print(json.dumps({"ok": True, "offline": True, "gameCommandsSent": 0, "negativeStateCases": 12,
                      "lua51Validated": runtime.exists(), "snapshotsAndCityWatchValidated": runtime.exists(),
                      "explicitHumanSourceValidated": runtime.exists(), "humanSourceNegativeCases": 6,
                      "viewModesValidated": runtime.exists(), "viewMissingAPINegativeCases": 3,
                      "delayedViewRestorationValidated": runtime.exists()}))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--session", type=Path, default=tuner.DEFAULT_SESSION)
    parser.add_argument("--save", type=Path, default=DEFAULT_SAVE)
    parser.add_argument("--save-sha", default=DEFAULT_SAVE_SHA)
    parser.add_argument("--start-turn", type=int, default=215)
    parser.add_argument("--stop-turn", type=int, default=230)
    parser.add_argument("--return-player", type=int, default=0)
    parser.add_argument("--source-mode", choices=("observer", "human"), default="observer",
                        help="Human explicitly allows the same paused return-player save to switch to observer, including VP slot-change AI decisions")
    parser.add_argument("--view-mode", choices=("preserve", "standard", "strategic"), default="preserve",
                        help="Preserve the loaded view by default; explicit modes apply while paused after observer normalization and are verified in status polls")
    parser.add_argument("--watch-city", default="Abernethy")
    parser.add_argument("--logs", type=Path, default=perf.DEFAULT_LOGS)
    parser.add_argument("--game-pid", type=int)
    parser.add_argument("--start-ticks", type=int)
    parser.add_argument("--expected-dll-sha")
    parser.add_argument("--expected-mods-json", type=Path,
                        help="Explicit JSON list of ModID/Version records; default preserves the historical four-mod fixture")
    parser.add_argument("--command-timeout", type=float, default=120)
    parser.add_argument("--load-timeout", type=float, default=240)
    parser.add_argument("--maximum-seconds", type=float, default=1800)
    parser.add_argument("--poll-seconds", type=float, default=15)
    parser.add_argument("--resume-prepared", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    args.expected_mods = EXPECTED_MODS.copy()
    if args.expected_mods_json:
        records = json.loads(args.expected_mods_json.read_text(encoding="utf-8-sig"))
        if not isinstance(records, list) or not records:
            parser.error("Expected mods must be a nonempty JSON list")
        args.expected_mods = {}
        for item in records:
            if (not isinstance(item, dict) or not isinstance(item.get("ModID"), str)
                    or re.fullmatch(r"[0-9a-fA-F-]{36}", item["ModID"]) is None
                    or type(item.get("Version")) is not int or item["Version"] < 1
                    or item["ModID"].lower() in args.expected_mods):
                parser.error("Expected mods require unique IDs and positive integer versions")
            args.expected_mods[item["ModID"].lower()] = item["Version"]
    if args.self_test:
        self_test();return 0
    if args.run_dir is None or args.game_pid is None or args.start_ticks is None or args.expected_dll_sha is None:
        parser.error("--run-dir, --game-pid, --start-ticks and --expected-dll-sha are required")
    if not 0 <= args.start_turn < args.stop_turn or args.stop_turn-args.start_turn > 1000 or not 0 <= args.return_player <= 63:
        parser.error("Specify a0–1000-turn bounded interval and valid return player")
    if not 0 < args.command_timeout <= 120 or not 1 <= args.poll_seconds <= 60 or not 1 <= args.maximum_seconds <= 28800:
        parser.error("Command budget(0,120], polling1–60s, maximum interval1–28800s")
    if not 1 <= args.load_timeout <= 1800:
        parser.error("Load timeout must be1–1800 seconds")
    args.save_sha = args.save_sha.upper();args.expected_dll_sha = args.expected_dll_sha.upper()
    if any(re.fullmatch(r"[0-9A-F]{64}", value) is None for value in (args.save_sha, args.expected_dll_sha)):
        parser.error("Save/DLL SHA values must have64 hexadecimal characters")
    replay = BehaviorReplay(args)
    try:
        replay.execute();return 0
    except Exception as exc:
        failure = {"ok": False, "utc": perf.utc(), "error": str(exc), "safeStopObserved": replay.safe_stop,
                   "watchdogsLeftArmed": not replay.safe_stop, "mutationRetried": False, "gameLeftOpen": True}
        replay.record_failure(failure)
        print(json.dumps(failure), flush=True);return 1


if __name__ == "__main__":
    raise SystemExit(main())
