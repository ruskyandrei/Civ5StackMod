"""Stage only sampled-scope finish gates; never modify production files."""
from pathlib import Path
import difflib, hashlib, json, subprocess

root=Path(__file__).resolve().parents[1]
stage=root/'work/inline-plan-finish-staged'
stage.mkdir(exist_ok=True)
control='cf8f842e2733841255a1d5bc741e4d95a387299b'
names=('CvStackingDiagnostics.h','CvStackingDiagnostics.cpp')
proof={'control':control,'files':{}}
patch=[]
for name in names:
    path='CvGameCoreDLL_Expansion2/'+name
    original=subprocess.check_output(['git','show',control+':'+path],cwd=root).decode('utf-8-sig')
    candidate=original
    if name.endswith('.h'):
        before='        ~PlanSampleScope();\n        void Finish();'
        after='        ~PlanSampleScope() { Finish(); }\n        void Finish() { if (sampled) FinishSampled(); }'
        assert candidate.count(before)==1
        candidate=candidate.replace(before,after,1)
        before='        PlanSampleScope& operator=(const PlanSampleScope&);\n        bool sampled;'
        after='        PlanSampleScope& operator=(const PlanSampleScope&);\n        void FinishSampled();\n        bool sampled;'
        assert candidate.count(before)==1
        candidate=candidate.replace(before,after,1)
    else:
        before='    PlanSampleScope::~PlanSampleScope() { Finish(); }\n    void PlanSampleScope::Finish()'
        after='    void PlanSampleScope::FinishSampled()'
        assert candidate.count(before)==1
        candidate=candidate.replace(before,after,1)
    (stage/('control-'+name)).write_text(original,encoding='utf-8',newline='\n')
    (stage/name).write_text(candidate,encoding='utf-8',newline='\n')
    proof['files'][name]={'originalSHA256':hashlib.sha256(original.encode()).hexdigest(),
                         'candidateSHA256':hashlib.sha256(candidate.encode()).hexdigest()}
    patch.extend(difflib.unified_diff(original.splitlines(keepends=True),candidate.splitlines(keepends=True),fromfile='a/'+path,tofile='b/'+path))
(stage/'inline-finish.patch').write_text(''.join(patch),encoding='utf-8',newline='\n')
(stage/'staging-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof))
