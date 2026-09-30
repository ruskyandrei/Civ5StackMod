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
#define GetTickCount phaseTick
'''

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
 GC.game.turn=10;phaseClock=0;phaseTickCalls=0;
}
void disabledTests(){
 fresh();{CvStackingDiagnostics::TurnPhaseScope scope(0,"off");}
 expect(phaseTickCalls==0&&opens==0&&writes==0&&dbReads==0,"disabled timer performs no clock, file, or DB scan");
 fresh();cfg["DiagnosticsCategoryMask"]=2;CvStackingDiagnostics::SetLevel(1);phaseTickCalls=0;const int before=writes;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"masked");}
 expect(phaseTickCalls==0&&writes==before&&countText(logs(),"|TURN_PHASE|")==0,"performance category mask disables all timer work");
 fresh();cfg["DiagnosticsPerformanceInterval"]=0;CvStackingDiagnostics::SetLevel(1);phaseTickCalls=0;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"interval_off");}
 expect(phaseTickCalls==0&&countText(logs(),"|TURN_PHASE|")==0,"zero interval disables phase timers");
 fresh();cfg["DiagnosticsPerformanceInterval"]=5;CvStackingDiagnostics::SetLevel(1);GC.game.turn=11;phaseTickCalls=0;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"unsampled");}
 expect(phaseTickCalls==0&&countText(logs(),"|TURN_PHASE|")==0,"unsampled turns do not read clock or record timer");
 fresh();cfg["DiagnosticsPlayer"]=2;CvStackingDiagnostics::SetLevel(1);phaseTickCalls=0;
 {CvStackingDiagnostics::TurnPhaseScope scope(0,"wrong_player");}
 expect(phaseTickCalls==0&&countText(logs(),"|TURN_PHASE|")==0,"player filter bypasses irrelevant phases");
 fresh();CvStackingDiagnostics::SetLevel(1);phaseTickCalls=0;{CvStackingDiagnostics::TurnPhaseScope scope(0,NULL);}
 expect(phaseTickCalls==0&&countText(logs(),"|TURN_PHASE|")==0,"null phase is safely disabled");
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
int main(){expect(sizeof(void*)==4,"native x86 VC9");disabledTests();intervalAndNestedTests();lifecycleAndErrorTests();CvStackingDiagnostics::Reset();printf("turn phase timing: %d checks, %d failures\n",checks,failures);return failures?1:0;}
'''

cpp = out / "turn-phase-source-test.cpp"
cpp.write_text(head + actual + tests, encoding="utf-8")
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
