"""Lightweight synthetic validation of the offline native PLAN_SAMPLE parser."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sample_profile", root / "work/profile-plan-samples.py")
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)
checks = 0


def expect(label, condition):
    global checks
    checks += 1
    if not condition:
        raise AssertionError(label)


def sample(serial=1, thread=80, tick=1020, frequency=1000000, calls=None, target=2225):
    calls = list(calls if calls is not None else [8192]*len(profile.PARTS))
    phase = (target*1664525+1013904223) & 4095
    selected = [(count+((phase+index*97) & 4095))//4096 for index, count in enumerate(calls)]
    ticks = [count*500 for count in selected]
    value = dict(targetPlot=target, serial=serial, thread=thread, stride=4096, phase=phase,
        qpcFrequency=frequency, qpcFrequencyCalls=1, qpcReads=2*sum(selected), clockFailures=0,
        parts=",".join(profile.PARTS), semantics=profile.SEMANTICS)
    for key, array in zip(profile.ARRAYS, (calls, selected, selected, ticks, [500 if count else 0 for count in selected])):
        value[key] = ",".join(map(str, array))
    return dict(raw_tick=tick, tick=tick, turn=252, player=3, category="PLAN_SAMPLE", values=value, origin=f"synthetic-{serial}-{thread}")


def row(category="PLAN", tick=1010, player=3, turn=252, **fields):
    return dict(raw_tick=tick, tick=tick, turn=turn, player=player, category=category, values=fields, origin=f"{category}-{tick}")


def replace_array(record, key, index, value):
    array = record["values"][key].split(",")
    array[index] = str(value)
    record["values"][key] = ",".join(array)


def rejected(label, mutate, expected):
    record = sample()
    mutate(record)
    result, errors = profile.decode(record)
    expect(label, result is None and any(expected in error for error in errors))


actual, errors = profile.decode(sample())
expect("frozen schema valid", actual is not None and not errors)
expect("all thirteen fixed parts decoded", tuple(part["part"] for part in actual["parts"]) == profile.PARTS)
expect("known sample conversion", actual["parts"][0]["sampled_wall_ms"] == 1.0)
expect("maximum sample conversion", actual["parts"][0]["maximum_sample_wall_ms"] == .5)
expect("explicit approximate extrapolation", actual["parts"][0]["estimated_total_ms"] == 4096.0)
expect("sampling coverage", actual["parts"][0]["sampling_fraction"] == 2/8192)
expect("low-sample caution", actual["parts"][0]["warnings"])

rejected("short calls array", lambda r: r["values"].update(calls="1,2"), "invalid_array_length")
rejected("long part array", lambda r: r["values"].update(parts=r["values"]["parts"]+",other"), "part_order")
rejected("reordered parts", lambda r: r["values"].update(parts=",".join(reversed(profile.PARTS))), "part_order")
rejected("missing array", lambda r: r["values"].pop("maxTicks"), "missing_or_non_csv")
rejected("zero frequency", lambda r: r["values"].update(qpcFrequency=0), "invalid_qpc_frequency")
rejected("missing frequency", lambda r: r["values"].pop("qpcFrequency"), "qpcFrequency:")
rejected("QPF called twice", lambda r: r["values"].update(qpcFrequencyCalls=2), "frequency_call_count")
rejected("unsupported stride", lambda r: r["values"].update(stride=2048), "unsupported_stride")
rejected("phase outside stride", lambda r: r["values"].update(phase=4096), "invalid_phase")
rejected("zero thread", lambda r: r["values"].update(thread=0), "zero_serial_or_thread")
rejected("zero serial", lambda r: r["values"].update(serial=0), "zero_serial_or_thread")
rejected("negative target", lambda r: r["values"].update(targetPlot=-1), "targetPlot:")
rejected("negative array item", lambda r: replace_array(r,"ticks",0,-1), "non_unsigned")
rejected("overflow array item", lambda r: replace_array(r,"ticks",0,1 << 64), "integer_overflow")
rejected("overflow clock scalar", lambda r: r["values"].update(qpcReads=1 << 64), "qpcReads:")
rejected("bad array integer", lambda r: replace_array(r,"samples",0,"NaN"), "non_unsigned")
rejected("completed exceeds selected", lambda r: replace_array(r,"samples",0,3), "counts_out_of_order")
rejected("selected mismatches frozen schedule", lambda r: replace_array(r,"selected",0,1), "stride_schedule")
rejected("maximum exceeds sum", lambda r: replace_array(r,"maxTicks",0,1001), "tick_totals")
rejected("ticks without completed samples", lambda r: replace_array(r,"samples",0,0), "tick_totals")
rejected("too few QPC reads", lambda r: r["values"].update(qpcReads=1), "qpc_reads_disagree")
rejected("too many QPC reads", lambda r: r["values"].update(qpcReads=1000), "qpc_reads_disagree")
rejected("too many failures", lambda r: r["values"].update(clockFailures=1), "failures_exceed")
rejected("wrong semantics", lambda r: r["values"].update(semantics="CPU"), "semantics")
rejected("explicit native message truncation", lambda r: r.update(raw_message="[message truncated]"), "explicit_message_truncation")

zero = sample(calls=[0]*13)
decoded, errors = profile.decode(zero)
expect("uncalled parts exactly zero but have no max sample", not errors and decoded["parts"][0]["estimated_total_ms"] == 0 and decoded["parts"][0]["maximum_sample_wall_ms"] is None)
missing = sample(calls=[1]*13)
decoded, errors = profile.decode(missing)
expect("called below stride unknown", not errors and decoded["parts"][0]["estimated_total_ms"] is None)
expect("unknown cannot appear as zero total", profile.analyze([missing])["whole_selection_parts"][0]["estimated_total_all_plans_ms"] is None)
omitted = sample()
replace_array(omitted,"samples",0,0)
replace_array(omitted,"ticks",0,0)
replace_array(omitted,"maxTicks",0,0)
omitted["values"]["qpcReads"] -= 2
decoded, errors = profile.decode(omitted)
expect("scope omissions need not be clock failures", not errors and decoded["parts"][0]["estimated_total_ms"] is None and decoded["clockFailures"] == 0)
expect("scope omission noted", decoded["warnings"])
failed = deepcopy(omitted)
failed["values"]["clockFailures"] = 2
decoded, errors = profile.decode(failed)
expect("failed entry scopes recognized", not errors and decoded["clockFailures"] == 2)
zero_ticks = sample()
replace_array(zero_ticks,"ticks",0,0)
replace_array(zero_ticks,"maxTicks",0,0)
decoded, errors = profile.decode(zero_ticks)
expect("sub-resolution completed samples accepted with caution", not errors and any("zero ticks" in warning for warning in decoded["parts"][0]["warnings"]))

plan = row(target="25:25", milliseconds=9000, states=5000)
perf = row("PLAN_PERF", 1009, target="25:25", searchMs=9000)
result = profile.analyze([perf,plan,sample()], map_width=88)
association = result["plans"][0]["plan_association"]
expect("coordinates verified but identity remains candidate", association["status"] == "target_verified_adjacent_candidate")
expect("adjacent perf candidate retained", association["preceding_perf_candidate"]["fields"]["searchMs"] == 9000)
expect("without map width target unverified", profile.analyze([plan,sample()])["plans"][0]["plan_association"]["status"] == "target_unverified_adjacent_candidate")
expect("mismatched coordinate rejected", profile.analyze([plan,sample()], map_width=90)["plans"][0]["plan_association"]["status"] == "target_mismatch")
explicit = row(targetPlot=2225, serial=1, thread=80)
expect("future explicit identity safely verified", profile.analyze([explicit,sample()])["plans"][0]["plan_association"]["status"] == "identity_and_target_verified")
explicit["values"]["serial"] = 2
expect("different serial is not a shared search", profile.analyze([explicit,sample()])["plans"][0]["plan_association"]["status"] == "identity_mismatch")
expect("intervening unrelated record does not borrow stale PLAN", profile.analyze([plan,row("TURN_PHASE"),sample()], map_width=88)["plans"][0]["plan_association"]["status"] == "unmatched")
expect("different player not matched", profile.analyze([row(player=2,target="25:25"),sample()],map_width=88)["plans"][0]["plan_association"]["status"] == "unmatched")
expect("different turn not matched", profile.analyze([row(turn=251,target="25:25"),sample()],map_width=88)["plans"][0]["plan_association"]["status"] == "unmatched")

result = profile.analyze([sample(),sample(serial=2,frequency=2000000)])
expect("frequencies converted per row", result["whole_selection_parts"][0]["sampled_wall_ms"] == 1.5)
expect("per-plan estimates summed only for same part", result["whole_selection_parts"][0]["estimated_total_all_plans_ms"] == 6144.0)
expect("no combined all-parts total", "total_estimated_ms" not in result and "total_estimated_ms" not in result["turn_player_target_groups"][0])
unknown = sample(serial=2,calls=[1]*13)
result = profile.analyze([sample(),unknown])
expect("mixed known unknown keeps known estimate only", result["whole_selection_parts"][0]["approximate_estimate_known_plans_ms"] == 4096.0)
expect("mixed known unknown no full estimate", result["whole_selection_parts"][0]["estimated_total_all_plans_ms"] is None)
expect("unknown coverage explicit", result["whole_selection_parts"][0]["unknown_cost_plans"] == 1 and result["whole_selection_parts"][0]["unknown_cost_calls"] == 1)
result = profile.analyze([sample(),sample()])
expect("same identity duplicates all excluded", result["valid_sample_rows"] == 0 and result["invalid_sample_rows"] == 2)
result = profile.analyze([sample(),sample(thread=81)])
expect("same serial on distinct threads valid", result["valid_sample_rows"] == 2)
different = sample(serial=2)
different["turn"] = 253
different["player"] = 7
expect("turn player filtering exact", profile.analyze([sample(),different],turn=252,player=3)["valid_sample_rows"] == 1)
expect("empty valid selection explicit", profile.analyze([sample()],turn=251)["valid_sample_rows"] == 0)
expect("notes distinguish wall CPU and overlap", any("not CPU" in text for text in profile.NOTES) and any("Do not sum" in text for text in profile.NOTES))


def native_line(record):
    values = " ".join(f"{key}={value}" for key,value in record["values"].items())
    return f"STACKDIAG|{record['raw_tick']}|turn={record['turn']}|player={record['player']}|{record['category']}|{values}\n"


with tempfile.TemporaryDirectory(prefix="plan-sample-fixture-", dir=root/"work") as temporary:
    directory = Path(temporary)
    header = "STACKDIAG|SESSION|run=fixture-native segment=0\n"
    text = header+native_line(plan)+native_line(sample())
    (directory/"segment.log").write_text(text,encoding="utf-8")
    (directory/"rolling.log").write_text(text,encoding="utf-8")
    (directory/"other-run.log").write_text(text.replace("run=fixture-native","run=other"),encoding="utf-8")
    records,quality = profile.load(directory,"fixture-native")
    result = profile.analyze(records,quality,map_width=88)
    expect("canonical segment aliases counted once", result["valid_sample_rows"] == 1 and len(quality["duplicate_segment_files_ignored"]) == 1)
    expect("other run excluded", len(quality["headers"]) == 1)
    (directory/"rolling.log").write_text(text[:-50],encoding="utf-8")
    records,quality = profile.load(directory,"fixture-native")
    expect("partial prefix copy ignored safely", len(records) == 2 and not quality["conflicting_segment_files"])
    (directory/"segment1.log").write_text("STACKDIAG|SESSION|run=fixture-native segment=1\n"+native_line(sample(serial=2))[:-30],encoding="utf-8")
    records,quality = profile.load(directory,"fixture-native")
    expect("incomplete native row skipped", len(quality["incomplete_tails_skipped"]) == 1)
    expect("partial archive warning", profile.analyze(records,quality)["warnings"])
    (directory/"segment2.log").write_text("STACKDIAG|SESSION|run=fixture-native segment=2\n"+native_line(sample(serial=3)).rstrip("\n")+" [message truncated]\n",encoding="utf-8")
    records,quality = profile.load(directory,"fixture-native")
    expect("complete but explicitly truncated native row rejected", profile.analyze(records,quality)["invalid_sample_rows"] == 1)
    (directory/"rolling.log").write_text(text.replace("milliseconds=9000","milliseconds=8000"),encoding="utf-8")
    records,quality = profile.load(directory,"fixture-native")
    expect("conflicting duplicate segment warned", quality["conflicting_segment_files"] and any("Conflicting copies" in warning for warning in profile.analyze(records,quality)["warnings"]))

report = dict(checks=checks,failures=0,scope="Synthetic fixed-schema parsing, sample coverage/approximation, qualified PLAN matching, canonical duplicate segments, incomplete/truncated records and filters; no native build or game action.")
(root/"work/plan-sample-profile-fixture-result.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report))
