"""Offline PLAN_SAMPLE analysis. Only the requested JSON file is written.

Samples are inclusive wall-clock measurements and systematically selected.
Estimates are approximate, may alias periodic work, and must not be summed
across parts. No samples means unknown work, rather than zero cost.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location("wall_profile", Path(__file__).with_name("profile-turn-phases.py"))
wall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wall)

PARTS = (
    "combatMove", "turnEnd", "stackScore", "unitDanger", "dangerKey",
    "dangerLeaf", "preferred", "moveUpdate", "nextAssignments",
    "citySimulation", "unitSimulation", "damageMath", "randomDamageMath",
)
ARRAYS = ("calls", "selected", "samples", "ticks", "maxTicks")
STRIDE = 4096
CADENCE_STRIDES = (4096,4096,4096,4096,4096,256,256,4096,64,4096,4096,4096,4096)
MAX_U64 = (1 << 64)-1
SEMANTICS = "inclusive_same_thread_wall_samples"
NOTES = [
    "Times are inclusive same-thread WALL QPC samples, not CPU time.",
    "Timing envelopes include sampler/Finish overhead and QPC granularity; tiny helpers can be dominated by this floor. No calibrated subtraction is applied.",
    "Parts overlap. Do not sum estimates from different parts or subtract parent/child estimates as exclusive cost.",
    "Systematic stride selection can alias periodic work; low sample counts have especially uncertain estimates.",
    "Selected outer scopes can include suppressed nested-search or callback wall time.",
    "dangerKey includes construction and lookup; dangerLeaf is scalar-miss/outcome resolution, including reused outcomes, excluding cache admission.",
    "estimated_total_ms is sampled_wall_ms * calls / completed_samples, an approximate extrapolation with no confidence interval.",
    "No completed samples for a called part means unknown cost, never zero.",
    "Existing PLAN rows lack thread/serial. Even an adjacent target-verified PLAN is a candidate association, not proven shared search identity.",
]


def integer(value, maximum=MAX_U64):
    return type(value) is int and 0 <= value <= maximum


def csv_integers(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name}: missing_or_non_csv_array")
    values = value.split(",")
    if len(values) != len(PARTS):
        raise ValueError(f"{name}: invalid_array_length_{len(values)}")
    if any(not re.fullmatch(r"\d+", item) for item in values):
        raise ValueError(f"{name}: non_unsigned_integer")
    result = list(map(int, values))
    if any(item > MAX_U64 for item in result):
        raise ValueError(f"{name}: integer_overflow")
    return result


def decode(record):
    value = record["values"]
    errors, warnings = [], []
    if "[message truncated]" in record.get("raw_message", ""):
        errors.append("explicit_message_truncation")
    if value.get("parts") != ",".join(PARTS):
        errors.append("unsupported_or_missing_part_order")
    for name in ("targetPlot", "serial", "thread", "stride", "phase", "qpcFrequency", "qpcFrequencyCalls", "qpcReads", "clockFailures"):
        if not integer(value.get(name)):
            errors.append(f"{name}: missing_or_invalid_unsigned_integer")
    if not errors:
        if value["serial"] == 0 or value["thread"] == 0:
            errors.append("zero_serial_or_thread")
        if value["stride"] != STRIDE or not 0 <= value["phase"] < STRIDE:
            errors.append("unsupported_stride_or_invalid_phase")
        if value["qpcFrequency"] == 0 or value["qpcFrequencyCalls"] != 1:
            errors.append("invalid_qpc_frequency_or_frequency_call_count")
    if value.get("semantics") != SEMANTICS:
        errors.append("unsupported_or_missing_semantics")
    arrays = {}
    for name in ARRAYS:
        try:
            arrays[name] = csv_integers(value.get(name), name)
        except ValueError as error:
            errors.append(str(error))
    if errors:
        return None, errors
    cadence = value.get("cadenceVersion", 1)
    if cadence == 1 and not any(key in value for key in ("strides", "phases")):
        strides = [STRIDE]*len(PARTS)
        phases = [(value["phase"]+index*97) & (STRIDE-1) for index in range(len(PARTS))]
    elif cadence == 2:
        try:
            strides = csv_integers(value.get("strides"), "strides")
            phases = csv_integers(value.get("phases"), "phases")
        except ValueError as error:
            return None, [str(error)]
        if tuple(strides) != CADENCE_STRIDES:
            errors.append("unsupported_v2_part_strides")
        if any(not 0 <= phase < stride for stride,phase in zip(strides,phases)):
            errors.append("v2_part_phase_out_of_bounds")
        if not errors and any(phase != ((value["phase"]+index*97) & (strides[index]-1)) for index,phase in enumerate(phases)):
            errors.append("v2_part_phase_disagrees_with_base_phase")
    else:
        return None, ["unsupported_cadence_version_or_unversioned_metadata"]
    if errors:
        return None, errors
    for index, name in enumerate(PARTS):
        calls, selected, samples, ticks, maximum = (arrays[key][index] for key in ARRAYS)
        phase, stride = phases[index], strides[index]
        expected_selected = (calls+phase)//stride
        if not samples <= selected <= calls:
            errors.append(f"{name}: sample_counts_out_of_order")
        if selected != expected_selected:
            errors.append(f"{name}: selected_disagrees_with_stride_schedule")
        if (samples == 0 and (ticks != 0 or maximum != 0)) or maximum > ticks:
            errors.append(f"{name}: inconsistent_tick_totals")
    selected, completed = sum(arrays["selected"]), sum(arrays["samples"])
    if not selected+completed <= value["qpcReads"] <= 2*selected:
        errors.append("qpc_reads_disagree_with_selected_and_completed_scopes")
    if value["clockFailures"] > selected-completed:
        errors.append("clock_failures_exceed_incomplete_selected_scopes")
    if errors:
        return None, errors
    if value["clockFailures"]:
        warnings.append("QPC failed for some selected scopes; surviving samples may not be representative.")
    if selected != completed:
        warnings.append("Some selected scopes did not complete; clock failures and scope/session lifecycle can both cause omissions.")
    parts = []
    for index, name in enumerate(PARTS):
        calls, chosen, samples, ticks, maximum = (arrays[key][index] for key in ARRAYS)
        milliseconds = ticks*1000/value["qpcFrequency"]
        approximate = milliseconds*calls/samples if samples else (0.0 if calls == 0 else None)
        part_warnings = []
        if calls and not samples:
            part_warnings.append("Called work has no completed sample: cost is unknown.")
        elif 0 < samples < 30:
            part_warnings.append("Fewer than 30 completed samples: extrapolation is especially uncertain.")
        if samples and ticks == 0:
            part_warnings.append("Completed samples measured zero ticks; zero-resolution measurements do not establish zero cost.")
        if chosen != samples:
            part_warnings.append("Selected sample completion is incomplete.")
        parts.append(dict(part=name, stride=strides[index], phase=phases[index], calls=calls, selected=chosen, samples=samples,
            sampling_fraction=samples/calls if calls else None,
            selected_completion_fraction=samples/chosen if chosen else None,
            sampled_ticks=ticks, max_ticks=maximum, sampled_wall_ms=milliseconds,
            maximum_sample_wall_ms=maximum*1000/value["qpcFrequency"] if samples else None,
            mean_sample_wall_ms=milliseconds/samples if samples else None,
            estimated_total_ms=approximate, estimate_kind="approximate_sample_mean_extrapolation" if samples else ("no_calls" if not calls else "unknown_no_completed_samples"),
            warnings=part_warnings))
    return dict(turn=record["turn"], player=record["player"], targetPlot=value["targetPlot"],
        serial=value["serial"], thread=value["thread"], stride=STRIDE, phase=value["phase"],
        cadenceVersion=cadence, strides=strides, phases=phases,
        qpcFrequency=value["qpcFrequency"], qpcFrequencyCalls=value["qpcFrequencyCalls"],
        qpcReads=value["qpcReads"], clockFailures=value["clockFailures"],
        tick=record["tick"], origin=record.get("origin"), parts=parts, warnings=warnings), []


def associate_plan(records, position, sample, map_width):
    """Only adjacent PLAN/PLAN_PERF candidates; never borrow a stale target.

    Target equality alone does not establish the TLS serial/thread identity.
    Old PLAN rows therefore remain explicitly qualified candidate associations.
    """
    result = dict(status="unmatched", candidate=None)
    if position == 0:
        return result
    previous = records[position-1]
    if previous["category"] not in ("PLAN", "PLAN_PERF"):
        result["reason"] = "previous_native_record_is_not_PLAN_or_PLAN_PERF"
        return result
    if previous["turn"] != sample["turn"] or previous["player"] != sample["player"]:
        result["reason"] = "adjacent_plan_has_different_turn_or_player"
        return result
    value = previous["values"]
    result["candidate"] = dict(category=previous["category"], origin=previous.get("origin"),
        tick=previous["tick"], lag_ms=sample["tick"]-previous["tick"], fields=value)
    target_verified = False
    if integer(value.get("targetPlot")):
        target_verified = value["targetPlot"] == sample["targetPlot"]
        if not target_verified:
            result.update(status="target_mismatch", reason="explicit_targetPlot_disagrees")
            return result
    elif map_width is not None:
        match = re.fullmatch(r"(\d+):(\d+)", str(value.get("target", "")))
        if match:
            x, y = map(int, match.groups())
            target_verified = x < map_width and y*map_width+x == sample["targetPlot"]
            if not target_verified:
                result.update(status="target_mismatch", reason="target_coordinates_disagree_with_supplied_map_width")
                return result
    mismatched = [key for key in ("thread", "serial") if key in value and value[key] != sample[key]]
    if mismatched:
        result.update(status="identity_mismatch", reason=",".join(mismatched))
    elif target_verified and all(key in value for key in ("thread", "serial")):
        result.update(status="identity_and_target_verified", reason="adjacent_explicit_target_and_identity_fields_match")
    elif target_verified:
        result.update(status="target_verified_adjacent_candidate", reason="PLAN_thread_or_serial_missing_shared_search_identity_unproven")
    else:
        result.update(status="target_unverified_adjacent_candidate", reason="need_explicit_targetPlot_or_supplied_map_width_and_PLAN_identity_fields")
    # PLAN_PERF normally immediately precedes PLAN. Attach it only with the
    # same native target spelling; it remains qualified by the PLAN association.
    if previous["category"] == "PLAN" and position >= 2:
        perf = records[position-2]
        if (perf["category"] == "PLAN_PERF" and perf["turn"] == sample["turn"]
                and perf["player"] == sample["player"]
                and perf["values"].get("target") == value.get("target")):
            result["preceding_perf_candidate"] = dict(origin=perf.get("origin"), tick=perf["tick"], fields=perf["values"])
    return result


def summarize_parts(plans):
    result = []
    for name in PARTS:
        rows = [plan["parts"][PARTS.index(name)] for plan in plans]
        calls, selected, samples = (sum(row[key] for row in rows) for key in ("calls", "selected", "samples"))
        missing = [row for row in rows if row["calls"] and row["samples"] == 0]
        estimates = [row["estimated_total_ms"] for row in rows if row["samples"]]
        sampled = sum(row["sampled_wall_ms"] for row in rows)
        result.append(dict(part=name, plans=len(plans), called_plans=sum(row["calls"] > 0 for row in rows),
            sampled_plans=sum(row["samples"] > 0 for row in rows), calls=calls, selected=selected, samples=samples,
            sampling_fraction=samples/calls if calls else None, selected_completion_fraction=samples/selected if selected else None,
            sampled_wall_ms=sampled, maximum_sample_wall_ms=max((row["maximum_sample_wall_ms"] for row in rows if row["samples"]), default=None),
            approximate_estimate_known_plans_ms=sum(estimates) if estimates else (0.0 if not calls else None),
            estimated_total_all_plans_ms=sum(estimates) if not missing and (estimates or not calls) else None,
            unknown_cost_plans=len(missing), unknown_cost_calls=sum(row["calls"] for row in missing),
            below_30_sample_called_plans=sum(row["calls"] > 0 and row["samples"] < 30 for row in rows),
            warnings=["Inclusive approximate estimates; do not add to other parts.", "Systematic selection can alias periodic work."]
                     + (["Some called plans have no completed samples; the full part total is unknown."] if missing else [])))
    return result


def analyze(records, quality=None, turn=None, player=None, map_width=None):
    invalid, decoded = [], []
    for position, record in enumerate(records):
        if record["category"] != "PLAN_SAMPLE" or (turn is not None and record["turn"] != turn) or (player is not None and record["player"] != player):
            continue
        sample, errors = decode(record)
        if errors:
            invalid.append(dict(origin=record.get("origin"), turn=record["turn"], player=record["player"], errors=errors))
        else:
            sample["plan_association"] = associate_plan(records, position, sample, map_width)
            decoded.append(sample)
    # Reject all duplicated identity rows, including conflicting versions. A
    # copied segment is handled separately by the canonical segment loader.
    identities = Counter((r["turn"], r["player"], r["targetPlot"], r["thread"], r["serial"]) for r in decoded)
    plans = []
    for row in decoded:
        key = (row["turn"], row["player"], row["targetPlot"], row["thread"], row["serial"])
        if identities[key] > 1:
            invalid.append(dict(origin=row["origin"], turn=row["turn"], player=row["player"], errors=["duplicate_sample_identity"], identity=key))
        else:
            plans.append(row)
    grouped = defaultdict(list)
    for row in plans:
        grouped[(row["turn"], row["player"], row["targetPlot"])].append(row)
    warnings = []
    quality = quality or {}
    if quality.get("conflicting_segment_files"):
        warnings.append("Conflicting copies of a native segment exist. The largest copy was selected; archive completeness is uncertain.")
    if quality.get("gaps") or quality.get("earlier_segments_missing") or quality.get("incomplete_tails_skipped"):
        warnings.append("Native archive is partial. Counts describe retained complete records only.")
    if quality.get("clock_reversals"):
        warnings.append("Native clock order contains reversals; candidate time adjacency is not reliable evidence of shared search identity.")
    return dict(schema="native_PLAN_SAMPLE_v1_v2", filters=dict(turn=turn, player=player, map_width=map_width),
        measurement_notes=NOTES, warnings=warnings, archive_quality=quality,
        valid_sample_rows=len(plans), invalid_sample_rows=len(invalid), invalid_rows=invalid,
        association_counts=dict(Counter(row["plan_association"]["status"] for row in plans)),
        whole_selection_parts=summarize_parts(plans),
        turn_player_target_groups=[dict(turn=key[0], player=key[1], targetPlot=key[2],
            target_coordinates=[key[2] % map_width, key[2]//map_width] if map_width else None,
            plan_rows=len(rows), parts=summarize_parts(rows)) for key, rows in sorted(grouped.items())],
        plans=plans)


def load(directory, run):
    records, quality = wall.load(directory, run)
    # Preserve the explicit truncation marker, which the shared field parser
    # intentionally ignores. Only canonical files and sample rows are reread.
    messages = {}
    for header in quality["headers"]:
        path = Path(header["path"])
        with path.open(encoding="utf-8-sig", errors="replace") as stream:
            for index, line in enumerate(stream, 1):
                if "|PLAN_SAMPLE|" in line:
                    messages[f"{path.name}:{index}"] = line
    for record in records:
        if record["category"] == "PLAN_SAMPLE":
            record["raw_message"] = messages.get(record["origin"], "")
    return records, quality


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_directory", type=Path)
    parser.add_argument("--run", required=True, help="Exact native session run identifier; never combine different sessions")
    parser.add_argument("--turn", type=int)
    parser.add_argument("--player", type=int)
    parser.add_argument("--map-width", type=int, help="Optional verified map width to translate targetPlot to PLAN x:y; not inferred")
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    if options.map_width is not None and options.map_width <= 0:
        parser.error("--map-width must be positive")
    if not options.native_directory.is_dir():
        parser.error("native_directory must exist")
    records, quality = load(options.native_directory, options.run)
    if not quality["headers"]:
        parser.error("No matching native run segments found")
    result = analyze(records, quality, options.turn, options.player, options.map_width)
    result["native_directory"] = str(options.native_directory.resolve())
    result["run"] = options.run
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(output=str(options.output.resolve()), valid_sample_rows=result["valid_sample_rows"],
        invalid_sample_rows=result["invalid_sample_rows"], association_counts=result["association_counts"])))
    return 0 if not result["invalid_sample_rows"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
