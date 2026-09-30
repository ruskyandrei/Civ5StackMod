"""Read-only TURN_PHASE CPU endpoints/entry aggregates and bounded wall-gap review.

CPU counters belong to individual threads; union them separately per thread.
Nested CPU/wall scope totals are inclusive. Never sum them as complete turns,
interpolate CPU at clipped boundaries, or call wall-minus-CPU pure engine idle.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("wall_profile", Path(__file__).with_name("profile-turn-phases.py"))
wall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wall)


def analyze(records, turn, maximum_gaps=24):
    phases, invalid_cpu, missing_cpu = [], [], 0
    for record in records:
        if record["category"] != "TURN_PHASE":
            continue
        interval, error = wall.phase_interval(record)
        value = record["values"]
        if error or value.get("semantics") != "inclusive":
            continue
        cpu_start, cpu_end = value.get("cpuStart100ns"), value.get("cpuEnd100ns")
        available = value.get("cpuAvailable") == 1
        if available and (type(cpu_start) is not int or type(cpu_end) is not int
                          or not 0 <= cpu_start <= cpu_end < (1 << 64)
                          or value.get("cpu100ns") != cpu_end-cpu_start):
            invalid_cpu.append(record["origin"]);available = False
        if not available:
            missing_cpu += record["turn"] == turn
        phases.append(dict(sourceTurn=record["turn"], player=record["player"], phase=value.get("phase"),
            thread=value.get("thread"), interval=interval, elapsed_ms=interval[1]-interval[0], cpuAvailable=available,
            cpuStart100ns=cpu_start if available else None, cpuEnd100ns=cpu_end if available else None,
            cpu_ms=(cpu_end-cpu_start)/10000 if available else None, values=value, origin=record["origin"]))
    current = [r for r in records if r["turn"] == turn and r["category"] not in wall.TIMING_CATEGORIES]
    following = [r for r in records if r["turn"] == turn+1 and r["category"] not in wall.TIMING_CATEGORIES]
    if not current:
        raise ValueError("Selected turn has no legacy native record")
    start = min(r["tick"] for r in current)
    end = min((r["tick"] for r in following), default=None)
    complete = end is not None and end >= start
    selected = [p for p in phases if p["sourceTurn"] == turn]
    if complete:
        window = (start, end)
        window_convention = "first native event excluding TURN_PHASE/TURN_UPDATE_GAP from T to T+1; includes adjacent-turn preparation bounds"
    else:
        window = (start, max((p["interval"][1] for p in selected), default=start))
        window_convention = "partial observed phase extent only; not a complete native turn"
    covered = wall.clip([p["interval"] for p in phases], window)
    gaps, cursor = [], window[0]
    for a, b in covered:
        if a > cursor: gaps.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < window[1]: gaps.append((cursor, window[1]))
    gap_rows = []
    for a, b in sorted(gaps, key=lambda span: span[1]-span[0], reverse=True):
        previous = [p for p in phases if p["interval"][1] == a]
        following_phases = [p for p in phases if p["interval"][0] == b]
        left, right = defaultdict(list), defaultdict(list)
        for p in previous:
            if p["cpuAvailable"]: left[p["thread"]].append(p)
        for p in following_phases:
            if p["cpuAvailable"]: right[p["thread"]].append(p)
        cpu_bounds = []
        for thread in sorted(set(left) & set(right)):
            # Multiple nested scopes can share a coarse tick. Their latest CPU
            # end and earliest CPU start avoid inventing intervening CPU work.
            before = max(left[thread], key=lambda p: p["cpuEnd100ns"])
            after = min(right[thread], key=lambda p: p["cpuStart100ns"])
            valid = after["cpuStart100ns"] >= before["cpuEnd100ns"]
            delta = (after["cpuStart100ns"]-before["cpuEnd100ns"])/10000 if valid else None
            cpu_bounds.append(dict(thread=thread, valid=valid, cpu_before100ns=before["cpuEnd100ns"],
                cpu_after100ns=after["cpuStart100ns"], cpu_ms=delta,
                wall_minus_same_thread_cpu_ms=b-a-delta if valid else None,
                previous_phase=before["phase"], next_phase=after["phase"],
                previous_player=before["player"], next_player=after["player"],
                previous_sourceTurn=before["sourceTurn"], next_sourceTurn=after["sourceTurn"],
                previous_origin=before["origin"], next_origin=after["origin"]))
        gap_rows.append(dict(start_tick=a, end_tick=b, wall_ms=b-a, same_thread_cpu=cpu_bounds,
            previous_phases=[dict(sourceTurn=p["sourceTurn"], player=p["player"], phase=p["phase"], thread=p["thread"]) for p in previous[-8:]],
            next_phases=[dict(sourceTurn=p["sourceTurn"], player=p["player"], phase=p["phase"], thread=p["thread"]) for p in following_phases[:8]]))
    groups = defaultdict(list)
    for p in selected: groups[(p["player"], p["phase"], p["thread"])].append(p)
    inclusive = []
    for (player, phase, thread), entries in groups.items():
        cpu = [p["cpu_ms"] for p in entries if p["cpuAvailable"]]
        inclusive.append(dict(player=player, phase=phase, thread=thread, calls=len(entries), cpu_available_calls=len(cpu),
            inclusive_wall_ms=sum(p["elapsed_ms"] for p in entries), inclusive_cpu_ms=sum(cpu) if cpu else None,
            maximum_wall_ms=max(p["elapsed_ms"] for p in entries), maximum_cpu_ms=max(cpu) if cpu else None))
    per_thread = defaultdict(list)
    for p in phases:
        if p["cpuAvailable"] and window[0] <= p["interval"][0] <= p["interval"][1] <= window[1]:
            per_thread[p["thread"]].append((p["cpuStart100ns"], p["cpuEnd100ns"]))
    entry_rows = [p for p in selected if p["phase"] == "unit_ai_entry"]
    aggregate_names = ("entryCalls", "busyReturns", "aggregateHookMs", "aggregateGuardMs", "aggregateCPUMeasuredCalls", "aggregateHookCPU100ns", "aggregateGuardCPU100ns")
    entry_totals = {name: sum(p["values"].get(name, 0) for p in entry_rows) for name in aggregate_names}
    gap_cpu = [r["same_thread_cpu"][0]["cpu_ms"] for r in gap_rows if len(r["same_thread_cpu"]) == 1 and r["same_thread_cpu"][0]["valid"]]
    return dict(turn=turn, complete_native_boundary=complete,
        window=dict(start_tick=window[0], end_tick=window[1], duration_ms=window[1]-window[0], convention=window_convention),
        phase_union_wall_ms=wall.length(covered), wall_gap_ms=sum(b-a for a,b in gaps),
        phase_cpu_unions_fully_contained_per_thread_ms={str(thread): wall.length(spans)/10000 for thread,spans in per_thread.items()},
        unambiguous_same_thread_gap_cpu_ms=sum(gap_cpu),
        gaps=gap_rows[:maximum_gaps], total_gap_count=len(gap_rows), displayed_gap_count=min(len(gap_rows), maximum_gaps),
        phases_inclusive=sorted(inclusive, key=lambda p:p["inclusive_wall_ms"], reverse=True),
        unit_ai_entry=dict(totals=entry_totals, rows=sorted(entry_rows,key=lambda p:p["elapsed_ms"],reverse=True)),
        invalid_cpu_origins=invalid_cpu, unavailable_cpu_phase_calls=missing_cpu,
        limitations=["Phase sums/CPU are inclusive, not disjoint turn totals; thread CPU unions include only fully contained wall scopes and exclude clipped scopes without interpolation.",
            "CPU endpoint differences measure only that thread's CPU between observed reads; wall-minus-CPU can include other-thread work, synchronization, scheduler delay and clock quantization, not pure engine idle.",
            "Unit-entry aggregates sum completed spans; earlier busy polls are not interval bounds and may overlap nested calls.",
            "Legacy boundaries may include return-player transition in an autoplay-stop-adjacent interval; prefer positive autoplay/observer boundaries for steady turn comparisons."])


def self_test():
    def rec(tick, turn=7, player=0, category="TURN_PHASE", **values):
        return dict(raw_tick=tick%wall.MOD, tick=tick, turn=turn, player=player, category=category, values=values, origin="synthetic")
    def phase(a,b,ca,cb,name,thread=1,turn=7):
        return rec(b,turn=turn,phase=name,startTick=a,endTick=b,elapsedMs=b-a,semantics="inclusive",thread=thread,cpuAvailable=1,cpuStart100ns=ca,cpuEnd100ns=cb,cpu100ns=cb-ca)
    rows=[rec(0,category="X"),phase(0,20,1000,3000,"parent"),phase(5,10,1200,1400,"child"),phase(50,80,3500,4500,"next"),rec(100,turn=8,category="X")]
    d=analyze(rows,7);assert d["wall_gap_ms"]==50 and d["phase_union_wall_ms"]==50
    assert d["phase_cpu_unions_fully_contained_per_thread_ms"]=={"1":0.3}
    known=next(g for g in d["gaps"] if g["start_tick"]==20);assert known["same_thread_cpu"][0]["cpu_ms"]==0.05
    assert known["same_thread_cpu"][0]["wall_minus_same_thread_cpu_ms"]==29.95
    other=[rows[0],phase(0,20,1000,3000,"a",thread=1),phase(50,80,10,200,"b",thread=2),rows[-1]]
    assert not next(g for g in analyze(other,7)["gaps"] if g["start_tick"]==20)["same_thread_cpu"]
    bad=phase(0,20,1000,3000,"bad");bad["values"]["cpu100ns"]=1
    assert analyze([rows[0],bad,rows[-1]],7)["invalid_cpu_origins"]==["synthetic"]
    assert not analyze(rows[:-1],7)["complete_native_boundary"]
    next_turn=[rows[0],phase(0,20,1000,3000,"a"),phase(70,90,3500,4000,"nextprep",turn=8),rows[-1]]
    assert analyze(next_turn,7)["phase_union_wall_ms"]==40
    unavailable=phase(0,20,1000,3000,"unavailable");unavailable["values"]["cpuAvailable"]=0
    assert analyze([rows[0],unavailable,rows[-1]],7)["unavailable_cpu_phase_calls"]==1
    anchored=[rec(10,category="X"),*rows[1:-1],rec(110,turn=8,category="X")]
    mixed=[rec(2,category="TURN_UPDATE_GAP",startTick=0,endTick=2,elapsedMs=2),*anchored,
           rec(90,turn=8,category="TURN_UPDATE_GAP",startTick=0,endTick=90,elapsedMs=90)]
    ordinary,new=analyze(anchored,7),analyze(mixed,7)
    assert new["window"]==ordinary["window"] and new["window"]["duration_ms"]==100
    assert new["phase_union_wall_ms"]==ordinary["phase_union_wall_ms"] and new["wall_gap_ms"]==ordinary["wall_gap_ms"]
    return {"checks":11,"failures":0,"scope":"synthetic nested CPU union/gap endpoints/cross-thread/invalid/unavailable/partial/adjacent-turn/new-gap-anchor attribution"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",nargs="?",type=Path);parser.add_argument("--run");parser.add_argument("--turn",type=int)
    parser.add_argument("--maximum-gaps",type=int,default=24);parser.add_argument("--output",type=Path);parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:print(json.dumps(self_test()));return
    if args.directory is None or not args.run or args.turn is None or args.output is None or not 1<=args.maximum_gaps<=128:
        parser.error("directory, --run, --turn, --output and maximum-gaps1–128 required")
    records,quality=wall.load(args.directory,args.run)
    try: result=dict(run=args.run,**analyze(records,args.turn,args.maximum_gaps),archive_quality=quality)
    except ValueError as exc:parser.error(str(exc))
    output=args.output.resolve()
    if output.suffix.lower()!=".json" or any(output==p.resolve() for p in args.directory.glob("*.log")):
        parser.error("output must be JSON and cannot replace an input log")
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("turn","complete_native_boundary","window","wall_gap_ms","unambiguous_same_thread_gap_cpu_ms")}))


if __name__=="__main__":main()
