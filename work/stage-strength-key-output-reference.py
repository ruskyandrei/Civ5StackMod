"""Work-only direct output-reference strength-key stage; no compilation/game calls."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = "0511f8a4fbec6a9d2d5a961fd4223bffdd5efe94"
PATH = "CvGameCoreDLL_Expansion2/CvUnit.cpp"
OUT = ROOT / "work/strength-key-output-reference-staged"


def function(source, signature):
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def normalized(text):
    return text.replace("\r\n", "\n")


def generate():
    old = normalized(subprocess.check_output(["git", "show", BASE + ":" + PATH], cwd=ROOT).decode("utf-8-sig"))
    new = old
    changes = []

    def once(before, after):
        nonlocal new
        assert new.count(before) == 1
        new = new.replace(before, after, 1)
        changes.append((before, after))

    key = function(old, "static CvStackingStrengthCache::Key MakeStackStrengthKey(")
    assert key.count("\tCvStackingStrengthCache::Key key;\n") == 1
    assert key.count("\treturn key;\n") == 1
    filled = key.replace("static CvStackingStrengthCache::Key MakeStackStrengthKey(int kind,", "static void FillStackStrengthKey(CvStackingStrengthCache::Key& key, int kind,", 1)
    filled = filled.replace("\tCvStackingStrengthCache::Key key;\n", "", 1).replace("\treturn key;\n", "", 1)
    once(key, filled)

    wrappers = ("GetGenericMeleeStrengthModifier", "GetMaxRangedCombatStrength", "GetMaxAttackStrength", "GetMaxDefenseStrength")
    original_wrappers = {}
    for name in wrappers:
        wrapper = function(new, "int CvUnit::" + name + "(")
        original_wrappers[name] = wrapper
        const = "const " if name == "GetGenericMeleeStrengthModifier" else ""
        start = "\t" + const + "CvStackingStrengthCache::Key key = MakeStackStrengthKey("
        assert wrapper.count(start) == 1
        edited = wrapper.replace(start, "\tCvStackingStrengthCache::Key key;\n\tFillStackStrengthKey(key, ", 1)
        once(wrapper, edited)

    # Exactly the same getter assignments in the same order; all22 words remain.
    old_body = key[key.index("{") + 1:key.rindex("}")]
    new_body = filled[filled.index("{") + 1:filled.rindex("}")]
    assert new_body == old_body.replace("\n\tCvStackingStrengthCache::Key key;", "", 1).replace("\treturn key;\n", "", 1)
    assert new_body.count("key.values[") == old_body.count("key.values[") == 22
    assert "MakeStackStrengthKey" not in new

    unchanged = {}
    for name in wrappers:
        sig = "int CvUnit::" + name + "Uncached("
        body = function(old, sig)
        assert function(new, sig) == body
        unchanged[sig] = hashlib.sha256(body.encode()).hexdigest()
    for name in ("GetDamageCombatModifier", "GetEmbarkedUnitDefense"):
        sig = "int CvUnit::" + name + "("
        body = function(old, sig)
        assert function(new, sig) == body
        unchanged[sig] = hashlib.sha256(body.encode()).hexdigest()
    restored = new
    for before, after in reversed(changes):
        assert restored.count(after) == 1
        restored = restored.replace(after, before, 1)
    assert restored == old

    dependencies = {}
    for name in ("CvUnit.h", "CvStackingStrengthCache.h", "CvStackingStrengthCache.cpp", "CvTacticalAI.cpp", "CvStackingRules.h", "CvStackingRules.cpp", "CvStackingDiagnostics.h", "CvStackingDiagnostics.cpp"):
        path = "CvGameCoreDLL_Expansion2/" + name
        pinned = normalized(subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT).decode("utf-8-sig"))
        dependencies[name] = hashlib.sha256(pinned.encode()).hexdigest()
    proof = dict(control=BASE, original_sha256=hashlib.sha256(old.encode()).hexdigest(), candidate_sha256=hashlib.sha256(new.encode()).hexdigest(),
                 whole_reverse_exact=True, all22_assignments_same_order=True, unchanged_math_functions=unchanged, unchanged_dependencies=dependencies,
                 production_untouched=True, scope="Private static output-reference builder plus four local initializer callsites only; no Context/cache/math/flags/getter sequence/budget/ABI/save changes; native ROI unknown.")
    return old, new, proof


if __name__ == "__main__":
    old, new, proof = generate()
    OUT.mkdir(exist_ok=True)
    (OUT / "control.cpp").write_text(old, encoding="utf-8")
    (OUT / "CvUnit.cpp").write_text(new, encoding="utf-8")
    (OUT / "key-output-reference.patch").write_text("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile="a/" + PATH, tofile="b/" + PATH)), encoding="utf-8")
    (OUT / "manifest.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof))
