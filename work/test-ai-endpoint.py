"""Actual-source regression: successful approximate paths may have no turn endpoint."""
from pathlib import Path
import os,subprocess,sys,json,hashlib
root=Path(__file__).resolve().parents[1];out=root/'work/ai-endpoint-regression';out.mkdir(exist_ok=True)
raw=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_bytes();s=raw.decode('utf-8-sig').replace('\r\n','\n')
a=s.index('\t\tif (!pUnit->GeneratePath(pTarget, iFlags, GetRecruitRange()))',s.index('bool CvTacticalAI::PositionUnitsAroundTarget'))
b=s.index('\n\t}\n\n\t//third round:',a)
actual=s[a:b]
assert actual.count('GetPathEndFirstTurnPlot()')==1
assert actual.index('if (!pApproachEndPlot)')<actual.index('GetDanger(')<actual.index('CvStackingDiagnostics::Record(')
prefix=r'''
#include <cstdio>
#include <cstdarg>
const int UNITAI_CITY_BOMBARD=7,DOMAIN_LAND=0,TACTICAL_DOMINANCE_FRIENDLY=1;
struct CvPlot{int id;CvPlot(int n):id(n){}int GetPlotIndex()const{return id;}};
struct CvUnit{enum{MOVEFLAG_NO_EMBARK=1};CvPlot*end;CvPlot*start;bool path,clearDuringDanger,clearDuringProtection;int role,danger,hp,calls,dangerCalls;const CvPlot*dangerPlot;
 CvUnit(CvPlot*s):end(NULL),start(s),path(true),clearDuringDanger(false),clearDuringProtection(false),role(UNITAI_CITY_BOMBARD),danger(3),hp(100),calls(0),dangerCalls(0),dangerPlot(NULL){}
 bool GeneratePath(CvPlot*,int,int){return path;}CvPlot*GetPathEndFirstTurnPlot(){++calls;return end;}
 int GetDanger(CvPlot*p){++dangerCalls;dangerPlot=p;if(clearDuringDanger)end=NULL;return danger;}
 bool IsCanAttack(){return true;}int AI_getUnitAIType(){return role;}int GetCurrHitPoints(){return hp;}int getOwner(){return 8;}int GetID(){return 7495;}CvPlot*plot(){return start;}bool isEmbarked(){return false;}};
struct CvTacticalDominanceZone{int GetOverallDominanceFlag(){return TACTICAL_DOMINANCE_FRIENDLY;}};
struct Analysis{CvPlot*used;CvTacticalDominanceZone zone;Analysis():used(NULL){}CvTacticalDominanceZone*GetZoneByPlot(CvPlot*p){used=p;return &zone;}}analysis;
static Analysis*GetTacticalAnalysisMap(){return &analysis;}static int GetRecruitRange(){return 8;}
static bool accepted=false;static CvPlot*protectionPlot=NULL;static int protectionCalls=0,moved=0;
static bool CanApproachInProtectedStack(CvUnit*u,CvPlot*p,int){++protectionCalls;protectionPlot=p;if(u->clearDuringProtection)u->end=NULL;return accepted;}
static void ExecuteMoveToPlot(CvUnit*,CvPlot*,bool,int){++moved;}
namespace CvStackingDiagnostics{bool enabled=true;int records=0,destination=-1;void Record(int,int,const char*,const char*,...){if(!enabled)return;va_list a;va_start(a,NULL);va_end(a);++records;}}
'''
# Native record signature has a named last fixed parameter for valid va_start.
prefix=prefix.replace('const char*,...){if(!enabled)return;va_list a;va_start(a,NULL);va_end(a);++records;}', 'const char*format,...){if(!enabled)return;va_list a;va_start(a,format);va_arg(a,int);va_arg(a,int);destination=va_arg(a,int);va_end(a);++records;}')
wrapper='static void Approach(CvUnit*pUnit,CvPlot*pTarget){int iFlags=0;for(int once=0;once<1;++once){\n'+actual+'\n}}\n'
suffix=r'''
static int tests=0,failed=0;static void check(const char*n,bool b){++tests;if(!b){++failed;printf("FAIL %s\n",n);}}
static void reset(){accepted=false;protectionPlot=NULL;protectionCalls=0;moved=0;analysis.used=NULL;CvStackingDiagnostics::records=0;CvStackingDiagnostics::destination=-1;}
int main(){CvPlot start(1),target(2),end(3);
 for(int level=0;level<2;++level){reset();CvStackingDiagnostics::enabled=level!=0;CvUnit u(&start);Approach(&u,&target);check("successful empty path read once",u.calls==1);check("empty path skipped before forecasts",u.dangerCalls==0&&protectionCalls==0);check("empty path never logged or moved",CvStackingDiagnostics::records==0&&moved==0&&analysis.used==NULL);}
 reset();CvUnit fail(&start);fail.path=false;Approach(&fail,&target);check("failed path no endpoint read",fail.calls==0&&moved==0);
 reset();CvUnit safe(&start);safe.end=&end;safe.danger=0;Approach(&safe,&target);check("safe real path preserved",moved==1&&analysis.used==&end&&safe.dangerPlot==&end);check("safe endpoint queried once",safe.calls==1);
 reset();CvUnit exposed(&start);exposed.end=&end;Approach(&exposed,&target);check("unprotected danger still rejected",moved==0&&protectionCalls==1);check("diagnostic uses checked endpoint",CvStackingDiagnostics::records==1&&CvStackingDiagnostics::destination==3);
 reset();CvUnit protectedUnit(&start);protectedUnit.end=&end;accepted=true;Approach(&protectedUnit,&target);check("protected real approach preserved",moved==1&&protectionPlot==&end&&analysis.used==&end);
 reset();CvUnit cleared(&start);cleared.end=&end;cleared.clearDuringDanger=true;accepted=true;Approach(&cleared,&target);check("danger may clear cache without losing endpoint",moved==1&&protectionPlot==&end&&analysis.used==&end&&cleared.calls==1);check("log retains captured destination",CvStackingDiagnostics::destination==3);
 reset();CvUnit helperClear(&start);helperClear.end=&end;helperClear.clearDuringProtection=true;accepted=true;Approach(&helperClear,&target);check("protection may clear cache without losing endpoint",moved==1&&analysis.used==&end&&helperClear.calls==1);
 reset();CvUnit melee(&start);melee.end=&end;melee.role=0;melee.danger=30;Approach(&melee,&target);check("ordinary half-health threshold unchanged",moved==1&&protectionCalls==0);
 printf("endpoint source regression: %d checks, %d failures\n",tests,failed);return failed?1:0;}
'''
cpp=out/'endpoint-source-test.cpp';cpp.write_text(prefix+wrapper+suffix,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'endpoint-source-test.exe';c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'endpoint.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps({'source_sha256':hashlib.sha256(raw).hexdigest().upper(),'returncode':r.returncode,'output':r.stdout+r.stderr,'scope':'Actual approach block extracted and compiled with engine stubs; successful-empty approximate path and cache invalidation controls; not full DLL/game validation.'},indent=2),encoding='utf-8');sys.exit(r.returncode)
