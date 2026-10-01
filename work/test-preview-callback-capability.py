"""Actual DLL82/staged cache module + native capability-provider differential.

No production write/full DLL/game call. Native unit/player enumeration and lock
services are explicit deterministic substitutes; cache bodies, provider, input
filter and native mutable getter/setter bodies are actual source. Missing proof
is tested as unsupported, never silently supplied an always-safe stub.
"""
from pathlib import Path
import hashlib,importlib.util,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/preview-callback-capability-regression';OUT.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('preview_stage',ROOT/'work/stage-preview-callback-capability.py')
stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
old,new=stage.generate();function=stage.function
production='--production' in sys.argv
if production:
    live={name:(ROOT/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8-sig').replace('\r\n','\n') for name in stage.NAMES}
    for name in stage.NAMES:assert live[name]==new[name],'Actual production does not exactly match staged proof: '+name
    new=live

def module(text):
    return '\n'.join(line for line in text.splitlines() if line not in ('#include "CvGameCoreDLLPCH.h"','#include "CvStackingStrengthCache.h"','#include "LintFree.h"'))

control_header=old['CvStackingStrengthCache.h'].replace('#pragma once','').replace('namespace CvStackingStrengthCache','namespace ControlCache',1)
trial_header=new['CvStackingStrengthCache.h'].replace('#pragma once','')
control_module=module(old['CvStackingStrengthCache.cpp']).replace('namespace CvStackingStrengthCache','namespace ControlCache',1)
trial_module=module(new['CvStackingStrengthCache.cpp'])
for signature in ('\t\tstruct Hash\n','\tbool Lookup(','\tvoid Store('):
    assert function(old['CvStackingStrengthCache.cpp'],signature)==function(new['CvStackingStrengthCache.cpp'],signature),signature
provider=function(new['CvTacticalAI.cpp'],'static bool StackPreviewCallbackCapabilities(')
inputs=function(new['CvTacticalAI.cpp'],'static bool StackPreviewInputsSupported(')
getters='\n'.join(function(old['CvUnit.cpp'],signature) for signature in ('void CvUnit::SetBaseCombatStrength(', 'int CvUnit::GetBaseCombatStrength(', 'bool CvUnit::IsCanAttackRanged(', 'bool CvUnit::IsCanAttackWithMove(', 'bool CvUnit::IsCanAttack(', 'bool CvUnit::IsCombatUnit(', 'bool CvUnit::IsCanDefend(', 'bool CvUnit::IsCanHeavyCharge(', 'int CvUnit::GetMoraleBreakChance('))
ignore=function(old['CvDangerPlots.cpp'],'bool CvDangerPlots::ShouldIgnoreUnit(')
def record_parts(source):
    start=source.index('CvStackingDiagnostics::Record(1,ePlayer,"PLAN_PERF"');opening=source.index('(',start)
    cursor=opening+1;depth=1;quoted=False;escaped=False;begin=cursor;parts=[]
    while depth:
        char=source[cursor]
        if quoted:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
        elif char=='"':quoted=True
        elif char=='(':depth+=1
        elif char==')':
            depth-=1
            if not depth:parts.append(source[begin:cursor].strip())
        elif char==',' and depth==1:
            parts.append(source[begin:cursor].strip());begin=cursor+1
        cursor+=1
    return source[start:cursor]+';',parts
old_record,old_parts=record_parts(old['CvTacticalAI.cpp']);record,parts=record_parts(new['CvTacticalAI.cpp'])
fmt=json.loads(parts[3]);old_fmt=json.loads(old_parts[3])
assert len(re.findall(r'%(?:I64|l)?[diu]',fmt))==len(parts)-4
assert len(parts)==len(old_parts)+4
assert fmt.replace(' callbackProofScans=%lu callbackProofFlags=%lu callbackValidationBypasses=%lu callbackSuspensions=%lu','')==old_fmt
assert parts[-4:]==['strength.capabilityScans','strength.capabilityFlags','strength.capabilityValidationBypasses','strength.capabilitySuspensions']
formatter=r'''
void Check(const char*,bool);
char formattedPlan[3072];
namespace CvStackingDiagnostics { void Record(int,int,const char*,const char*format,...){va_list args;va_start(args,format);vsprintf_s(formattedPlan,sizeof(formattedPlan),format,args);va_end(args);} }
void CheckPlanFormat(){
 struct Target{int getX()const{return 12;}int getY()const{return 24;}}target;Target*pTarget=&target;int ePlayer=0;
 DWORD searchBegin=11,planningBegin=2,searchEnd=20,yieldMs=1;unsigned int yieldCount=2;
 unsigned long gStackDangerHits=1,gStackDangerMisses=2,gStackDefenderHits=3,gStackDefenderMisses=4,gStackDangerEvictions=5,gStackDefenderEvictions=6;
 unsigned long gStackOutcomeBuilds=7,gStackOutcomeReuses=8,gStackOutcomeBypasses=9,gStackPacketHits=10,gStackPacketBuilds=11,gStackPacketBypasses=12;
 size_t gStackKeyPayloadBytes=13,gStackOutcomeCurrentBytes=14,gStackOutcomePeakBytes=15;
 vector<int>gStackDangerForecasts(1),gStackDefenderForecasts(2);
 CvStackingStrengthCache::Stats strength={};
 strength.capabilityScans=101;strength.capabilityFlags=102;strength.capabilityValidationBypasses=103;strength.capabilitySuspensions=104;
 RECORD
 Check("actual PLAN_PERF added counters have correct positional arguments",strstr(formattedPlan,"callbackProofScans=101 callbackProofFlags=102 callbackValidationBypasses=103 callbackSuspensions=104")!=NULL);
 strength.capabilityScans=strength.capabilityFlags=strength.capabilityValidationBypasses=strength.capabilitySuspensions=0xffffffffUL;
 RECORD
 Check("actual PLAN_PERF format stays within3072-byte diagnostic bound",strlen(formattedPlan)<3072&&strstr(formattedPlan,"callbackProofScans=4294967295")!=NULL);
}
'''.replace('RECORD',record)
prefix=r'''
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <cstdarg>
#include <vector>
using namespace std;
#define VALIDATE_OBJECT() ((void)0)
#define GD_INT_GET(value) D_##value
typedef int PlayerTypes;
const int DOMAIN_LAND=0,DOMAIN_SEA=1,DOMAIN_AIR=2,DOMAIN_HOVER=3,DOMAIN_IMMOBILE=4,MAX_PLAYERS=4,NO_PLAYER=-1,ISHUMAN_AI_UNITS=0;
int D_BARBARIAN_CAMP_IMPROVEMENT=77;
bool MOD_EVENTS_CAN_MOVE_INTO=false,MOD_EVENTS_AIRLIFT=false,MOD_EVENTS_SEALIFT=false,MOD_EVENTS_UNIT_RANGEATTACK=false,MOD_EVENTS_CITY_BOMBARD=false,MOD_EVENTS_REBASE=false,MOD_EVENTS_UNIT_ACTIONS=false;
bool gameLock=true;unsigned providerCalls=0,validatorCalls=0,fieldReads=0;
void(*lookupInjection)()=NULL;
struct DLL{bool HasGameCoreLock()const{return gameLock;}}dll;DLL*gDLL=&dll;
struct CvPlot{bool isCity()const{return false;}bool isVisible(int)const{return true;}int getRevealedImprovementType(int)const{return 0;}}sourcePlot;
struct CvUnit{
 int domain,id,m_iBaseCombat,ranged,range,m_iCanHeavyCharge,m_iCanMoraleBreak;bool dead,delayed,nuclear;
 CvUnit(int i=0):domain(DOMAIN_LAND),id(i),m_iBaseCombat(12),ranged(0),range(1),m_iCanHeavyCharge(0),m_iCanMoraleBreak(0),dead(false),delayed(false),nuclear(false){}
 int getDomainType()const{++fieldReads;if(lookupInjection){void(*cb)()=lookupInjection;lookupInjection=NULL;cb();}return domain;}
 bool IsDead()const{return dead;}bool isDelayedDeath()const{return delayed;}bool isCargo()const{return false;}
 int GetRange()const{return range;}int GetBaseRangedCombatStrength()const{return ranged;}
 int getOwner()const{return 0;}int getTeam()const{return 0;}CvPlot*plot()const{return &sourcePlot;}bool isInvisible(int,bool)const{return false;}bool isOnlyDefensive()const{return false;}
 void SetBaseCombatStrength(int);int GetBaseCombatStrength()const;bool IsCanAttackRanged()const;bool IsCanAttackWithMove()const;bool IsCanAttack()const;bool IsCombatUnit()const;bool IsCanDefend()const;bool IsCanHeavyCharge()const;int GetMoraleBreakChance()const;
};
struct CvPlayer{
 vector<CvUnit*> units;vector<pair<int,int> >interceptors;
 const CvUnit*firstUnit(int*cursor)const{*cursor=0;return units.empty()?NULL:units[0];}
 const CvUnit*nextUnit(int*cursor)const{++*cursor;return (size_t)*cursor<units.size()?units[*cursor]:NULL;}
 const vector<pair<int,int> >&GetPossibleInterceptors()const{return interceptors;}
 const CvUnit*getUnit(int id)const{for(size_t i=0;i<units.size();++i)if(units[i]->id==id)return units[i];return NULL;}
 int getTeam()const{return 0;}bool isHuman(int)const{return false;}
};
CvPlayer players[MAX_PLAYERS];
#define GET_PLAYER(owner) players[(owner)]
struct CvDangerPlots{vector<int>m_DangerPlots;int m_ePlayer;CvDangerPlots():m_DangerPlots(1),m_ePlayer(0){}bool ShouldIgnoreUnit(const CvUnit*,bool);};
'''

tests=r'''
unsigned checks=0,failures=0;
void Check(const char*name,bool good){++checks;if(!good){++failures;if(failures<20)printf("FAIL:%s\n",name);}}
bool ActualProvider(unsigned&flags,bool scan){if(scan)++providerCalls;else ++validatorCalls;return StackPreviewCallbackCapabilities(flags,scan);}
void ClearWorld(){for(int i=0;i<MAX_PLAYERS;++i){players[i].units.clear();players[i].interceptors.clear();}MOD_EVENTS_CAN_MOVE_INTO=MOD_EVENTS_AIRLIFT=MOD_EVENTS_SEALIFT=MOD_EVENTS_UNIT_RANGEATTACK=MOD_EVENTS_CITY_BOMBARD=MOD_EVENTS_REBASE=MOD_EVENTS_UNIT_ACTIONS=false;gameLock=true;providerCalls=validatorCalls=fieldReads=0;lookupInjection=NULL;}
void InvalidateDuringScan(){CvStackingStrengthCache::Invalidate();}
void NestDuringScan(){CvStackingStrengthCache::Scope nested(64,ActualProvider);}
void DropLockDuringScan(){gameLock=false;}
bool reentryRejected=false;
void ReenterDuringScan(){long generation;reentryRejected=!CvStackingStrengthCache::Context(generation);}
void ThrowDuringScan(){throw 9;}
unsigned randomState=51731;unsigned Next(){randomState=randomState*1664525u+1013904223u;return randomState;}
DWORD WINAPI Foreign(void*){
 unsigned before=providerCalls;long generation;CvStackingStrengthCache::Scope skipped(64,ActualProvider);
 bool allowed=CvStackingStrengthCache::Context(generation);
 {CvStackingStrengthCache::PreviewSuspension suspension;}
 return !allowed&&providerCalls==before?0:1;
}
int main(){
 ClearWorld();CvUnit plane(2),interceptor(3);plane.domain=DOMAIN_AIR;plane.m_iBaseCombat=0;plane.ranged=20;plane.range=4;players[1].units.push_back(&plane);players[0].units.push_back(&interceptor);players[0].interceptors.push_back(make_pair(3,0));
 unsigned flags=0;Check("source provider sees current stock ranged AIR as safe",StackPreviewCallbackCapabilities(flags,true)&&flags==0);
 plane.SetBaseCombatStrength(1);Check("actual mutable AIR melee-base setter is observed",StackPreviewCallbackCapabilities(flags,true)&&(flags&CvStackingStrengthCache::CALLBACK_AIR_BLOCKADER));plane.SetBaseCombatStrength(0);
 plane.ranged=0;plane.range=10;plane.nuclear=true;CvDangerPlots danger;
 Check("zero-base nonranged nuclear/utility AIR is not a threat source",danger.ShouldIgnoreUnit(&plane,false)&&!plane.IsCanAttack()&&!plane.IsCanAttackWithMove());
 Check("stock zero-base nonranged AIR does not disable all caches",StackPreviewCallbackCapabilities(flags,true)&&flags==0);
 plane.SetBaseCombatStrength(4);Check("current positive-base AIR melee is a source and globally excluded",!danger.ShouldIgnoreUnit(&plane,false)&&plane.IsCanAttackWithMove()&&StackPreviewCallbackCapabilities(flags,true)&&(flags&CvStackingStrengthCache::CALLBACK_AIR_BLOCKADER));
 plane.SetBaseCombatStrength(-4);Check("unclamped negative AIR base can defend and remains excluded",plane.IsCanDefend()&&StackPreviewCallbackCapabilities(flags,true)&&(flags&CvStackingStrengthCache::CALLBACK_AIR_BLOCKADER));
 plane.SetBaseCombatStrength(0);plane.ranged=20;plane.nuclear=false;
 Check("current ranged AIR remains an actual source with zero melee base",!danger.ShouldIgnoreUnit(&plane,false)&&plane.IsCanAttackRanged());
 for(int domain=DOMAIN_LAND;domain<=DOMAIN_IMMOBILE;++domain)if(domain!=DOMAIN_AIR){interceptor.domain=domain;interceptor.m_iCanHeavyCharge=1;Check("all nonAIR possible heavy interceptors flagged",StackPreviewCallbackCapabilities(flags,true)&&(flags&CvStackingStrengthCache::CALLBACK_AIR_ESCAPE));}interceptor.m_iCanHeavyCharge=0;interceptor.domain=DOMAIN_LAND;
 interceptor.m_iCanMoraleBreak=1;Check("conservative interceptor morale flag",StackPreviewCallbackCapabilities(flags,true)&&(flags&CvStackingStrengthCache::CALLBACK_AIR_ESCAPE));interceptor.m_iCanMoraleBreak=0;
 bool*options[]={&MOD_EVENTS_CAN_MOVE_INTO,&MOD_EVENTS_AIRLIFT,&MOD_EVENTS_SEALIFT,&MOD_EVENTS_UNIT_RANGEATTACK,&MOD_EVENTS_CITY_BOMBARD,&MOD_EVENTS_REBASE,&MOD_EVENTS_UNIT_ACTIONS};
 for(int i=0;i<7;++i){*options[i]=true;Check("every modern hook option rejects capability proof",!StackPreviewCallbackCapabilities(flags,true));*options[i]=false;}
 gameLock=false;Check("thread is not a substitute for actual core lock",!StackPreviewCallbackCapabilities(flags,true));gameLock=true;
 unsigned beforeFields=fieldReads;Check("cheap provider validation reads no world fields",StackPreviewCallbackCapabilities(flags,false)&&fieldReads==beforeFields);
 vector<CvUnit*>group;group.push_back(&interceptor);Check("native ground input group supported",StackPreviewInputsSupported(group));group.push_back(&plane);Check("AIR preview input rejects even zero-base stock aircraft",!StackPreviewInputsSupported(group));
 long generation;{CvStackingStrengthCache::Scope absent(64);Check("missing provider is explicitly unsupported",!CvStackingStrengthCache::Context(generation));}
 providerCalls=0;
 {CvStackingStrengthCache::Scope scope(64,ActualProvider);Check("explicit current-world proof activates context",CvStackingStrengthCache::Context(generation));Check("first safe scan executed once",providerCalls==1);
  unsigned fieldsAfterCapture=fieldReads;for(int i=0;i<1000;++i)Check("safe readiness reuses bounded proof",CvStackingStrengthCache::Context(generation));Check("no per-hit world scan",providerCalls==1&&fieldReads==fieldsAfterCapture&&validatorCalls>=1000);
  {CvStackingStrengthCache::PreviewSuspension suspended;Check("suspension disables owned context",!CvStackingStrengthCache::Context(generation)&&CvStackingStrengthCache::IsPreviewSuspended());
   {CvStackingStrengthCache::PreviewSuspension nested;Check("nested suspension remains disabled",!CvStackingStrengthCache::Context(generation));}plane.SetBaseCombatStrength(5);
  }
  Check("mutable setter after suspended callbacks is rescanned",!CvStackingStrengthCache::Context(generation)&&providerCalls==2);
  {CvStackingStrengthCache::PreviewSuspension suspended;plane.SetBaseCombatStrength(0);}
  Check("safe current world regained only after exit",CvStackingStrengthCache::Context(generation)&&providerCalls==3);
  CvStackingStrengthCache::Invalidate();lookupInjection=InvalidateDuringScan;Check("post-provider epoch change rejects publication",!CvStackingStrengthCache::Context(generation));Check("following call captures fresh proof",CvStackingStrengthCache::Context(generation));
  CvStackingStrengthCache::Invalidate();lookupInjection=NestDuringScan;Check("post-provider nested transition rejects publication",!CvStackingStrengthCache::Context(generation));Check("nested exit permits a newly captured proof",CvStackingStrengthCache::Context(generation));
  CvStackingStrengthCache::Invalidate();lookupInjection=DropLockDuringScan;Check("postscan live lock validation rejects publication",!CvStackingStrengthCache::Context(generation));gameLock=true;Check("postscan lock restore captures a new proof",CvStackingStrengthCache::Context(generation));
  CvStackingStrengthCache::Invalidate();lookupInjection=ReenterDuringScan;Check("provider reentry returns conservative unknown",CvStackingStrengthCache::Context(generation)&&reentryRejected);
  CvStackingStrengthCache::Invalidate();lookupInjection=ThrowDuringScan;bool threw=false;try{CvStackingStrengthCache::Context(generation);}catch(int){threw=true;}Check("provider exception unwinds in-flight build state",threw&&CvStackingStrengthCache::Context(generation));
  for(int option=0;option<7;++option){CvStackingStrengthCache::Key warm={};warm.values[0]=2;warm.values[1]=option;CvStackingStrengthCache::Context(generation);CvStackingStrengthCache::Store(warm,generation,917);*options[option]=true;Check("warmed proof rejects each live modern-option transition",!CvStackingStrengthCache::Context(generation));*options[option]=false;Check("modern-option restore requires recapture",CvStackingStrengthCache::Context(generation));int result=0;Check("modern-option restore never revives an old ring entry",!CvStackingStrengthCache::Lookup(warm,generation,result));}
  CvStackingStrengthCache::Key warm={};warm.values[0]=2;warm.values[1]=999;CvStackingStrengthCache::Context(generation);CvStackingStrengthCache::Store(warm,generation,23);gameLock=false;Check("warmed proof rejects actual lock loss without scene signal",!CvStackingStrengthCache::Context(generation));plane.SetBaseCombatStrength(7);gameLock=true;Check("lock restore does not revive stale safe capability",!CvStackingStrengthCache::Context(generation));{CvStackingStrengthCache::PreviewSuspension suspended;plane.SetBaseCombatStrength(0);}Check("native safe state requires fresh post-exit proof",CvStackingStrengthCache::Context(generation));int absent=0;Check("lock restore never revives old ring values",!CvStackingStrengthCache::Lookup(warm,generation,absent));
  HANDLE thread=CreateThread(NULL,0,Foreign,NULL,0,NULL);Check("native foreign thread started",thread!=NULL);if(thread){Check("bounded foreign thread exited",WaitForSingleObject(thread,5000)==WAIT_OBJECT_0);DWORD exit=1;GetExitCodeThread(thread,&exit);CloseHandle(thread);Check("foreign scope cannot scan owning metadata",exit==0);}Check("foreign epoch invalidation rescans owner proof",CvStackingStrengthCache::Context(generation));
  try{CvStackingStrengthCache::PreviewSuspension unwind;throw 7;}catch(int){}Check("exception unwinds suspension depth",!CvStackingStrengthCache::IsPreviewSuspended()&&CvStackingStrengthCache::Context(generation));
  CvStackingStrengthCache::Stats observed=CvStackingStrengthCache::GetStats();Check("bounded observability records scans/unsafe OR/validation/suspension",observed.capabilityScans>1&&(observed.capabilityFlags&CvStackingStrengthCache::CALLBACK_AIR_BLOCKADER)&&observed.capabilityValidationBypasses>=7&&observed.capabilitySuspensions>=4);
 }
 for(int capacity=1;capacity<=127;capacity=capacity==1?7:capacity==7?127:128){
  ControlCache::Scope control(capacity);CvStackingStrengthCache::Scope trial(capacity,ActualProvider);
  for(int step=0;step<5000;++step){ControlCache::Key a={};CvStackingStrengthCache::Key b={};for(int i=0;i<22;++i)a.values[i]=b.values[i]=(int)(Next()%24);a.values[0]=b.values[0]=step%4;long oldEpoch,newEpoch;bool oldContext=ControlCache::Context(oldEpoch),newContext=CvStackingStrengthCache::Context(newEpoch);Check("whole actual Context stock availability agrees",oldContext==newContext);int oldResult=-1,newResult=-1;bool oldHit=ControlCache::Lookup(a,oldEpoch,oldResult),newHit=CvStackingStrengthCache::Lookup(b,newEpoch,newResult);Check("whole actual hash/full-equality lookup agrees",oldHit==newHit&&oldResult==newResult);if(!oldHit){ControlCache::Store(a,oldEpoch,step);CvStackingStrengthCache::Store(b,newEpoch,step);}ControlCache::Stats x=ControlCache::GetStats();CvStackingStrengthCache::Stats y=CvStackingStrengthCache::GetStats();Check("entry/FIFO bounded stock accounting agrees",x.entries==y.entries&&x.peakEntries==y.peakEntries&&x.evictions==y.evictions&&x.limit==y.limit);if(step%103==0){ControlCache::Invalidate();CvStackingStrengthCache::Invalidate();}}
 }
 printf("PREVIEW CALLBACK CAPABILITY:%u checks,%u failures; actual whole cache modules/provider/getters, stock FIFO equivalence and explicit unsafe lifecycle; no native ROI claim\n",checks,failures);return failures?1:0;
}
'''
tests=tests.replace(' printf("PREVIEW CALLBACK CAPABILITY:', ' CheckPlanFormat();\n printf("PREVIEW CALLBACK CAPABILITY:',1)
code='\n'.join((prefix,control_header,trial_header,control_module,trial_module,getters,ignore,provider,inputs,formatter,tests))
(OUT/'test.cpp').write_text(code,encoding='utf-8')
if '--emit-only' in sys.argv:print('Explicit-provider actual-source fixture emitted; no compilation');sys.exit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=OUT/'test.exe';built=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(OUT/'test.cpp'),'/Fe'+str(exe)],cwd=OUT,env=env,capture_output=True,text=True,timeout=45);(OUT/'compile.log').write_text(built.stdout+built.stderr,encoding='utf-8')
if built.returncode:print(built.stdout+built.stderr);sys.exit(built.returncode)
run=subprocess.run([str(exe)],cwd=OUT,capture_output=True,text=True,timeout=15);print(run.stdout+run.stderr,end='');(OUT/'result.json').write_text(json.dumps(dict(control=stage.BASE,returncode=run.returncode,output=run.stdout+run.stderr,production_untouched=True,bound_current_production=production,source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in new.items()},fixture_sha256=hashlib.sha256(code.encode()).hexdigest(),actual_source_module=True,actual_source_provider=True,missing_provider_negative_tested=True,scope='Whole stock control/trial key/hash/lookup/store/FIFO with explicit native proof-provider substitutes; source mutable getter/setter + unsupported/nested/foreign/suspension/postscan checks. Complete combat numerical body tests are separate.'),indent=2),encoding='utf-8');sys.exit(run.returncode)
