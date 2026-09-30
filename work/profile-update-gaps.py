"""Read-only bounded TURN_UPDATE_GAP review; inclusive children are not summed.

Only wrapper spans plus separately measured between-wrapper dispatch intervals
are disjoint. Game/head/hooks/activation-tail totals overlap those spans and
each other. Thread CPU does not identify work/waits on other threads.
"""
from __future__ import annotations
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("wall_profile", Path(__file__).with_name("profile-turn-phases.py"))
wall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wall)
PARTS = ("wrapper", "game", "activationTail", "beginHook", "endHook", "preMovesHead", "dispatch")


def analyze(records, turn):
    rows, invalid = [], []
    for record in records:
        if record["turn"] != turn or record["category"] != "TURN_UPDATE_GAP":
            continue
        value = record["values"]
        try:
            def integer(name):
                number = value[name]
                if type(number) is not int or number < 0:
                    raise ValueError("invalid " + name)
                return number
            if (value.get("semantics") != "activation_to_first_unit_entry"
                    or value.get("totals") != "inclusive_overlapping_not_phase_bounds"):
                raise ValueError("unsupported summary semantics")
            start, end, elapsed = (integer(name) for name in ("startTick", "endTick", "elapsedMs"))
            if not (start < wall.MOD and end < wall.MOD and elapsed < wall.HALF
                    and (end-start) % wall.MOD == elapsed):
                raise ValueError("inconsistent tick bounds")
            ended = record["tick"] - ((record["raw_tick"]-end) % wall.MOD)
            interval = (ended-elapsed, ended)
            available = integer("cpuAvailable") == 1
            cpu_start, cpu_end, cpu_delta = (integer(name) for name in ("cpuStart100ns", "cpuEnd100ns", "cpu100ns"))
            if available and (cpu_end < cpu_start or cpu_delta != cpu_end-cpu_start):
                raise ValueError("inconsistent CPU endpoints")
            if not available and (cpu_start or cpu_end or cpu_delta):
                raise ValueError("unavailable CPU endpoints must be zero")
            parts = {}
            for part in PARTS:
                calls, measured = integer(part+"Calls"), integer(part+"CPUMeasured")
                milliseconds, cpu = integer(part+"Ms"), integer(part+"CPU100ns")
                if measured > calls:
                    raise ValueError("CPU measurements exceed " + part + " calls")
                parts[part] = dict(calls=calls, wall_ms=milliseconds, cpu_ms=cpu/10000,
                    cpu_measured_calls=measured, cpu_complete=measured==calls,
                    overlap="disjoint wrapper/dispatch" if part in ("wrapper", "dispatch") else "inclusive child; do not sum")
            covered = parts["wrapper"]["wall_ms"] + parts["dispatch"]["wall_ms"]
            if covered > elapsed:
                raise ValueError("wrapper and dispatch exceed pending span")
            warnings = []
            if parts["game"]["wall_ms"] > parts["wrapper"]["wall_ms"]:
                warnings.append("Game body time exceeds wrapper coverage; direct/reentrant body calls may be present")
            if any(not parts[p]["cpu_complete"] for p in PARTS):
                warnings.append("Some aggregate CPU spans are unavailable; their CPU totals are partial")
            core_lock = dict(recorded=False)
            if "coreLockAttempts" in value:
                attempts, completed, measured = (integer(key) for key in
                    ("coreLockAttempts", "coreLockCompleted", "coreLockCPUMeasured"))
                if not measured <= completed <= attempts:
                    raise ValueError("inconsistent completed core-lock counts")
                core_lock = dict(recorded=True, attempts=attempts, completed=completed,
                    incomplete=attempts-completed, wall_ms=integer("coreLockMs"),
                    cpu_ms=integer("coreLockCPU100ns")/10000, cpu_measured_calls=measured,
                    maximum_ms=integer("maximumCoreLockMs"),
                    overlap="completed constructor acquire envelope; includes diagnostic overhead; can overlap dispatch/body")
            rows.append(dict(player=record["player"], thread=integer("thread"), interval=interval,
                elapsed_ms=elapsed, cpu_available=available, cpu_start100ns=cpu_start if available else None,
                cpu_end100ns=cpu_end if available else None, cpu_ms=cpu_delta/10000 if available else None,
                parts=parts, wrapper_plus_dispatch_ms=covered, edge_unattributed_ms=elapsed-covered,
                maximum_dispatch_ms=integer("maximumDispatchMs"), nested_scopes=integer("nestedScopes"),
                wrapper_clipped_start=integer("wrapperClippedStart") == 1, core_lock_acquire=core_lock,
                warnings=warnings, origin=record["origin"]))
        except (KeyError, ValueError) as exc:
            invalid.append(dict(origin=record["origin"], reason=str(exc)))
    legacy = [r for r in records if r["category"] not in wall.TIMING_CATEGORIES]
    start = min((r["tick"] for r in legacy if r["turn"]==turn), default=None)
    end = min((r["tick"] for r in legacy if r["turn"]==turn+1), default=None)
    intervals = [r["interval"] for r in rows]
    span_sum = sum(r["elapsed_ms"] for r in rows)
    union_ms = wall.length(intervals)
    return dict(turn=turn, native_window=dict(start_tick=start, end_tick=end,
            duration_ms=end-start if start is not None and end is not None else None),
        row_count=len(rows), duplicate_player_rows={str(p):n for p,n in Counter(r["player"] for r in rows).items() if n>1},
        pending_span_sum_ms=span_sum, pending_span_union_ms=union_ms, rows_overlap=span_sum!=union_ms,
        aggregate_wrapper_ms=sum(r["parts"]["wrapper"]["wall_ms"] for r in rows),
        aggregate_dispatch_ms=sum(r["parts"]["dispatch"]["wall_ms"] for r in rows),
        aggregate_edge_unattributed_ms=sum(r["edge_unattributed_ms"] for r in rows),
        aggregate_pending_cpu_ms=sum(r["cpu_ms"] for r in rows if r["cpu_available"]),
        unavailable_pending_cpu_rows=sum(not r["cpu_available"] for r in rows),
        rows=sorted(rows, key=lambda r:r["elapsed_ms"], reverse=True), invalid_rows=invalid,
        limits="Pending activation windows only, not the whole round. Wrapper and dispatch are disjoint; game/head/hooks/tail totals overlap. CPU endpoints belong to each row's thread; wall minus CPU is not proof of rendering, sleep, or any specific wait. Edge remainder is outside measured wrapper/dispatch coverage. No timing rows are native legacy anchors.")


def self_test():
    def gap(player=3, start=10, end=110, cpu=True):
        value=dict(startTick=start, endTick=end, elapsedMs=(end-start)%wall.MOD, thread=7,
            cpuAvailable=int(cpu), cpuStart100ns=100 if cpu else 0, cpuEnd100ns=300 if cpu else 0,
            cpu100ns=200 if cpu else 0, semantics="activation_to_first_unit_entry",
            totals="inclusive_overlapping_not_phase_bounds", maximumDispatchMs=70,nestedScopes=0,wrapperClippedStart=1)
        for part in PARTS:
            value.update({part+"Calls":1,part+"Ms":0,part+"CPU100ns":0,part+"CPUMeasured":int(cpu)})
        value.update(wrapperMs=30,gameMs=25,beginHookMs=15,preMovesHeadMs=20,dispatchMs=70)
        return dict(raw_tick=end%wall.MOD,tick=end,turn=8,player=player,category="TURN_UPDATE_GAP",values=value,origin="synthetic")
    result=analyze([gap()],8)
    assert result["aggregate_dispatch_ms"]==70 and result["aggregate_wrapper_ms"]==30
    assert result["rows"][0]["edge_unattributed_ms"]==0 and result["pending_span_union_ms"]==100
    assert result["rows"][0]["cpu_ms"]==.02
    # Head includes begin hook; this sum intentionally exceeds game time.
    assert not result["invalid_rows"] and result["rows"][0]["parts"]["preMovesHead"]["overlap"].startswith("inclusive")
    unavailable=analyze([gap(cpu=False)],8)
    assert unavailable["unavailable_pending_cpu_rows"]==1 and unavailable["rows"][0]["cpu_ms"] is None
    bad=gap();bad["values"]["dispatchMs"]=100
    assert len(analyze([bad],8)["invalid_rows"])==1
    wrap=gap(start=wall.MOD-20,end=80)
    assert analyze([wrap],8)["rows"][0]["elapsed_ms"]==100
    repeated=analyze([gap(),gap(start=90,end=190)],8)
    assert repeated["rows_overlap"] and repeated["duplicate_player_rows"]=={"3":2}
    anchor=dict(raw_tick=20,tick=20,turn=8,player=0,category="SUMMARY",values={},origin="synthetic")
    next_anchor={**anchor,"turn":9,"raw_tick":200,"tick":200}
    leading=gap(start=0,end=10);trailing={**gap(start=110,end=150),"turn":9}
    assert analyze([leading,anchor,trailing,next_anchor],8)["native_window"]["duration_ms"]==180
    lock=gap();lock["values"].update(coreLockAttempts=2,coreLockCompleted=1,coreLockMs=20,coreLockCPU100ns=0,coreLockCPUMeasured=1,maximumCoreLockMs=20)
    lock_row=analyze([lock],8)["rows"][0]
    assert lock_row["core_lock_acquire"]["incomplete"]==1 and lock_row["edge_unattributed_ms"]==0
    lock["values"]["coreLockCompleted"]=3
    assert len(analyze([lock],8)["invalid_rows"])==1
    return dict(checks=11,failures=0,game_calls=0,scope="synthetic overlap/partial CPU/reconciliation/wrap/duplicate/timing-anchor/core-lock validation")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",nargs="?",type=Path);parser.add_argument("--run");parser.add_argument("--turn",type=int)
    parser.add_argument("--output",type=Path);parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test: print(json.dumps(self_test()));return
    if args.directory is None or not args.run or args.turn is None or args.output is None:
        parser.error("directory, --run, --turn and --output required")
    output=args.output.resolve()
    if output.suffix.lower()!=".json" or output.name in ("replay-manifest.json","world-before.json","world-after.json"):
        parser.error("output must be a derived JSON file, not replay evidence")
    records,quality=wall.load(args.directory,args.run)
    result=dict(run=args.run,**analyze(records,args.turn),archive_quality=quality)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:result[key] for key in ("run","turn","row_count","aggregate_wrapper_ms","aggregate_dispatch_ms","aggregate_edge_unattributed_ms","invalid_rows")}))


if __name__=="__main__":main()
