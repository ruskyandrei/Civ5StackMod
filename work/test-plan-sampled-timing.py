"""Actual-source sparse PLAN sampler and reverse-strip gameplay equivalence.

Deterministic diagnostic/clock services replace engine IO and QPC values. Actual
TLS, session/scope guards, Reset/SetLevel hooks and formatting compile with VC9.
No DLL build, deployment, game calls or user-config changes.
"""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2';out=root/'work/plan-sample-timing-regression';out.mkdir(exist_ok=True)
control='b977a7a0be50bddb12219a764f98ff0bae5db5db'
files=['CvStackingDiagnostics.h','CvStackingDiagnostics.cpp','CvTacticalAI.cpp','CvUnitCombat.cpp','CvStackingRules.cpp','Lua/CvLuaGame.h','Lua/CvLuaGame.cpp']
sources={name:(core/name).read_text(encoding='utf-8-sig') for name in files}
def strip(text):
 text=re.sub(r'^    // BEGIN PLAN_SAMPLE_DIAGNOSTIC_ONLY\n.*?^    // END PLAN_SAMPLE_DIAGNOSTIC_ONLY\n','',text,flags=re.M|re.S)
 text=''.join(line for line in text.splitlines(keepends=True) if 'PLAN_SAMPLE_DIAGNOSTIC_ONLY' not in line)
 return text.replace(' || !strcmp(category,"PLAN_SAMPLE")','').replace(', {"DiagnosticsTacticalSampling",0,0}','')
xml_path='(1) Community Patch/Database Changes/StackingConfig.xml'
xml=(root/xml_path).read_text(encoding='utf-8-sig');xml_old=subprocess.check_output(['git','show',control+':'+xml_path],cwd=root).decode('utf-8-sig');assert strip(xml)==xml_old,'XML changed beyond the default-off diagnostic option'
equivalence={xml_path:dict(identical=True)}
for name,text in sources.items():
 original=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/'+name],cwd=root).decode('utf-8-sig')
 clean=strip(text)
 assert clean==original,'Gameplay/source ordering changed after stripping diagnostics: '+name
 equivalence[name]=dict(control_sha256=hashlib.sha256(original.encode()).hexdigest(),reverse_stripped_sha256=hashlib.sha256(clean.encode()).hexdigest(),identical=True)
(out/'source-equivalence.json').write_text(json.dumps(dict(control=control,files=equivalence),indent=2))
def blocks(text):return re.findall(r'^    // BEGIN PLAN_SAMPLE_DIAGNOSTIC_ONLY\n(.*?)^    // END PLAN_SAMPLE_DIAGNOSTIC_ONLY\n',text,re.M|re.S)
def function(text,name):
 a=text.index(name);b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
header=''.join(blocks(sources['CvStackingDiagnostics.h']));data,implementation=blocks(sources['CvStackingDiagnostics.cpp'])
lua=''.join(blocks(sources['Lua/CvLuaGame.cpp']))
lua_declarations='\n'.join(line.split(' //')[0] for line in sources['Lua/CvLuaGame.h'].splitlines() if 'lSetStackingTacticalSampling(' in line or 'lGetStackingTacticalSampling(' in line)
assert 'Method(SetStackingTacticalSampling);' in sources['Lua/CvLuaGame.cpp'] and 'Method(GetStackingTacticalSampling);' in sources['Lua/CvLuaGame.cpp']
reset=function(sources['CvStackingDiagnostics.cpp'],'void Reset()');toggle=function(sources['CvStackingDiagnostics.cpp'],'void SetLevel(')
assert 'InvalidatePlanSampleEpoch();' in reset and 'InvalidatePlanSampleEpoch();' in toggle
category=function(sources['CvStackingDiagnostics.cpp'],'int categoryBit(')
assert sources['CvTacticalAI.cpp'].count(' // PLAN_SAMPLE_DIAGNOSTIC_ONLY')==14
assert sources['CvUnitCombat.cpp'].count(' // PLAN_SAMPLE_DIAGNOSTIC_ONLY')==1
prefix=r'''
#define NOMINMAX
#include <windows.h>
#include <cstdio>
#include <cstdarg>
#include <cstdlib>
#include <new>
#include <string>
#include <vector>
#include <cstring>
#include <climits>
typedef int PlayerTypes;const int NO_PLAYER=-1,MAX_PLAYERS=64;
static volatile LONG allocationCalls=0;
void* operator new(size_t n){InterlockedIncrement(&allocationCalls);void*p=malloc(n?n:1);if(!p)throw std::bad_alloc();return p;}
void operator delete(void*p){free(p);}void* operator new[](size_t n){return ::operator new(n);}void operator delete[](void*p){::operator delete(p);}
static volatile LONG qpcCalls=0,qpfCalls=0,ownerReads=0,settingReads=0,recordCalls=0,lockCalls=0;
static unsigned __int64 tick=100000;static int counterFailure=0;static bool frequencyFailure=false,backward=false;
BOOL FixtureCounter(LARGE_INTEGER*p){InterlockedIncrement(&qpcCalls);if(counterFailure>0){--counterFailure;return FALSE;}tick+=37;p->QuadPart=backward?0:(LONGLONG)tick;return TRUE;}
BOOL FixtureFrequency(LARGE_INTEGER*p){InterlockedIncrement(&qpfCalls);p->QuadPart=1000000;return !frequencyFailure;}
DWORD FixtureThread(){InterlockedIncrement(&ownerReads);return ::GetCurrentThreadId();}
static DWORD ownerThread=::GetCurrentThreadId();
struct DLLService{bool HasGameCoreLock(){return ::GetCurrentThreadId()==ownerThread;}}dll;DLLService*gDLL=&dll;
#define QueryPerformanceCounter FixtureCounter
#define QueryPerformanceFrequency FixtureFrequency
#define GetCurrentThreadId FixtureThread
static int testTurn=252,testInterval=1,testMask=16,testFilter=-1,testDefaultLevel=1,testXmlSampling=0;
struct GameService{int getGameTurn()const{return testTurn;}}game;
struct Globals{GameService&getGame(){return game;}}GC;
struct Sync{CRITICAL_SECTION value;Sync(){InitializeCriticalSection(&value);}~Sync(){DeleteCriticalSection(&value);}}sync;
struct Lock{Lock(){InterlockedIncrement(&lockCalls);EnterCriticalSection(&sync.value);}~Lock(){LeaveCriticalSection(&sync.value);}};
unsigned long phaseGeneration=0;
int level=1,rowTurn=-1,memoryTurn=-1,rows=0;
bool initialized=false,failed=false,suppressed=false,optionsLoaded=false;
char prefix[96]="",status[1024]="";wchar_t directory[MAX_PATH]=L"";unsigned int configHash=0,pendingWrites=0;DWORD lastFlush=0;
struct Costs{}costs;struct EntryCosts{}entryCosts[MAX_PLAYERS];int playerTurn[MAX_PLAYERS]={0},playerAfterTurn[MAX_PLAYERS]={0},passTurn[MAX_PLAYERS]={0};FILE*output=NULL;
void clearUpdateGapState(){}void closeFile(){output=NULL;}int getLevelUnlocked(){return level<0?testDefaultLevel:level;}
void writeLine(int,int,const char*,const char*){}bool ensureFile(){return true;}void configHeader(){}
int setting(const char*name,int fallback){InterlockedIncrement(&settingReads);if(!strcmp(name,"DiagnosticsPerformanceInterval"))return testInterval;if(!strcmp(name,"DiagnosticsTacticalSampling"))return testXmlSampling;return fallback;}
'''
services=r'''
bool categoryEnabledUnlocked(int required,PlayerTypes player,const char*name){return getLevelUnlocked()>=required&&!failed&&(testFilter<0||testFilter==player)&&(testMask&categoryBit(name))!=0;}
static std::string lastRow;static size_t maximumRow=0;
namespace CvStackingDiagnostics{void Record(int level,PlayerTypes player,const char*cat,const char*format,...){if(!categoryEnabledUnlocked(level,player,cat))return;char row[3072];va_list args;va_start(args,format);int result=_vsnprintf_s(row,sizeof(row),_TRUNCATE,format,args);va_end(args);if(result<0){printf("FAILED fixture row truncation\n");exit(2);}lastRow=row;if(lastRow.size()>maximumRow)maximumRow=lastRow.size();InterlockedIncrement(&recordCalls);}}
struct lua_State{int type;bool value,pushed;};const int LUA_TBOOLEAN=3;
void luaL_checktype(lua_State*L,int,int type){if(L->type!=type)throw 19;}
int lua_toboolean(lua_State*L,int){return L->value?1:0;}void lua_pushboolean(lua_State*L,int value){L->pushed=value!=0;}
'''
tests=r'''
using namespace CvStackingDiagnostics;
int checks=0,failures=0;void Expect(const char*name,bool value){++checks;if(!value){++failures;if(failures<10)printf("FAIL %s\n",name);}}
void Clean(){memset(&planSamples,0,sizeof(planSamples));tacticalSamplingOverride=1;testXmlSampling=0;level=1;failed=false;testTurn=252;testInterval=1;testMask=16;testFilter=-1;frequencyFailure=false;counterFailure=0;backward=false;qpcCalls=qpfCalls=ownerReads=settingReads=recordCalls=lockCalls=0;lastRow.clear();}
void SelectNext(PlanSamplePart part){unsigned long offset=(planSamples.phase+(unsigned long)part*97UL)&4095;planSamples.counter[part].calls=4095-offset;}
void EarlyReturn(){PlanSampleSession session(3,101);SelectNext(PLAN_UNIT_DANGER);PlanSampleScope sample(PLAN_UNIT_DANGER);tick+=99;return;}
DWORD WINAPI Foreign(void*){LONG clocks=qpcCalls,owners=ownerReads,settings=settingReads,allocations=allocationCalls;for(int i=0;i<10000;++i){PlanSampleScope sample(PLAN_DAMAGE_MATH);}bool fast=qpcCalls==clocks&&ownerReads==owners&&settingReads==settings&&allocationCalls==allocations;{PlanSampleSession noCoreLock(3,101);PlanSampleScope sample(PLAN_UNIT_DANGER);}return fast&&!planSamples.enabled&&planSamples.depth==0?0:1;}
static PlanSampleScope* foreignFinish=NULL;static PlanSampleState matchingState;
DWORD WINAPI MatchingForeign(void*){memcpy(&planSamples,&matchingState,sizeof(planSamples));PlanSampleCounter before=planSamples.counter[PLAN_UNIT_DANGER];LONG clocks=qpcCalls;foreignFinish->Finish();return before.samples==planSamples.counter[PLAN_UNIT_DANGER].samples&&before.ticks==planSamples.counter[PLAN_UNIT_DANGER].ticks&&clocks==qpcCalls?0:1;}
int main(){
 Clean();Expect("category16 existing mask",categoryBit("PLAN_SAMPLE")==16);
 LONG allocations=allocationCalls;for(int i=0;i<50000;++i){PlanSampleScope sample(PLAN_UNIT_DANGER);sample.Finish();}
 Expect("off hot path no clocks owner settings logs locks allocations",qpcCalls==0&&qpfCalls==0&&ownerReads==0&&settingReads==0&&recordCalls==0&&lockCalls==0&&allocationCalls==allocations);
 Clean();tacticalSamplingOverride=-1;Expect("XML default off",!GetTacticalSamplingEnabled());{PlanSampleSession disabled(3,100);LONG settings=settingReads;for(int i=0;i<10000;++i){PlanSampleScope sample(PLAN_UNIT_DANGER);}Expect("defaultoff hot probes do not reread settings",settingReads==settings);}Expect("defaultoff has no calibration owner clock row",qpfCalls==0&&qpcCalls==0&&ownerReads==0&&recordCalls==0);
 unsigned long generation=phaseGeneration;long epoch=ReadPlanSampleEpoch();SetTacticalSamplingEnabled(true);Expect("sampling API opts in without altering existing phase generation",GetTacticalSamplingEnabled()&&phaseGeneration==generation&&ReadPlanSampleEpoch()!=epoch);SetTacticalSamplingEnabled(false);Expect("sampling API opts out",!GetTacticalSamplingEnabled());
 testXmlSampling=1;Reset();Expect("load Reset returns XML sampling true",GetTacticalSamplingEnabled());SetTacticalSamplingEnabled(false);Expect("override XML sampling false",!GetTacticalSamplingEnabled());Reset();Expect("load drops sampling override",GetTacticalSamplingEnabled());testXmlSampling=0;Reset();Expect("load defaults sampling off",!GetTacticalSamplingEnabled());
 Clean();lua_State yes={LUA_TBOOLEAN,true,false},no={LUA_TBOOLEAN,false,true},bad={2,true,false};Expect("actual Lua boolean setter returns enabled state",CvLuaGame::lSetStackingTacticalSampling(&yes)==1&&yes.pushed&&GetTacticalSamplingEnabled());Expect("actual Lua boolean getter",CvLuaGame::lGetStackingTacticalSampling(&yes)==1&&yes.pushed);Expect("actual Lua false setter",CvLuaGame::lSetStackingTacticalSampling(&no)==1&&!no.pushed&&!GetTacticalSamplingEnabled());epoch=ReadPlanSampleEpoch();try{CvLuaGame::lSetStackingTacticalSampling(&bad);Expect("Lua wrong type rejected",false);}catch(int){Expect("Lua wrong type before mutation",!GetTacticalSamplingEnabled()&&ReadPlanSampleEpoch()==epoch);}
 Clean();
 level=0;{PlanSampleSession disabled(3,100);for(int i=0;i<10000;++i){PlanSampleScope sample(PLAN_UNIT_DANGER);}}
 Expect("disabled session no clocks owner setting or row",qpcCalls==0&&qpfCalls==0&&ownerReads==0&&settingReads==0&&recordCalls==0&&planSamples.depth==0);
 Clean();testMask=8;{PlanSampleSession disabled(3,100);}Expect("mask excluded no calibration",qpfCalls==0&&qpcCalls==0&&recordCalls==0);
 Clean();testFilter=2;{PlanSampleSession disabled(3,100);}Expect("player excluded no calibration",qpfCalls==0&&qpcCalls==0&&recordCalls==0);
 Clean();testInterval=0;{PlanSampleSession disabled(3,100);}Expect("interval0 excluded no calibration",qpfCalls==0&&qpcCalls==0&&recordCalls==0);
 Clean();testInterval=5;{PlanSampleSession disabled(3,100);}Expect("turn interval excluded no calibration",qpfCalls==0&&qpcCalls==0&&recordCalls==0);
 Clean();unsigned __int64 selected=0;{PlanSampleSession session(3,100);Expect("single successful calibration",qpfCalls==1&&planSamples.frequency==1000000);
  for(int part=0;part<PLAN_SAMPLE_PARTS;++part){unsigned long offset=(planSamples.phase+part*97UL)&4095;for(int i=0;i<10000;++i){PlanSampleScope sample((PlanSamplePart)part);}PlanSampleCounter&v=planSamples.counter[part];unsigned expected=(10000+offset)/4096;Expect("exact4096 phase counts",v.calls==10000&&v.selected==expected&&v.samples==expected&&v.ticks==expected*37&&v.maximum==37);selected+=expected;}
  LONG clocks=qpcCalls,owners=ownerReads,settings=settingReads,locks=lockCalls,allocs=allocationCalls;for(int i=0;i<10000;++i){PlanSampleScope excluded(PLAN_UNIT_DANGER,false);}Expect("ineligible hot path no services",qpcCalls==clocks&&ownerReads==owners&&settingReads==settings&&lockCalls==locks&&allocationCalls==allocs);
 }
 Expect("one bounded row13 fixed fields",recordCalls==1&&lastRow.find("parts=combatMove,turnEnd")!=std::string::npos&&lastRow.find("randomDamageMath")!=std::string::npos&&lastRow.find("overlap=parent_child_not_additive")!=std::string::npos&&maximumRow<3072);
 Expect("exact successful clock read accounting",qpcCalls==selected*2&&qpfCalls==1&&lastRow.find("qpcFrequencyCalls=1")!=std::string::npos);
 Clean();{PlanSampleSession session(3,101);SelectNext(PLAN_UNIT_DANGER);{PlanSampleScope outer(PLAN_UNIT_DANGER);tick+=40;LONG clocks=qpcCalls,owners=ownerReads,settings=settingReads,locks=lockCalls,allocs=allocationCalls;{PlanSampleSession nested(3,102);for(int i=0;i<10000;++i){PlanSampleScope inner(PLAN_UNIT_DANGER);}}Expect("nested no clock owner settings log locks allocation",qpcCalls==clocks&&ownerReads==owners&&settingReads==settings&&lockCalls==locks&&allocationCalls==allocs);tick+=60;}Expect("outer samples include nested envelope",planSamples.counter[PLAN_UNIT_DANGER].samples==1&&planSamples.counter[PLAN_UNIT_DANGER].ticks==137);}
 Expect("nested emits no second row",recordCalls==1);
 Clean();{PlanSampleSession session(3,101);unsigned __int64 before=planSamples.counter[PLAN_UNIT_DANGER].calls;LONG clocks=qpcCalls;HANDLE worker=CreateThread(NULL,0,Foreign,NULL,0,NULL);Expect("foreign worker exists",worker!=NULL);if(worker){WaitForSingleObject(worker,10000);DWORD result=1;GetExitCodeThread(worker,&result);Expect("foreign TLS never consumes owning payload",result==0);CloseHandle(worker);}Expect("foreign cannot sample or modify parent",qpcCalls==clocks&&planSamples.counter[PLAN_UNIT_DANGER].calls==before);}
 Expect("foreign session no second row",recordCalls==1);
 Clean();{PlanSampleSession session(3,101);SelectNext(PLAN_UNIT_DANGER);{PlanSampleScope sample(PLAN_UNIT_DANGER);foreignFinish=&sample;memcpy(&matchingState,&planSamples,sizeof(planSamples));HANDLE worker=CreateThread(NULL,0,MatchingForeign,NULL,0,NULL);if(worker){WaitForSingleObject(worker,10000);DWORD result=1;GetExitCodeThread(worker,&result);Expect("same serial/epoch foreign Finish cannot touch its TLS",result==0);CloseHandle(worker);}else Expect("same-state foreign fixture worker created",false);sample.Finish();Expect("owner can still finish after foreign attempt",planSamples.counter[PLAN_UNIT_DANGER].samples==1&&qpcCalls==2);}}Expect("cross-thread completion stays one owner row",recordCalls==1);
 Clean();generation=phaseGeneration;{PlanSampleSession session(3,101);SelectNext(PLAN_UNIT_DANGER);{PlanSampleScope sample(PLAN_UNIT_DANGER);SetTacticalSamplingEnabled(false);sample.Finish();}Expect("sampling-only toggle rejects live selected sample",qpcCalls==1&&phaseGeneration==generation);}Expect("sampling-only toggle rejects old row",recordCalls==0);
 Clean();{PlanSampleSession session(3,101);SelectNext(PLAN_UNIT_DANGER);{PlanSampleScope sample(PLAN_UNIT_DANGER);Reset();sample.Finish();}Expect("Reset discards selected sample without second clock",qpcCalls==1&&recordCalls==0);}Expect("Reset epoch rejects outer emission",recordCalls==0&&planSamples.depth==0);
 SetTacticalSamplingEnabled(true);{PlanSampleSession refreshed(3,101);SelectNext(PLAN_UNIT_DANGER);PlanSampleScope sample(PLAN_UNIT_DANGER);}Expect("new session after Reset can sample",recordCalls==1);
 Clean();{PlanSampleSession session(3,101);SelectNext(PLAN_UNIT_DANGER);{PlanSampleScope sample(PLAN_UNIT_DANGER);SetLevel(0);sample.Finish();}for(int i=0;i<10000;++i){PlanSampleScope off(PLAN_UNIT_DANGER);}Expect("toggleoff stops clocks after invalidation",qpcCalls==1);}Expect("toggleoff emits no stale row",recordCalls==0);
 SetLevel(1);{PlanSampleSession enabled(3,101);SelectNext(PLAN_UNIT_DANGER);PlanSampleScope sample(PLAN_UNIT_DANGER);}Expect("new enabled session resumes",recordCalls==1);
 Clean();try{PlanSampleSession session(3,101);SelectNext(PLAN_UNIT_DANGER);PlanSampleScope sample(PLAN_UNIT_DANGER);tick+=90;throw 7;}catch(int){}Expect("exception RAII counts and emits once",recordCalls==1&&planSamples.depth==0&&planSamples.counter[PLAN_UNIT_DANGER].samples==1&&planSamples.counter[PLAN_UNIT_DANGER].ticks==127);
 Clean();EarlyReturn();Expect("early return RAII counts and emits once",recordCalls==1&&planSamples.depth==0&&planSamples.counter[PLAN_UNIT_DANGER].samples==1);
 Clean();{PlanSampleSession session(3,101);SelectNext(PLAN_DANGER_KEY);{PlanSampleScope sample(PLAN_DANGER_KEY);sample.Finish();sample.Finish();}Expect("explicit finish then destructor once",qpcCalls==2&&planSamples.counter[PLAN_DANGER_KEY].samples==1);}
 Clean();{PlanSampleSession session(3,101);SelectNext(PLAN_DANGER_LEAF);counterFailure=1;{PlanSampleScope sample(PLAN_DANGER_LEAF);}Expect("counter start failure has no invented duration",planSamples.counter[PLAN_DANGER_LEAF].selected==1&&planSamples.counter[PLAN_DANGER_LEAF].samples==0&&planSamples.clockFailures==1&&qpcCalls==1);}
 Clean();{PlanSampleSession session(3,101);SelectNext(PLAN_DANGER_LEAF);{PlanSampleScope sample(PLAN_DANGER_LEAF);counterFailure=1;}Expect("counter finish failure has no invented duration",planSamples.counter[PLAN_DANGER_LEAF].samples==0&&planSamples.clockFailures==1&&qpcCalls==2);}
 Clean();{PlanSampleSession session(3,101);SelectNext(PLAN_DANGER_LEAF);{PlanSampleScope sample(PLAN_DANGER_LEAF);backward=true;}Expect("counter backwards rejected",planSamples.counter[PLAN_DANGER_LEAF].samples==0&&planSamples.clockFailures==1);backward=false;}
 Clean();frequencyFailure=true;{PlanSampleSession session(3,101);for(int i=0;i<10000;++i){PlanSampleScope sample(PLAN_DANGER_LEAF);}}Expect("frequency failure disables all sampling",qpfCalls==1&&qpcCalls==0&&recordCalls==0&&ownerReads==0);
 Clean();{PlanSampleSession session(3,101);for(int part=0;part<PLAN_SAMPLE_PARTS;++part){PlanSampleCounter&v=planSamples.counter[part];v.calls=v.selected=v.samples=v.ticks=v.maximum=~(unsigned __int64)0;}}
 Expect("maximum64bit formatting stays below row bound",recordCalls==1&&maximumRow<3072);
 printf("actual sparse PLAN timing: %d checks, %d failures; maxRow%u; original8productionfiles reverse-stripped byte-identical; diagnostic/clock services deterministic\n",checks,failures,(unsigned)maximumRow);return failures?1:0;}
'''
fixture=prefix+'namespace CvStackingDiagnostics{'+header+'}\nnamespace{'+data+'}\n'+category+services+'class CvLuaGame{public:'+lua_declarations+'};\n'+'namespace CvStackingDiagnostics{'+reset+toggle+implementation+'}\n'+lua+'\n'+tests
(out/'test.cpp').write_text(fixture,encoding='utf-8')
if '--emit-only' in sys.argv:print('Sampler source equivalence verified and fixture emitted; no compile/run');sys.exit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe';compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(run.stdout+run.stderr,end='');(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,control=control,source_equivalence=equivalence,fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),scope='Actual TLS sparse timing state/session/scope, category bit, Reset/SetLevel; deterministic engine/clock/log services. Whole8source files reverse-stripped byte-identical to DLL58. NativeVC9 x86; not game timing.'),indent=2));sys.exit(run.returncode)
