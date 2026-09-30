"""Verify benchmark mods, restoring only an empty list at the fresh main menu.

Uses the existing persistent civ5_tuner service sequentially; never starts a
connection/service, activates mods or loads a game. A mismatched nonempty list
is left unchanged. Ambiguous mutations/timeouts are never retried, including
rerunning this helper with the same evidence directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import civ5_tuner as tuner

UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z")


def expected_mods(items):
    if not isinstance(items, list) or not items:
        raise ValueError("Expected mods must be a nonempty explicit ModID/Version list")
    result, seen = [], set()
    for item in items:
        if (not isinstance(item, dict) or not isinstance(item.get("ModID"), str)
                or not UUID.fullmatch(item["ModID"]) or type(item.get("Version")) is not int
                or not 1 <= item["Version"] <= 2147483647):
            raise ValueError("Expected mods require canonical UUIDs and positive integer versions")
        ident = item["ModID"].lower()
        if ident in seen:
            raise ValueError("Duplicate expected mod UUID")
        seen.add(ident)
        result.append({"ModID": ident, "Version": item["Version"]})
    return result


def lua_source(expected):
    literals = ",\n".join(" {ModID=" + tuner.lua_string(m["ModID"]) + ",Version=" + str(m["Version"]) + "}" for m in expected)
    return "local expected={\n" + literals + "\n}\n" + r'''
local guid="^%x%x%x%x%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$"
local function read()
 local ok,mods=pcall(Modding.GetEnabledModsByActivationOrder)
 if not ok or type(mods)~="table" then return nil,"enabled_list_unavailable" end
 local rows,seen={},{}
 for _,mod in ipairs(mods) do
  if type(mod)~="table" or type(mod.ModID)~="string" or not string.match(mod.ModID,guid)
   or type(mod.Version)~="number" or mod.Version~=math.floor(mod.Version) or mod.Version<1 or mod.Version>2147483647 then
   return nil,"invalid_enabled_entry"
  end
  local id=string.lower(mod.ModID)
  if seen[id] then return nil,"duplicate_enabled_uuid" end
  seen[id]=mod.Version;rows[#rows+1]={ModID=id,Version=mod.Version}
 end
 return rows,nil,seen
end
local function exact(rows,set)
 if not rows or #rows~=#expected then return false end
 for _,mod in ipairs(expected) do if set[mod.ModID]~=mod.Version then return false end end
 return true
end
local before,error,set=read()
if not before then return {ok=false,status="invalid_enabled_list",error=error,attempted=0} end
if #before>0 then
 if not exact(before,set) then return {ok=false,status="nonempty_mismatch",before=before,after=before,attempted=0} end
 local after,afterError,afterSet=read()
 return {ok=exact(after,afterSet),status=exact(after,afterSet) and "already_exact" or "verification_failed",
  error=afterError,before=before,after=after,attempted=0}
end
for index,mod in ipairs(expected) do
 local ok=pcall(Modding.EnableMod,mod.ModID,mod.Version)
 if not ok then
  local after,afterError=read()
  return {ok=false,status="enable_failed",failedIndex=index,attempted=index,before=before,after=after,error=afterError}
 end
end
local after,afterError,afterSet=read()
return {ok=exact(after,afterSet),status=exact(after,afterSet) and "restored" or "verification_failed",
 error=afterError,before=before,after=after,attempted=#expected}
'''


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def ensure(run_dir, expected, session, timeout, service=tuner.call_service):
    run = run_dir.resolve()
    allowed = (ROOT / "work/test-runs").resolve()
    if run == allowed or not run.is_relative_to(allowed):
        raise ValueError("Run directory must be below this project's work/test-runs")
    expected = expected_mods(expected)
    run.mkdir(parents=True, exist_ok=True)
    # Preserve the dispatch intent even on an ambiguous timeout. A new process
    # invocation cannot silently retry the same directory's mutation.
    paths = {key: run / name for key, name in {
        "contexts": "ensure-mods-contexts.json", "source": "ensure-mods.lua",
        "dispatch": "ensure-mods-dispatched.json", "response": "ensure-mods-result.json"}.items()}
    if any(path.exists() for path in paths.values()):
        raise ValueError("Mod-check evidence already exists; do not redispatch")
    expected_path = run / "expected-mods.json"
    if expected_path.exists():
        if expected_mods(json.loads(expected_path.read_text(encoding="utf-8-sig"))) != expected:
            raise ValueError("Existing expected-mods.json differs from explicit input")
    else:
        write_json(expected_path, expected)
    source = lua_source(expected)
    paths["source"].write_text(source, encoding="utf-8")
    try:
        contexts = service(session, "states", {"timeout": timeout}, timeout)
    except Exception as exc:
        write_json(paths["contexts"], {"ok": False, "errorType": type(exc).__name__, "mutationDispatched": False})
        raise RuntimeError("Main-menu context verification failed before mutation") from None
    write_json(paths["contexts"], contexts)
    names = {item["name"] for item in contexts.get("contexts", [])}
    if not contexts.get("ok") or "InGame" in names or "ModsBrowser" not in names:
        raise ValueError("Requires a fresh main-menu ModsBrowser context with InGame absent")
    write_json(paths["dispatch"], {"utc": datetime.now(timezone.utc).isoformat(),
        "context": "ModsBrowser", "expectedCount": len(expected), "mutationRetried": False})
    started = time.monotonic()
    try:
        response = service(session, "exec", {"context": "ModsBrowser", "source": source, "timeout": timeout}, timeout)
    except Exception as exc:
        write_json(paths["response"], {"ok": False, "status": "unknown_outcome", "errorType": type(exc).__name__,
                                      "seconds": time.monotonic() - started, "mutationRetried": False})
        raise RuntimeError("Mod-check dispatch failed; outcome unknown, inspect evidence without retrying") from None
    write_json(paths["response"], {"seconds": time.monotonic() - started, "result": response, "mutationRetried": False})
    values = response.get("values", [])
    if not response.get("ok") or len(values) != 1 or not isinstance(values[0], dict) or not values[0].get("ok"):
        raise RuntimeError("Mod-check failed; enabled list preserved in evidence, no retry or activation")
    result = values[0]
    if result.get("status") not in ("restored", "already_exact"):
        raise RuntimeError("Unexpected mod-check response; inspect evidence")
    actual = expected_mods(result.get("after"))
    if {m["ModID"]: m["Version"] for m in actual} != {m["ModID"]: m["Version"] for m in expected}:
        raise RuntimeError("Returned enabled mod set differs from explicit expectation")
    return {"ok": True, "status": result["status"], "expectedCount": len(expected),
            "attempted": result.get("attempted"), "runDirectory": str(run)}


def self_test():
    sys.path.insert(0, str(ROOT / "work/lua-validation"))
    from lupa.lua51 import LuaRuntime
    expected = [{"ModID": "11111111-2222-3333-4444-555555555555", "Version": 1},
                {"ModID": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "Version": 2}]
    source = lua_source(expected_mods(expected))
    checks = 0
    def check(value):
        nonlocal checks
        checks += 1
        assert value
    def execute(initial, mode="normal"):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute('mods={};calls={};mode=' + tuner.lua_string(mode) + r'''
Modding={GetEnabledModsByActivationOrder=function() return mods end,
 EnableMod=function(id,version) calls[#calls+1]={id,version};if mode=="error" and #calls==2 then error("enable failed") end
  if mode~="ignore" or #calls~=2 then mods[#mods+1]={ModID=id,Version=version} end end,
 DisableMod=function() error("must never disable") end}
''')
        for item in initial:
            lua.execute("mods[#mods+1]={ModID=" + tuner.lua_string(item["ModID"]) + ",Version=" + str(item["Version"]) + "}")
        result = lua.execute(source)
        return lua, result
    lua, result = execute([])
    check(result["ok"] and result["status"] == "restored" and len(lua.globals().calls) == 2)
    check(lua.globals().calls[1][1] == expected[0]["ModID"] and lua.globals().calls[2][1] == expected[1]["ModID"])
    for initial in (list(reversed(expected)), [{**m, "ModID": m["ModID"].upper()} for m in expected]):
        lua, result = execute(initial);check(result["ok"] and result["status"] == "already_exact" and len(lua.globals().calls) == 0)
    for initial in ([expected[0]], [{**expected[0], "Version": 9}, expected[1]], [*expected, {"ModID": "99999999-8888-7777-6666-555555555555", "Version": 3}]):
        lua, result = execute(initial);check(not result["ok"] and result["status"] == "nonempty_mismatch" and len(lua.globals().calls) == 0 and len(lua.globals().mods) == len(initial))
    for mode in ("error", "ignore"):
        lua, result = execute([], mode);check(not result["ok"] and len(lua.globals().calls) == 2 and len(lua.globals().mods) == 1)
    lua, result = execute([expected[0], expected[0]]);check(not result["ok"] and result["status"] == "invalid_enabled_list" and len(lua.globals().calls) == 0)
    for invalid in ([], [{**expected[0], "Version": True}], [{**expected[0], "Version": 0}], [{**expected[0], "Version": 1.5}], [{**expected[0], "ModID": '";EnableMod();--'}], [expected[0], {**expected[0], "ModID": expected[0]["ModID"].upper()}]):
        try: expected_mods(invalid)
        except ValueError: check(True)
        else: check(False)
    with tempfile.TemporaryDirectory(dir=ROOT / "work/test-runs", prefix="ensure-mods-fixture-") as temporary:
        base = Path(temporary);calls = []
        def guarded(session, endpoint, job, timeout):
            calls.append(endpoint)
            return {"ok": True, "contexts": [{"name": "ModsBrowser"}, {"name": "InGame"}]}
        try: ensure(base / "ingame", expected, "not-a-session", 3, guarded)
        except ValueError: check(calls == ["states"])
        else: check(False)
        calls.clear()
        def timed_out(session, endpoint, job, timeout):
            calls.append(endpoint)
            if endpoint == "states": return {"ok": True, "contexts": [{"name": "ModsBrowser"}]}
            raise TimeoutError()
        try: ensure(base / "timeout", expected, "not-a-session", 3, timed_out)
        except RuntimeError: check(calls == ["states", "exec"] and (base / "timeout/ensure-mods-dispatched.json").exists())
        else: check(False)
        calls.clear()
        try: ensure(base / "timeout", expected, "not-a-session", 3, timed_out)
        except ValueError: check(not calls)
        else: check(False)
        calls.clear()
        def exact_service(session, endpoint, job, timeout):
            calls.append(endpoint)
            if endpoint == "states": return {"ok": True, "contexts": [{"name": "ModsBrowser"}]}
            return {"ok": True, "values": [{"ok": True, "status": "already_exact", "after": list(reversed(expected)), "attempted": 0}]}
        verified = ensure(base / "exact", expected, "not-a-session", 3, exact_service)
        check(verified["status"] == "already_exact" and calls == ["states", "exec"])
        check((base / "exact/ensure-mods.lua").read_text() == source and json.loads((base / "exact/expected-mods.json").read_text()) == expected)
        try: ensure(ROOT / "work", expected, "not-a-session", 3, exact_service)
        except ValueError: check(calls == ["states", "exec"])
        else: check(False)
    return {"checks": checks, "failures": 0, "scope": "Lua5.1 empty/exact/mismatch/enable-failure plus Python validation/InGame/timeout/redispatch guards; no game connection"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--expected-mods-json", type=Path)
    parser.add_argument("--session", default=str(tuner.DEFAULT_SESSION))
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test();print(json.dumps(result));return 0
    if args.run_dir is None or args.expected_mods_json is None or not 0 < args.timeout <= 120:
        parser.error("--run-dir, --expected-mods-json and timeout(0,120] are required")
    try:
        expected = expected_mods(json.loads(args.expected_mods_json.read_text(encoding="utf-8-sig")))
        result = ensure(args.run_dir, expected, args.session, args.timeout)
        print(json.dumps(result));return 0
    except Exception as exc:
        # Print no session data, engine output or exception payload that could
        # contain credentials. Full structured mod/context evidence is on disk.
        print(json.dumps({"ok": False, "errorType": type(exc).__name__, "message": "Mod check failed; inspect run evidence; no automatic retry"}));return 1


if __name__ == "__main__":
    raise SystemExit(main())
