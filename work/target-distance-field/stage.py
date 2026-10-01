"""Emit a diagnostic-only distance-field timing patch; never edit core files."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CONTROL = "e38b19798"
CPP = "CvGameCoreDLL_Expansion2/CvTacticalAI.cpp"
READER = "work/profile-turn-phases.py"
SIGNATURE = "void TacticalAIHelpers::UpdatePlotDistanceToTarget(PlayerTypes ePlayer, CvPlot* pTargetPlot)"
LINE = '\tCvStackingDiagnostics::TurnPhaseScope phase(ePlayer,"target_distance_fields"); // TARGET_DISTANCE_FIELD_TIMING_DIAGNOSTIC_ONLY\n'
OLD_FAMILY = 'name in ("immediate_city_opportunities", "stacking_offensive_moves")'
NEW_FAMILY = 'name in ("immediate_city_opportunities", "stacking_offensive_moves", "target_distance_fields")'
CONTROLS = [CPP, READER, "CvGameCoreDLL_Expansion2/CvStackingDiagnostics.cpp", "CvGameCoreDLL_Expansion2/CvStackingDiagnostics.h",
            "CvGameCoreDLL_Expansion2/CvAStar.cpp", "CvGameCoreDLL_Expansion2/CvAStar.h", "CvGameCoreDLL_Expansion2/CvPlot.cpp",
            "CvGameCoreDLL_Expansion2/CvPlayer.cpp", "CvGameCoreDLL_Expansion2/CvTeam.cpp"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def extract(text, signature=SIGNATURE):
    start = text.index(signature)
    opening = text.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def transform(text):
    assert "TARGET_DISTANCE_FIELD_TIMING_DIAGNOSTIC_ONLY" not in text
    body = extract(text)
    assert body.count("GetPlotsInReach(") == 2
    opening = text.index("{", text.index(SIGNATURE))
    assert text[opening:opening + 2] == "{\n"
    return text[:opening + 2] + LINE + text[opening + 2:]


def normalized(data):
    return data.decode("utf-8-sig").replace("\r\n", "\n")


def encode_like(text, original):
    bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
    if b"\r\n" in original:
        text = text.replace("\n", "\r\n")
    return bom + text.encode("utf-8")


def pinned(path):
    return subprocess.check_output(["git", "show", f"{CONTROL}:{path}"], cwd=ROOT)


def prepare(production=False):
    # Even production mode derives the complete expected candidate from pinned
    # DLL93; it never treats the mutable live candidate as its own oracle.
    control = pinned(CPP)
    current = (ROOT / CPP).read_bytes()
    old = normalized(control)
    new = transform(old)
    assert new.replace(LINE, "", 1) == old
    assert extract(new).replace(LINE, "", 1) == extract(old)
    reader_bytes = (ROOT / READER).read_bytes()
    reader = normalized(pinned(READER))
    assert reader.count(OLD_FAMILY) == 1
    staged_reader = reader.replace(OLD_FAMILY, NEW_FAMILY, 1)
    assert staged_reader.replace(NEW_FAMILY, OLD_FAMILY, 1) == reader
    expected = {CPP: new if production else old, READER: staged_reader if production else reader}
    raw_controls, pinned_hashes = {}, {}
    for path in CONTROLS:
        baseline = pinned(path)
        actual = (ROOT / path).read_bytes()
        assert normalized(actual) == expected.get(path, normalized(baseline)), "whole-file control/candidate drift: " + path
        raw_controls[path] = sha(actual)
        pinned_hashes[path] = sha(normalized(baseline).encode("utf-8"))
    candidate_bytes = encode_like(new, current)
    line_bytes = LINE.replace("\n", "\r\n").encode("utf-8") if b"\r\n" in current else LINE.encode("utf-8")
    baseline_bytes = encode_like(old, current)
    assert candidate_bytes.replace(line_bytes, b"", 1) == baseline_bytes
    assert current == (candidate_bytes if production else baseline_bytes), "unexpected Tactical BOM/EOL or bytes"
    (OUT / "CvTacticalAI.cpp").write_bytes(candidate_bytes)
    (OUT / "profile-turn-phases.py").write_bytes(encode_like(staged_reader, reader_bytes))
    patch = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile="a/" + CPP, tofile="b/" + CPP))
    patch += "".join(difflib.unified_diff(reader.splitlines(True), staged_reader.splitlines(True), fromfile="a/" + READER, tofile="b/" + READER))
    (OUT / "measurement.patch").write_text(patch, encoding="utf-8", newline="\n")
    proof = dict(controlCommit=CONTROL, sourceHEAD=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                 controlSHA256=sha(control), currentSHA256=sha(current), candidateSHA256=sha((OUT / "CvTacticalAI.cpp").read_bytes()),
                 candidateNormalizedSHA256=sha(new.encode("utf-8")), readerCandidateNormalizedSHA256=sha(staged_reader.encode("utf-8")),
                 fullSourceReverseExact=True, fullSourceReverseBytesExact=True, functionReverseExact=True, existingFloodCalls=2, addedTimerScopes=1,
                 coreMutated=False, productionBound=production, controls=raw_controls, pinnedNormalizedDependencyHashes=pinned_hashes)
    target = "production-source-proof.json" if production else "source-proof.json"
    (OUT / target).write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", action="store_true", help="Validate the complete live timer candidate against pinned DLL93, then emit proof only in this work folder.")
    args = parser.parse_args()
    proof = prepare(args.production)
    print(json.dumps({k: v for k, v in proof.items() if k != "controls"}))


if __name__ == "__main__":
    main()
