"""Actual native VC9 phase timer/policy/file I/O regression; game services stubbed.

The clock is deterministic. This verifies diagnostic gating and inclusive
interval semantics, not real turn timings or game behavior.
"""
from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root / "work/turn-phase-timing-regression"
out.mkdir(exist_ok=True)
(out / "logs").mkdir(exist_ok=True)
core = root / "CvGameCoreDLL_Expansion2"
source = (core / "CvStackingDiagnostics.cpp").read_text(encoding="utf-8-sig")
# Fixed DLL54 source control: removing only these diagnostic statements must
# preserve the complete original update/activation functions and callback order.
for name, signature, added in (
    ("CvDllGame.cpp", "void CvDllGame::Update()", (
        "\tCvStackingDiagnostics::UpdateBoundaryScope boundary(CvStackingDiagnostics::UPDATE_WRAPPER);\n",)),
    ("CvGame.cpp", "void CvGame::update()", (
        "\tCvStackingDiagnostics::UpdateBoundaryScope updateBoundary(CvStackingDiagnostics::UPDATE_GAME);\n",
        "\t\t\tCvStackingDiagnostics::UpdateBoundaryScope hookBoundary(CvStackingDiagnostics::UPDATE_BEGIN_HOOK);\n",
        "\t\t\tCvStackingDiagnostics::UpdateBoundaryScope hookBoundary(CvStackingDiagnostics::UPDATE_END_HOOK);\n",
        "\t\t\t\tCvStackingDiagnostics::BeforeUpdateMoves();\n")),
    ("CvPlayer.cpp", "void CvPlayer::setTurnActive(bool bNewValue, bool bDoTurn)", (
        "\tCvStackingDiagnostics::ActivationTailScope activationTail;\n",
        "\t\t\t\t\t\tactivationTail.Start(GetID(),!isHuman(ISHUMAN_AI_UNITS) && !isObserver());\n")),
):
    current = (core / name).read_text(encoding="utf-8-sig")
    baseline = subprocess.check_output(["git", "show", "0273c8e3e:CvGameCoreDLL_Expansion2/"+name], cwd=root).decode("utf-8-sig")
    def body(text):
        start = text.index(signature)
        return text[start:text.index("\n//", start)].strip()
    actual_body = body(current)
    for line in added:
        assert actual_body.count(line) == 1, (name, "missing/duplicate diagnostic boundary")
        actual_body = actual_body.replace(line, "")
    assert actual_body == body(baseline), (name, "original callback/control-flow changed")
actual = source[source.index("namespace\n"):source.index("    void OnPlayerTurn(")] + "}\n"
header = (core / "CvStackingDiagnostics.h").read_text(encoding="utf-8-sig")
declaration = header[header.index("    class TurnPhaseScope"):header.index("    class CombatScope")]
fixture = ast.parse((root / "work/test-diagnostics-core.py").read_text(encoding="utf-8-sig"))
head = next(ast.literal_eval(n.value) for n in fixture.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "head" for t in n.targets))
head += "\nnamespace CvStackingDiagnostics {\n" + declaration + "}\n"
head += r'''
static DWORD phaseClock=0;
static unsigned long phaseTickCalls=0;
static DWORD phaseTick(){++phaseTickCalls;return phaseClock;}
static DWORD phaseThread=17;
static unsigned __int64 phaseCPU=0;
static unsigned int phaseCPUReads=0;
static bool phaseCPUAvailable=true;
static DWORD phaseThreadId(){return phaseThread;}
static HANDLE phaseCurrentThread(){return (HANDLE)1;}
static BOOL phaseThreadTimes(HANDLE,LPFILETIME created,LPFILETIME exited,LPFILETIME kernel,LPFILETIME user){
 ++phaseCPUReads;if(!phaseCPUAvailable)return FALSE;
 created->dwLowDateTime=created->dwHighDateTime=exited->dwLowDateTime=exited->dwHighDateTime=0;
 kernel->dwLowDateTime=kernel->dwHighDateTime=0;user->dwLowDateTime=(DWORD)phaseCPU;user->dwHighDateTime=(DWORD)(phaseCPU>>32);return TRUE;}
#define GetTickCount phaseTick
#define GetCurrentThreadId phaseThreadId
#define GetCurrentThread phaseCurrentThread
#define GetThreadTimes phaseThreadTimes
'''

player_source = (core / "CvPlayerAI.cpp").read_text(encoding="utf-8-sig")
begin = player_source.index("void CvPlayerAI::AI_unitUpdate(bool bUpdateHomelandAI)")
end = player_source.index("\t// Measure real processing passes", begin)
entry_prefix = player_source[begin:end].replace("CvPlayerAI::AI_unitUpdate", "FlowPlayer::AI_unitUpdate", 1)
control_prefix = entry_prefix.replace("FlowPlayer::AI_unitUpdate", "FlowPlayer::Control", 1)
control_prefix = control_prefix.replace("\tCvStackingDiagnostics::UnitAIEntryScope entryPhase(GetID());\n", "")
control_prefix = control_prefix.replace("\tentryPhase.HookFinished();\n", "")
control_prefix = control_prefix.replace("\tconst bool busy=hasBusyUnitOrCity();\n\tentryPhase.Finish(busy);\n\tif(busy)", "\tif(hasBusyUnitOrCity())")
assert "entryPhase" not in control_prefix and entry_prefix.count("hasBusyUnitOrCity()") == 1
flow = r'''
static vector<string> flowTrace;
static bool flowBusy=false,flowScript=true,flowThrow=false;
static int flowGuardCalls=0;
struct ICvEngineScriptSystem1{} flowSystem;
struct FlowDLL{ICvEngineScriptSystem1*GetScriptSystem(){flowTrace.push_back("system");return flowScript?&flowSystem:NULL;}} flowDLL;
static FlowDLL*gDLL=&flowDLL;
struct FlowArgs{void Push(int){}};
struct CvLuaArgsHandle{FlowArgs value;FlowArgs*operator->(){return &value;}FlowArgs*get(){return &value;}};
namespace LuaSupport{void CallHook(ICvEngineScriptSystem1*,const char*,FlowArgs*,bool&){flowTrace.push_back("hook");phaseClock+=10;phaseCPU+=2000;if(flowThrow)throw 91;}}
struct FlowPlayer{int GetID()const{return 0;}bool hasBusyUnitOrCity(){flowTrace.push_back("guard");++flowGuardCalls;phaseClock+=3;phaseCPU+=1000;return flowBusy;}void AI_unitUpdate(bool);void Control(bool);};
'''
flow += entry_prefix + '\tflowTrace.push_back("body");\n}\n' + control_prefix + '\tflowTrace.push_back("body");\n}\n'

tests = r'''
#undef fflush
#undef _wfsopen
#undef fprintf
static int checks=0,failures=0;
void expect(bool okay,const char* name){++checks;if(!okay){++failures;printf("FAIL %s\n",name);}}
int countText(const string&s,const char*needle){int n=0;size_t p=0;while((p=s.find(needle,p))!=string::npos){++n;p+=strlen(needle);}return n;}
string logs(){
 CvStackingDiagnostics::Flush();string text;
 for(int i=0;i<setting("DiagnosticsMaxFiles",8);++i){wchar_t path[MAX_PATH];_snwprintf_s(path,MAX_PATH,_TRUNCATE,L"%s%S-%02d.log",directory,prefix,i);
  HANDLE f=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
  if(f!=INVALID_HANDLE_VALUE){char buffer[4096];DWORD count;while(ReadFile(f,buffer,sizeof(buffer),&count,NULL)&&count)text.append(buffer,count);CloseHandle(f);}
 }return text;
}
void fresh(){
 CvStackingDiagnostics::Reset();cfg.clear();cfg["DiagnosticsMemoryInterval"]=0;cfg["DiagnosticsMaxFileKB"]=64;cfg["DiagnosticsMaxFiles"]=2;
 cfg["DiagnosticsMaxRowsPerTurn"]=128;settingsReads=dbReads=opens=writes=0;openFailure=writeFailure=flushFailure=false;
 GC.game.turn=10;phaseClock=0;phaseTickCalls=0;phaseThread=17;phaseCPU=0;phaseCPUReads=0;phaseCPUAvailable=true;
}
void disabledTests(){
 fresh();{CvStackingDiagnostics::TurnPhaseScope scope(0,"off");}
 expect(phaseTickCalls==0&&phaseCPUReads==0&&opens==0&&writes==0&&dbReads==0,"disabled timer performs no clock, CPU, file, or DB scan");
 fresh();cfg["DiagnosticsCategoryMask"]=2;CvStackingDiagnostics::SetLevel(1);phaseTickCalls=0;const int before=writes;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"masked");}
 expect(phaseTickCalls==0&&phaseCPUReads==0&&writes==before&&countText(logs(),"|TURN_PHASE|")==0,"performance category mask disables all timer work");
 fresh();cfg["DiagnosticsPerformanceInterval"]=0;CvStackingDiagnostics::SetLevel(1);phaseTickCalls=0;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"interval_off");}
 expect(phaseTickCalls==0&&phaseCPUReads==0&&countText(logs(),"|TURN_PHASE|")==0,"zero interval disables phase timers");
 fresh();cfg["DiagnosticsPerformanceInterval"]=5;CvStackingDiagnostics::SetLevel(1);GC.game.turn=11;phaseTickCalls=0;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"unsampled");}
 expect(phaseTickCalls==0&&phaseCPUReads==0&&countText(logs(),"|TURN_PHASE|")==0,"unsampled turns do not read clock or CPU or record timer");
 fresh();cfg["DiagnosticsPlayer"]=2;CvStackingDiagnostics::SetLevel(1);phaseTickCalls=0;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"wrong_player");}
 expect(phaseTickCalls==0&&phaseCPUReads==0&&countText(logs(),"|TURN_PHASE|")==0,"player filter bypasses irrelevant phases");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseTickCalls=0;{CvStackingDiagnostics::TurnPhaseScope scope(0,NULL);}
 expect(phaseTickCalls==0&&phaseCPUReads==0&&countText(logs(),"|TURN_PHASE|")==0,"null phase is safely disabled");
}
void intervalAndNestedTests(){
 fresh();cfg["DiagnosticsCategoryMask"]=16;cfg["DiagnosticsPerformanceInterval"]=5;CvStackingDiagnostics::SetLevel(1);
 phaseClock=100;{CvStackingDiagnostics::TurnPhaseScope scope(0,"sampled");phaseClock=123;}
 string text=logs();expect(countText(text,"|TURN_PHASE|")==1,"sampled performance-only scope records once");
 expect(text.find("phase=sampled startTick=100 endTick=123 elapsedMs=23")!=string::npos,"actual start and end bounds preserve elapsed time");
 expect(text.find("semantics=inclusive")!=string::npos&&text.find("nested TURN_PHASE and PLAN intervals overlap")!=string::npos,"overlap semantics are explicit");
 expect(text.find("|player=0|TURN_PHASE|")!=string::npos&&text.find(" thread=")!=string::npos,"player and thread context included");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseClock=10;
 {CvStackingDiagnostics::TurnPhaseScope parent(1,"parent");phaseClock=20;{CvStackingDiagnostics::TurnPhaseScope child(1,"child");phaseClock=35;}phaseClock=60;}
 text=logs();expect(countText(text,"|TURN_PHASE|")==2,"nested timers record both scopes");
 expect(text.find("phase=parent startTick=10 endTick=60 elapsedMs=50")!=string::npos,"parent duration includes child interval");
 expect(text.find("phase=child startTick=20 endTick=35 elapsedMs=15")!=string::npos,"child interval remains separate for exclusive offline attribution");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseClock=1;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"explicit_finish");phaseClock=8;scope.Finish();const unsigned long tickReads=phaseTickCalls;scope.Finish();expect(phaseTickCalls==tickReads,"repeated Finish is inert");phaseClock=100;}
 text=logs();expect(countText(text,"|TURN_PHASE|")==1&&text.find("elapsedMs=7")!=string::npos,"Finish plus destructor cannot duplicate or extend duration");
 fresh();cfg["DiagnosticsVerboseStartTurn"]=20;CvStackingDiagnostics::SetLevel(2);phaseClock=8;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"verbose_summary");phaseClock=9;}
 expect(countText(logs(),"|TURN_PHASE|")==1,"top-level timers are summary evidence, independent of verbose windows");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseClock=0xfffffff0UL;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"clock_wrap");phaseClock=10;}
 expect(logs().find("elapsedMs=26")!=string::npos,"DWORD wrap preserves unsigned duration");
}
void leaveEarly(){CvStackingDiagnostics::TurnPhaseScope scope(0,"early_return");phaseClock=24;return;}
void lifecycleAndErrorTests(){
 fresh();CvStackingDiagnostics::SetLevel(1);phaseClock=3;leaveEarly();
 expect(logs().find("phase=early_return startTick=3 endTick=24 elapsedMs=21")!=string::npos,"RAII records early return");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseClock=2;
 try{CvStackingDiagnostics::TurnPhaseScope scope(0,"unwind");phaseClock=7;throw 41;}catch(int){}
 expect(logs().find("phase=unwind startTick=2 endTick=7 elapsedMs=5")!=string::npos,"RAII records exception unwinding");
 fresh();CvStackingDiagnostics::SetLevel(1);{CvStackingDiagnostics::TurnPhaseScope scope(0,"cross_turn");++GC.game.turn;}
 expect(countText(logs(),"|TURN_PHASE|")==0,"scope crossing turn boundary is not misattributed");
 fresh();CvStackingDiagnostics::SetLevel(1);{CvStackingDiagnostics::TurnPhaseScope scope(0,"before_reset");CvStackingDiagnostics::Reset();CvStackingDiagnostics::SetLevel(1);}
 expect(countText(logs(),"|TURN_PHASE|")==0,"reset invalidates old scopes even on same turn");
 fresh();CvStackingDiagnostics::SetLevel(1);{CvStackingDiagnostics::TurnPhaseScope scope(0,"before_level_change");CvStackingDiagnostics::SetLevel(2);}
 expect(countText(logs(),"|TURN_PHASE|")==0,"level/session change invalidates in-flight scope");
 fresh();cfg["DiagnosticsLevel"]=1;openFailure=true;{CvStackingDiagnostics::TurnPhaseScope scope(0,"failed_open");phaseClock=9;}
 expect(string(CvStackingDiagnostics::GetStatus()).find("Logging unavailable")!=string::npos,"logger open failure remains diagnostic-only");
 phaseTickCalls=0;{CvStackingDiagnostics::TurnPhaseScope scope(0,"already_failed");}
 expect(phaseTickCalls==0,"failed logger disables later timers");
 fresh();CvStackingDiagnostics::SetLevel(1);writeFailure=true;{CvStackingDiagnostics::TurnPhaseScope scope(0,"failed_write");phaseClock=9;}
 expect(string(CvStackingDiagnostics::GetStatus()).find("Logging unavailable")!=string::npos,"write error uses existing safe logger failure path");
}
void cpuTests(){
 fresh();CvStackingDiagnostics::SetLevel(1);phaseCPU=0x100000007ULL;phaseClock=10;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"cpu_absolute");phaseCPU+=12345;phaseClock=30;}
 string text=logs();expect(text.find("cpuAvailable=1 cpuStart100ns=4294967303 cpuEnd100ns=4294979648 cpu100ns=12345")!=string::npos,"64-bit absolute CPU start/end and delta are retained");
 expect(phaseCPUReads==2,"active simple phase reads CPU twice");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseCPUAvailable=false;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"cpu_unavailable");phaseClock=20;}
 text=logs();expect(text.find("cpuAvailable=0 cpuStart100ns=0 cpuEnd100ns=0 cpu100ns=0")!=string::npos,"unavailable CPU explicitly marked with safe zero fields");
 expect(phaseCPUReads==1,"failed initial CPU query does not repeat at end");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseCPU=100;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"cpu_backwards");phaseCPU=99;phaseClock=3;}
 expect(logs().find("cpuAvailable=0")!=string::npos,"backwards CPU counter rejected");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseClock=0;phaseCPU=100;
 {CvStackingDiagnostics::TurnPhaseScope parent(0,"cpu_parent");phaseClock=10;phaseCPU=200;{CvStackingDiagnostics::TurnPhaseScope child(0,"cpu_child");phaseClock=20;phaseCPU=300;}phaseClock=40;phaseCPU=500;}
 text=logs();expect(text.find("phase=cpu_parent")!=string::npos&&text.find("cpuStart100ns=100 cpuEnd100ns=500 cpu100ns=400")!=string::npos,"parent CPU is inclusive");
 expect(text.find("cpuStart100ns=200 cpuEnd100ns=300 cpu100ns=100")!=string::npos,"child CPU retains independent bounds without parent subtraction");
 fresh();CvStackingDiagnostics::SetLevel(1);{CvStackingDiagnostics::TurnPhaseScope scope(0,"wrong_thread");phaseThread=18;}
 expect(countText(logs(),"|TURN_PHASE|")==0&&phaseCPUReads==1,"foreign-thread finish drops phase without wrong-thread CPU query");
}
void entry(int player,DWORD start,DWORD hook,DWORD end,bool busy,unsigned __int64 cpuStart,unsigned __int64 cpuHook,unsigned __int64 cpuEnd){
 phaseClock=start;phaseCPU=cpuStart;CvStackingDiagnostics::UnitAIEntryScope probe(player);phaseClock=hook;phaseCPU=cpuHook;probe.HookFinished();phaseClock=end;phaseCPU=cpuEnd;probe.Finish(busy);}
void entryDisabledTests(){
 for(int mode=0;mode<5;++mode){fresh();if(mode){if(mode==1)cfg["DiagnosticsCategoryMask"]=2;if(mode==2)cfg["DiagnosticsPerformanceInterval"]=0;if(mode==3)cfg["DiagnosticsPerformanceInterval"]=3;if(mode==4)cfg["DiagnosticsPlayer"]=1;CvStackingDiagnostics::SetLevel(1);}phaseTickCalls=phaseCPUReads=0;const int written=writes;
  entry(0,10,20,30,true,1,2,3);entry(0,40,50,60,false,4,5,6);
  expect(phaseTickCalls==0&&phaseCPUReads==0&&writes==written,"disabled/masked/interval/unsampled/player-filtered entry has no timer CPU or row work");}
 fresh();CvStackingDiagnostics::SetLevel(1);phaseTickCalls=phaseCPUReads=0;entry(-1,1,2,3,false,1,2,3);entry(MAX_PLAYERS,1,2,3,false,1,2,3);
 expect(phaseTickCalls==0&&phaseCPUReads==0,"invalid player cannot index aggregate or read clocks");
}
void entryAggregationTests(){
 fresh();CvStackingDiagnostics::SetLevel(1);entry(0,100,120,125,true,1000,3000,4000);entry(0,200,240,242,true,6000,9000,10000);
 expect(countText(logs(),"phase=unit_ai_entry")==0&&entryCosts[0].calls==2,"busy polls accumulate without per-poll rows");
 entry(0,300,350,359,false,12000,22000,25000);string text=logs();
 expect(countText(text,"phase=unit_ai_entry")==1&&text.find("startTick=300 endTick=359 elapsedMs=59")!=string::npos,"real pass records only last contiguous span");
 expect(text.find("entryCalls=3 busyReturns=2 aggregateHookMs=110 aggregateGuardMs=16 maxHookMs=50 maxGuardMs=9")!=string::npos,"separate bounded hook/guard aggregate count/sum/max");
 expect(text.find("cpuStart100ns=12000 cpuEnd100ns=25000 cpu100ns=13000")!=string::npos&&text.find("aggregateCPUAvailable=1 aggregateCPUMeasuredCalls=3 aggregateHookCPU100ns=15000 aggregateGuardCPU100ns=5000")!=string::npos,"last CPU endpoints and previous busy CPU totals separate");
 expect(entryCosts[0].calls==0,"real pass consumes accumulated busy costs");
 entry(0,400,401,403,false,30000,30100,30200);text=logs();expect(text.find("entryCalls=1 busyReturns=0 aggregateHookMs=1 aggregateGuardMs=2")!=string::npos,"following real pass starts fresh aggregate window");
 fresh();CvStackingDiagnostics::SetLevel(1);entry(0,1,2,3,true,1,2,3);entry(1,4,5,6,false,4,5,6);expect(entryCosts[0].calls==1&&entryCosts[1].calls==0,"different players cannot consume each other's busy costs");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseCPUAvailable=false;entry(0,1,2,3,true,1,2,3);phaseCPUAvailable=true;entry(0,4,5,6,false,4,5,6);text=logs();
 expect(text.find("aggregateCPUAvailable=0 aggregateCPUMeasuredCalls=1")!=string::npos,"partially unavailable aggregate CPU cannot masquerade as complete");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseClock=0xfffffff0UL;{CvStackingDiagnostics::UnitAIEntryScope probe(0);phaseClock=4;probe.HookFinished();phaseClock=9;probe.Finish(false);}
 expect(logs().find("elapsedMs=25")!=string::npos&&logs().find("aggregateHookMs=20 aggregateGuardMs=5")!=string::npos,"entry and segment durations survive DWORD wrap");
}
void entryLifecycleTests(){
 fresh();CvStackingDiagnostics::SetLevel(1);entry(0,1,2,3,true,1,2,3);CvStackingDiagnostics::SetLevel(2);entry(0,4,5,6,false,4,5,6);
 expect(logs().find("entryCalls=1 busyReturns=0")!=string::npos,"level change drops pending busy aggregates");
 fresh();CvStackingDiagnostics::SetLevel(1);entry(0,1,2,3,true,1,2,3);CvStackingDiagnostics::Reset();CvStackingDiagnostics::SetLevel(1);entry(0,4,5,6,false,4,5,6);
 expect(logs().find("entryCalls=1 busyReturns=0")!=string::npos,"reset drops pending busy aggregates on same turn");
 fresh();CvStackingDiagnostics::SetLevel(1);entry(0,1,2,3,true,1,2,3);++GC.game.turn;entry(0,4,5,6,false,4,5,6);
 expect(logs().find("entryCalls=1 busyReturns=0")!=string::npos,"turn change drops old-turn aggregate on next completed entry");
 fresh();CvStackingDiagnostics::SetLevel(1);entry(0,1,2,3,true,1,2,3);phaseThread=18;entry(0,4,5,6,false,4,5,6);
 expect(logs().find("entryCalls=1 busyReturns=0")!=string::npos,"different thread never credits prior-thread busy CPU");
 fresh();CvStackingDiagnostics::SetLevel(1);entry(0,1,2,3,true,1,2,3);{CvStackingDiagnostics::UnitAIEntryScope probe(0);probe.HookFinished();++GC.game.turn;probe.Finish(false);}
 expect(entryCosts[0].calls==0&&countText(logs(),"phase=unit_ai_entry")==0,"cross-turn active entry drops matching old aggregate without row");
 fresh();CvStackingDiagnostics::SetLevel(1);entry(0,1,2,3,true,1,2,3);try{CvStackingDiagnostics::UnitAIEntryScope probe(0);throw 4;}catch(int){}
 expect(entryCosts[0].calls==0&&countText(logs(),"phase=unit_ai_entry")==0,"unfinished exception entry drops matching pending busy window");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseClock=10;{CvStackingDiagnostics::UnitAIEntryScope outer(0);entry(0,20,30,40,true,2,3,4);phaseClock=50;outer.HookFinished();phaseClock=60;outer.Finish(false);}
 expect(logs().find("elapsedMs=50")!=string::npos&&logs().find("aggregates sum completed entry spans")!=string::npos,"nested completed entry aggregates explicitly remain inclusive not union bounds");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseClock=1;{CvStackingDiagnostics::UnitAIEntryScope probe(0);phaseClock=2;probe.HookFinished();const unsigned int reads=phaseCPUReads;probe.HookFinished();expect(phaseCPUReads==reads,"duplicate hook finish is inert");phaseClock=3;probe.Finish(false);const unsigned int endReads=phaseCPUReads;probe.Finish(false);expect(phaseCPUReads==endReads,"duplicate entry Finish is inert");}
 expect(countText(logs(),"phase=unit_ai_entry")==1,"finish plus destructor records one entry row");
}
void entryFlowTests(){
 for(int enabled=0;enabled<2;++enabled)for(int script=0;script<2;++script)for(int busy=0;busy<2;++busy){
  fresh();if(enabled)CvStackingDiagnostics::SetLevel(1);flowScript=script!=0;flowBusy=busy!=0;flowThrow=false;flowTrace.clear();flowGuardCalls=0;FlowPlayer p;p.Control(false);vector<string>control=flowTrace;
  flowTrace.clear();flowGuardCalls=0;p.AI_unitUpdate(false);expect(flowTrace==control&&flowGuardCalls==1,"actual entry integration preserves hook/guard/body ordering and exactly one guard read");
 }
 fresh();CvStackingDiagnostics::SetLevel(1);entry(0,1,2,3,true,1,2,3);flowScript=true;flowBusy=false;flowThrow=true;flowGuardCalls=0;
 try{FlowPlayer p;p.AI_unitUpdate(false);}catch(int){}
 expect(flowGuardCalls==0&&entryCosts[0].calls==0&&countText(logs(),"phase=unit_ai_entry")==0,"actual throwing callback preserves early unwind and clears incomplete entry window");flowThrow=false;
}
void gapDisabledTests(){
 using namespace CvStackingDiagnostics;
 for(int mode=0;mode<6;++mode){fresh();if(mode){if(mode==1)cfg["DiagnosticsCategoryMask"]=2;if(mode==2)cfg["DiagnosticsPerformanceInterval"]=0;if(mode==3)cfg["DiagnosticsPerformanceInterval"]=3;if(mode==4)cfg["DiagnosticsPlayer"]=2;SetLevel(1);}phaseTickCalls=phaseCPUReads=0;int before=writes;
  {UpdateBoundaryScope wrapper(UPDATE_WRAPPER);UpdateBoundaryScope game(UPDATE_GAME);BeforeUpdateMoves();ActivationTailScope tail;tail.Start(0,mode!=5);{UpdateBoundaryScope hook(UPDATE_END_HOOK);}}
  expect(phaseTickCalls==0&&phaseCPUReads==0&&writes==before,"disabled/masked/unsampled/filtered/ineligible gap has zero clocks, CPU and rows");
  expect(!updateGap.active,"disabled/ineligible activation creates no pending player");}
}
void gapTimelineTests(){
 using namespace CvStackingDiagnostics;
 fresh();SetLevel(1);phaseTickCalls=phaseCPUReads=0;phaseClock=100;phaseCPU=1000;
 {UpdateBoundaryScope wrapper(UPDATE_WRAPPER);UpdateBoundaryScope game(UPDATE_GAME);
  expect(phaseTickCalls==0&&phaseCPUReads==0,"boundaries without pending player do not sample");BeforeUpdateMoves();
  phaseClock=110;phaseCPU=2000;{ActivationTailScope tail;tail.Start(3,true);phaseClock=130;phaseCPU=2200;}
  expect(countText(logs(),"|TURN_UPDATE_GAP|")==0,"activation and per-update boundaries produce no rows");
  phaseClock=140;phaseCPU=2300;{UpdateBoundaryScope hook(UPDATE_END_HOOK);phaseClock=190;phaseCPU=2600;}
  phaseClock=200;phaseCPU=2700;
 }
 // Distinguish game end and wrapper end in an ordinary two-call timeline.
 // Above both share one destructor tick; their overlap is intentional.
 phaseClock=400;phaseCPU=2700;
 {UpdateBoundaryScope wrapper(UPDATE_WRAPPER);phaseClock=401;phaseCPU=2710;UpdateBoundaryScope game(UPDATE_GAME);
  phaseClock=410;phaseCPU=2720;{UpdateBoundaryScope hook(UPDATE_BEGIN_HOOK);phaseClock=470;phaseCPU=2730;}
  phaseClock=480;phaseCPU=2740;BeforeUpdateMoves();phaseClock=490;phaseCPU=2800;
  UnitAIEntryScope first(3);expect(!updateGap.active,"first unit-AI entry consumes pending window before hook/search");
  phaseClock=495;phaseCPU=2850;first.HookFinished();phaseClock=497;phaseCPU=2860;first.Finish(true);
  phaseClock=10000;phaseCPU=100000; // Search/late enclosing destructors cannot extend closed window.
 }
 string text=logs();
 expect(countText(text,"|TURN_UPDATE_GAP|")==1,"one gap row despite busy first entry and enclosing late destructors");
 expect(text.find("|player=3|TURN_UPDATE_GAP|")!=string::npos,"pending new AI owner used instead of observer");
 expect(text.find("startTick=110 endTick=490 elapsedMs=380 thread=17 cpuAvailable=1 cpuStart100ns=2000 cpuEnd100ns=2800 cpu100ns=800")!=string::npos,"pending exact wall and absolute same-thread CPU bounds");
 expect(text.find("wrapperCalls=2 wrapperMs=180 wrapperCPU100ns=800 wrapperCPUMeasured=2 wrapperClippedStart=1")!=string::npos,"wrapper totals clip mid-call activation and first entry without search");
 expect(text.find("gameCalls=2 gameMs=179 gameCPU100ns=790 gameCPUMeasured=2")!=string::npos,"game overlaps wrapper with independent inclusive totals");
 expect(text.find("activationTailCalls=1 activationTailMs=20 activationTailCPU100ns=200")!=string::npos,"activation post-doTurn tail measured separately");
 expect(text.find("beginHookCalls=1 beginHookMs=60 beginHookCPU100ns=10")!=string::npos&&text.find("endHookCalls=1 endHookMs=50 endHookCPU100ns=300")!=string::npos,"begin and end engine-Lua hooks measured separately");
 expect(text.find("preMovesHeadCalls=1 preMovesHeadMs=79 preMovesHeadCPU100ns=30")!=string::npos,"next update head ends before updateMoves");
 expect(text.find("dispatchCalls=1 dispatchMs=200 dispatchCPU100ns=0 dispatchCPUMeasured=1 maximumDispatchMs=200")!=string::npos,"between-wrapper wall wait separated from DLL body and CPU");
 expect(text.find("totals=inclusive_overlapping_not_phase_bounds")!=string::npos,"spanning summary cannot masquerade as phase union");
 entry(3,11000,11001,11002,false,100000,100001,100002);
 expect(countText(logs(),"|TURN_UPDATE_GAP|")==1,"later busy/real passes do not emit duplicate activation gap");
}
void gapLifecycleTests(){
 using namespace CvStackingDiagnostics;
 fresh();SetLevel(1);phaseClock=5;{ActivationTailScope tail;tail.Start(1,true);tail.Start(2,true);phaseClock=8;}
 entry(2,10,11,12,false,0,0,0);expect(updateGap.active&&updateGap.actor==1,"other unit-AI actor cannot consume pending player");
 entry(1,15,16,17,false,0,0,0);expect(countText(logs(),"|TURN_UPDATE_GAP|")==1,"duplicate Start preserves first pending owner");
 fresh();SetLevel(1);{ActivationTailScope old;old.Start(1,true);{ActivationTailScope replacement;replacement.Start(2,true);} }
 entry(1,10,11,12,false,0,0,0);expect(updateGap.active&&updateGap.actor==2,"old destructor/actor cannot alter replaced pending activation");
 entry(2,20,21,22,false,0,0,0);expect(countText(logs(),"|TURN_UPDATE_GAP|")==1,"replacement is attributed once to its actual owner");
 for(int mode=0;mode<3;++mode){fresh();SetLevel(1);{UpdateBoundaryScope wrapper(UPDATE_WRAPPER);ActivationTailScope tail;tail.Start(1,true);if(mode==0)Reset();if(mode==1)SetLevel(2);if(mode==2)++GC.game.turn;}
  entry(1,10,11,12,false,0,0,0);expect(countText(logs(),"|TURN_UPDATE_GAP|")==0,"reset/level/turn changes drop stale gap without row");}
 fresh();SetLevel(1);{ActivationTailScope tail;tail.Start(1,true);}phaseThread=18;entry(1,10,11,12,false,0,0,0);phaseThread=17;entry(1,20,21,22,false,0,0,0);
 expect(countText(logs(),"|TURN_UPDATE_GAP|")==0,"foreign-thread first owner entry drops untrustworthy pending window");
 fresh();SetLevel(1);phaseClock=10;{UpdateBoundaryScope wrapper(UPDATE_WRAPPER);UpdateBoundaryScope game(UPDATE_GAME);ActivationTailScope tail;tail.Start(1,true);
  phaseClock=20;{UpdateBoundaryScope nestedWrapper(UPDATE_WRAPPER);UpdateBoundaryScope nestedGame(UPDATE_GAME);BeforeUpdateMoves();phaseClock=30;entry(1,30,31,32,false,0,0,0);}phaseClock=100;}
 string text=logs();expect(countText(text,"|TURN_UPDATE_GAP|")==1&&text.find("nestedScopes=2")!=string::npos,"nested wrappers counted without duplicate body totals/rows");
 expect(text.find("wrapperCalls=1 wrapperMs=20")!=string::npos&&text.find("gameCalls=1 gameMs=20")!=string::npos,"reentrant entry clips outer spans before search");
 fresh();SetLevel(1);phaseClock=0xfffffff0UL;{ActivationTailScope tail;tail.Start(0,true);phaseClock=0xfffffff5UL;}entry(0,10,11,12,false,0,0,0);
 expect(logs().find("startTick=4294967280 endTick=10 elapsedMs=26")!=string::npos,"pending DWORD wrap retains elapsed span");
 fresh();SetLevel(1);phaseCPUAvailable=false;{ActivationTailScope tail;tail.Start(0,true);}entry(0,10,11,12,false,0,0,0);
 expect(logs().find("|TURN_UPDATE_GAP|startTick=0 endTick=10 elapsedMs=10 thread=17 cpuAvailable=0 cpuStart100ns=0 cpuEnd100ns=0 cpu100ns=0")!=string::npos,"pending unavailable CPU explicitly marked safe");
 fresh();SetLevel(1);try{UpdateBoundaryScope wrapper(UPDATE_WRAPPER);ActivationTailScope tail;tail.Start(1,true);phaseClock=8;throw 71;}catch(int){}
 expect(updateDepth[UPDATE_WRAPPER]==0&&!updateGap.part[GAP_ACTIVATION].open&&!updateGap.part[UPDATE_WRAPPER].open,"exception/early unwind balances pending boundary depths");
 entry(1,10,11,12,false,0,0,0);expect(countText(logs(),"|TURN_UPDATE_GAP|")==1,"completed unwind still yields bounded pending-to-entry diagnostic");
}
int main(){expect(sizeof(void*)==4,"native x86 VC9");disabledTests();intervalAndNestedTests();lifecycleAndErrorTests();cpuTests();entryDisabledTests();entryAggregationTests();entryLifecycleTests();entryFlowTests();gapDisabledTests();gapTimelineTests();gapLifecycleTests();CvStackingDiagnostics::Reset();printf("turn phase timing: %d checks, %d failures\n",checks,failures);return failures?1:0;}
'''

cpp = out / "turn-phase-source-test.cpp"
cpp.write_text(head + actual + flow + tests, encoding="utf-8")
vc = root / "work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0"
sdk = root / "work/toolchain/sdk/windows"
env = os.environ.copy()
env["PATH"] = str(vc / "Vc7/bin") + ";" + str(vc / "Common7/IDE") + ";" + env.get("PATH", "")
env["INCLUDE"] = str(root / "work/toolchain/sdk/vc9/include") + ";" + str(sdk / "Include")
env["LIB"] = str(root / "work/toolchain/sdk/vc9/lib") + ";" + str(sdk / "Lib")
for name in ("CL", "_CL_", "LINK"):
    env.pop(name, None)
exe = out / "turn-phase-source-test.exe"
compiled = subprocess.run([
    str(vc / "Vc7/bin/cl.exe"), "/nologo", "/EHsc", "/MT", "/O2", str(cpp),
    "/Fo" + str(out / "turn-phase-source-test.obj"), "/Fe" + str(exe),
], cwd=out, env=env, capture_output=True, text=True, timeout=60)
(out / "compile.log").write_text(compiled.stdout + compiled.stderr, encoding="utf-8")
if compiled.returncode:
    print(compiled.stdout + compiled.stderr)
    sys.exit(compiled.returncode)
run = subprocess.run([str(exe)], cwd=out, env=env, capture_output=True, text=True, timeout=60)
print(run.stdout + run.stderr, end="")
(out / "result.json").write_text(json.dumps({
    "compile_returncode": compiled.returncode, "test_returncode": run.returncode,
    "output": run.stdout + run.stderr,
    "diagnostics_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
    "scope": "Actual native VC9 timer, gate and logger with deterministic clock/game services; no gameplay or turn-time performance proof",
}, indent=2), encoding="utf-8")
sys.exit(run.returncode)
