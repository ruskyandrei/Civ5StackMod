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
Read-only game-setup.json and manifest GameSetup record map dimensions/world
type, game speed and alive major count before the first census. A safe resume
retains the original proof and requires the live metadata to agree.
--view-mode preserves the current view by default. Explicit standard/strategic
requests validate the engine globals before preparation mutates game settings,
then apply the view in a separate late InGame request after the census while
paused. This lets deferred active-player restoration run first. A further
InGame status verifies final mode before continuation. Actual view is recorded
even for preserve when the API exists; old archives have unknown view.
--tactical-sampling preserves the current sampled profiler by default, including
DLLs without that optional API. Explicit on/off validates both boolean APIs
before replay preparation mutates settings, applies once while paused after
Summary diagnostics, then verifies the result before continuation and each poll.
Recorded profiler differences require explicit comparison allowance and do not
qualify as identical performance controls.

Commands and structured responses are archived with numbered files, alongside
Lua.log, rolling native segments, save/DLL identities, snapshots and analyzer
JSON. The expected human stop signals guards immediately, before final snapshots.
The game is left open for caller-controlled inspection/normal shutdown by default.
Optional --quit-after-complete verifies the census/archive/analyzers, requests
normal quit once through the existing service, waits at most30s for the exact
bound process, then stops that one service and records normal-exit.json. It never
forces termination or retries an unknown response. Unsafe
stop states are paused when the socket remains usable, then reported as failures;
they never silently qualify as a successful expected stop. No dispatched mutation
is retried after a timeout. --resume-prepared only recovers verified paused
preparation before any continuation was dispatched, preserving prior evidence.

Shared transport/process/archive helpers are imported from the existing replay
harness; its benchmark semantics/defaults are not modified by this script.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
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


def sampling_matches(status, mode, original=None):
    if not isinstance(status, dict):
        return False
    if mode not in ("preserve", "off", "on"):
        return False
    if mode != "preserve" and not (status.get("tacticalSamplingAPIAvailable") is True
            and status.get("tacticalSamplingValueValid") is True
            and status.get("tacticalSampling") is (mode == "on")):
        return False
    if original is not None:
        for field in ("tacticalSamplingAPIAvailable", "tacticalSamplingValueValid"):
            if field in original and status.get(field) is not original[field]:
                return False
        if original.get("tacticalSamplingValueValid") is True:
            return (type(status.get("tacticalSampling")) is bool
                    and status["tacticalSampling"] is original.get("tacticalSampling"))
    return True


def validate_resume_sampling(manifest, mode):
    if manifest.get("TacticalSamplingMode", "preserve") != mode:
        raise ValueError("Resume tactical sampling mode changed")


def lua_sampling_guard(status):
    """Use archived read-only values, never change/retry a runtime toggle."""
    if status.get("tacticalSamplingValueValid") is not True:
        return ""
    value = status.get("tacticalSampling")
    if type(value) is not bool:
        raise ValueError("Invalid prepared tactical sampling value")
    return ("\nassert(type(Game.GetStackingTacticalSampling)=='function' and "
            "Game.GetStackingTacticalSampling()==" + str(value).lower() +
            ", 'Prepared tactical sampling changed')\n")


def prepared(status, start, count, view_mode="preserve", sampling_mode="preserve"):
    if not isinstance(status, dict):
        return False
    return (status.get("turn") == start and status.get("autoplay") == count
            # VP observer slots can report IsHuman()==true or false. The
            # observer/pause/counter checks establish paused preparation.
            and status.get("observer") is True
            and status.get("pausePlayer") == status.get("activePlayer")
            and isinstance(status.get("activePlayer"), int) and status["activePlayer"] >= 0
            and status.get("diagnostics") == 1 and status.get("quickCombat") is True
            and status.get("quickMovement") is True and status.get("multiplayer") is False
            and view_matches(status, view_mode) and sampling_matches(status, sampling_mode))


def prepared_result(result, start, count, sampling_mode="preserve"):
    """An unknown result is not permission to replay preparation mutations."""
    return (isinstance(result, dict) and result.get("ok") is True
            and isinstance(result.get("values"), list) and len(result["values"]) == 1
            and prepared(result["values"][0], start, count, sampling_mode=sampling_mode))


def stopped(status, stop, player):
    return (status.get("turn") == stop and status.get("autoplay") == 0
            and status.get("activePlayer") == player and status.get("human") is True
            and status.get("observer") is False and status.get("returnPlayerAlive") is True)


def lua_sources(args):
    start, stop, player = args.start_turn, args.stop_turn, args.return_player
    count = stop - start
    source_mode = getattr(args, "source_mode", "observer")
    view_mode = getattr(args, "view_mode", "preserve")
    sampling_mode = getattr(args, "tactical_sampling", "preserve")
    if source_mode not in ("observer", "human"):
        raise ValueError("Unknown replay source mode")
    if view_mode not in ("preserve", "standard", "strategic"):
        raise ValueError("Unknown replay view mode")
    if sampling_mode not in ("preserve", "off", "on"):
        raise ValueError("Unknown tactical sampling mode")
    sampling_literal = tuner.lua_string(sampling_mode)
    sampling_check = f"""local requestedSampling={sampling_literal}
local samplingAPIAvailable=type(Game.GetStackingTacticalSampling)=='function'
 and type(Game.SetStackingTacticalSampling)=='function'
local originalSampling=nil
if type(Game.GetStackingTacticalSampling)=='function' then originalSampling=Game.GetStackingTacticalSampling() end
if requestedSampling~='preserve' then
 assert(samplingAPIAvailable and type(originalSampling)=='boolean','Tactical sampling APIs unavailable')
end"""
    sampling_apply = "" if sampling_mode == "preserve" else f"""
local samplingResult=Game.SetStackingTacticalSampling({str(sampling_mode == 'on').lower()})
assert(type(samplingResult)=='boolean' and samplingResult=={str(sampling_mode == 'on').lower()}
 and Game.GetStackingTacticalSampling()==samplingResult,'Tactical sampling request did not apply')"""
    sampling_continue = "" if sampling_mode == "preserve" else f"""
assert(type(Game.GetStackingTacticalSampling)=='function' and type(Game.SetStackingTacticalSampling)=='function'
 and Game.GetStackingTacticalSampling()=={str(sampling_mode == 'on').lower()},'Prepared tactical sampling changed')"""
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
result.tacticalSamplingRequested={sampling_literal}
result.tacticalSamplingAPIAvailable=type(Game.GetStackingTacticalSampling)=='function'
 and type(Game.SetStackingTacticalSampling)=='function'
result.tacticalSamplingValueValid=false
if type(Game.GetStackingTacticalSampling)=='function' then
 local sampling=Game.GetStackingTacticalSampling()
 result.tacticalSamplingValueValid=type(sampling)=='boolean'
 if result.tacticalSamplingValueValid then result.tacticalSampling=sampling end
end
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
{sampling_check}
local restored=Game.GetAIAutoPlay()
{stop_restored}
Game.SetStackingDiagnosticsLevel(1)
{sampling_apply}
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
ready.tacticalSamplingOriginal=originalSampling
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
{sampling_continue}
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
GAME_SETUP_FIELDS = ("turn", "width", "height", "worldSize", "worldType", "gameSpeed", "gameSpeedType", "aliveMajorCount")
GAME_SETUP = """
assert(Map and type(Map.GetGridSize)=='function' and type(Map.GetWorldSize)=='function'
 and type(Game.GetGameSpeedType)=='function','Game setup APIs unavailable')
local active=Game.GetActivePlayer()
assert(Players[active] and Players[active]:IsObserver() and Game.GetPausePlayer()==active
 and Game.GetAIAutoPlay()>0,'Game setup census requires paused prepared observer')
local width,height=Map.GetGridSize()
local worldSize=Map.GetWorldSize()
local speed=Game.GetGameSpeedType()
local function integer(value) return type(value)=='number' and value>-math.huge and value<math.huge and value==math.floor(value) end
assert(integer(width) and integer(height) and width>0 and height>0,'Invalid map dimensions')
assert(integer(worldSize) and worldSize>=0 and integer(speed) and speed>=0,'Invalid world/speed ID')
local world=GameInfo and GameInfo.Worlds and GameInfo.Worlds[worldSize]
local gameSpeed=GameInfo and GameInfo.GameSpeeds and GameInfo.GameSpeeds[speed]
assert(world and type(world.Type)=='string' and #world.Type>0
 and gameSpeed and type(gameSpeed.Type)=='string' and #gameSpeed.Type>0,'World/speed metadata unavailable')
local majorCount=0
for owner=0,63 do local player=Players[owner]
 if player and player:IsAlive() and not player:IsObserver() then
  assert(type(player.IsMajorCiv)=='function','Major player API unavailable')
  if player:IsMajorCiv() then majorCount=majorCount+1 end
 end
end
assert(majorCount>0,'No alive major civilizations')
return {turn=Game.GetGameTurn(),width=width,height=height,worldSize=worldSize,worldType=world.Type,
 gameSpeed=speed,gameSpeedType=gameSpeed.Type,aliveMajorCount=majorCount}
"""


def validate_game_setup(value, start):
    if not isinstance(value, dict) or value.get("turn") != start:
        raise ValueError("Game setup turn differs from paused source")
    for field in ("turn", "width", "height", "worldSize", "gameSpeed", "aliveMajorCount"):
        if type(value.get(field)) is not int:
            raise ValueError("Invalid integer game setup field: " + field)
    if (value["width"] <= 0 or value["height"] <= 0 or value["worldSize"] < 0 or value["gameSpeed"] < 0
            or not 1 <= value["aliveMajorCount"] <= 64):
        raise ValueError("Invalid positive game setup dimensions/IDs/major count")
    for field in ("worldType", "gameSpeedType"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise ValueError("Missing game setup type: " + field)
    return {field: value[field] for field in GAME_SETUP_FIELDS}


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


class ExactExitProcess:
    """Pin the original Windows process object, including PID-reuse races."""
    def __init__(self, pid, expected_ticks=None, names=()):
        if type(pid) is not int or pid <= 0:
            raise ValueError("Invalid shutdown process PID")
        self.pid, self.handle = pid, None
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.kernel.GetProcessTimes.restype = wintypes.BOOL
        self.kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.OpenProcess(0x100000 | 0x1000, False, pid)
        if not self.handle:
            raise OSError("Shutdown process is missing or inaccessible: PID " + str(pid))
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not self.kernel.GetProcessTimes(self.handle, *(ctypes.byref(t) for t in times)):
                raise OSError("Cannot read shutdown process start time")
            self.start_ticks = ((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime) + 504911232000000000
            path = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(path))
            if not self.kernel.QueryFullProcessImageNameW(self.handle, 0, path, ctypes.byref(size)):
                raise OSError("Cannot read shutdown process image")
            self.name = Path(path.value).stem.lower()
            if ((expected_ticks is not None and self.start_ticks != expected_ticks)
                    or (names and self.name not in names) or not self.alive()):
                raise ValueError("Exact shutdown PID/start/image did not match")
        except Exception:
            self.close()
            raise

    def alive(self):
        value = self.kernel.WaitForSingleObject(self.handle, 0)
        if value == 258:
            return True
        if value == 0:
            return False
        raise OSError("Cannot read bound shutdown process state")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def session_stamp(path):
    # Filesystem identity only: never extract, display or archive a credential.
    stat = Path(path).stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


def session_service_pid(path):
    # Whitelist only PID metadata. The auth token is never an identity field,
    # accessed here, returned, displayed or copied into replay evidence.
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    pid = value.get("pid") if isinstance(value, dict) else None
    if type(pid) is not int or pid <= 0:
        raise ValueError("Persistent session has no valid service PID metadata")
    return pid


class NormalExitBinding:
    def __init__(self, args, watcher, guard_pids):
        self.processes = []
        self.session = Path(args.session).resolve(strict=True)
        self.stamp = session_stamp(self.session)
        service_pid = watcher.get("Service")
        if (type(service_pid) is not int or service_pid <= 0
                or len({args.game_pid, service_pid, *guard_pids}) != 4):
            raise ValueError("Optional shutdown requires the exact existing Service PID in watcher manifest")
        if session_service_pid(self.session) != service_pid:
            raise ValueError("Persistent session PID differs from the exact existing service")
        try:
            self.game = ExactExitProcess(args.game_pid, args.start_ticks, ("civilizationv_dx11",))
            self.processes.append(self.game)
            self.service = ExactExitProcess(service_pid, names=("python", "pythonw", "python3"))
            self.processes.append(self.service)
            self.guards = []
            for pid in guard_pids:
                process = ExactExitProcess(pid, names=("pwsh", "powershell"))
                self.processes.append(process)
                self.guards.append(process)
            self.verify()
        except Exception:
            self.close()
            raise

    def verify(self, *, game_required=True, guards_required=True):
        if session_stamp(self.session) != self.stamp:
            raise ValueError("Bound persistent service session changed; do not reconnect")
        if session_service_pid(self.session) != self.service.pid:
            raise ValueError("Bound persistent session PID changed; do not reconnect")
        if not self.service.alive() or (game_required and not self.game.alive()):
            raise ValueError("Bound game/service process lost; do not retry")
        if guards_required and any(not process.alive() for process in self.guards):
            raise ValueError("Bound watchdog process lost before verified stop")

    def proof(self):
        return {"GamePID": self.game.pid, "GameStartTicks": self.game.start_ticks,
                "ServicePID": self.service.pid, "ServiceStartTicks": self.service.start_ticks,
                "GuardPIDs": [p.pid for p in self.guards], "GuardStartTicks": [p.start_ticks for p in self.guards],
                "SessionPath": str(self.session), "SessionFileIdentity": list(self.stamp)}

    def close(self):
        for process in self.processes:
            process.close()


def control_quit(session):
    # A new local IPC client, using the already-connected service; no engine
    # connection is opened. The convenience command already implements quit.
    try:
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/civ5_control.py"),
                                 "--session", str(session), "--timeout", "10", "quit"],
                                capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired as exc:
        def decoded(value):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
        return {"acknowledged": False, "timedOut": True, "stdout": decoded(exc.stdout), "stderr": decoded(exc.stderr)}
    try:
        response = json.loads(result.stdout)
    except (ValueError, TypeError):
        response = None
    return {"exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "result": response,
            "acknowledged": (result.returncode == 0 and isinstance(response, dict)
                             and response.get("ok") is True and response.get("values") == ["quit requested"])}


class BehaviorReplay(perf.Replay):
    def __init__(self, args):
        super().__init__(args)
        self.status_source, self.prepare_source, self.continue_source = lua_sources(args)
        self.view_source = lua_view_preparation(args)
        self.deadline = None
        self.exit_binding = None
        self.normal_exit_proof = None

    def call(self, *args, **kwargs):
        if self.exit_binding:
            self.exit_binding.verify(guards_required=not self.safe_stop)
        result = super().call(*args, **kwargs)
        if self.exit_binding:
            self.exit_binding.verify(guards_required=not self.safe_stop)
        return result

    def states(self, *args, **kwargs):
        if self.exit_binding:
            self.exit_binding.verify(guards_required=not self.safe_stop)
        result = super().states(*args, **kwargs)
        if self.exit_binding:
            self.exit_binding.verify(guards_required=not self.safe_stop)
        return result

    def close_exit_binding(self):
        if self.exit_binding:
            self.exit_binding.close()

    def quit_after_complete(self):
        if not getattr(self.args, "quit_after_complete", False):
            return None
        path = self.run / "normal-exit.json"
        if path.exists():
            raise ValueError("A normal shutdown attempt already exists; never repeat it")
        proof = {"requested": True, "utc": perf.utc(), "status": "validating",
                 "quitDispatched": False, "quitAcknowledged": False, "gameExitConfirmed": False,
                 "serviceStopDispatched": False, "forcedTermination": False, "mutationRetried": False}
        self.normal_exit_proof = proof
        def record():
            perf.write_json(path, proof)
            self.manifest["NormalExit"] = proof.copy()
            self.save_manifest()
        try:
            record()
            if (not self.safe_stop or not self.exit_binding
                    or not stopped(self.manifest.get("Stopped", {}), self.args.stop_turn, self.args.return_player)
                    or self.manifest.get("Status") != "completed_stopped_game_open"
                    or self.manifest.get("SaveSHA256After") != self.args.save_sha
                    or not self.manifest.get("AnalysisCompletedUTC")
                    or type(self.manifest.get("UnitCount")) is not int or self.manifest["UnitCount"] <= 0
                    or type(self.manifest.get("CityCount")) is not int or self.manifest["CityCount"] <= 0
                    or not (self.run / "world-after.json").is_file()
                    or not any((self.run / "native-segments").glob("*.log"))):
                raise ValueError("Normal quit requires verified stop, nonempty census, archive and completed analyses")
            census = json.loads((self.run / "world-after.json").read_text(encoding="utf-8-sig"))
            if not isinstance(census, dict) or census.get("expectedTurn") != self.args.stop_turn or not isinstance(census.get("players"), list):
                raise ValueError("After census does not establish the expected bounded stop")
            units, cities = 0, 0
            for player in census["players"]:
                if (not isinstance(player, dict) or not isinstance(player.get("units"), (list, dict))
                        or not isinstance(player.get("cities"), (list, dict))
                        or isinstance(player["units"], dict) and player["units"]
                        or isinstance(player["cities"], dict) and player["cities"]):
                    raise ValueError("Invalid after census arrays")
                units += len(player["units"])
                cities += len(player["cities"])
            if units != self.manifest["UnitCount"] or cities != self.manifest["CityCount"]:
                raise ValueError("After census counts differ from verified manifest")
            for script in ("summarize-stacking-diagnostics.py", "analyze-assault-campaign.py", "profile-campaign-log.py"):
                result = json.loads((self.run / (script + ".result.json")).read_text(encoding="utf-8-sig"))
                if result.get("exitCode") != 0:
                    raise ValueError("Normal quit requires every offline analyzer to succeed")
            self.exit_binding.verify(guards_required=False)
            proof.update(self.exit_binding.proof())
            live = self.call("InGame", self.status_source, "verify-stop-before-normal-quit", timeout=10)[0]
            if not stopped(live, self.args.stop_turn, self.args.return_player):
                raise ValueError("Completed replay state changed before normal quit")
            proof.update(status="requesting_quit", quitDispatched=True, quitDispatchedUTC=perf.utc())
            record()
            self.progress("normal-quit-request", gamePID=self.args.game_pid)
            reply = control_quit(self.args.session)
            proof["quitResponse"] = reply
            record()
            if reply.get("acknowledged") is not True:
                raise ValueError("Normal quit response unknown or rejected; no retry or service reconnect")
            proof.update(quitAcknowledged=True, status="waiting_game_exit")
            record()
            began = time.monotonic()
            deadline = began + 30
            while self.exit_binding.game.alive():
                self.exit_binding.verify(game_required=False, guards_required=False)
                if time.monotonic() >= deadline:
                    raise TimeoutError("Normal quit acknowledged but exact game process did not exit within30s")
                time.sleep(min(.1, max(0, deadline-time.monotonic())))
            proof.update(gameExitConfirmed=True, gameExitUTC=perf.utc(), gameExitWaitSeconds=time.monotonic()-began)
            record()
            self.exit_binding.verify(game_required=False, guards_required=False)
            proof.update(status="stopping_service", serviceStopDispatched=True)
            record()
            # /stop shuts down only the bound existing HTTP service. It does
            # not reconnect to the engine or issue any additional Lua action.
            stop = tuner.call_service(self.args.session, "stop", {"timeout": 5}, 5)
            proof["serviceStopResponse"] = stop
            record()
            if not isinstance(stop, dict) or stop.get("ok") is not True or stop.get("stopping") is not True:
                raise ValueError("Service stop response unknown or rejected; never retry")
            deadline = time.monotonic() + 5
            while self.exit_binding.service.alive() or self.exit_binding.session.exists():
                if self.exit_binding.session.exists() and session_stamp(self.exit_binding.session) != self.exit_binding.stamp:
                    raise ValueError("Service session replaced after stop; do not stop its replacement")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Service accepted stop but exact process/session remain after5s")
                time.sleep(min(.05, max(0, deadline-time.monotonic())))
            proof.update(status="completed", serviceExitConfirmed=True, sessionFileAbsent=True, completedUTC=perf.utc())
            self.manifest["Status"] = "completed_game_closed_service_stopped"
            record()
            return proof
        except Exception as exc:
            proof.update(status="failed", error=str(exc), failedUTC=perf.utc())
            record()
            raise

    def game_setup(self):
        live = validate_game_setup(self.call("InGame", GAME_SETUP, "read-game-setup")[0], self.args.start_turn)
        path = self.run / "game-setup.json"
        if path.exists():
            original = json.loads(path.read_text(encoding="utf-8-sig"))
            if (validate_game_setup(original, self.args.start_turn) != live
                    or original.get("sourceSaveSHA256") != self.args.save_sha
                    or ("GameSetup" in self.manifest and self.manifest["GameSetup"] != original)):
                raise ValueError("Existing game setup proof differs from live source/manifest; preserve it")
            proof = original
        else:
            if "GameSetup" in self.manifest:
                raise ValueError("Manifest game setup proof exists without its archived file")
            proof = {"utc": perf.utc(), "sourceSaveSHA256": self.args.save_sha, **live}
            perf.write_json(path, proof)
        self.manifest["GameSetup"] = proof
        self.save_manifest()
        return proof

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
        if getattr(self.args, "quit_after_complete", False):
            self.exit_binding = NormalExitBinding(self.args, watcher, guards)
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
            validate_resume_sampling(self.manifest, self.args.tactical_sampling)
            if self.manifest.get("QuitAfterComplete", False) != getattr(self.args, "quit_after_complete", False):
                raise ValueError("Resume normal-shutdown preference changed")
            if self.exit_binding and self.manifest.get("NormalExitBinding") != self.exit_binding.proof():
                raise ValueError("Resume game/service/guard/session shutdown binding changed")
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
            if not prepared_result(result, self.args.start_turn, count, self.args.tactical_sampling):
                raise ValueError("Original preparation did not establish exact bounded paused state")
            snapshot_path = self.run / f"manifest-before-resume-{self.sequence+1:03d}.json"
            with snapshot_path.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(self.manifest, indent=2)+"\n")
            failure = self.manifest.pop("Failure", None)
            if failure and failure not in self.manifest.setdefault("FailureHistory", []):
                self.manifest["FailureHistory"].append(failure)
            live = self.call("InGame", self.status_source, "resume-paused-behavior-state")[0]
            if (not prepared(live, self.args.start_turn, count, sampling_mode=self.args.tactical_sampling)
                    or not live["returnPlayerAlive"] or not sampling_matches(live, self.args.tactical_sampling,
                                                                           result["values"][0])):
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
                             "TacticalSamplingMode": self.args.tactical_sampling,
                             "ReturnPlayer": self.args.return_player, "DiagnosticLevel": 1, "QuickCombat": True, "QuickMovement": True,
                             "PID": self.args.game_pid, "StartTicks": self.args.start_ticks, "StartedUTC": perf.utc(),
                             "ExpectedDLLSHA256": self.args.expected_dll_sha, "WatchCity": self.args.watch_city,
                             "Limits": "First/return turns partial; human-source mode explicitly performs VP slot-change diplomacy/production/research/policy decisions; compare identical source/preparation only"}
            if self.exit_binding:
                self.manifest.update(QuitAfterComplete=True, NormalExitBinding=self.exit_binding.proof())
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
            if not prepared(ready, self.args.start_turn, count, sampling_mode=self.args.tactical_sampling):
                raise ValueError("Behavior preparation failed ready-state validation")
            self.manifest["Prepared"] = ready
            self.manifest["ViewModeOriginal"] = ready.get("viewModeOriginal")
            self.manifest["ViewModePrepared"] = ready.get("strategicView")
            self.manifest["TacticalSamplingOriginal"] = ready.get("tacticalSamplingOriginal")
            self.manifest["TacticalSamplingAPIAvailable"] = ready.get("tacticalSamplingAPIAvailable")
            self.manifest["TacticalSamplingPrepared"] = ready.get("tacticalSampling")
            self.save_manifest()
        proof = perf.gamecore_metadata(lambda: perf.exact_process(self.args.game_pid, self.args.start_ticks, guards),
                                       lambda **fields: self.progress("loaded-dll-metadata", **fields))
        module = proof["Modules"][0]
        if perf.sha(module) != self.args.expected_dll_sha:
            raise ValueError("Loaded gamecore path's DLL file does not match expected deployment SHA")
        self.manifest.update(InstalledDLL=module, SHA256=perf.sha(module))
        perf.write_json(self.run / "loaded-dll.json", {**proof, "Path": module, "SHA256": perf.sha(module)})
        self.archive_native()
        self.game_setup()
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
        initial_ready = self.manifest.get("Prepared", result["values"][0] if self.args.resume_prepared else {})
        if (not prepared(final_ready, self.args.start_turn, count, self.args.view_mode, self.args.tactical_sampling)
                or not final_ready["returnPlayerAlive"] or not isinstance(view_proof, dict)
                or view_proof.get("semantics") != "late_paused_view_preparation"
                or view_proof.get("viewModeRequested") != self.args.view_mode
                or view_proof.get("strategicView") != final_ready.get("strategicView")
                or not sampling_matches(final_ready, self.args.tactical_sampling, initial_ready)):
            raise ValueError("Final paused view preparation failed validation")
        self.manifest.setdefault("PreparedInitial", initial_ready.copy())
        self.manifest["Prepared"] = {**initial_ready, **final_ready, "viewModeResult": final_ready.get("strategicView")}
        self.manifest["ViewPreparation"] = view_proof
        self.manifest["ViewModePrepared"] = final_ready.get("strategicView")
        self.manifest["TacticalSamplingAPIAvailable"] = final_ready.get("tacticalSamplingAPIAvailable")
        self.manifest["TacticalSamplingPrepared"] = final_ready.get("tacticalSampling")
        self.manifest["TacticalSamplingOriginal"] = initial_ready.get("tacticalSamplingOriginal")
        self.manifest["Status"] = "armed"
        self.save_manifest()
        self.call("LoadScreen", lua_sampling_guard(final_ready) + self.continue_source, "continue-bounded-behavior")
        self.manifest.update(Status="running", ContinuedUTC=perf.utc())
        self.save_manifest()
        self.deadline = time.monotonic() + self.args.maximum_seconds
        while True:
            status = self.call("InGame", self.status_source, "behavior-status")[0]
            self.progress("behavior-progress", status=status)
            if (stopped(status, self.args.stop_turn, self.args.return_player)
                    and sampling_matches(status, self.args.tactical_sampling, final_ready)):
                self.safe_stop = True
                (self.run / "complete.signal").write_text("Expected behavior replay stopped "+perf.utc()+"\n", encoding="utf-8")
                self.manifest.update(Status="stopped", Stopped=status, StoppedUTC=perf.utc())
                self.manifest["ViewModeStopped"] = status.get("strategicView")
                self.manifest["TacticalSamplingStopped"] = status.get("tacticalSampling")
                self.save_manifest()
                break
            if (status["turn"] > self.args.stop_turn or status["autoplay"] == 0 or not status["returnPlayerAlive"]
                    or not view_matches(status, self.args.view_mode)
                    or not sampling_matches(status, self.args.tactical_sampling, final_ready)
                    or time.monotonic() >= self.deadline):
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
        self.manifest["AnalysisCompletedUTC"] = perf.utc()
        self.save_manifest()
        exit_proof = self.quit_after_complete()
        self.progress("behavior-replay-complete", run=str(self.run), nativeRun=self.manifest["NativeRun"], gameLeftOpen=exit_proof is None)


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
    assert "local samplingResult=Game.SetStackingTacticalSampling" not in preparation
    assert sampling_matches(ready, "preserve") and not sampling_matches(ready, "on")
    validate_resume_sampling({}, "preserve")
    for old, new in (("preserve", "on"), ("off", "on"), ("on", "preserve")):
        try: validate_resume_sampling({"TacticalSamplingMode": old}, new)
        except ValueError as exc: assert "sampling mode changed" in str(exc)
        else: raise AssertionError("Resume sampling mode changed")
    assert prepared_result({"ok": True, "values": [ready]}, 215, 15)
    for unknown in (None, {}, {"ok": False, "values": [ready]}, {"ok": True, "values": []},
                    {"ok": True, "values": [None]}, {"ok": True, "values": "timeout"}):
        assert not prepared_result(unknown, 215, 15)
    setup_fixture = dict(turn=215,width=88,height=58,worldSize=3,worldType="WORLDSIZE_STANDARD",
                         gameSpeed=1,gameSpeedType="GAMESPEED_STANDARD",aliveMajorCount=8)
    assert validate_game_setup(setup_fixture,215) == setup_fixture
    for changes in ({"turn":216},{"width":0},{"height":True},{"worldSize":-1},{"gameSpeed":1.5},
                    {"worldType":""},{"gameSpeedType":None},{"aliveMajorCount":0},{"aliveMajorCount":65}):
        try: validate_game_setup({**setup_fixture,**changes},215)
        except ValueError: pass
        else: raise AssertionError("Invalid game setup proof admitted")
    with tempfile.TemporaryDirectory(prefix="civ5-replay-setup-") as temporary:
        replay = object.__new__(BehaviorReplay)
        replay.run = Path(temporary)
        replay.args = argparse.Namespace(start_turn=215,save_sha="A"*64)
        replay.manifest = {}
        def fake_call(context, source, label):
            assert context=="InGame" and source==GAME_SETUP and label=="read-game-setup"
            return [setup_fixture.copy()]
        replay.call = fake_call
        replay.save_manifest = lambda: None
        first = replay.game_setup()
        archived = (replay.run/"game-setup.json").read_bytes()
        assert first == replay.manifest["GameSetup"] and replay.game_setup() == first
        assert (replay.run/"game-setup.json").read_bytes() == archived
        replay.call = lambda *arguments: [{**setup_fixture,"width":89}]
        try: replay.game_setup()
        except ValueError as exc: assert "differs from live" in str(exc)
        else: raise AssertionError("Changed live map replaced existing game setup proof")
        assert (replay.run/"game-setup.json").read_bytes() == archived and replay.manifest["GameSetup"]==first
        replay.call = fake_call
        replay.args.save_sha = "B"*64
        try: replay.game_setup()
        except ValueError: pass
        else: raise AssertionError("Changed source SHA reused game setup proof")
        assert (replay.run/"game-setup.json").read_bytes() == archived
    runtime = ROOT / "work/lua-validation"
    if runtime.exists():
        sys.path.insert(0, str(runtime))
        from lupa.lua51 import LuaRuntime
        lua = LuaRuntime(unpack_returned_tuples=True)
        syntax = lua.eval("function(s) assert(loadstring(s));return true end")
        for source in (status, preparation, continuation, OWNER_LIST, GAME_SETUP, OWNER_SNAPSHOT.replace("OWNER_ARGUMENT", "0"), PAUSE_UNEXPECTED):
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
        # Actual generated Lua: default preserve keeps old-DLL support, explicit
        # APIs are validated before any prep mutation, and toggles never retry.
        assert preserved['tacticalSamplingAPIAvailable'] is False
        assert preserved['tacticalSamplingValueValid'] is False and 'tacticalSampling' not in preserved
        sampling_mock = """
state.sampling=ORIGINAL_SAMPLING;state.samplingCalls=0
Game.GetStackingTacticalSampling=function() return state.sampling end
Game.SetStackingTacticalSampling=function(value)
 assert(type(value)=='boolean' and state.pause==state.active and state.turn==215 and state.diag==1)
 calls[#calls+1]={'sampling',value};state.samplingCalls=state.samplingCalls+1;state.sampling=value;return value
end
"""
        for mode, original, desired, setters in (("preserve",False,False,0),("preserve",True,True,0),
                ("off",False,False,1),("off",True,False,1),("on",False,True,1),("on",True,True,1)):
            configured = argparse.Namespace(**vars(human_args), tactical_sampling=mode)
            sample_status, sample_prepare, sample_continue = lua_sources(configured)
            assert syntax(sample_status) and syntax(sample_prepare) and syntax(sample_continue)
            if mode != "preserve":
                assert sample_prepare.index('Tactical sampling APIs unavailable') < sample_prepare.index('Game.SetStackingDiagnosticsLevel(1)')
                assert sample_prepare.index('Game.SetStackingDiagnosticsLevel(1)') < sample_prepare.index('local samplingResult=')
            lua.execute(human_reset+"\n"+sampling_mock.replace('ORIGINAL_SAMPLING',str(original).lower()))
            observed = dict(lua.execute(sample_prepare).items())
            assert prepared(observed,215,15,sampling_mode=mode)
            assert observed['tacticalSamplingOriginal'] is original and observed['tacticalSampling'] is desired
            assert observed['tacticalSamplingRequested']==mode and observed['tacticalSamplingAPIAvailable'] is True
            assert lua.globals().state.samplingCalls==setters and len(lua.globals().calls)==5+setters
            assert sampling_matches(dict(lua.execute(sample_status).items()),mode,observed)
            lua.execute("state.sampling=not state.sampling;state.continued=0;Game.SetPausePlayer=function(n) assert(n==8 or n==-1);state.pause=n end")
            changed = dict(lua.execute(sample_status).items())
            assert not sampling_matches(changed,mode,observed)
            try: lua.execute(lua_sampling_guard(observed)+sample_continue)
            except Exception as exc: assert 'Prepared tactical sampling changed' in str(exc)
            else: raise AssertionError('Changed sampling continued')
            assert lua.globals().state.continued==0 and lua.globals().state.pause==8
            lua.execute('state.sampling='+str(desired).lower())
            assert lua.execute(lua_sampling_guard(observed)+sample_continue)=='continued'
            assert lua.globals().state.continued==1 and lua.globals().state.samplingCalls==setters
        for mode in ('off','on'):
            configured = argparse.Namespace(**vars(human_args), tactical_sampling=mode)
            _, source, _ = lua_sources(configured)
            for unavailable in ("Game.GetStackingTacticalSampling=nil;Game.SetStackingTacticalSampling=nil",
                    "Game.GetStackingTacticalSampling=function() return false end;Game.SetStackingTacticalSampling=nil",
                    "Game.GetStackingTacticalSampling=nil;Game.SetStackingTacticalSampling=function() end",
                    "Game.GetStackingTacticalSampling=function() return 0 end;Game.SetStackingTacticalSampling=function() end"):
                lua.execute(human_reset+'\n'+unavailable)
                try: lua.execute(source)
                except Exception as exc: assert 'Tactical sampling APIs unavailable' in str(exc)
                else: raise AssertionError('Explicit sampling admitted missing/invalid APIs')
                assert len(lua.globals().calls)==0 and lua.globals().state.auto==0 and lua.globals().state.pause==0
        configured = argparse.Namespace(**vars(human_args), tactical_sampling='on')
        _, source, _ = lua_sources(configured)
        for invalid_result in ('nil','0','false'):
            lua.execute(human_reset+'\n'+sampling_mock.replace('ORIGINAL_SAMPLING','false')+"\n"+
                "Game.SetStackingTacticalSampling=function(value) state.samplingCalls=state.samplingCalls+1;return "+invalid_result+" end")
            try: lua.execute(source)
            except Exception as exc: assert 'Tactical sampling request did not apply' in str(exc)
            else: raise AssertionError('Unapplied sampling accepted')
            assert lua.globals().state.samplingCalls==1 and lua.globals().state.auto==0 and lua.globals().state.pause==0
        # Old API omission remains safe in both generated source modes.
        lua.execute(human_reset+"\nGame.GetStackingTacticalSampling=nil;Game.SetStackingTacticalSampling=nil")
        old_ready = dict(lua.execute(human_prepare).items())
        assert prepared(old_ready,215,15) and not old_ready['tacticalSamplingAPIAvailable']
        assert sampling_matches(old_ready,'preserve',old_ready) and lua_sampling_guard(old_ready)==''
        setup_mock = """
Map={GetGridSize=function() return 88,58 end,GetWorldSize=function() return 3 end}
Game.GetGameSpeedType=function() return 1 end
GameInfo.Worlds={[3]={Type='WORLDSIZE_STANDARD'}}
GameInfo.GameSpeeds={[1]={Type='GAMESPEED_STANDARD'}}
Players[0].IsMajorCiv=function() return true end
Players[1].IsMajorCiv=function() return true end
Players[2]={IsAlive=function() return true end,IsObserver=function() return false end,IsMajorCiv=function() return false end}
Players[3]={IsAlive=function() return false end,IsObserver=function() return false end,IsMajorCiv=function() return true end}
"""
        lua.execute(setup_mock)
        actual = validate_game_setup(dict(lua.execute(GAME_SETUP).items()),215)
        assert actual == {**setup_fixture,"aliveMajorCount":2}
        assert len(lua.globals().calls)==5 and lua.globals().state.pause==8 and lua.globals().state.auto==15
        for invalid in ("Map.GetGridSize=nil","Map.GetWorldSize=nil","Game.GetGameSpeedType=nil",
                "Map.GetGridSize=function() return 0,58 end","Map.GetGridSize=function() return true,58 end",
                "Map.GetGridSize=function() return math.huge,58 end","Map.GetWorldSize=function() return -1 end",
                "GameInfo.Worlds=nil","GameInfo.GameSpeeds[1].Type=nil","Players[0].IsMajorCiv=nil"):
            lua.execute(setup_mock+"\n"+invalid)
            try: lua.execute(GAME_SETUP)
            except Exception: pass
            else: raise AssertionError("Missing/invalid game setup API or metadata admitted")
            assert len(lua.globals().calls)==5 and lua.globals().state.pause==8 and lua.globals().state.auto==15
    print(json.dumps({"ok": True, "offline": True, "gameCommandsSent": 0, "negativeStateCases": 12,
                      "lua51Validated": runtime.exists(), "snapshotsAndCityWatchValidated": runtime.exists(),
                      "explicitHumanSourceValidated": runtime.exists(), "humanSourceNegativeCases": 6,
                      "viewModesValidated": runtime.exists(), "viewMissingAPINegativeCases": 3,
                      "delayedViewRestorationValidated": runtime.exists(), "tacticalSamplingModesValidated": runtime.exists(),
                      "samplingMissingAPINegativeCases": 8, "samplingUnknownResultNegativeCases": 9,
                      "samplingDriftContinuationAndPollCases": 6, "samplingResumeModeChangeCases": 3,
                      "gameSetupLua51Validated": runtime.exists(), "gameSetupAPINegativeCases":10,
                      "gameSetupMetadataNegativeCases":9,"gameSetupResumeProofPreserved":True}))


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
    parser.add_argument("--tactical-sampling", choices=("preserve", "off", "on"), default="preserve",
                        help="Preserve sampled-profiler state, including old DLLs; explicit on/off validates optional boolean APIs before preparation and verifies every status")
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
    parser.add_argument("--quit-after-complete", action="store_true",
                        help="After verified stop/census/archive/analyses, request normal quit once and stop the exact existing service; default leaves game open")
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
        if args.quit_after_complete:
            failure["normalExit"] = replay.normal_exit_proof
            failure["gameLeftOpen"] = False if (replay.normal_exit_proof or {}).get("gameExitConfirmed") else None
        replay.record_failure(failure)
        print(json.dumps(failure), flush=True);return 1
    finally:
        replay.close_exit_binding()


if __name__ == "__main__":
    raise SystemExit(main())
