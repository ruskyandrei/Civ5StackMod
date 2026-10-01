"""Read-only resident shortcut counters from frozen native replay archives.

Ratios describe recorded work, never saved seconds. Existing policy fields are
compared separately from representation-dependent physical estimates/timings.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("resident_phase_reader", ROOT / "profile-turn-phases.py")
reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
NEW = ("residentHits", "residentCaptures", "residentRejects", "prepBuildAttempts", "prepReuseAttempts")
LEGACY = ("dangerHits", "dangerMisses", "defenderHits", "defenderMisses", "entries", "payloadBytes",
          "dangerEvictions", "defenderEvictions", "meleeStrengthHits", "meleeStrengthMisses",
          "rangedStrengthHits", "rangedStrengthMisses", "attackStrengthHits", "attackStrengthMisses",
          "defenseStrengthHits", "defenseStrengthMisses", "strengthEntries", "strengthPeakEntries", "strengthLimit",
          "strengthEvictions", "strengthInvalidations", "outcomeBuilds", "outcomeReuses", "outcomeBypasses",
          "outcomeRetainedBytes", "outcomePeakRetainedBytes", "packetHits", "packetBuilds", "packetBypasses",
          "callbackProofScans", "callbackProofFlags", "callbackValidationBypasses", "callbackSuspensions", "forecastBackend")
REPRESENTATION = "forecastEstimatedBytes"


def percentage(part, total):
    return None if total <= 0 else round(part * 100.0 / total, 4)


def load(folder, run, turns):
    records, quality = reader.load(folder / "native-segments", run)
    problems = bool(quality["gaps"] or quality["earlier_segments_missing"] or quality["conflicting_segment_files"] or
                    quality["malformed_records"] or quality["incomplete_tails_skipped"] or quality["clock_reversals"])
    selected = [r for r in records if r["category"] == "PLAN_PERF" and (not turns or r["turn"] in turns)]
    truncated = [dict(turn=r["turn"], origin=r["origin"]) for r in records if r["category"] == "TRUNCATED" and (not turns or r["turn"] in turns)]
    return selected, dict(archiveQuality=quality, incompleteCounterEvidence=problems or bool(truncated) or not selected, truncationRows=truncated)


def validate(row, require_new):
    values = row["values"]
    missing = [k for k in LEGACY + (NEW if require_new else ()) if k not in values]
    if "target" not in values: missing.append("target")
    invalid = [k for k in LEGACY + NEW + (REPRESENTATION,) if k in values and
               (not isinstance(values[k], str) if k == "forecastBackend" else type(values[k]) is not int or not 0 <= values[k] <= (1 << 32) - 1)]
    return dict(origin=row["origin"], missing=missing, invalid=invalid) if missing or invalid else None


def aggregate(rows, identity):
    numeric = [k for k in LEGACY + NEW if k != "forecastBackend" and k != "callbackProofFlags"]
    total = {k: sum(r["values"].get(k, 0) for r in rows) for k in numeric}
    total["callbackProofFlags"] = 0
    for r in rows: total["callbackProofFlags"] |= r["values"].get("callbackProofFlags", 0)
    hits = total["dangerHits"]; resident = total["residentHits"]; full_hits = hits - resident
    queries = hits + total["dangerMisses"]
    consistency = []
    if any(r["values"].get("residentHits", 0) > r["values"].get("dangerHits", 0) or
           r["values"].get("residentCaptures", 0) > max(0, r["values"].get("dangerHits", 0) - r["values"].get("residentHits", 0)) for r in rows):
        consistency.append("per_PLAN_counter_relationship_invalid_or_wrap")
    if full_hits < 0: consistency.append("residentHits_exceed_dangerHits_or_counter_wrap")
    if total["residentCaptures"] > max(0, full_hits): consistency.append("captures_exceed_recorded_full_lookup_hits_or_counter_wrap")
    attempts = total["prepBuildAttempts"] + total["prepReuseAttempts"]
    return dict(**identity, planRows=len(rows), counters=total,
                resident_share_of_danger_hits_percent=percentage(resident, hits) if not consistency else None,
                resident_share_of_all_recorded_danger_queries_percent=percentage(resident, queries) if not consistency else None,
                capture_share_of_danger_hits_percent=percentage(total["residentCaptures"], hits) if not consistency else None,
                capture_share_of_full_lookup_hits_percent=percentage(total["residentCaptures"], full_hits) if not consistency else None,
                prep_reuse_share_of_recorded_prep_attempts_percent=percentage(total["prepReuseAttempts"], attempts),
                consistencyWarnings=consistency,
                forecast_backends=sorted(set(r["values"].get("forecastBackend", "unknown") for r in rows)),
                physical_estimate_recorded_rows=sum(REPRESENTATION in r["values"] for r in rows),
                physical_estimate_max_bytes=max((r["values"][REPRESENTATION] for r in rows if REPRESENTATION in r["values"]), default=None))


def summarize(rows):
    turn_groups, player_groups, target_groups = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in rows:
        turn_groups[r["turn"]].append(r)
        player_groups[(r["turn"], r["player"])].append(r)
        target_groups[(r["turn"], r["player"], r["values"]["target"])].append(r)
    turns = [aggregate(group, dict(turn=turn)) for turn, group in sorted(turn_groups.items())]
    players = [aggregate(group, dict(turn=key[0], player=key[1])) for key, group in sorted(player_groups.items())]
    targets = [aggregate(group, dict(turn=key[0], player=key[1], target=key[2])) for key, group in sorted(target_groups.items())]
    high_reject = sorted(targets, key=lambda r: r["counters"]["residentRejects"], reverse=True)[:12]
    return dict(turns=turns, players=players, targets=targets, largest_recorded_reject_groups=high_reject)


def compare(control, candidate, reliable):
    mismatches = []; alignment = True
    for index in range(max(len(control), len(candidate))):
        a = control[index] if index < len(control) else None; b = candidate[index] if index < len(candidate) else None
        ai = None if a is None else (a["turn"], a["player"], a["values"].get("target"))
        bi = None if b is None else (b["turn"], b["player"], b["values"].get("target"))
        if ai != bi: alignment = False; mismatches.append(dict(index=index, baselineIdentity=ai, candidateIdentity=bi)); continue
        delta = {key: [a["values"].get(key), b["values"].get(key)] for key in LEGACY if a["values"].get(key) != b["values"].get(key)}
        if delta: mismatches.append(dict(index=index, turn=ai[0], player=ai[1], target=ai[2], differences=delta))
    physical = [dict(index=i, turn=a["turn"], player=a["player"], target=a["values"].get("target"),
                     baseline=a["values"].get(REPRESENTATION), candidate=b["values"].get(REPRESENTATION))
                for i, (a, b) in enumerate(zip(control, candidate)) if a["values"].get(REPRESENTATION) != b["values"].get(REPRESENTATION)]
    return dict(legacy_field_count=len(LEGACY), legacy_fields=list(LEGACY), planRowCounts=[len(control), len(candidate)],
                sequence_identity_equal=alignment, legacy_policy_and_capacity_fields_equal=(not mismatches if reliable else None),
                mismatch_count=len(mismatches), first_mismatches=mismatches[:10],
                physical_estimate_field=REPRESENTATION, physical_difference_rows=len(physical), physical_examples=physical[:8],
                limitations="Comparison covers these34 recorded fields only; timing, new metadata fields, engine configuration, actual RSS and complete game semantics are separate evidence. Peak/retained sizes are not additive memory consumption.")


def self_test():
    assert len(LEGACY) == 34
    def row(turn=253, target="25:25", **changes):
        v = {k: 0 for k in LEGACY + NEW}; v.update(forecastBackend="indexed", target=target, forecastEstimatedBytes=1000,
                                                      dangerHits=100, dangerMisses=10, residentHits=30, residentCaptures=20,
                                                      residentRejects=5, prepBuildAttempts=10, prepReuseAttempts=40); v.update(changes)
        return dict(turn=turn, player=3, category="PLAN_PERF", origin="synthetic", values=v)
    r = row(); assert validate(r, True) is None
    a = aggregate([r], dict(turn=253)); assert a["resident_share_of_danger_hits_percent"] == 30 and a["capture_share_of_full_lookup_hits_percent"] == 28.5714
    assert a["prep_reuse_share_of_recorded_prep_attempts_percent"] == 80
    assert percentage(0, 0) is None and percentage(0, 10) == 0
    assert aggregate([row(dangerHits=0, residentHits=0, residentCaptures=0)], {})["capture_share_of_full_lookup_hits_percent"] is None
    assert aggregate([row(residentHits=101)], {})["consistencyWarnings"]
    old = row(); [old["values"].pop(k) for k in NEW]
    assert validate(old, False) is None and validate(old, True)["missing"] == list(NEW)
    assert compare([old], [row(forecastEstimatedBytes=2000)], True)["legacy_policy_and_capacity_fields_equal"]
    assert compare([old], [row(payloadBytes=1)], True)["legacy_policy_and_capacity_fields_equal"] is False
    assert compare([], [], False)["legacy_policy_and_capacity_fields_equal"] is None
    assert compare([old], [row(target="1:1")], True)["sequence_identity_equal"] is False
    assert validate(row(residentHits=-1), True)["invalid"] == ["residentHits"]
    assert aggregate([row(callbackProofFlags=1), row(callbackProofFlags=2)], {})["counters"]["callbackProofFlags"] == 3
    groups = summarize([row(), row(), row(turn=252)]); assert len(groups["targets"]) == 2 and groups["targets"][1]["planRows"] == 2
    absent = row(); absent["values"].pop(REPRESENTATION); assert aggregate([absent], {})["physical_estimate_max_bytes"] is None
    no_target = row(); no_target["values"].pop("target"); assert validate(no_target, True)["missing"] == ["target"]
    assert aggregate([row(residentHits=101, residentCaptures=0), row(residentHits=0, residentCaptures=0)], {})["resident_share_of_danger_hits_percent"] is None
    print(json.dumps(dict(checks=18, failures=0, offline=True, gameCalls=0, scope="Synthetic aggregation, missing/zero/invalid counters, exact legacy fields, physical estimate separation, per-PLAN inconsistency, sequence mismatch and flags OR")))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path); p.add_argument("--run"); p.add_argument("--control-dir", type=Path); p.add_argument("--control-run")
    p.add_argument("--turn", action="append", type=int); p.add_argument("--output", type=Path); p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test: self_test(); return
    if not args.run_dir or not args.run: p.error("--run-dir and --run are required")
    if bool(args.control_dir) != bool(args.control_run): p.error("control directory and run must be supplied together")
    rows, evidence = load(args.run_dir, args.run, set(args.turn or []))
    validation = [problem for row in rows if (problem := validate(row, True))]
    report = dict(run=args.run, evidence=evidence, validation=validation, **(summarize(rows) if not validation else {}),
                  limitations=["Counters reset each PLAN; rows group by source turn/player/target, not a whole-process clock.",
                               "residentRejects is selective and has no reason code: high values do not prove eviction, dirty state or lost eligibility.",
                               "Prep counters are attempts; a copy/build may fail later. Generic unsupported calls are not a denominator.",
                               "Rates describe recorded work only. No stride scaling or seconds-saved prediction is made."])
    if args.control_dir:
        old, control_evidence = load(args.control_dir, args.control_run, set(args.turn or []))
        old_validation = [problem for row in old if (problem := validate(row, False))]
        reliable = not evidence["incompleteCounterEvidence"] and not control_evidence["incompleteCounterEvidence"] and not validation and not old_validation
        report.update(controlRun=args.control_run, controlEvidence=control_evidence, controlValidation=old_validation,
                      comparison=compare(old, rows, reliable))
    result = json.dumps(report, indent=2)
    if args.output:
        if args.output.suffix.lower() != ".json" or args.output.name in ("replay-manifest.json", "world-before.json", "world-after.json", "normal-exit.json", "loaded-dll.json"):
            p.error("output must be a new report JSON, not replay input evidence")
        args.output.write_text(result + "\n", encoding="utf-8")
        print(json.dumps(dict(output=str(args.output.resolve()), planRows=len(rows), validationErrors=len(validation), incompleteCounterEvidence=evidence["incompleteCounterEvidence"])))
    else: print(result)


if __name__ == "__main__": main()
