"""Stage a diagnostics-only cadence patch from frozen DLL60; never apply it."""
from __future__ import annotations
import ast
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "work/plan-sample-cadence-staged"
out.mkdir(exist_ok=True)
control = "688798c3b"
names = ["CvStackingDiagnostics.cpp", "CvStackingDiagnostics.h"]
sources = {name: subprocess.check_output(["git","show",f"{control}:CvGameCoreDLL_Expansion2/{name}"],cwd=root).decode("utf-8-sig") for name in names}
original = dict(sources)
source = sources[names[0]]


def change(before, after):
    global source
    assert source.count(before) == 1, before[:120]
    source = source.replace(before,after)


change("    const unsigned long PLAN_SAMPLE_STRIDE = 4096;\n",
    "    const unsigned long PLAN_SAMPLE_STRIDE = 4096;\n"
    "    // Sparse expensive parents need denser samples; dense leaf/key/math probes\n"
    "    // retain their existing cadence. These values only affect diagnostics.\n"
    "    const unsigned long PLAN_SAMPLE_STRIDES[CvStackingDiagnostics::PLAN_SAMPLE_PARTS] =\n"
    "        {4096,4096,4096,4096,4096,256,256,4096,64,4096,4096,4096,4096};\n")
change("        planSamples.phase=((unsigned long)targetPlotIndex*1664525UL+1013904223UL)&(PLAN_SAMPLE_STRIDE-1);",
    "        // Rotate repeated targets by the outer TLS serial, without gameplay RNG.\n"
    "        planSamples.phase=((unsigned long)targetPlotIndex*1664525UL+serial*2246822519UL+1013904223UL)&(PLAN_SAMPLE_STRIDE-1);")
change('        char calls[384]="",selected[384]="",samples[384]="",ticks[384]="",maximum[384]="";\n        size_t a=0,b=0,c=0,d=0,e=0;',
    '        char calls[384]="",selected[384]="",samples[384]="",ticks[384]="",maximum[384]="",strides[96]="",phases[96]="";\n        size_t a=0,b=0,c=0,d=0,e=0,f=0,g=0;')
change('            const PlanSampleCounter& part=planSamples.counter[i];\n',
    '            const PlanSampleCounter& part=planSamples.counter[i];\n'
    '            const unsigned long stride=PLAN_SAMPLE_STRIDES[i];\n'
    '            const unsigned long phase=(planSamples.phase+(unsigned long)i*97UL)&(stride-1);\n'
    '            f+=sprintf_s(strides+f,sizeof(strides)-f,"%s%lu",i?",":"",stride);\n'
    '            g+=sprintf_s(phases+g,sizeof(phases)-g,"%s%lu",i?",":"",phase);\n')
change('stride=%lu phase=%lu qpcFrequency=', 'stride=%lu phase=%lu cadenceVersion=2 strides=%s phases=%s qpcFrequency=')
change('planSamples.target,serial,planSamples.thread,PLAN_SAMPLE_STRIDE,planSamples.phase,planSamples.frequency,',
    'planSamples.target,serial,planSamples.thread,PLAN_SAMPLE_STRIDE,planSamples.phase,strides,phases,planSamples.frequency,')
change('        const unsigned long phase=(planSamples.phase+(unsigned long)value*97UL)&(PLAN_SAMPLE_STRIDE-1);\n        if((count.calls+phase)&(PLAN_SAMPLE_STRIDE-1)) return;',
    '        const unsigned long stride=PLAN_SAMPLE_STRIDES[value];\n'
    '        const unsigned long phase=(planSamples.phase+(unsigned long)value*97UL)&(stride-1);\n'
    '        if((count.calls+phase)&(stride-1)) return;')
sources[names[0]] = source
sources[names[1]] = sources[names[1]].replace('    // Sparse inclusive wall-time samples inside one owned tactical search.\n',
    '    // Inclusive wall samples: sparse parents use denser cadence; each row\n'
    '    // records its per-part strides/phases. Timing overhead is included.\n')

# The disabled scope prefix and all code outside the two sampler implementation
# blocks remain identical. No default setting, callback or gameplay body changes.
def sampler_blocks(text):
    return re.findall(r'^    // BEGIN PLAN_SAMPLE_DIAGNOSTIC_ONLY\n(.*?)^    // END PLAN_SAMPLE_DIAGNOSTIC_ONLY\n',text,re.M|re.S)
def outside(text):
    return re.sub(r'^    // BEGIN PLAN_SAMPLE_DIAGNOSTIC_ONLY\n.*?^    // END PLAN_SAMPLE_DIAGNOSTIC_ONLY\n','',text,flags=re.M|re.S)
for name in names:
    assert outside(original[name]) == outside(sources[name]), name
scope_sig='    PlanSampleScope::PlanSampleScope('
prefix_end='        const unsigned long phase='
old_prefix=original[names[0]][original[names[0]].index(scope_sig):].split(prefix_end,1)[0]
new_prefix=source[source.index(scope_sig):].split('        const unsigned long stride=',1)[0]
assert old_prefix == new_prefix
patch=''.join(''.join(difflib.unified_diff(original[name].splitlines(keepends=True),sources[name].splitlines(keepends=True),
    fromfile='a/CvGameCoreDLL_Expansion2/'+name,tofile='b/CvGameCoreDLL_Expansion2/'+name)) for name in names)
(out/'cadence.patch').write_text(patch,encoding='utf-8',newline='\n')
for name,text in sources.items():
    (out/name).write_text(text,encoding='utf-8',newline='\n')
proof=dict(control=control,production_applied=False,files={name:dict(original_sha256=hashlib.sha256(original[name].encode()).hexdigest(),
    staged_sha256=hashlib.sha256(sources[name].encode()).hexdigest(),outside_sampler_blocks_identical=True) for name in names},
    disabled_scope_prefix_identical=True,per_part_strides=[4096,4096,4096,4096,4096,256,256,4096,64,4096,4096,4096,4096],
    phase_formula='(targetPlot*1664525 + outerTLSserial*2246822519 + 1013904223 + partIndex*97) & (partStride-1); ULONG32 arithmetic',
    no_gameplay_rng=True,estimated_row_increase='Two bounded13-element metadata CSV arrays plus cadenceVersion=2')
(out/'staging-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')

# A separate work-copy parser supports both original v1 and explicit v2 cadence.
# The live/committed parser is deliberately not replaced by this preparation.
parser=(root/'work/profile-plan-samples.py').read_text(encoding='utf-8')
parser=parser.replace('STRIDE = 4096\n','STRIDE = 4096\nCADENCE_STRIDES = (4096,4096,4096,4096,4096,256,256,4096,64,4096,4096,4096,4096)\n',1)
before='''    for index, name in enumerate(PARTS):
        calls, selected, samples, ticks, maximum = (arrays[key][index] for key in ARRAYS)
        phase = (value["phase"]+index*97) & (STRIDE-1)
        expected_selected = (calls+phase)//STRIDE'''
after='''    cadence = value.get("cadenceVersion", 1)
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
        expected_selected = (calls+phase)//stride'''
assert parser.count(before)==1
parser=parser.replace(before,after)
parser=parser.replace('parts.append(dict(part=name, calls=calls, selected=chosen, samples=samples,','parts.append(dict(part=name, stride=strides[index], phase=phases[index], calls=calls, selected=chosen, samples=samples,',1)
parser=parser.replace('serial=value["serial"], thread=value["thread"], stride=STRIDE, phase=value["phase"],','serial=value["serial"], thread=value["thread"], stride=STRIDE, phase=value["phase"],\n        cadenceVersion=cadence, strides=strides, phases=phases,',1)
parser=parser.replace('schema="native_PLAN_SAMPLE_v1"','schema="native_PLAN_SAMPLE_v1_v2"',1)
parser=parser.replace('    "Times are inclusive same-thread WALL QPC samples, not CPU time.",','    "Times are inclusive same-thread WALL QPC samples, not CPU time.",\n    "Timing envelopes include sampler/Finish overhead and QPC granularity; tiny helpers can be dominated by this floor. No calibrated subtraction is applied.",',1)
(root/'work/profile-plan-samples-cadence.py').write_text(parser,encoding='utf-8',newline='\n')
print(json.dumps(dict(staged=str(out),patch=str(out/'cadence.patch'),production_applied=False)))
