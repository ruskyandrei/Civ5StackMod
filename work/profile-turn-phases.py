"""Offline native TURN_PHASE interval profile; writes only the requested JSON.

Inclusive phase/PLAN durations must never all be added together. The native
Primary round bounds exclude newly added TURN_PHASE rows for comparison with
the old DLL. The original all-event profile-campaign-log.py bounds are retained
separately; that older script does not exclude TURN_PHASE.
PLAN location is estimated: its high precision timer stops before finalization.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

MOD = 1 << 32
HALF = MOD // 2
SESSION = re.compile(r"^STACKDIAG\|SESSION\|(.+)$")
RECORD = re.compile(r"^STACKDIAG\|(\d+)\|turn=(-?\d+)\|player=(-?\d+)\|([^|]+)\|(.*)$")
FIELD = re.compile(r"(?:^|\s)([A-Za-z][A-Za-z0-9_]*)=([^\s;]+)")
CHILD_PHASES = {
    "player_doTurn": {"ai_turn_pre", "grand_strategy_ai", "diplomacy_ai", "player_post_diplomacy"},
    "player_post_diplomacy": {"player_prepare", "cities_and_production", "player_yields_research_culture", "ai_turn_post", "player_unit_turn"},
    "player_prepare": {"player_danger_update", "military_stats", "economic_ai", "military_ai", "religion_trade_specialization_league_ai", "minor_civ_ai"},
    "ai_turn_pre": {"unit_power_sort", "annex_raze_ai"},
    "ai_turn_post": {"great_people_ai", "espionage_ai", "trade_ai_post"},
    "player_unit_turn": {"unit_cleanup_pre", "unit_doTurn_calls", "unit_promotions_garrison_post"},
    "unit_ai_update": {"tactical_ai", "tactical_visibility", "homeland_ai"},
    "tactical_ai": {"tactical_visibility", "tactical_targets", "tactical_recruit", "immediate_city_opportunities", "tactical_dominance"},
    "tactical_dominance": {"tactical_high_priority", "tactical_zone_attacks", "tactical_reinforcements", "tactical_mid_priority", "tactical_low_priority"},
    "tactical_high_priority": {"tactical_operations"},
    "tactical_operations": {"stacking_offensive_moves"},
}


def fields(text):
    return {key: int(value) if re.fullmatch(r"-?\d+", value) else value
            for key, value in FIELD.findall(text)}


def union(intervals):
    merged = []
    for start, end in sorted((a, b) for a, b in intervals if b > a):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def length(intervals):
    return sum(b-a for a, b in union(intervals))


def clip(intervals, window):
    if window is None:
        return union(intervals)
    return union((max(a, window[0]), min(b, window[1])) for a, b in intervals)


def intersection(left, right):
    left, right = union(left), union(right)
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a, b = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
        if b > a:
            result.append((a, b))
        if left[i][1] < right[j][1]:
            i += 1
        else:
            j += 1
    return result


def unwrap(records):
    epoch, previous = 0, None
    wraps, reversals = 0, []
    for record in records:
        raw = record["raw_tick"]
        if previous is not None:
            delta = raw-previous
            if delta < -HALF:
                epoch += MOD
                wraps += 1
            elif delta < 0 or delta > HALF:
                reversals.append(record.get("origin", "synthetic"))
        record["tick"] = epoch+raw
        previous = raw
    return wraps, reversals


def load(directory, run):
    selected, candidates = {}, defaultdict(list)
    for path in sorted(directory.glob("*.log")):
        with path.open(encoding="utf-8-sig", errors="replace") as stream:
            match = SESSION.fullmatch(stream.readline().rstrip("\r\n"))
        if not match:
            continue
        header = fields(match[1])
        if header.get("run") == run and isinstance(header.get("segment"), int):
            candidates[header["segment"]].append((path.stat().st_size, path, header))
    duplicates, conflicts = [], []
    for segment, versions in candidates.items():
        versions.sort(key=lambda item: (item[0], str(item[1])), reverse=True)
        selected[segment] = versions[0]
        largest, chosen, _ = versions[0]
        chosen_bytes = chosen.read_bytes()
        for size, other, _ in versions[1:]:
            other_bytes = other.read_bytes()
            # A short copy may end in a partially written row, but must otherwise
            # be a prefix of the retained complete segment, not a different run.
            if not chosen_bytes.startswith(other_bytes):
                conflicts.append(dict(segment=segment, chosen=str(chosen), other=str(other)))
            duplicates.append(dict(segment=segment, kept=str(chosen), ignored=str(other), bytes=size))
    records, malformed, incomplete = [], [], []
    configuration, headers = {}, []
    for segment, (_, path, header) in sorted(selected.items()):
        headers.append(dict(segment=segment, path=str(path.resolve()), header=header))
        with path.open(encoding="utf-8-sig", errors="replace") as stream:
            next(stream)
            for line_number, line in enumerate(stream, 2):
                origin = f"{path.name}:{line_number}"
                if not line.endswith("\n"):
                    incomplete.append(origin)
                    continue
                match = RECORD.fullmatch(line.rstrip("\r\n"))
                if not match:
                    if line.strip():
                        malformed.append(origin)
                    continue
                raw, turn, player = map(int, match.group(1, 2, 3))
                category, message = match.group(4, 5)
                if not 0 <= raw < MOD:
                    malformed.append(origin)
                    continue
                values = fields(message)
                for key, value in re.findall(r"setting:([A-Za-z0-9_]+)=(-?\d+)", message):
                    configuration[key] = int(value)
                records.append(dict(raw_tick=raw, turn=turn, player=player, category=category,
                                    values=values, origin=origin))
    wraps, reversals = unwrap(records)
    numbers = sorted(selected)
    gaps = [[a+1, b-1] for a, b in zip(numbers, numbers[1:]) if b > a+1]
    return records, dict(segment_numbers=numbers, gaps=gaps,
        earlier_segments_missing=bool(numbers and numbers[0] != 0), headers=headers,
        duplicate_segment_files_ignored=duplicates, conflicting_segment_files=conflicts,
        malformed_records=len(malformed), malformed_examples=malformed[:10],
        incomplete_tails_skipped=incomplete, DWORD_wraps=wraps, clock_reversals=reversals[:10],
        configuration=configuration)


def phase_interval(record):
    value = record["values"]
    start, end, duration = (value.get(k) for k in ("startTick", "endTick", "elapsedMs"))
    if not all(isinstance(v, int) for v in (start, end, duration)):
        return None, "missing_integer_bounds"
    if not 0 <= start < MOD or not 0 <= end < MOD or not 0 <= duration < HALF:
        return None, "invalid_bounds"
    if (end-start) % MOD != duration:
        return None, "bounds_disagree_with_elapsed"
    age = (record["raw_tick"]-end) % MOD
    if age >= HALF:
        return None, "end_after_record_tick"
    absolute_end = record["tick"]-age
    return (absolute_end-duration, absolute_end), None


def family(name):
    if name.startswith("tactical_") or name in ("immediate_city_opportunities", "stacking_offensive_moves"):
        return "tactical_scopes"
    if name == "homeland_ai":
        return "homeland_scope"
    if name == "unit_ai_update":
        return "unit_ai_enclosing_scope"
    return "player_preparation_and_other_ai_scopes"


def analyze(records, turn, player_filter=None, quality=None):
    current = [r for r in records if r["turn"] == turn]
    if not current:
        raise ValueError(f"No native records for turn {turn}.")
    following = [r for r in records if r["turn"] == turn+1]
    any_begin = min(r["tick"] for r in current)
    any_next = min((r["tick"] for r in following), default=None)
    any_window = (any_begin, any_next) if any_next is not None and any_next >= any_begin else None
    legacy_current = [r for r in current if r["category"] != "TURN_PHASE"]
    legacy_following = [r for r in following if r["category"] != "TURN_PHASE"]
    first_legacy = min(legacy_current, key=lambda r: r["tick"], default=None)
    next_legacy = min(legacy_following, key=lambda r: r["tick"], default=None)
    begin = first_legacy["tick"] if first_legacy else None
    next_begin = next_legacy["tick"] if next_legacy else None
    complete_boundary = begin is not None and next_begin is not None and next_begin >= begin
    window = (begin, next_begin) if complete_boundary else None
    warnings, phases, recorded_window_phases, plans, perf_pending = [], [], [], [], {}
    invalid = []
    for record in records:
        key = (record["turn"], record["player"], record["values"].get("target"))
        if record["category"] == "PLAN_PERF":
            perf_pending[key] = record
        value = record["values"]
        if record["category"] == "TURN_PHASE":
            interval, error = phase_interval(record)
            if error or value.get("semantics") != "inclusive" or not isinstance(value.get("phase"), str):
                if record["turn"] == turn:
                    invalid.append(dict(origin=record.get("origin"), reason=error or "unsupported_phase_semantics"))
                continue
            phase = dict(sourceTurn=record["turn"], player=record["player"], phase=value["phase"],
                thread=value.get("thread"), interval=interval, elapsed_ms=interval[1]-interval[0],
                origin=record.get("origin"))
            if record["turn"] == turn:
                phases.append(phase)
            # A legacy first-event window can extend into next-turn preparation.
            # Preserve its provenance instead of calling those measured bounds
            # uninstrumented engine time or charging them to selected-turn AI.
            if window and ((interval[1] > interval[0] and interval[1] > window[0] and interval[0] < window[1])
                           or (interval[0] == interval[1] and window[0] <= interval[0] < window[1])):
                recorded_window_phases.append(dict(phase,
                    clipped_interval=(max(interval[0], window[0]), min(interval[1], window[1]))))
        if record["turn"] != turn:
            continue
        if record["category"] == "PLAN":
            milliseconds = value.get("milliseconds")
            if not isinstance(milliseconds, int) or milliseconds < 0:
                warnings.append("A PLAN row has no valid nonnegative milliseconds; skipped.")
                continue
            perf = perf_pending.pop(key, None)
            finalize = perf["values"].get("finalizeMs") if perf else None
            # The cvStopWatch search ends before finalization. Pair the preceding
            # target-matched PLAN_PERF; its finalizeMs ends just before formatting
            # that row. This remains an estimate because two clocks/log emission
            # are involved, not an exact search-start event.
            if perf and isinstance(finalize, int) and finalize >= 0 and perf["tick"] <= record["tick"]:
                end = perf["tick"]-finalize
                anchor = "preceding_PLAN_PERF_tick_minus_finalizeMs"
            else:
                end = record["tick"]
                anchor = "PLAN_emission_tick_fallback_includes_unknown_finalization_lag"
            plans.append(dict(player=record["player"], target=value.get("target"),
                interval=(end-milliseconds, end), milliseconds=milliseconds, estimated=True,
                end_anchor=anchor, coarse_search_ms=perf["values"].get("searchMs") if perf else None,
                origin=record.get("origin")))

    truncations = [dict(origin=r.get("origin"), values=r["values"]) for r in current if r["category"] == "TRUNCATED"]
    dropped = [dict(player=r["player"], origin=r.get("origin"), dropped=r["values"].get("dropped"))
               for r in current if r["category"] == "DIAGNOSTIC_COST" and r["values"].get("dropped", 0) > 0]
    if not complete_boundary:
        warnings.append("Legacy non-TURN_PHASE boundaries are incomplete; comparable full-round duration/unattributed time are unavailable.")
    if (begin, next_begin) != (any_begin, any_next):
        warnings.append("New timing rows change first-event boundaries; use the legacy non-TURN_PHASE window for DLL comparison.")
    if not phases:
        warnings.append("No TURN_PHASE rows: timings may be disabled, filtered, unsampled, or unavailable; absence is not zero work.")
    if truncations or dropped:
        warnings.append("Diagnostic row-budget truncation/drops observed; measured coverage is incomplete.")
    if invalid:
        warnings.append("Invalid/unsupported TURN_PHASE rows were excluded.")
    if quality:
        if quality.get("gaps") or quality.get("conflicting_segment_files") or quality.get("clock_reversals"):
            warnings.append("Segment gaps/conflicts or clock reversals limit authoritative attribution.")
        cfg = quality.get("configuration", {})
        if cfg.get("DiagnosticsPlayer", -1) >= 0:
            warnings.append("Native diagnostics are player-filtered; unmeasured time includes other players.")
        if cfg.get("DiagnosticsPerformanceInterval", 1) == 0 or turn % max(1, cfg.get("DiagnosticsPerformanceInterval", 1)):
            warnings.append("Performance phase sampling excludes this turn by configuration.")
    if player_filter is not None:
        warnings.append("CLI player filter affects player tables only; full-round coverage still uses all retained players.")

    all_phase = clip([p["interval"] for p in phases], window)
    all_plan = clip([p["interval"] for p in plans], window)
    combined = union(all_phase+all_plan)
    recorded_phase_union = union(p["clipped_interval"] for p in recorded_window_phases)
    recorded_combined = union(recorded_phase_union+all_plan)
    phase_plan_overlap = length(intersection(all_phase, all_plan))
    player_rows = []
    players = sorted({r["player"] for r in current if r["player"] >= 0})
    for player in players:
        if player_filter is not None and player != player_filter:
            continue
        entries = [p for p in phases if p["player"] == player]
        searches = [p for p in plans if p["player"] == player]
        phase_groups = defaultdict(list)
        for entry in entries:
            phase_groups[entry["phase"]].append(entry)
        tables = []
        for name, samples in phase_groups.items():
            measured = clip([p["interval"] for p in samples], window)
            plan_overlap = length(intersection(measured, [p["interval"] for p in searches]))
            child_names = CHILD_PHASES.get(name, set())
            children = [entry["interval"] for entry in entries if entry["phase"] in child_names
                and any(entry["thread"] == parent["thread"] and parent["interval"][0] <= entry["interval"][0]
                        and entry["interval"][1] <= parent["interval"][1] for parent in samples)]
            child_covered = intersection(measured, clip(children, window))
            outside_plan = length(measured)-plan_overlap
            # Subtract the union of direct children only. A grandchild is already
            # inside a direct child's interval and must not be subtracted twice.
            child_outside_plan = length(child_covered)-length(intersection(child_covered, [p["interval"] for p in searches]))
            tables.append(dict(phase=name, calls=len(samples), inclusive_sum_ms=sum(p["elapsed_ms"] for p in samples),
                maximum_ms=max(p["elapsed_ms"] for p in samples), union_in_round_ms=length(measured),
                estimated_PLAN_overlap_ms=plan_overlap, outside_estimated_PLAN_ms=outside_plan,
                direct_child_union_ms=length(child_covered), exclusive_remainder_ms=length(measured)-length(child_covered),
                exclusive_remainder_outside_estimated_PLAN_ms=outside_plan-child_outside_plan,
                family=family(name)))
        measured = clip([p["interval"] for p in entries], window)
        search_union = clip([p["interval"] for p in searches], window)
        grouped = {}
        for name in ("tactical_scopes", "homeland_scope", "unit_ai_enclosing_scope", "player_preparation_and_other_ai_scopes"):
            grouped[name] = clip([p["interval"] for p in entries if family(p["phase"]) == name], window)
        tactical = grouped["tactical_scopes"]
        homeland = grouped["homeland_scope"]
        family_output = {name: dict(union_ms=length(intervals),
            estimated_PLAN_overlap_ms=length(intersection(intervals, search_union)),
            outside_estimated_PLAN_ms=length(intervals)-length(intersection(intervals, search_union)))
            for name, intervals in grouped.items()}
        # Disjoint priority partition, not a claim that every instruction in a
        # legacy-named parent originates upstream. Helpers can run inside it.
        tactical_ms = length(tactical)
        homeland_only = length(union(tactical+homeland))-tactical_ms
        remaining = length(measured)-length(union(tactical+homeland))
        player_rows.append(dict(player=player, phase_calls=len(entries), measured_union_ms=length(measured),
            measured_union_outside_estimated_PLAN_ms=length(measured)-length(intersection(measured, search_union)),
            PLAN_calls=len(searches), PLAN_milliseconds_sum=sum(p["milliseconds"] for p in searches),
            estimated_PLAN_union_ms=length(search_union), families_inclusive=family_output,
            disjoint_measured_partition_ms=dict(tactical=tactical_ms, homeland_excluding_tactical=homeland_only,
                other_measured_scopes=remaining),
            phases=sorted(tables, key=lambda x: x["inclusive_sum_ms"], reverse=True)))
    round_ms = window[1]-window[0] if window else None
    any_phases = clip([p["interval"] for p in phases], any_window)
    any_plans = clip([p["interval"] for p in plans], any_window)
    any_duration = any_window[1]-any_window[0] if any_window else None
    return dict(turn=turn, selected_player=player_filter, complete_native_boundary=complete_boundary,
        native_round_window=dict(start_tick=begin, next_turn_first_tick=next_begin, duration_ms=round_ms,
            first_category=first_legacy["category"] if first_legacy else None,
            next_first_category=next_legacy["category"] if next_legacy else None,
            first_origin=first_legacy.get("origin") if first_legacy else None,
            next_first_origin=next_legacy.get("origin") if next_legacy else None,
            convention="first non-TURN_PHASE native record of selected turn to first non-TURN_PHASE record of following turn; legacy-comparable event window, not an engine CPU timer"),
        native_all_event_window=dict(start_tick=any_begin, next_turn_first_tick=any_next, duration_ms=any_duration,
            convention="all native rows, matching existing profile-campaign-log; new timing rows can move these anchors"),
        all_event_coverage=dict(phase_union_ms=length(any_phases), estimated_PLAN_union_ms=length(any_plans),
            phase_or_estimated_PLAN_union_ms=length(union(any_phases+any_plans)),
            round_unattributed_by_phase_scopes_ms=any_duration-length(any_phases) if any_duration is not None else None,
            round_unattributed_by_phases_and_estimated_PLAN_ms=any_duration-length(union(any_phases+any_plans)) if any_duration is not None else None),
        observed_last_tick=max(r["tick"] for r in current),
        coverage_scope="selected source turn only, clipped to the legacy event window; player tables retain that same selected-turn attribution",
        coverage=dict(phase_calls=len(phases), phase_union_ms=length(all_phase), top_enclosing_union_ms=length(all_phase),
            PLAN_calls=len(plans), PLAN_milliseconds_sum=sum(p["milliseconds"] for p in plans),
            estimated_PLAN_union_ms=length(all_plan), phase_and_estimated_PLAN_overlap_ms=phase_plan_overlap,
            measured_phase_outside_estimated_PLAN_ms=length(all_phase)-phase_plan_overlap,
            phase_or_estimated_PLAN_union_ms=length(combined),
            round_outside_estimated_PLAN_ms=round_ms-length(all_plan) if round_ms is not None else None,
            round_unattributed_by_phase_scopes_ms=round_ms-length(all_phase) if round_ms is not None else None,
            round_unattributed_by_phases_and_estimated_PLAN_ms=round_ms-length(combined) if round_ms is not None else None),
        recorded_window_coverage=dict(scope="all retained TURN_PHASE rows whose bounds intersect the legacy event window, regardless of sourceTurn; selected-turn PLAN estimates unchanged",
            phase_calls=len(recorded_window_phases), source_turn_calls=dict(Counter(p["sourceTurn"] for p in recorded_window_phases)),
            phase_union_ms=length(recorded_phase_union),
            additional_phase_coverage_vs_selected_turn_ms=length(recorded_phase_union)-length(all_phase) if window else None,
            phase_and_estimated_PLAN_overlap_ms=length(intersection(recorded_phase_union, all_plan)),
            measured_phase_outside_estimated_PLAN_ms=length(recorded_phase_union)-length(intersection(recorded_phase_union, all_plan)),
            phase_or_estimated_PLAN_union_ms=length(recorded_combined),
            round_unattributed_by_phase_scopes_ms=round_ms-length(recorded_phase_union) if round_ms is not None else None,
            round_unattributed_by_phases_and_estimated_PLAN_ms=round_ms-length(recorded_combined) if round_ms is not None else None),
        recorded_window_phase_intervals=recorded_window_phases,
        players=player_rows, phase_intervals=phases, truncated_events=truncations, diagnostic_drop_samples=dropped,
        invalid_phase_rows=invalid, PLAN_anchor_counts=dict(Counter(p["end_anchor"] for p in plans)),
        PLAN_intervals=plans, warnings=warnings,
        limitations=["Phase summaries are inclusive and overlap; use union/disjoint partition, not sums of all labels.",
            "PLAN location is estimated from high precision duration and coarse emission/finalization ticks; logger delay/quantization can shift overlap attribution.",
            "Existing performance flags, player filters, row budgets, unfinished scopes/turns and retained segments limit coverage.",
            "Original VP versus stacking is a scope label distinction, not proof of source provenance for every instruction.",
            "The legacy event window may include adjacent-turn phase bounds; recorded_window_coverage includes those with sourceTurn provenance, while coverage/player tables remain selected-turn only.",
            "Complete native boundary means the next turn is observed; it does not prove every prior phase/event was retained."])


def self_test():
    checks = 0

    def expect(ok, name):
        nonlocal checks
        checks += 1
        if not ok:
            raise AssertionError(name)

    def rec(tick, turn=7, player=0, category="X", **value):
        return dict(raw_tick=tick % MOD, turn=turn, player=player, category=category, values=value, origin="synthetic")

    expect(union([(0, 100), (20, 40), (80, 120), (120, 130)]) == [(0, 130)], "nested/overlap/touch union")
    expect(length([(1, 1), (2, 5), (3, 7), (9, 8)]) == 5, "empty/reversed and duplicate coverage")
    expect(intersection([(0, 20), (30, 40)], [(10, 35)]) == [(10, 20), (30, 35)], "intersection across gaps")
    rows = [rec(0), rec(40, category="PLAN_PERF", target="x", finalizeMs=10, searchMs=20),
            rec(42, category="PLAN", target="x", milliseconds=20),
            rec(80, category="TURN_PHASE", phase="tactical_ai", startTick=20, endTick=80, elapsedMs=60, thread=1, semantics="inclusive"),
            rec(100, category="TURN_PHASE", phase="unit_ai_update", startTick=0, endTick=100, elapsedMs=100, thread=1, semantics="inclusive"),
            rec(130, player=1, category="TURN_PHASE", phase="economic_ai", startTick=110, endTick=130, elapsedMs=20, thread=1, semantics="inclusive"),
            rec(200, turn=8)]
    unwrap(rows)
    a = analyze(rows, 7)
    expect(a["native_round_window"]["duration_ms"] == 200, "full native boundary")
    expect(a["coverage"]["phase_union_ms"] == 120, "nested phase sum not double counted")
    expect(a["coverage"]["round_unattributed_by_phase_scopes_ms"] == 80, "native round residual")
    expect(a["coverage"]["estimated_PLAN_union_ms"] == 20, "PLAN anchored before finalization")
    expect(a["PLAN_intervals"][0]["interval"] == (10, 30), "PLAN end is perf tick minus finalize")
    expect(a["coverage"]["phase_and_estimated_PLAN_overlap_ms"] == 20, "PLAN overlap union")
    expect(a["coverage"]["measured_phase_outside_estimated_PLAN_ms"] == 100, "phase outside PLAN")
    p = a["players"][0]
    expect(p["measured_union_ms"] == 100, "per player parent union")
    expect(p["disjoint_measured_partition_ms"] == dict(tactical=60, homeland_excluding_tactical=0, other_measured_scopes=40), "scope partition sums once")
    expect(p["phases"][0]["inclusive_sum_ms"] == 100 and p["phases"][0]["calls"] == 1, "inclusive phase detail retained")
    expect(p["phases"][0]["exclusive_remainder_ms"] == 40 and p["phases"][0]["exclusive_remainder_outside_estimated_PLAN_ms"] == 30, "direct child union excluded once from parent remainder")
    filtered = analyze(rows, 7, 1)
    expect(len(filtered["players"]) == 1 and filtered["coverage"] == a["coverage"], "CLI filter does not corrupt whole round")
    partial = analyze(rows[:-1], 7)
    expect(not partial["complete_native_boundary"] and partial["coverage"]["round_unattributed_by_phase_scopes_ms"] is None, "partial turn does not invent total")
    wrap = [rec(MOD-30), rec(10, category="TURN_PHASE", phase="economic_ai", startTick=MOD-20, endTick=5, elapsedMs=25, thread=1, semantics="inclusive"), rec(20, turn=8)]
    count, reversal = unwrap(wrap)
    w = analyze(wrap, 7)
    expect(count == 1 and not reversal, "DWORD wrap unwrapped")
    expect(w["native_round_window"]["duration_ms"] == 50 and w["coverage"]["phase_union_ms"] == 25, "wrapped bounds and whole window")
    bad = [rec(0), rec(20, category="TURN_PHASE", phase="bad", startTick=2, endTick=15, elapsedMs=12, semantics="inclusive"), rec(40, turn=8)]
    unwrap(bad)
    b = analyze(bad, 7)
    expect(len(b["invalid_phase_rows"]) == 1 and b["coverage"]["phase_calls"] == 0, "invalid bound consistency rejected")
    trunc = rows[:-1]+[rec(150, category="TRUNCATED"), rec(160, category="DIAGNOSTIC_COST", dropped=9), rows[-1]]
    unwrap(trunc)
    t = analyze(trunc, 7)
    expect(len(t["truncated_events"]) == 1 and t["diagnostic_drop_samples"][0]["dropped"] == 9, "budget quality records")
    fallback = [rec(0), rec(70, category="PLAN", target="fallback", milliseconds=30), rec(100, turn=8)]
    unwrap(fallback)
    f = analyze(fallback, 7)
    expect(f["PLAN_intervals"][0]["interval"] == (40, 70) and "fallback" in f["PLAN_intervals"][0]["end_anchor"], "missing PERF fallback explicitly marked")
    outside = [rec(10), rec(20, category="TURN_PHASE", phase="before_native_event", startTick=0, endTick=20, elapsedMs=20, semantics="inclusive"), rec(30, turn=8)]
    unwrap(outside)
    expect(analyze(outside, 7)["coverage"]["phase_union_ms"] == 10, "phase boundaries clip to existing native round convention")
    overlap = [rec(0), rec(30, category="PLAN", target="a", milliseconds=30), rec(40, category="PLAN", target="b", milliseconds=30), rec(60, turn=8)]
    unwrap(overlap)
    o = analyze(overlap, 7)
    expect(o["coverage"]["PLAN_milliseconds_sum"] == 60 and o["coverage"]["estimated_PLAN_union_ms"] == 40, "overlapping PLAN sum differs from union")
    sample = analyze(rows, 7, quality=dict(configuration={"DiagnosticsPlayer": 1, "DiagnosticsPerformanceInterval": 3}))
    expect(any("player-filtered" in x for x in sample["warnings"]) and any("sampling excludes" in x for x in sample["warnings"]), "configured filter and sampling acknowledged")
    expect(analyze(fallback, 7)["coverage"]["phase_calls"] == 0, "absence of timers not fabricated")
    repeated = rows[:-1]+[rec(140, category="TURN_PHASE", phase="economic_ai", startTick=125, endTick=140, elapsedMs=15, thread=1, semantics="inclusive")]+[rows[-1]]
    unwrap(repeated)
    r = analyze(repeated, 7)
    detail = next(p for p in r["players"][0]["phases"] if p["phase"] == "economic_ai")
    expect(detail["calls"] == 1 and detail["maximum_ms"] == 15, "calls/max detail independent of other players")
    expect(r["coverage"]["phase_union_ms"] == 130, "different-player overlap counted once globally")
    future = [rec(0), rec(20, category="TURN_PHASE", phase="future", startTick=10, endTick=25, elapsedMs=15, semantics="inclusive"), rec(40, turn=8)]
    unwrap(future)
    expect(analyze(future, 7)["invalid_phase_rows"][0]["reason"] == "end_after_record_tick", "impossible future end rejected")
    q = analyze(rows, 7, quality=dict(gaps=[[1, 2]], conflicting_segment_files=[{}], clock_reversals=["x"]))
    expect(any("Segment gaps" in x for x in q["warnings"]), "archive gaps/conflicts/reversals acknowledged")
    anchor = [rec(5, category="TURN_PHASE", phase="early", startTick=0, endTick=5, elapsedMs=5, semantics="inclusive"),
              rec(10), rec(20, category="TURN_PHASE", phase="straddles", startTick=8, endTick=20, elapsedMs=12, semantics="inclusive"),
              rec(80), rec(105, turn=8, category="TURN_PHASE", phase="next_early", startTick=100, endTick=105, elapsedMs=5, semantics="inclusive"), rec(120, turn=8)]
    unwrap(anchor)
    anchored = analyze(anchor, 7)
    expect(anchored["native_round_window"]["start_tick"] == 10 and anchored["native_round_window"]["next_turn_first_tick"] == 120, "legacy anchor excludes early timing rows")
    expect(anchored["native_round_window"]["duration_ms"] == 110 and anchored["native_all_event_window"]["duration_ms"] == 100, "both distinct event windows exposed")
    expect(anchored["coverage"]["phase_union_ms"] == 10 and anchored["all_event_coverage"]["phase_union_ms"] == 12, "each window clips early phase intervals independently")
    baseline_anchor = [x for x in anchor if x["category"] != "TURN_PHASE"]
    expect(analyze(baseline_anchor, 7)["native_round_window"] == anchored["native_round_window"], "timing rows cannot change baseline-comparable bounds")
    expect(anchored["recorded_window_coverage"]["phase_union_ms"] == 15 and anchored["recorded_window_coverage"]["additional_phase_coverage_vs_selected_turn_ms"] == 5,
           "next-turn early preparation included alongside selected-turn view")
    expect(next(x for x in anchored["recorded_window_phase_intervals"] if x["phase"] == "next_early")["sourceTurn"] == 8,
           "adjacent-turn coverage retains source provenance")
    crossing = [rec(10), rec(100, turn=8, category="TURN_PHASE", phase="next_crossing", startTick=5, endTick=100, elapsedMs=95, thread=1, semantics="inclusive"), rec(120, turn=8)]
    unwrap(crossing)
    crossed = analyze(crossing, 7)
    expect(crossed["coverage"]["phase_union_ms"] == 0 and crossed["recorded_window_coverage"]["phase_union_ms"] == 90,
           "adjacent source turn crossing window cannot fabricate selected-turn work")
    expect(crossed["recorded_window_phase_intervals"][0]["clipped_interval"] == (10, 100)
           and crossed["recorded_window_coverage"]["round_unattributed_by_phase_scopes_ms"] == 20,
           "adjacent-turn crossing bounds clip and residual remains explicit")
    return dict(checks=checks, failures=0, scope="synthetic nested/overlap/wrap/partial/filter/PLAN anchor/row-budget interval semantics")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path)
    parser.add_argument("--run")
    parser.add_argument("--turn", type=int)
    parser.add_argument("--player", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
    else:
        if args.directory is None or args.run is None or args.turn is None or args.output is None:
            parser.error("directory, --run, --turn and --output are required.")
        records, quality = load(args.directory, args.run)
        try:
            result = dict(run=args.run, **analyze(records, args.turn, args.player, quality), archive_quality=quality)
        except ValueError as error:
            parser.error(str(error))
    if args.output:
        target = args.output.resolve()
        inputs = list(args.directory.glob("*.log")) if args.directory else []
        if target.suffix.lower() != ".json" or any(target == p.resolve() or (target.exists() and target.samefile(p)) for p in inputs):
            parser.error("output must be a JSON file and must not replace an input log.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        print(json.dumps({k: result[k] for k in ("turn", "coverage") if k in result} or result))
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
