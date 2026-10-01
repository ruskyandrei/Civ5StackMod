"""Compile current sampler cadence with VC9 stubs and a frozen-DLL60 patch oracle.

Does not apply the patch, build the full DLL, read changing tactical bodies,
deploy anything or launch Civ V. Deterministic clocks measure accounting only.
"""
from pathlib import Path
import ast
import hashlib
import json
import os
import re
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
staged=root/'work/plan-sample-cadence-staged'
out=root/'work/plan-sample-cadence-regression';out.mkdir(exist_ok=True)
control='688798c3b'
sources={name:(root/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8') for name in ('CvStackingDiagnostics.cpp','CvStackingDiagnostics.h')}
for name, source in sources.items():
    assert source == (staged/name).read_text(encoding='utf-8'), f'Production cadence differs from reviewed frozen60 proposal: {name}'
base={}
for node in ast.parse((root/'work/test-plan-sampled-timing.py').read_text(encoding='utf-8-sig')).body:
    if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('prefix','services','tests'):
        base[node.targets[0].id]=ast.literal_eval(node.value)
assert set(base)=={'prefix','services','tests'}

def blocks(text):return re.findall(r'^    // BEGIN PLAN_SAMPLE_DIAGNOSTIC_ONLY\n(.*?)^    // END PLAN_SAMPLE_DIAGNOSTIC_ONLY\n',text,re.M|re.S)
def function(text,name):
    start=text.index(name);end=text.index('{',start)+1;depth=1
    while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

header=''.join(blocks(sources['CvStackingDiagnostics.h']))
data,implementation=blocks(sources['CvStackingDiagnostics.cpp'])
reset=function(sources['CvStackingDiagnostics.cpp'],'void Reset()')
toggle=function(sources['CvStackingDiagnostics.cpp'],'void SetLevel(')
category=function(sources['CvStackingDiagnostics.cpp'],'int categoryBit(')
lua_source=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/Lua/CvLuaGame.cpp'],cwd=root).decode('utf-8-sig')
lua_header=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/Lua/CvLuaGame.h'],cwd=root).decode('utf-8-sig')
lua=''.join(blocks(lua_source))
lua_declarations='\n'.join(line.split(' //')[0] for line in lua_header.splitlines() if 'lSetStackingTacticalSampling(' in line or 'lGetStackingTacticalSampling(' in line)
tests=base['tests']
old='unsigned long offset=(planSamples.phase+(unsigned long)part*97UL)&4095;planSamples.counter[part].calls=4095-offset;'
new='unsigned long stride=PLAN_SAMPLE_STRIDES[part],offset=(planSamples.phase+(unsigned long)part*97UL)&(stride-1);planSamples.counter[part].calls=stride-1-offset;'
assert old in tests;tests=tests.replace(old,new)
old='unsigned long offset=(planSamples.phase+part*97UL)&4095;'
new='unsigned long stride=PLAN_SAMPLE_STRIDES[part],offset=(planSamples.phase+part*97UL)&(stride-1);'
assert old in tests;tests=tests.replace(old,new)
tests=tests.replace('unsigned expected=(10000+offset)/4096;Expect("exact4096 phase counts"','unsigned expected=(10000+offset)/stride;Expect("exact per-part phase counts"')
marker=' Expect("exact successful clock read accounting",'
assert marker in tests
extra=r'''
 Expect("cadence schema version emitted",lastRow.find("cadenceVersion=2")!=std::string::npos);
 Expect("cadence13 strides emitted",lastRow.find("strides=4096,4096,4096,4096,4096,256,256,4096,64,4096,4096,4096,4096")!=std::string::npos);
 Expect("cadence phase metadata emitted",lastRow.find(" phases=")!=std::string::npos);
 FILE* valid=fopen("valid-cadence-row.txt","wb");Expect("valid cadence fixture row saved",valid!=NULL);if(valid){fputs(lastRow.c_str(),valid);fputc('\n',valid);fclose(valid);}
 unsigned long firstPhase=planSamples.phase,firstSerial=planSamples.serial;
 {PlanSampleSession repeatedTarget(3,100);Expect("repeated target gets next outer serial",planSamples.serial==firstSerial+1);Expect("repeated target rotates phase",planSamples.phase!=firstPhase);Expect("target serial phase formula",planSamples.phase==(((unsigned long)100*1664525UL+planSamples.serial*2246822519UL+1013904223UL)&4095));}
 for(int part=0;part<PLAN_SAMPLE_PARTS;++part){unsigned long expected=part==PLAN_DANGER_LEAF||part==PLAN_PREFERRED_ASSIGNMENTS?256:part==PLAN_NEXT_ASSIGNMENTS?64:4096;Expect("all13 exact cadence constants",PLAN_SAMPLE_STRIDES[part]==expected);}
 Clean();planSampleSerial=~0UL;{PlanSampleSession wrapped(3,100);Expect("serial wrap skips zero",planSamples.serial==1);Expect("serial wrap has reproducible phase",planSamples.phase==(((unsigned long)100*1664525UL+2246822519UL+1013904223UL)&4095));}
 Clean();{PlanSampleSession parent(3,100);unsigned long phase=planSamples.phase,serial=planSamples.serial;{PlanSampleSession nested(3,200);Expect("nested keeps outer cadence phase",planSamples.phase==phase&&planSamples.serial==serial);}}
 Clean();{PlanSampleSession strideBoundary(3,100);SelectNext(PLAN_NEXT_ASSIGNMENTS);for(int i=0;i<65;++i){PlanSampleScope sample(PLAN_NEXT_ASSIGNMENTS);}Expect("stride64 first and sixty-fifth both selected",planSamples.counter[PLAN_NEXT_ASSIGNMENTS].samples==2);}
 Clean();{PlanSampleSession strideBoundary(3,100);SelectNext(PLAN_PREFERRED_ASSIGNMENTS);for(int i=0;i<257;++i){PlanSampleScope sample(PLAN_PREFERRED_ASSIGNMENTS);}Expect("stride256 first and two-hundred-fifty-seventh both selected",planSamples.counter[PLAN_PREFERRED_ASSIGNMENTS].samples==2);}
 Clean();{PlanSampleSession strideBoundary(3,100);SelectNext(PLAN_DANGER_LEAF);for(int i=0;i<257;++i){PlanSampleScope sample(PLAN_DANGER_LEAF);}Expect("leaf stride256 accounting",planSamples.counter[PLAN_DANGER_LEAF].samples==2);}
 Clean();selected=0;{PlanSampleSession accounting(3,100);for(int part=0;part<PLAN_SAMPLE_PARTS;++part){SelectNext((PlanSamplePart)part);{PlanSampleScope sample((PlanSamplePart)part);}++selected;}}
'''
tests=tests.replace(marker,extra+marker)
# The extra scenarios reset the clocks. Restore the original successful-clock
# assertion with an isolated explicit one-per-part accounting scenario above.
tests=tests.replace('original8productionfiles reverse-stripped byte-identical','current production sampler exact reviewed frozen60 proposal')
fixture=base['prefix']+'namespace CvStackingDiagnostics{'+header+'}\nnamespace{'+data+'}\n'+category+base['services']+'class CvLuaGame{public:'+lua_declarations+'};\nnamespace CvStackingDiagnostics{'+reset+toggle+implementation+'}\n'+lua+'\n'+tests
(out/'test.cpp').write_text(fixture,encoding='utf-8')
if '--emit-only' in sys.argv:
    print('Current production cadence fixture emitted; no compilation or game action')
    raise SystemExit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe'
compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:
    print(compiled.stdout+compiled.stderr);raise SystemExit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30)
print(run.stdout+run.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,control=control,production_applied=True,
    fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),scope='Current Diagnostics sampler/header/reset/level methods exactly match frozen60 cadence proposal; frozen60 Lua methods unchanged. Actual TLS/cadence/row formatting; deterministic clock/engine stubs, no full DLL or game.'),indent=2)+'\n',encoding='utf-8')
raise SystemExit(run.returncode)
