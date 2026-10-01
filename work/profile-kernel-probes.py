"""Read retained PLAN_KERNEL_PROBE rows without extrapolating sampled work.

Only the requested JSON file is written. Counts describe observed footprints,
not certified interchangeable kernels or saved CPU time.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path


def sibling_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


samples = sibling_module("kernel_plan_samples", "profile-plan-samples.py")
packets = sibling_module("kernel_packet_probes", "profile-packet-probes.py")
wall = samples.wall
MAX_U64 = (1 << 64) - 1
KINDS = ("unit", "stack")
SUFFIXES = (
    "Calls", "Selected", "Complete", "Groups", "Repeats", "SameIncarnation",
    "CrossIncarnation", "ParentAtMutation", "UnknownRelation", "Mismatches",
    "ZeroKeys", "KeyVisits", "ScalarHits", "ScalarMisses", "OutcomeBuilds",
    "PrepInsideTicks", "PrepOutsideTicks", "KernelTicks",
)
SHARED = (
    "evictions", "clears", "oversized", "unavailable", "invalidated", "nested",
    "unknownStates", "keyBytes", "peakKeyBytes",
)
CONFIG = {
    "version": 1, "stride": 64, "slots": 128, "words": 2048, "stateSlots": 8192,
}
IDENTITY = ("turn", "player", "targetPlot", "thread", "serial")
WIRE_NOTE = "observed_footprint_not_certified_reuse_no_stride_scaling_inclusive_kernel_overlaps_prepInside"
NUMERIC_FIELDS = tuple(CONFIG) + ("serial", "target", "thread", "frequency", "metadataBytes") + tuple(
    prefix + suffix for prefix in KINDS for suffix in SUFFIXES
) + SHARED
NOTES = [
    "No stride scaling, whole-search extrapolation, predicted saved simulations or saved-time estimate is performed.",
    "Equality is of the recorded footprint and observed result, not certification that every kernel dependency or policy side effect was captured. Original kernels always execute.",
    "The cohort is coherent for kernel kind, owner, actor ID and destination. It is not an ordinal one-in-64 schedule; selected/calls need not equal 1/64.",
    "The 128-group diagnostic FIFO, 2048-word footprint limit, 512-word source limit, 128-participant limit, scene clears and row budget censor observations. Missing groups or rows are not zero opportunities.",
    "SameIncarnation, CrossIncarnation and ParentAtMutation refer to tokens for covered initialization/mutation hooks. They do not certify every state field; absent tokens and bounded registry lookup failures remain unknown.",
    "The 8192-slot incarnation registry probes at most 64 slots. unknownStates is failed registry lookup count, not a count of distinct states or all unknown relations.",
    "The whole outer enemy injury ledger deliberately overcovers the scalar keys' source-projected injuries. Unrelated injuries can split reusable kernels; low repeat counts cannot alone reject incremental evaluation.",
    "KernelTicks is inclusive same-thread QPC wall time, including PrepInsideTicks. PrepOutsideTicks is constructor/Finish metadata outside that envelope. Do not add inside preparation to kernel time, combine overlapping envelopes, or subtract all preparation as exclusive cost.",
    "Only completed selected frames accumulate timings. Failed/unsupported/oversized preparation, session allocation and mutation-hook costs can be omitted; these counters do not measure total profiler overhead.",
    "QPC failures and zero-resolution samples are not separately counted by this emitter. Zero ticks for called work or frequency zero means unknown timing, not zero CPU cost.",
    "ScalarHits, ScalarMisses and OutcomeBuilds are counter deltas within completed selected kernels; they are observed work, not a guarantee of avoidable work. OutcomeBuilds includes shared-packet builds in the current cache implementation.",
    "PLAN_SAMPLE uses exact turn/player/target/thread/serial identity. Historical PLAN/PERF lack thread/serial; bounded adjacency and verified target provide only candidate associations.",
    "Key payload and metadata bytes are per-PLAN snapshots summarized by maxima, not summed heap memory or process RSS. Diagnostic metadata is separate from gameplay forecast capacity/FIFO.",
]


def unsigned(value, maximum=MAX_U64):
    return type(value) is int and 0 <= value <= maximum


def identity(row):
    return tuple(row[key] for key in IDENTITY)


def duplicate_fields(record, names):
    raw = record.get("raw_message", "")
    wire = wall.RECORD.fullmatch(raw.rstrip("\r\n"))
    pairs = wall.FIELD.findall(wire.group(5) if wire else raw)
    return sorted(key for key, count in Counter(key for key, value in pairs).items() if count > 1 and key in names)


def decode(record):
    value = record["values"]
    errors, warnings = [], []
    if "[message truncated]" in record.get("raw_message", ""):
        errors.append("explicit_message_truncation")
    repeated = duplicate_fields(record, NUMERIC_FIELDS + ("note",))
    if repeated:
        errors.append("duplicate_fields:" + ",".join(repeated))
    for name in NUMERIC_FIELDS:
        if not unsigned(value.get(name)):
            errors.append(name + ":missing_or_invalid_unsigned_integer")
    if errors:
        return None, errors
    for name, expected in CONFIG.items():
        if value[name] != expected:
            errors.append("unsupported_" + name)
    if value.get("note") != WIRE_NOTE:
        errors.append("unsupported_or_missing_observation_semantics")
    if not 0 < value["serial"] <= (1 << 32) - 1 or not 0 < value["thread"] <= (1 << 32) - 1:
        errors.append("invalid_native_identity")
    if value["target"] > (1 << 31) - 1:
        errors.append("invalid_native_plot_index")
    if not 128 * 2048 * 4 <= value["metadataBytes"] <= 3 * 1024 * 1024:
        errors.append("metadata_footprint_out_of_bounds")
    for prefix in KINDS:
        fields = {suffix: value[prefix + suffix] for suffix in SUFFIXES}
        if not fields["Complete"] <= fields["Selected"] <= fields["Calls"]:
            errors.append(prefix + ":completion_counts_out_of_order")
        if fields["Groups"] + fields["Repeats"] != fields["Complete"]:
            errors.append(prefix + ":groups_and_repeats_do_not_sum_to_complete")
        if fields["SameIncarnation"] + fields["CrossIncarnation"] + fields["UnknownRelation"] != fields["Repeats"]:
            errors.append(prefix + ":relation_classes_do_not_sum_to_repeats")
        for child, parent in (("Mismatches", "Repeats"), ("ParentAtMutation", "Repeats"), ("ZeroKeys", "Complete")):
            if fields[child] > fields[parent]:
                errors.append(prefix + ":" + child + "_exceeds_" + parent)
        if fields["ScalarHits"] + fields["ScalarMisses"] != fields["KeyVisits"]:
            warnings.append(prefix + ":key_visits_differ_from_scalar_counter_deltas")
        if fields["Selected"] != fields["Complete"]:
            warnings.append(prefix + ":selected_frames_incomplete")
        if fields["Complete"] and (not value["frequency"] or not fields["KernelTicks"]):
            warnings.append(prefix + ":completed_kernel_wall_time_unknown_or_zero_resolution")
    if value["evictions"] > value["unitGroups"] + value["stackGroups"]:
        errors.append("evictions_exceed_group_admissions")
    if not value["keyBytes"] <= value["peakKeyBytes"] <= 128 * 2048 * 4:
        errors.append("key_payload_or_peak_out_of_bounds")
    if value["keyBytes"] % 4 or value["peakKeyBytes"] % 4:
        errors.append("key_payload_not_word_aligned")
    if errors:
        return None, errors
    row = {name: value[name] for name in NUMERIC_FIELDS if name != "target"}
    row.update(targetPlot=value["target"], turn=record["turn"], player=record["player"],
               tick=record["tick"], origin=record.get("origin"), warnings=warnings)
    row["kinds"] = {}
    for prefix in KINDS:
        fields = {suffix: value[prefix + suffix] for suffix in SUFFIXES}
        clocks = {}
        for field in ("KernelTicks", "PrepInsideTicks", "PrepOutsideTicks"):
            known = fields["Complete"] > 0 and value["frequency"] > 0
            if fields[field] == 0 and (field != "PrepInsideTicks" or fields["KeyVisits"] > 0):
                known = False
            clocks[field] = dict(ticks=fields[field], observed_wall_ms=fields[field] * 1000 / value["frequency"] if known else None,
                                 status="retained_completed_envelope" if known else "unknown_no_complete_or_clock_resolution")
        row["kinds"][prefix] = dict(counts=fields, clocks=clocks,
            incomplete_selected=fields["Selected"] - fields["Complete"],
            observed_repeat_fraction=fields["Repeats"] / fields["Complete"] if fields["Complete"] else None,
            observed_matching_repeat_count=fields["Repeats"] - fields["Mismatches"])
    return row, []


def aggregate(rows):
    result = dict(plan_probe_rows=len(rows), counts={name: sum(row[name] for row in rows) if rows else None for name in SHARED if name not in ("keyBytes", "peakKeyBytes")},
                  per_plan_max_bytes={name: max((row[name] for row in rows), default=None) for name in ("metadataBytes", "keyBytes", "peakKeyBytes")}, kinds={})
    for prefix in KINDS:
        fields = {suffix: sum(row[prefix + suffix] for row in rows) if rows else None for suffix in SUFFIXES}
        timing = {}
        for name in ("KernelTicks", "PrepInsideTicks", "PrepOutsideTicks"):
            known = [row["kinds"][prefix]["clocks"][name]["observed_wall_ms"] for row in rows if row["kinds"][prefix]["clocks"][name]["observed_wall_ms"] is not None]
            called_unknown = sum(row[prefix + "Calls"] > 0 and row["kinds"][prefix]["clocks"][name]["observed_wall_ms"] is None for row in rows)
            timing[name] = dict(known_completed_wall_ms=sum(known) if known else None, known_row_count=len(known), called_rows_with_unknown_time=called_unknown,
                               scope="Retained completed selected envelopes; inclusive/nonadditive, no extrapolation.")
        complete = fields["Complete"]
        result["kinds"][prefix] = dict(counts=fields, timings=timing,
            observed_repeat_fraction=fields["Repeats"] / complete if complete else None,
            observed_matching_repeat_count=fields["Repeats"] - fields["Mismatches"] if rows else None,
            fraction_scope="Retained complete coherent-cohort observations only; FIFO/bounds/lifecycle/row-censored.")
    return result


def associate_legacy(records, position, probe, map_width):
    skipped = None
    if position and records[position - 1]["category"] == "PLAN_PACKET_PROBE":
        packet, errors = packets.decode(records[position - 1])
        if errors or identity(packet) != identity(probe):
            return dict(status="unmatched", candidate=None, reason="intervening_packet_footer_invalid_or_identity_mismatch")
        skipped = dict(category="PLAN_PACKET_PROBE", origin=packet["origin"], identity=list(identity(packet)))
        position -= 1
    result = samples.associate_plan(records, position, probe, map_width)
    if skipped:
        result["skipped_exact_identity_footer"] = skipped
    return result


def analyze(records, quality=None, turn=None, player=None, map_width=None):
    selected = lambda row: (turn is None or row["turn"] == turn) and (player is None or row["player"] == player)
    invalid, probe_candidates, sample_candidates = [], [], []
    for position, record in enumerate(records):
        if not selected(record) or record["category"] not in ("PLAN_KERNEL_PROBE", "PLAN_SAMPLE"):
            continue
        row, errors = decode(record) if record["category"] == "PLAN_KERNEL_PROBE" else samples.decode(record)
        if record["category"] == "PLAN_SAMPLE":
            duplicate = duplicate_fields(record, ("targetPlot", "thread", "serial", "stride", "phase", "qpcFrequency",
                "qpcFrequencyCalls", "qpcReads", "clockFailures", "parts", "semantics", "cadenceVersion", "strides", "phases") + samples.ARRAYS)
            if duplicate:
                errors += ["duplicate_fields:" + ",".join(duplicate)]
        if errors:
            invalid.append(dict(category=record["category"], origin=record.get("origin"), turn=record["turn"], player=record["player"], errors=errors))
        else:
            row["position"] = position
            (probe_candidates if record["category"] == "PLAN_KERNEL_PROBE" else sample_candidates).append(row)

    def unique(rows, category):
        counts = Counter(identity(row) for row in rows)
        good = []
        for row in rows:
            if counts[identity(row)] == 1:
                good.append(row)
            else:
                invalid.append(dict(category=category, origin=row.get("origin"), turn=row["turn"], player=row["player"], errors=["duplicate_identity"], identity=list(identity(row))))
        return good

    probes = unique(probe_candidates, "PLAN_KERNEL_PROBE")
    timed = unique(sample_candidates, "PLAN_SAMPLE")
    timed_by_id = {identity(row): row for row in timed}
    probes_by_id = {identity(row): row for row in probes}
    for probe in probes:
        other = timed_by_id.get(identity(probe))
        probe["sample_association"] = dict(status="identity_verified" if other else "unmatched", origin=other["origin"] if other else None,
            parts=[dict(part=part["part"], calls=part["calls"], samples=part["samples"], sampled_wall_ms=part["sampled_wall_ms"]) for part in other["parts"]] if other else None)
        probe["legacy_plan_association"] = associate_legacy(records, probe.pop("position"), probe, map_width)
        if map_width:
            probe["target_coordinates"] = [probe["targetPlot"] % map_width, probe["targetPlot"] // map_width]
    quality = quality or {}
    drops = [dict(origin=row.get("origin"), turn=row["turn"], player=row["player"], fields=row["values"]) for row in records if selected(row) and row["category"] == "TRUNCATED"]
    costs = [dict(origin=row.get("origin"), turn=row["turn"], player=row["player"], fields=row["values"]) for row in records if selected(row) and row["category"] == "DIAGNOSTIC_COST"]
    warnings = []
    if not probes:
        warnings.append("No valid kernel probe rows: opportunities and timing are unknown, not zero.")
    if invalid:
        warnings.append("Invalid or duplicate-identity rows were excluded; retained coverage is incomplete.")
    if quality.get("conflicting_segment_files"):
        warnings.append("Conflicting segment copies were found; archive completeness is uncertain.")
    if any(quality.get(name) for name in ("gaps", "earlier_segments_missing", "incomplete_tails_skipped", "malformed_records")):
        warnings.append("Native archive has gaps, malformed lines or incomplete tails; counts cover retained complete records only.")
    if quality.get("clock_reversals"):
        warnings.append("Native clock reversals make legacy adjacency timing unreliable.")
    if drops or any(unsigned(row["fields"].get("dropped")) and row["fields"]["dropped"] > 0 for row in costs):
        warnings.append("Diagnostic row drops are reported; missing probe/SAMPLE rows can be budget-censored.")
    groups = defaultdict(list)
    for probe in probes:
        groups[(probe["turn"], probe["player"], probe["targetPlot"])].append(probe)
    unmatched = [dict(identity=list(identity(row)), origin=row["origin"]) for row in timed if identity(row) not in probes_by_id]
    return dict(schema="native_PLAN_KERNEL_PROBE_v1", filters=dict(turn=turn, player=player, map_width=map_width), measurement_notes=NOTES,
        warnings=warnings, archive_quality=quality, invalid_rows=invalid, invalid_row_count=len(invalid),
        coverage=dict(valid_probe_rows=len(probes), valid_sample_rows=len(timed), probe_sample_identity_matches=sum(identity(row) in timed_by_id for row in probes),
            probes_without_sample=sum(identity(row) not in timed_by_id for row in probes), samples_without_probe=len(unmatched),
            retained_native_PLAN_rows=sum(selected(row) and row["category"] == "PLAN" for row in records),
            retained_native_PLAN_PERF_rows=sum(selected(row) and row["category"] == "PLAN_PERF" for row in records)),
        whole_selection=aggregate(probes), legacy_association_counts=dict(Counter(row["legacy_plan_association"]["status"] for row in probes)),
        diagnostic_drop_rows=drops, diagnostic_cost_rows=costs, samples_without_probe=unmatched,
        turn_player_target_groups=[dict(turn=key[0], player=key[1], targetPlot=key[2], target_coordinates=[key[2] % map_width, key[2] // map_width] if map_width else None,
            **aggregate(value)) for key, value in sorted(groups.items())], plans=probes)


def load(directory, run):
    records, quality = wall.load(directory, run)
    messages = {}
    for header in quality["headers"]:
        path = Path(header["path"])
        with path.open(encoding="utf-8-sig", errors="replace") as stream:
            for index, line in enumerate(stream, 1):
                if any("|" + category + "|" in line for category in ("PLAN_KERNEL_PROBE", "PLAN_PACKET_PROBE", "PLAN_SAMPLE")):
                    messages[f"{path.name}:{index}"] = line
    for record in records:
        if record["category"] in ("PLAN_KERNEL_PROBE", "PLAN_PACKET_PROBE", "PLAN_SAMPLE"):
            record["raw_message"] = messages.get(record["origin"], "")
    return records, quality


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_directory", type=Path)
    parser.add_argument("--run", required=True, help="Exact native session run ID; never merge sessions")
    parser.add_argument("--turn", type=int)
    parser.add_argument("--player", type=int)
    parser.add_argument("--map-width", type=int, help="Optional independently verified map width; never inferred")
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    if not options.native_directory.is_dir():
        parser.error("native_directory must exist")
    if options.map_width is not None and options.map_width <= 0:
        parser.error("--map-width must be positive")
    records, quality = load(options.native_directory, options.run)
    if not quality["headers"]:
        parser.error("No matching native session segments found")
    report = analyze(records, quality, options.turn, options.player, options.map_width)
    report.update(native_directory=str(options.native_directory.resolve()), run=options.run)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(options.output.resolve()), coverage=report["coverage"], invalid_row_count=report["invalid_row_count"], warnings=report["warnings"])))
    return 2 if report["invalid_row_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
