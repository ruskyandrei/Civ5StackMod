"""Lightweight synthetic reader tests; no compiler, game or timing benchmark."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("kernel_profile", ROOT / "profile-kernel-probes.py")
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)
checks = 0


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        raise AssertionError(label)


def record(category, fields, tick=100, turn=253, player=3, origin="synthetic:1", suffix=""):
    message = " ".join(f"{key}={value}" for key, value in fields.items()) + suffix
    raw = f"STACKDIAG|{tick}|turn={turn}|player={player}|{category}|{message}"
    return dict(category=category, values=profile.wall.fields(message), raw_tick=tick, tick=tick,
                turn=turn, player=player, origin=origin, raw_message=raw)


def probe(serial=1, **extra):
    values = {field: 0 for field in profile.NUMERIC_FIELDS}
    values.update(profile.CONFIG)
    values.update(serial=serial, target=321, thread=7, frequency=1000, metadataBytes=1253376,
                  unitCalls=120, unitSelected=9, unitComplete=8, unitGroups=3, unitRepeats=5,
                  unitSameIncarnation=2, unitCrossIncarnation=2, unitUnknownRelation=1,
                  unitParentAtMutation=1, unitMismatches=1, unitZeroKeys=1,
                  unitKeyVisits=10, unitScalarHits=8, unitScalarMisses=2, unitOutcomeBuilds=1,
                  unitPrepInsideTicks=50, unitPrepOutsideTicks=80, unitKernelTicks=200,
                  evictions=1, keyBytes=512, peakKeyBytes=1024, note=profile.WIRE_NOTE)
    values.update(extra)
    return record("PLAN_KERNEL_PROBE", values)


def sample(serial=1, **extra):
    zero = ",".join("0" for name in profile.samples.PARTS)
    values = dict(targetPlot=321, thread=7, serial=serial, stride=4096, phase=0,
                  qpcFrequency=1000, qpcFrequencyCalls=1, qpcReads=0, clockFailures=0,
                  parts=",".join(profile.samples.PARTS), calls=zero, selected=zero,
                  samples=zero, ticks=zero, maxTicks=zero, semantics=profile.samples.SEMANTICS)
    values.update(extra)
    return record("PLAN_SAMPLE", values, tick=104, origin="synthetic:sample")


def packet(serial=1):
    values = {name: 0 for name in profile.packets.COUNTS + profile.packets.BYTES}
    values.update(version=2, serial=serial, thread=7, targetPlot=321, prefilterBits=2,
                  cohortBits=3, slots=128, maxKeyWords=512, metadataBytes=270000)
    return record("PLAN_PACKET_PROBE", values, tick=102, origin="synthetic:packet")


def main():
    # Bind every reader field and its semantic marker to the actual frozen wire.
    source = (ROOT / "destination-kernel-probe-fragment.cpp").read_text(encoding="utf-8-sig")
    wire = re.search(r'"version=1 serial=%lu target=%d thread=%lu stride=64 slots=128 words=2048 stateSlots=8192 frequency=.*?"', source).group(0)[1:-1]
    names = re.findall(r"(?:^|\s)([A-Za-z][A-Za-z0-9_]*)=", wire)
    check(set(names) == set(profile.NUMERIC_FIELDS) | {"note"}, "emitter/reader fields exact")
    check(len(names) == len(set(names)), "emitter fields unique")
    check("note=" + profile.WIRE_NOTE in wire, "wire note matches")
    check("KERNEL_PROBE_STATE_LOOKUP_LIMIT=64" in source, "documented registry bound")

    row, errors = profile.decode(probe())
    check(not errors, "valid row accepted")
    check(row["targetPlot"] == 321 and "target" not in row, "target normalization")
    check(row["kinds"]["unit"]["observed_matching_repeat_count"] == 4, "mismatches separate from matching repeats")
    check(row["kinds"]["unit"]["clocks"]["KernelTicks"]["observed_wall_ms"] == 200, "QPC conversion")
    check(row["kinds"]["stack"]["clocks"]["KernelTicks"]["observed_wall_ms"] is None, "no selected frames is unknown")
    check("unit:selected_frames_incomplete" in row["warnings"], "incomplete selection warning")

    invalid_cases = [
        {"unitCalls": -1}, {"unitCalls": True}, {"unitCalls": (1 << 64)},
        {"serial": 0}, {"serial": (1 << 32)}, {"thread": 0}, {"thread": (1 << 32)},
        {"target": -1}, {"target": (1 << 31)}, {"version": 2}, {"stride": 32},
        {"slots": 127}, {"words": 1024}, {"stateSlots": 4096},
        {"metadataBytes": 1}, {"metadataBytes": 3 * 1024 * 1024 + 1},
        {"unitComplete": 10}, {"unitSelected": 121}, {"unitGroups": 4},
        {"unitSameIncarnation": 3}, {"unitParentAtMutation": 6}, {"unitMismatches": 6},
        {"unitZeroKeys": 9}, {"evictions": 4}, {"keyBytes": 1028},
        {"peakKeyBytes": 128 * 2048 * 4 + 4}, {"keyBytes": 1}, {"peakKeyBytes": 1023},
        {"note": "guaranteed_saved_time"},
    ]
    for update in invalid_cases:
        candidate = probe(**update)
        if update.get("unitCalls") is True:
            candidate["values"]["unitCalls"] = True  # parse service cannot synthesize a bool native value.
        check(bool(profile.decode(candidate)[1]), "invalid " + str(update))
    missing = probe()
    del missing["values"]["unitCalls"]
    check(bool(profile.decode(missing)[1]), "missing numeric field rejected")
    duplicate = probe()
    duplicate["raw_message"] += " unitCalls=120"
    check(any("duplicate_fields" in error for error in profile.decode(duplicate)[1]), "duplicate numeric field rejected")
    duplicate["raw_message"] = probe()["raw_message"] + " note=" + profile.WIRE_NOTE
    check(any("duplicate_fields" in error for error in profile.decode(duplicate)[1]), "duplicate semantics rejected")
    truncated = probe()
    truncated["raw_message"] += " [message truncated]"
    check("explicit_message_truncation" in profile.decode(truncated)[1], "explicit truncation rejected")

    warning_only = profile.decode(probe(unitScalarHits=7))[0]
    check("unit:key_visits_differ_from_scalar_counter_deltas" in warning_only["warnings"], "counter equality is warning not unjustified rejection")
    freq_zero = profile.decode(probe(frequency=0))[0]
    check(freq_zero is not None and freq_zero["kinds"]["unit"]["clocks"]["KernelTicks"]["observed_wall_ms"] is None, "frequency failure unknown")
    zero_tick = profile.decode(probe(unitKernelTicks=0))[0]
    check(zero_tick["kinds"]["unit"]["clocks"]["KernelTicks"]["observed_wall_ms"] is None, "zero ticks not zero work")
    no_keys = profile.decode(probe(unitKeyVisits=0, unitScalarHits=0, unitScalarMisses=0, unitPrepInsideTicks=0))[0]
    check(no_keys["kinds"]["unit"]["clocks"]["PrepInsideTicks"]["observed_wall_ms"] == 0, "no key visits no inside instrumentation")
    other = profile.decode(probe(serial=2, frequency=2000))[0]
    combined = profile.aggregate([row, other])
    check(combined["kinds"]["unit"]["timings"]["KernelTicks"]["known_completed_wall_ms"] == 300, "each row uses own frequency")
    check(combined["per_plan_max_bytes"]["keyBytes"] == 512, "snapshot bytes maxima not sums")
    check(combined["kinds"]["unit"]["counts"]["Calls"] == 240, "retained counts sum")
    check(profile.aggregate([])["kinds"]["unit"]["counts"]["Calls"] is None, "no rows counts unknown")
    check(not any("estimate" in key or "saved" in key for key in combined["kinds"]["unit"]), "no extrapolated output")

    plan = record("PLAN", dict(target="57:3", ms=10), tick=101, origin="synthetic:plan")
    perf = record("PLAN_PERF", dict(target="57:3", dangerHits=12), tick=100, origin="synthetic:perf")
    sequence = [perf, plan, packet(), probe(), sample()]
    result = profile.analyze(sequence, map_width=88)
    check(result["coverage"]["probe_sample_identity_matches"] == 1, "exact SAMPLE identity joined")
    check(result["plans"][0]["legacy_plan_association"]["status"] == "target_verified_adjacent_candidate", "legacy association remains candidate")
    check("skipped_exact_identity_footer" in result["plans"][0]["legacy_plan_association"], "one exact packet footer skipped")
    check("preceding_perf_candidate" in result["plans"][0]["legacy_plan_association"], "bounded PERF association retained")
    no_width = profile.analyze(sequence)
    check(no_width["plans"][0]["legacy_plan_association"]["status"] == "target_unverified_adjacent_candidate", "map width not inferred")
    check(profile.analyze([plan, probe(), sample()], map_width=88)["plans"][0]["legacy_plan_association"]["status"] == "target_verified_adjacent_candidate", "direct PLAN works")
    check(profile.analyze([plan, packet(serial=2), probe()], map_width=88)["plans"][0]["legacy_plan_association"]["status"] == "unmatched", "different footer never skipped")
    bad_footer = packet()
    bad_footer["values"]["cohortQueries"] = 1
    check(profile.analyze([plan, bad_footer, probe()])["plans"][0]["legacy_plan_association"]["status"] == "unmatched", "invalid footer never skipped")
    unrelated = record("COMBAT", dict(target=321), tick=102)
    check(profile.analyze([plan, unrelated, probe()], map_width=88)["plans"][0]["legacy_plan_association"]["status"] == "unmatched", "arbitrary intervening records not scanned")
    check(profile.analyze([plan, packet(), packet(), probe()])["plans"][0]["legacy_plan_association"]["status"] == "unmatched", "at most one footer skip")
    explicit = record("PLAN", dict(targetPlot=321, serial=1, thread=7), tick=101)
    check(profile.analyze([explicit, probe()])["plans"][0]["legacy_plan_association"]["status"] == "identity_and_target_verified", "explicit identity recognized")
    mismatch = record("PLAN", dict(targetPlot=322), tick=101)
    check(profile.analyze([mismatch, probe()])["plans"][0]["legacy_plan_association"]["status"] == "target_mismatch", "target mismatch rejected")

    dup_result = profile.analyze([probe(), probe(), sample()])
    check(dup_result["coverage"]["valid_probe_rows"] == 0 and dup_result["invalid_row_count"] == 2, "ambiguous probe identity all excluded")
    dup_sample = profile.analyze([probe(), sample(), sample()])
    check(dup_sample["coverage"]["probe_sample_identity_matches"] == 0 and dup_sample["invalid_row_count"] == 2, "ambiguous SAMPLE identity all excluded")
    bad_sample = sample()
    bad_sample["raw_message"] += " phase=0"
    check(profile.analyze([probe(), bad_sample])["invalid_row_count"] == 1, "duplicate SAMPLE configuration rejected")
    unmatched = profile.analyze([probe(), sample(serial=2)])
    check(unmatched["coverage"]["probes_without_sample"] == 1 and unmatched["coverage"]["samples_without_probe"] == 1, "missing exact joins explicit")
    empty = profile.analyze([])
    check(any("unknown, not zero" in message for message in empty["warnings"]), "empty result unknown")
    filtered = profile.analyze([probe(), sample()], turn=252)
    check(filtered["coverage"]["valid_probe_rows"] == 0, "turn filter exact")
    filtered = profile.analyze([probe(), sample()], player=2)
    check(filtered["coverage"]["valid_sample_rows"] == 0, "player filter exact")
    quality = dict(gaps=[[1, 1]], earlier_segments_missing=True, conflicting_segment_files=[1],
                   incomplete_tails_skipped=[1], malformed_records=1, clock_reversals=[1])
    cost = record("DIAGNOSTIC_COST", dict(dropped=1))
    drop = record("TRUNCATED", dict(rows=4096))
    censored = profile.analyze([probe(), sample(), cost, drop], quality)
    check(len(censored["warnings"]) == 4, "archive/drop censor warnings")
    check(len(censored["diagnostic_drop_rows"]) == 1, "drop evidence retained")
    check("whole outer enemy" in " ".join(profile.NOTES), "whole-ledger bias documented")
    check("PrepInsideTicks" in " ".join(profile.NOTES) and "Do not add" in " ".join(profile.NOTES), "timing overlap explicit")

    # Largest-width fields fit the existing message budget; not a valid count graph.
    max_values = {name: profile.MAX_U64 for name in profile.NUMERIC_FIELDS}
    max_values.update(profile.CONFIG, serial=(1 << 32) - 1, target=(1 << 31) - 1,
                      thread=(1 << 32) - 1, metadataBytes=3 * 1024 * 1024, note=profile.WIRE_NOTE)
    max_bytes = len(record("PLAN_KERNEL_PROBE", max_values)["raw_message"].encode("utf-8"))
    check(max_bytes < 3072, "maximum numeric row width below native message bound")

    # Canonical run/segment loader retains the largest prefix-copy, flags tails,
    # excludes other sessions and exposes the exact raw wire for validation.
    with tempfile.TemporaryDirectory(prefix="kernel-probe-reader-") as temporary:
        directory = Path(temporary)
        header = "STACKDIAG|SESSION|run=synthetic-kernel segment=0\n"
        body = "\n".join(item["raw_message"] for item in sequence) + "\n"
        (directory / "native.log").write_text(header + body, encoding="utf-8")
        (directory / "copy.log").write_text(header + body[:100], encoding="utf-8")
        (directory / "different.log").write_text(header.replace("synthetic-kernel", "different") + body, encoding="utf-8")
        (directory / "segment2.log").write_text(header.replace("segment=0", "segment=2") + record("COMBAT", dict(v=1))["raw_message"], encoding="utf-8")
        loaded, archive = profile.load(directory, "synthetic-kernel")
        check(len(loaded) == len(sequence), "canonical prefix-copy/session dedup")
        check(len(archive["duplicate_segment_files_ignored"]) == 1, "duplicate segment evidence")
        check(archive["gaps"] == [[1, 1]] and archive["incomplete_tails_skipped"], "partial archive recognized")
        loaded_report = profile.analyze(loaded, archive, map_width=88)
        check(loaded_report["coverage"]["probe_sample_identity_matches"] == 1, "loaded exact identity join")
        check(not loaded_report["invalid_rows"], "loaded valid wire decoded")
        check(any("archive has gaps" in message for message in loaded_report["warnings"]), "partial archive warning survives")
        check(loaded_report["plans"][0]["origin"].startswith("native.log:"), "origin uses retained canonical segment")

    output = ROOT / "kernel-probe-profile-regression" / "result.json"
    output.parent.mkdir(exist_ok=True)
    result = dict(checks=checks, failures=0, maximum_wire_bytes=max_bytes,
                  compiler_used=False, game_used=False, benchmark_used=False,
                  frozen_schema_source="work/destination-kernel-probe-fragment.cpp",
                  source_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (
                      ROOT / "profile-kernel-probes.py", ROOT / "test-kernel-probe-profile.py", ROOT / "destination-kernel-probe-fragment.cpp")},
                  notes="Synthetic parser checks only; no native opportunity or speed claim.")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(result=str(output), **result)))


if __name__ == "__main__":
    main()
