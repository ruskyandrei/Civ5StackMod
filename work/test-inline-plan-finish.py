"""Actual-source VC9 sampled scope lifecycle checks, staged or adopted."""
from pathlib import Path
import argparse, hashlib, json, subprocess

root=Path(__file__).resolve().parents[1]
args=argparse.ArgumentParser(description=__doc__)
args.add_argument('--production',action='store_true')
opts=args.parse_args()
stage=root/'work/inline-plan-finish-staged'
proof=json.loads((stage/'staging-proof.json').read_text())
candidate_root=root/'CvGameCoreDLL_Expansion2' if opts.production else stage
for name, hashes in proof['files'].items():
    original=subprocess.check_output(['git','show',proof['control']+':CvGameCoreDLL_Expansion2/'+name],cwd=root).decode('utf-8-sig')
    actual=(candidate_root/name).read_text(encoding='utf-8-sig')
    assert hashlib.sha256(original.encode()).hexdigest()==hashes['originalSHA256'],name
    assert hashlib.sha256(actual.encode()).hexdigest()==hashes['candidateSHA256'],name

# Reuse the existing meaningful sampler lifecycle/cadence fixture. Extract
# exactly the current candidate bodies, including inline header gates; preserve
# its deterministic clock, nested/foreign thread, unwind and duplicate-finish
# assertions. This runner never touches live game state or source files.
script=(root/'work/test-plan-sample-cadence.py').read_text(encoding='utf-8-sig')
before="staged=root/'work/plan-sample-cadence-staged'"
assert script.count(before)==1
script=script.replace(before,"staged=Path(CANDIDATE_ROOT)",1)
script=script.replace("out=root/'work/plan-sample-cadence-regression'","out=root/'work/inline-plan-finish-regression'",1)
before="sources={name:(root/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8') for name in ('CvStackingDiagnostics.cpp','CvStackingDiagnostics.h')}"
assert script.count(before)==1
script=script.replace(before,"sources={name:(staged/name).read_text(encoding='utf-8') for name in ('CvStackingDiagnostics.cpp','CvStackingDiagnostics.h')}",1)
script=script.replace('current production sampler exact reviewed frozen60 proposal','actual staged/adopted inline finish candidate; current cadence and lifecycle')
exec(compile(script,'tracked actual cadence fixture with inline finish source','exec'),{'__file__':str(root/'work/test-inline-plan-finish.py'),'__name__':'__main__','CANDIDATE_ROOT':str(candidate_root)})
