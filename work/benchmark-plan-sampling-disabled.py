"""Separate-TU disabled sampler overhead; ignored diagnostic experiment only.

Requires test-plan-sampled-timing.py to emit its actual-source scaffold first.
Ctor/dtor live in a different object from both probes, like the production DLL.
"""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];out=root/'work/plan-sample-disabled-benchmark';out.mkdir(exist_ok=True)
scaffold=root/'work/plan-sample-timing-regression/test.cpp';assert scaffold.exists(),'Run test-plan-sampled-timing.py --emit-only first'
header=(root/'CvGameCoreDLL_Expansion2/CvStackingDiagnostics.h').read_text();block=re.search(r'// BEGIN PLAN_SAMPLE_DIAGNOSTIC_ONLY\n(.*?)    // END PLAN_SAMPLE_DIAGNOSTIC_ONLY',header,re.S)[1]
source=(root/'CvGameCoreDLL_Expansion2/CvUnitCombat.cpp').read_text(encoding='utf-8-sig')
def function(text,name):
 a=text.index(name);b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
math=function(source,'int CvUnitCombat::DoDamageMath(');raw=''.join(line for line in math.splitlines(keepends=True)if'PLAN_SAMPLE_DIAGNOSTIC_ONLY' not in line)
prefix=r'''
#define NOMINMAX
#include <windows.h>
#include <cmath>
#include <algorithm>
using std::max;
typedef int PlayerTypes;
struct CvSeeder{};
struct Game{int randRangeExclusive(int a,int b,const CvSeeder&){return b-a;}};
struct Globals{Game game;Game&getGame(){return game;}};
static Globals damageGC;
#define GC damageGC
#define MIN(a,b) std::min(a,b)
'''
probes=prefix+'namespace CvStackingDiagnostics{'+block+'}\n'+raw.replace('int CvUnitCombat::DoDamageMath(','__declspec(noinline) int BaselineMath(',1)+'\n'+math.replace('int CvUnitCombat::DoDamageMath(','__declspec(noinline) int ProfiledMath(',1)+r'''
__declspec(noinline) int BaselineProbe(int i){return (i*33)^(i>>3);}
__declspec(noinline) int ProfiledProbe(int i){CvStackingDiagnostics::PlanSampleScope sample(CvStackingDiagnostics::PLAN_UNIT_DANGER);return (i*33)^(i>>3);}
'''
main=r'''
#define NOMINMAX
#include <windows.h>
#include <cstdio>
struct CvSeeder{};
int BaselineMath(int,int,int,int,bool,const CvSeeder&,int);int ProfiledMath(int,int,int,int,bool,const CvSeeder&,int);
int BaselineProbe(int);int ProfiledProbe(int);
volatile unsigned sink=0;
double Run(bool profiled,bool math,unsigned n){LARGE_INTEGER a,b,f;QueryPerformanceFrequency(&f);QueryPerformanceCounter(&a);unsigned total=0;CvSeeder seed;
 for(unsigned i=0;i<n;++i)total+=(unsigned)(math?(profiled?ProfiledMath(1700+i%1100,1100+i%800,2400,1200,false,seed,(i%11)-5):BaselineMath(1700+i%1100,1100+i%800,2400,1200,false,seed,(i%11)-5)):(profiled?ProfiledProbe(i&65535):BaselineProbe(i&65535)));
 QueryPerformanceCounter(&b);sink=total;return1000.0*(b.QuadPart-a.QuadPart)/f.QuadPart;}
int main(){unsigned mismatches=0;CvSeeder seed;for(int i=0;i<2000;++i)if(BaselineMath(1700+i%1100,1100+i%800,2400,1200,false,seed,(i%11)-5)!=ProfiledMath(1700+i%1100,1100+i%800,2400,1200,false,seed,(i%11)-5))++mismatches;
 for(int math=0;math<2;++math){unsigned n=math?1000000:20000000;for(int p=0;p<2;++p){double a,b;if(p){b=Run(true,math!=0,n);a=Run(false,math!=0,n);}else{a=Run(false,math!=0,n);b=Run(true,math!=0,n);}printf("disabled separateTU %s pass%d calls%u baseline_ms%.3f sampledOff_ms%.3f extra_ns_per_call%.3f\n",math?"actualDoDamageMath":"tinyProbe",p,n,a,b,1000000.0*(b-a)/n);}}
 printf("disabled math result mismatches%u sink%u; synthetic bounded x86VC9, no game timing claim\n",mismatches,sink);return mismatches?1:0;}
'''
main=main.replace('return1000.0','return 1000.0')
(out/'module.cpp').write_text(scaffold.read_text(),encoding='utf-8');(out/'probes.cpp').write_text(probes,encoding='utf-8');(out/'main.cpp').write_text(main,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
cl=str(vc/'Vc7/bin/cl.exe');logs=[]
for name in ('module','probes','main'):
 args=[cl,'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0','/c',str(out/(name+'.cpp')),'/Fo'+str(out/(name+'.obj'))]
 if name=='module':args+=['/Dmain=FixtureUnusedMain']
 r=subprocess.run(args,cwd=out,env=env,capture_output=True,text=True,timeout=60);logs.append(r.stdout+r.stderr)
 if r.returncode:(out/'compile.log').write_text(''.join(logs));print(logs[-1]);sys.exit(r.returncode)
exe=out/'test.exe';r=subprocess.run([cl,'/nologo',str(out/'module.obj'),str(out/'probes.obj'),str(out/'main.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=30);logs.append(r.stdout+r.stderr);(out/'compile.log').write_text(''.join(logs))
if r.returncode:print(logs[-1]);sys.exit(r.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='');(out/'result.json').write_text(json.dumps(dict(returncode=r.returncode,output=r.stdout+r.stderr,scope='Sampler ctor/dtor compiled in separate actual-source diagnostic TU from baseline/profiled probes. Actual DoDamageMath body with deterministic random service; sampling defaults inactive. Synthetic VC9 results, not whole-DLL/native turn timing.'),indent=2));sys.exit(r.returncode)
