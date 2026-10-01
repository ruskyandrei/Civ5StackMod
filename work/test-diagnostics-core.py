"""VC9 actual diagnostics policy/IO; independent PATH-only probes tested separately."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
from path_profile_fixture import strip as strip_path_diagnostics
root=Path(__file__).resolve().parents[1];out=root/'work/diagnostics-core-regression';out.mkdir(exist_ok=True);logs=out/'logs';logs.mkdir(exist_ok=True)
src=(root/'CvGameCoreDLL_Expansion2/CvStackingDiagnostics.cpp').read_text(encoding='utf-8-sig');actual=strip_path_diagnostics(src[src.index('namespace\n'):src.index('    void OnPlayerTurn(')])+'}\n'
actual=actual[:-2]+src[src.index('    void AfterPlayerUnitAI('):src.index('    void CombatScope::AddUnit(')]+'}\n'
head=r"""
#include <cstdio>
#include <cstdarg>
#include <string>
#include <map>
#include <vector>
#define NOMINMAX
#include <windows.h>
#include <direct.h>
#include <share.h>
using namespace std;
typedef int PlayerTypes;
const int MAX_PLAYERS=64,NO_PLAYER=-1;
#define CURRENT_GAMECORE_VERSION "native-policy-test"
static map<string,int> cfg;static int settingsReads=0,dbReads=0,opens=0,writes=0;static bool openFailure=false,writeFailure=false,flushFailure=false;
namespace CvStacking{int GetInt(const char*n,int f){++settingsReads;map<string,int>::const_iterator i=cfg.find(n);return i==cfg.end()?f:i->second;}}
namespace Database{struct Results{int pos;Results():pos(0){}bool Step(){return pos++==0;}const char*GetText(const char*n){return n[0]=='K'?"test:key":"7";}};struct Connection{bool Execute(Results&,const char*){++dbReads;return true;}};}
static Database::Connection db;
struct Game{int turn;Game():turn(1){}int getGameTurn(){return turn;}};
struct Map{int getGridWidth(){return 80;}int getGridHeight(){return 52;}};
struct Global{Game game;Map map;Game&getGame(){return game;}Map&getMap(){return map;}Database::Connection*GetGameDatabase(){return &db;}}GC;
struct SamplingDLLService{bool HasGameCoreLock()const{return false;}}samplingDLL;static SamplingDLLService*gDLL=&samplingDLL;
static wstring logLocator=L"logs\\StackingDiagnostics-path.log";
struct FILogFile{enum{kDontTimeStamp=1};const wchar_t*GetFileName(){return logLocator.c_str();}} locator;
struct LogMgr{FILogFile*GetLog(const char*,int){return &locator;}}LOGFILEMGR;
namespace CvStackingDiagnostics{void Reset();void SetLevel(int);int GetLevel();const char*GetStatus();bool Enabled(int,PlayerTypes=NO_PLAYER);void Record(int,PlayerTypes,const char*,const char*,...);}
struct Plot{int GetPlotIndex()const{return 12;}bool isCity()const{return true;}} testPlot;
const int AI_TACTICAL_MOVE_NONE=0,AI_HOMELAND_MOVE_NONE=0,AI_HOMELAND_MOVE_UNASSIGNED=1;
struct CvUnit{int id;bool dead;CvUnit(int n=0):id(n),dead(false){}bool isDelayedDeath()const{return dead;}bool IsCombatUnit()const{return true;}
 Plot*plot(){return &testPlot;}int getArmyID()const{return -1;}bool IsHurt()const{return false;}int getTacticalMove()const{return 0;}int getHomelandMove()const{return 1;}
 int GetID()const{return id;}int GetCurrHitPoints()const{return 100;}int getMoves()const{return 0;}bool TurnProcessed()const{return true;}bool IsGarrisoned()const{return false;}};
typedef Plot CvPlot;
struct CvArmyAI{int GetID(){return 1;}int GetNumSlotsFilled(){return 4;}int GetNumFormationEntries(){return 8;}};
struct CvAIOperation{int GetID(){return 1;}int GetOperationType(){return 2;}int GetOperationState(){return 3;}int GetEnemy(){return 1;}CvPlot*GetTargetPlot(){return &testPlot;}CvPlot*GetMusterPlot(){return &testPlot;}CvArmyAI*GetArmy(int){return NULL;}int GetNumUnitsNeededToBeBuilt(){return 2;}int GetNumUnitsCommittedToBeBuilt(){return 1;}int GetTurnStarted(){return 0;}};
struct CvPlayer{vector<CvAIOperation*>operations;size_t getNumAIOperations(){return operations.size();}CvAIOperation*getAIOperationByIndex(size_t i){return operations[i];}vector<CvUnit*> units;int GetID()const{return 0;}CvUnit*firstUnit(int*i){*i=0;return units.empty()?NULL:units[0];}CvUnit*nextUnit(int*i){++*i;return *i<(int)units.size()?units[*i]:NULL;}};
static FILE* testOpen(const wchar_t*path,const wchar_t*mode,int sharing){++opens;if(openFailure)return NULL;return _wfsopen(path,mode,sharing);}
static int testPrint(FILE*p,const char*f,...){++writes;if(writeFailure)return -1;va_list a;va_start(a,f);int r=vfprintf(p,f,a);va_end(a);return r;}
static int testFlush(FILE*p){return flushFailure?EOF:fflush(p);}
#define fflush testFlush
#define _wfsopen testOpen
#define fprintf testPrint
"""
diagnostics_header=strip_path_diagnostics((root/'CvGameCoreDLL_Expansion2/CvStackingDiagnostics.h').read_text(encoding='utf-8-sig'))
phase_declaration=diagnostics_header[diagnostics_header.index('    class TurnPhaseScope'):diagnostics_header.index('    class CombatScope')]
head+='\nnamespace CvStackingDiagnostics {\n'+phase_declaration+'}\n'
tail=r"""
#undef fflush
#undef _wfsopen
#undef fprintf
static int checks=0,failures=0;
void expect(bool ok,const char*n){++checks;if(!ok){++failures;printf("FAIL %s\n",n);}}
string slurpCurrent(bool flush=true){if(flush)CvStackingDiagnostics::Flush();string s;for(int i=0;i<setting("DiagnosticsMaxFiles",8);++i){wchar_t p[MAX_PATH];_snwprintf_s(p,MAX_PATH,_TRUNCATE,L"%s%S-%02d.log",directory,prefix,i);HANDLE f=CreateFileW(p,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);if(f!=INVALID_HANDLE_VALUE){char b[4096];DWORD n;while(ReadFile(f,b,sizeof b,&n,NULL)&&n)s.append(b,n);CloseHandle(f);}else if(GetLastError()!=2){static bool printed=false;if(!printed){printf("READBACK_ERROR=%lu path=%S\n",GetLastError(),p);printed=true;}}}return s;}
int countText(const string&s,const char*t){int n=0;size_t p=0;while((p=s.find(t,p))!=string::npos){++n;p+=strlen(t);}return n;}
void fresh(){CvStackingDiagnostics::Reset();cfg.clear();cfg["DiagnosticsMemoryInterval"]=0;cfg["DiagnosticsMaxFileKB"]=64;cfg["DiagnosticsMaxFiles"]=2;cfg["DiagnosticsMaxRowsPerTurn"]=32;settingsReads=dbReads=opens=writes=0;openFailure=writeFailure=flushFailure=false;logLocator=L"logs\\StackingDiagnostics-path.log";GC.game.turn=1;}
DWORD WINAPI concurrentStatus(LPVOID){for(int i=0;i<100;++i){CvStackingDiagnostics::SetLevel(i%3);const char*p=CvStackingDiagnostics::GetStatus();if(!p||!p[0])return 1;}return 0;}
int main(){
 CvUnit unit(7),dead(8);dead.dead=true;CvPlayer player;player.units.push_back(&unit);player.units.push_back(&dead);
 fresh();CvStackingDiagnostics::AfterPlayerUnitAI(player);expect(opens==0&&writes==0,"after-AI observer off does not open logs");
 CvStackingDiagnostics::SetLevel(1);CvStackingDiagnostics::AfterPlayerUnitAI(player);string decisions=slurpCurrent();
 expect(countText(decisions,"|DECISION_SUMMARY|")==1,"summary after actual AI pass");expect(decisions.find("combat=1 inCities=1 inArmies=0 healthyUnassigned=1")!=string::npos,"after-AI counts ignore delayed deaths");
 expect(countText(decisions,"|UNIT_DECISION|")==0,"summary omits per-unit detail");CvStackingDiagnostics::AfterPlayerUnitAI(player);expect(countText(slurpCurrent(),"|DECISION_SUMMARY|")==1,"duplicate AI passes do not duplicate observation");
 CvStackingDiagnostics::SetLevel(2);GC.game.turn=10;CvStackingDiagnostics::AfterPlayerUnitAI(player);expect(countText(slurpCurrent(),"|UNIT_DECISION|")==1,"verbose detail follows XML interval");
 expect(unit.id==7&&!unit.dead&&GC.game.turn==10,"decision logging does not mutate units or turn");
 CvStackingDiagnostics::Reset();cfg["DiagnosticsLevel"]=1;CvStackingDiagnostics::AfterPlayerUnitAI(player);expect(countText(slurpCurrent(),"|DECISION_SUMMARY|")==1,"same-turn reload permits new-session observation");
 fresh();CvStackingDiagnostics::Record(1,0,"TEST","off");expect(opens==0&&writes==0&&dbReads==0,"default off no file or DB scans");expect(CvStackingDiagnostics::GetLevel()==0,"default off");CvStackingDiagnostics::SetLevel(-1);CvStackingDiagnostics::SetLevel(3);expect(CvStackingDiagnostics::GetLevel()==0&&opens==0,"invalid setter ignored");
 fresh();cfg["DiagnosticsLevel"]=1;cfg["DiagnosticsPlayer"]=2;CvStackingDiagnostics::Record(1,1,"TEST","wrongplayer");expect(opens==0,"player filter suppresses file");CvStackingDiagnostics::Record(1,2,"TEST","rightplayer");expect(opens==1,"XML summary opens on first relevant event");expect(dbReads==9,"configuration scan once opening");expect(configHash!=0,"configuration fingerprint resolved");expect(slurpCurrent().find("rightplayer")!=string::npos&&slurpCurrent().find("wrongplayer")==string::npos,"filter affects actual bytes");int reads=settingsReads;CvStackingDiagnostics::Record(1,2,"TEST","again");expect(settingsReads==reads,"cached numeric settings");expect(CvStackingDiagnostics::Enabled(1,NO_PLAYER),"global memory records bypass player filter");expect(!CvStackingDiagnostics::Enabled(2,2),"summary excludes verbose");expect(GC.game.turn==1,"recording leaves game getter state unchanged");
 fresh();CvStackingDiagnostics::SetLevel(1);for(int i=0;i<40;++i)CvStackingDiagnostics::Record(1,0,"BUDGET","row=%d",i);string s=slurpCurrent();expect(countText(s,"|BUDGET|")==32,"actual row budget");expect(countText(s,"|TRUNCATED|")==1,"one truncation marker per turn");++GC.game.turn;CvStackingDiagnostics::Record(1,0,"BUDGET","nextturn");expect(rows==1&&!suppressed&&slurpCurrent().find("nextturn")!=string::npos,"budget resets next turn");CvStackingDiagnostics::Record(1,0,"TEXT","a\nb\rc");expect(slurpCurrent().find("a b c")!=string::npos,"record sanitizes newlines");string longText(8000,'x');CvStackingDiagnostics::Record(1,0,"LONG","%s",longText.c_str());expect(slurpCurrent().find("[message truncated]")!=string::npos,"long formatting visibly truncated");
 fresh();CvStackingDiagnostics::SetLevel(2);string firstPrefix=prefix;unsigned int firstHash=configHash;cfg["DiagnosticsMaxFiles"]=9;expect(setting("DiagnosticsMaxFiles",8)==2,"midload raw setting changes do not bypass cached policy");for(int i=0;i<220;++i){++GC.game.turn;CvStackingDiagnostics::Record(2,0,"ROTATE","%s",longText.c_str());}expect(sequence>2,"actual byte-limit rotation");expect(string(prefix)==firstPrefix,"rotation keeps session identity");int files=0;WIN32_FIND_DATAW data;wstring pattern=wstring(directory)+wstring(firstPrefix.begin(),firstPrefix.end())+L"-*.log";HANDLE find=FindFirstFileW(pattern.c_str(),&data);if(find!=INVALID_HANDLE_VALUE){do{++files;expect(data.nFileSizeHigh==0&&data.nFileSizeLow<=65536,"each retained file respects byte cap");}while(FindNextFileW(find,&data));FindClose(find);}expect(files==2,"rolling file count bounded");char tag[64];sprintf_s(tag,"configFNV=%08X",firstHash);expect(countText(slurpCurrent(),tag)==2,"rotated headers retain fingerprint");unsigned int oldSeq=sequence;CvStackingDiagnostics::SetLevel(0);expect(output==NULL&&string(CvStackingDiagnostics::GetStatus())=="Off","off closes and displays off");CvStackingDiagnostics::SetLevel(1);expect(string(prefix)==firstPrefix&&sequence==oldSeq+1,"off/on retains session ring");
 fresh();openFailure=true;CvStackingDiagnostics::SetLevel(1);expect(failed&&output==NULL,"open failure latched");int oldOpens=opens;for(int i=0;i<8;++i)CvStackingDiagnostics::Record(1,0,"FAIL","x");expect(opens==oldOpens,"open failure does not retry spam");expect(string(CvStackingDiagnostics::GetStatus()).find("unavailable")!=string::npos,"open failure visible");openFailure=false;CvStackingDiagnostics::SetLevel(1);expect(!failed&&output!=NULL,"explicit setter retries after failure");writeFailure=true;CvStackingDiagnostics::Record(1,0,"FAIL","write");expect(failed&&output==NULL,"write failure latched and closed");writeFailure=false;
 fresh();logLocator=L"C:\\"+wstring(400,L'x')+L"\\locator.log";CvStackingDiagnostics::SetLevel(1);expect(failed&&opens==0,"oversized engine path fails before open");fresh();GetFullPathNameW(L"logs\\",MAX_PATH,directory,NULL);wcsncat_s(directory,MAX_PATH,wstring(190,L'x').c_str(),_TRUNCATE);strcpy_s(prefix,sizeof(prefix),"long-test-prefix-long-test-prefix-long-test-prefix");CvStackingDiagnostics::SetLevel(1);expect(failed&&opens==0,"filename formatting truncation fails before open");
 fresh();CvStackingDiagnostics::SetLevel(2);HANDLE t=CreateThread(NULL,0,concurrentStatus,NULL,0,NULL);for(int i=0;i<100;++i)CvStackingDiagnostics::Record(1,0,"THREAD","row=%d",i);DWORD result=1;expect(t!=NULL&&WaitForSingleObject(t,10000)==WAIT_OBJECT_0,"concurrent recursive logging lock completes");if(t){GetExitCodeThread(t,&result);CloseHandle(t);}expect(result==0,"TLS status remains valid during concurrent toggles");CvStackingDiagnostics::Reset();expect(CvStackingDiagnostics::GetLevel()==0&&prefix[0]==0&&!output,"reset restores XML default and starts new identity next use");

 fresh();cfg["DiagnosticsFlushIntervalMilliseconds"]=0;cfg["DiagnosticsFlushEveryRows"]=4;CvStackingDiagnostics::SetLevel(1);
 CvStackingDiagnostics::Record(1,0,"BUFFER","row=1");CvStackingDiagnostics::Record(1,0,"BUFFER","row=2");
 expect(countText(slurpCurrent(false),"|BUFFER|")==0&&pendingWrites==2,"bounded buffering avoids per-row disk writes");
 CvStackingDiagnostics::Record(1,0,"BUFFER","row=3");CvStackingDiagnostics::Record(1,0,"BUFFER","row=4");
 expect(countText(slurpCurrent(false),"|BUFFER|")==4&&pendingWrites==0,"row threshold flushes live-readable batch");
 CvStackingDiagnostics::Record(1,0,"BUFFER","manual");CvStackingDiagnostics::Flush();expect(slurpCurrent(false).find("manual")!=string::npos,"explicit flush works without level change");
 CvStackingDiagnostics::Record(1,0,"LONG_PLAN","critical");expect(slurpCurrent(false).find("critical")!=string::npos,"critical histories flush immediately");
 fresh();cfg["DiagnosticsImmediateFlush"]=1;CvStackingDiagnostics::SetLevel(1);CvStackingDiagnostics::Record(1,0,"BUFFER","immediate");expect(slurpCurrent(false).find("immediate")!=string::npos,"XML restores immediate crash-trace mode");
 fresh();cfg["DiagnosticsFlushEveryRows"]=100;cfg["DiagnosticsFlushIntervalMilliseconds"]=1;CvStackingDiagnostics::SetLevel(1);lastFlush=GetTickCount()-10;CvStackingDiagnostics::Record(1,0,"BUFFER","timed");expect(slurpCurrent(false).find("timed")!=string::npos,"elapsed threshold checked during record without a background thread");
 fresh();CvStackingDiagnostics::SetLevel(1);CvStackingDiagnostics::Record(1,0,"BUFFER","flush_failure");flushFailure=true;CvStackingDiagnostics::Flush();expect(failed&&!output,"flush failure disables further logging safely");flushFailure=false;
 fresh();cfg["DiagnosticsCategoryMask"]=2;CvStackingDiagnostics::SetLevel(2);CvStackingDiagnostics::Record(1,0,"PLAN","filtered");CvStackingDiagnostics::Record(1,0,"REINFORCEMENT","kept");CvStackingDiagnostics::Record(1,0,"LONG_PLAN","critical_mask");
 s=slurpCurrent();expect(s.find("filtered")==string::npos&&s.find("kept")!=string::npos&&s.find("critical_mask")!=string::npos,"category mask skips tactical rows but retains military and safety anomalies");
 expect(!CvStackingDiagnostics::EnabledCategory(2,0,"PLAN_ASSIGN"),"caller can skip disabled detail collection");
 fresh();cfg["DiagnosticsCategoryMask"]=16;CvStackingDiagnostics::SetLevel(1);CvStackingDiagnostics::Record(1,0,"PLAN_PERF","timing_only");CvStackingDiagnostics::Record(1,0,"PLAN","plan_filtered");s=slurpCurrent();expect(s.find("timing_only")!=string::npos&&s.find("plan_filtered")==string::npos,"performance-only mask keeps planner timing without tactical rows");
 fresh();cfg["DiagnosticsCategoryMask"]=4;CvStackingDiagnostics::SetLevel(1);CvStackingDiagnostics::Record(1,0,"PLAN_PERF","timing_filtered");CvStackingDiagnostics::Record(1,0,"PLAN","plan_only");s=slurpCurrent();expect(s.find("timing_filtered")==string::npos&&s.find("plan_only")!=string::npos,"tactical-only mask does not collect planner timing");
 fresh();cfg["DiagnosticsVerboseStartTurn"]=5;cfg["DiagnosticsVerboseEndTurn"]=6;CvStackingDiagnostics::SetLevel(2);expect(!CvStackingDiagnostics::Enabled(2,0)&&CvStackingDiagnostics::Enabled(1,0),"before verbose window summary remains enabled");GC.game.turn=5;expect(CvStackingDiagnostics::Enabled(2,0),"verbose starts on configured turn");GC.game.turn=6;expect(CvStackingDiagnostics::Enabled(2,0),"verbose includes last configured turn");GC.game.turn=7;expect(!CvStackingDiagnostics::Enabled(2,0),"verbose stops after configured window");
 fresh();cfg["DiagnosticsSummaryInterval"]=5;CvStackingDiagnostics::SetLevel(1);CvStackingDiagnostics::AfterPlayerUnitAI(player);expect(countText(slurpCurrent(),"|DECISION_SUMMARY|")==0,"post-AI snapshot honors summary interval");GC.game.turn=5;CvStackingDiagnostics::AfterPlayerUnitAI(player);expect(countText(slurpCurrent(),"|DECISION_SUMMARY|")==1,"post-AI snapshot emits on sample turn");
 fresh();cfg["DiagnosticsCategoryMask"]=2;CvStackingDiagnostics::SetLevel(1);CvAIOperation op;player.operations.push_back(&op);CvStackingDiagnostics::AfterPlayerUnitAI(player);s=slurpCurrent();expect(s.find("|OPERATION_STATUS|")!=string::npos&&s.find("neededBuild=2 training=1")!=string::npos,"military-only filter retains operation/production lifecycle without unit snapshots");player.operations.clear();
 fresh();CvStackingDiagnostics::Flush();expect(!output&&!opens,"manual flush never starts disabled logging");
 // Isolated actual-CRT output benchmark, not a game or whole-turn benchmark.
 double timings[2][3];LARGE_INTEGER freq;QueryPerformanceFrequency(&freq);
 for(int repeat=0;repeat<3;++repeat)for(int immediate=0;immediate<2;++immediate)
 {
  fresh();cfg["DiagnosticsMaxFileKB"]=65536;cfg["DiagnosticsMaxRowsPerTurn"]=65536;cfg["DiagnosticsImmediateFlush"]=immediate;cfg["DiagnosticsFlushIntervalMilliseconds"]=0;CvStackingDiagnostics::SetLevel(2);
  string payload(250,'x');LARGE_INTEGER start,end;QueryPerformanceCounter(&start);
  for(int i=0;i<1000;++i)CvStackingDiagnostics::Record(2,0,"BENCH","index=%d value=%s",i,payload.c_str());
  CvStackingDiagnostics::Flush();QueryPerformanceCounter(&end);timings[immediate][repeat]=(double)(end.QuadPart-start.QuadPart)/freq.QuadPart;
  expect(costs.recorded==1000&&costs.dropped==0,"benchmark retains all records");
  string bytes=slurpCurrent(false);expect(countText(bytes,"|BENCH|")==1000,"buffer mode preserves every benchmark row");
 }
 for(int mode=0;mode<2;++mode){double*a=timings[mode];if(a[0]>a[1]){double t=a[0];a[0]=a[1];a[1]=t;}if(a[1]>a[2]){double t=a[1];a[1]=a[2];a[2]=t;}if(a[0]>a[1]){double t=a[0];a[0]=a[1];a[1]=t;}}
 printf("IOBENCH bufferedMedianSeconds=%.6f immediateMedianSeconds=%.6f immediateOverBuffered=%.3f rows=1000 repeats=3\n",timings[0][1],timings[1][1],timings[1][1]/timings[0][1]);
 CvStackingDiagnostics::Reset();

 printf("diagnostics core policy regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
"""
cpp=out/'diagnostics-policy-source-test.cpp';cpp.write_text(head+actual+tail,encoding='utf-8');vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for k in ('CL','_CL_','LINK'):env.pop(k,None)
exe=out/'diagnostics-policy-source-test.exe';cmd=[str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'diagnostics-policy-source-test.obj'),'/Fe'+str(exe)]
c=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True);(out/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='');res={'source_sha256':hashlib.sha256((root/'CvGameCoreDLL_Expansion2/CvStackingDiagnostics.cpp').read_bytes()).hexdigest().upper(),'extracted_sha256':hashlib.sha256(actual.encode()).hexdigest().upper(),'compile_returncode':c.returncode,'test_returncode':r.returncode,'output':r.stdout+r.stderr,'scope':'actual logger helpers Reset/GetLevel/Enabled/GetStatus/SetLevel/Record; real VC9 CRT file IO and threads, deterministic engine/DB getters and injected failures; OnPlayerTurn/CombatScope source-reviewed only'};(out/'result.json').write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8');sys.exit(r.returncode)
