"""Light, source-bound checks for the staged timing delta; no C++ compilation."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("distance_stage", HERE / "stage.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
checks = 0


def check(value, label):
    global checks
    checks += 1
    assert value, label


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", action="store_true", help="Bind all nine live files against the exact DLL93 plus timer candidate before running checks.")
    args = parser.parse_args()
    proof = stage.prepare(args.production)
    for path, digest in proof["controls"].items():
        check(stage.sha((stage.ROOT / path).read_bytes()) == digest, "control drift: " + path)
    current = stage.normalized(stage.pinned(stage.CPP))
    candidate_path = stage.ROOT / stage.CPP if args.production else HERE / "CvTacticalAI.cpp"
    candidate = stage.normalized(candidate_path.read_bytes())
    check(candidate.count(stage.LINE) == 1, "one combined timer")
    check(candidate.replace(stage.LINE, "", 1) == current, "complete source reversal")
    original_bytes = stage.encode_like(current, (stage.ROOT / stage.CPP).read_bytes())
    line_bytes = stage.LINE.replace("\n", "\r\n").encode("utf-8") if b"\r\n" in original_bytes else stage.LINE.encode("utf-8")
    check(candidate_path.read_bytes().replace(line_bytes, b"", 1) == original_bytes, "byte-exact source reversal including BOM/EOL")
    body = stage.extract(candidate)
    check(body.replace(stage.LINE, "", 1) == stage.extract(current), "unchanged full helper body")
    check(body.index(stage.LINE) < body.index("gDistanceToTargetPlots.clear()"), "start before both floods/preparation")
    check(body.count("GetPlotsInReach(") == 2 and body.index("PT_LAND_UNIT_SIMPLE") < body.index("PT_NAVAL_UNIT_SIMPLE"), "both original floods/order")
    check(body.rstrip().endswith("gTargetPlot = pTargetPlot;\n}"), "scope includes original completion/copy")
    check(candidate.count("TurnPhaseScope") == current.count("TurnPhaseScope") + 1, "one emitter callsite only")
    diag = stage.normalized((stage.ROOT / "CvGameCoreDLL_Expansion2/CvStackingDiagnostics.cpp").read_bytes())
    constructor = stage.extract(diag, "TurnPhaseScope::TurnPhaseScope(PlayerTypes player,const char* phase)")
    finish = stage.extract(diag, "void TurnPhaseScope::Finish()")
    record = stage.extract(diag, "void Record(int required, PlayerTypes player, const char* category, const char* format, ...)")
    for needle in ['categoryEnabledUnlocked(1,player,"TURN_PHASE")', 'DiagnosticsPerformanceInterval', 'turn%interval', 'GetCurrentThreadId()', 'threadCPU100ns']:
        check(needle in constructor, "existing scope gate: " + needle)
    check('Record(1,actor,"TURN_PHASE"' in finish and 'semantics=inclusive' in finish, "existing Summary inclusive emitter")
    check('DiagnosticsMaxRowsPerTurn' in record and '++costs.dropped' in record, "existing hard row budget/drop evidence")
    check('turn!=GC.getGame().getGameTurn()' in finish and 'generation!=phaseGeneration' in finish, "reset/turn invalidation preserved")
    reader_path = stage.ROOT / stage.READER if args.production else HERE / "profile-turn-phases.py"
    rs = importlib.util.spec_from_file_location("distance_reader", reader_path)
    reader = importlib.util.module_from_spec(rs); rs.loader.exec_module(reader)
    check(reader.family("target_distance_fields") == "tactical_scopes", "new family explicit")
    old_reader = stage.normalized(stage.pinned(stage.READER))
    check(stage.normalized(reader_path.read_bytes()).replace(stage.NEW_FAMILY, stage.OLD_FAMILY, 1) == old_reader, "reader delta one classification only")
    def row(tick, turn=7, category="CITY_DEFENSE", **values):
        return dict(raw_tick=tick, tick=tick, turn=turn, player=0, category=category, values=values, origin="synthetic")
    rows = [row(0), row(10, category="TURN_PHASE", phase="target_distance_fields", startTick=0, endTick=10, elapsedMs=10, thread=1, semantics="inclusive"),
            row(50, category="PLAN_PERF", target="x", finalizeMs=0, searchMs=25), row(50, category="PLAN", target="x", milliseconds=25),
            row(70, category="TURN_PHASE", phase="tactical_operations", startTick=0, endTick=70, elapsedMs=70, thread=1, semantics="inclusive"), row(100, turn=8)]
    result = reader.analyze(rows, 7)
    check(result["coverage"]["phase_union_ms"] == 70, "nested combined interval not added twice")
    check(result["coverage"]["estimated_PLAN_union_ms"] == 25, "PLAN timing unchanged")
    check(result["native_round_window"]["duration_ms"] == 100, "phase metadata cannot move legacy anchors")
    phase = next(p for p in result["players"][0]["phases"] if p["phase"] == "target_distance_fields")
    check(phase["outside_estimated_PLAN_ms"] == 10, "pre-PLAN field span reported directly")
    check(not re.search(r'\b(?:Sleep|SetLevel|SetTacticalSamplingEnabled)\(', body), "no new scheduling/diagnostic controls")
    output = dict(checks=checks, failures=0, kind="light source-binding/reversal/existing gates/budget/inclusive parser checks", cppCompiled=False,
                  productionBound=args.production, controlCommit=stage.CONTROL, sourceHEAD=proof["sourceHEAD"],
                  candidateSHA256=proof["currentSHA256"] if args.production else proof["candidateSHA256"],
                  candidateNormalizedSHA256=proof["candidateNormalizedSHA256"], readerCandidateNormalizedSHA256=proof["readerCandidateNormalizedSHA256"])
    (HERE / ("production-test-result.json" if args.production else "test-result.json")).write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
