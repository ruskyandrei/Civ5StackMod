"""VC9 actual diagnostics policy/IO test; engine getters stubbed, CRT files under work only."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];out=root/'work/diagnostics-core-regression';out.mkdir(exist_ok=True);logs=out/'logs';logs.mkdir(exist_ok=True)
src=(root/'CvGameCoreDLL_Expansion2/CvStackingDiagnostics.cpp').read_text(encoding='utf-8-sig');actual=src[src.index('namespace\n'):src.index('    void OnPlayerTurn(')]+'}\n'
head=r"""
#include <cstdio>
#include <cstdarg>
#include <string>
#include <map>
#include <vector>
#include <windows.h>
#include <direct.h>
#include <share.h>
using namespace std;
typedef int PlayerTypes;
const int MAX_PLAYERS=64,NO_PLAYER=-1;
#define CURRENT_GAMECORE_VERSION "native-policy-test"
static map<string,int> cfg;static int settingsReads=0,dbReads=0,opens=0,writes=0;static bool openFailure=false,writeFailure=false;
namespace CvStacking{int GetInt(const char*n,int f){++settingsReads;map<string,int>::const_iterator i=cfg.find(n);return i==cfg.end()?f:i->second;}}
namespace Database{struct Results{int pos;Results():pos(0){}bool Step(){return pos++==0;}const char*GetText(const char*n){return n[0]=='K'?"test:key":"7";}};struct Connection{bool Execute(Results&,const char*){++dbReads;return true;}};}
static Database::Connection db;
struct Game{int turn;Game():turn(1){}int getGameTurn(){return turn;}};
struct Map{int getGridWidth(){return 80;}int getGridHeight(){return 52;}};
struct Global{Game game;Map map;Game&getGame(){return game;}Map&getMap(){return map;}Database::Connection*GetGameDatabase(){return &db;}}GC;
static wstring logLocator=L"logs\\StackingDiagnostics-path.log";
struct FILogFile{enum{kDontTimeStamp=1};const wchar_t*GetFileName(){return logLocator.c_str();}} locator;
struct LogMgr{FILogFile*GetLog(const char*,int){return &locator;}}LOGFILEMGR;
namespace CvStackingDiagnostics{void Reset();void SetLevel(int);int GetLevel();const char*GetStatus();bool Enabled(int,PlayerTypes=NO_PLAYER);void Record(int,PlayerTypes,const char*,const char*,...);}
static FILE* testOpen(const wchar_t*path,const wchar_t*mode,int sharing){++opens;if(openFailure)return NULL;return _wfsopen(path,mode,sharing);}
static int testPrint(FILE*p,const char*f,...){++writes;if(writeFailure)return -1;va_list a;va_start(a,f);int r=vfprintf(p,f,a);va_end(a);return r;}
#define _wfsopen testOpen
#define fprintf testPrint
"""
tail=r"""
#undef _wfsopen
#undef fprintf
static int checks=0,failures=0;
void expect(bool ok,const char*n){++checks;if(!ok){++failures;printf("FAIL %s\n",n);}}
string slurpCurrent(){string s;for(int i=0;i<setting("DiagnosticsMaxFiles",8);++i){wchar_t p[MAX_PATH];_snwprintf_s(p,MAX_PATH,_TRUNCATE,L"%s%S-%02d.log",directory,prefix,i);HANDLE f=CreateFileW(p,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);if(f!=INVALID_HANDLE_VALUE){char b[4096];DWORD n;while(ReadFile(f,b,sizeof b,&n,NULL)&&n)s.append(b,n);CloseHandle(f);}else if(GetLastError()!=2){static bool printed=false;if(!printed){printf("READBACK_ERROR=%lu path=%S\n",GetLastError(),p);printed=true;}}}return s;}
int countText(const string&s,const char*t){int n=0;size_t p=0;while((p=s.find(t,p))!=string::npos){++n;p+=strlen(t);}return n;}
void fresh(){CvStackingDiagnostics::Reset();cfg.clear();cfg["DiagnosticsMemoryInterval"]=0;cfg["DiagnosticsMaxFileKB"]=64;cfg["DiagnosticsMaxFiles"]=2;cfg["DiagnosticsMaxRowsPerTurn"]=32;settingsReads=dbReads=opens=writes=0;openFailure=writeFailure=false;logLocator=L"logs\\StackingDiagnostics-path.log";GC.game.turn=1;}
DWORD WINAPI concurrentStatus(LPVOID){for(int i=0;i<100;++i){CvStackingDiagnostics::SetLevel(i%3);const char*p=CvStackingDiagnostics::GetStatus();if(!p||!p[0])return 1;}return 0;}
int main(){
 fresh();CvStackingDiagnostics::Record(1,0,"TEST","off");expect(opens==0&&writes==0&&dbReads==0,"default off no file or DB scans");expect(CvStackingDiagnostics::GetLevel()==0,"default off");CvStackingDiagnostics::SetLevel(-1);CvStackingDiagnostics::SetLevel(3);expect(CvStackingDiagnostics::GetLevel()==0&&opens==0,"invalid setter ignored");
 fresh();cfg["DiagnosticsLevel"]=1;cfg["DiagnosticsPlayer"]=2;CvStackingDiagnostics::Record(1,1,"TEST","wrongplayer");expect(opens==0,"player filter suppresses file");CvStackingDiagnostics::Record(1,2,"TEST","rightplayer");expect(opens==1,"XML summary opens on first relevant event");expect(dbReads==9,"configuration scan once opening");expect(configHash!=0,"configuration fingerprint resolved");expect(slurpCurrent().find("rightplayer")!=string::npos&&slurpCurrent().find("wrongplayer")==string::npos,"filter affects actual bytes");int reads=settingsReads;CvStackingDiagnostics::Record(1,2,"TEST","again");expect(settingsReads==reads,"cached numeric settings");expect(CvStackingDiagnostics::Enabled(1,NO_PLAYER),"global memory records bypass player filter");expect(!CvStackingDiagnostics::Enabled(2,2),"summary excludes verbose");expect(GC.game.turn==1,"recording leaves game getter state unchanged");
 fresh();CvStackingDiagnostics::SetLevel(1);for(int i=0;i<40;++i)CvStackingDiagnostics::Record(1,0,"BUDGET","row=%d",i);string s=slurpCurrent();expect(countText(s,"|BUDGET|")==32,"actual row budget");expect(countText(s,"|TRUNCATED|")==1,"one truncation marker per turn");++GC.game.turn;CvStackingDiagnostics::Record(1,0,"BUDGET","nextturn");expect(rows==1&&!suppressed&&slurpCurrent().find("nextturn")!=string::npos,"budget resets next turn");CvStackingDiagnostics::Record(1,0,"TEXT","a\nb\rc");expect(slurpCurrent().find("a b c")!=string::npos,"record sanitizes newlines");string longText(8000,'x');CvStackingDiagnostics::Record(1,0,"LONG","%s",longText.c_str());expect(slurpCurrent().find("[message truncated]")!=string::npos,"long formatting visibly truncated");
 fresh();CvStackingDiagnostics::SetLevel(2);string firstPrefix=prefix;unsigned int firstHash=configHash;cfg["DiagnosticsMaxFiles"]=9;expect(setting("DiagnosticsMaxFiles",8)==2,"midload raw setting changes do not bypass cached policy");for(int i=0;i<220;++i){++GC.game.turn;CvStackingDiagnostics::Record(2,0,"ROTATE","%s",longText.c_str());}expect(sequence>2,"actual byte-limit rotation");expect(string(prefix)==firstPrefix,"rotation keeps session identity");int files=0;WIN32_FIND_DATAW data;wstring pattern=wstring(directory)+wstring(firstPrefix.begin(),firstPrefix.end())+L"-*.log";HANDLE find=FindFirstFileW(pattern.c_str(),&data);if(find!=INVALID_HANDLE_VALUE){do{++files;expect(data.nFileSizeHigh==0&&data.nFileSizeLow<=65536,"each retained file respects byte cap");}while(FindNextFileW(find,&data));FindClose(find);}expect(files==2,"rolling file count bounded");char tag[64];sprintf_s(tag,"configFNV=%08X",firstHash);expect(countText(slurpCurrent(),tag)==2,"rotated headers retain fingerprint");unsigned int oldSeq=sequence;CvStackingDiagnostics::SetLevel(0);expect(output==NULL&&string(CvStackingDiagnostics::GetStatus())=="Off","off closes and displays off");CvStackingDiagnostics::SetLevel(1);expect(string(prefix)==firstPrefix&&sequence==oldSeq+1,"off/on retains session ring");
 fresh();openFailure=true;CvStackingDiagnostics::SetLevel(1);expect(failed&&output==NULL,"open failure latched");int oldOpens=opens;for(int i=0;i<8;++i)CvStackingDiagnostics::Record(1,0,"FAIL","x");expect(opens==oldOpens,"open failure does not retry spam");expect(string(CvStackingDiagnostics::GetStatus()).find("unavailable")!=string::npos,"open failure visible");openFailure=false;CvStackingDiagnostics::SetLevel(1);expect(!failed&&output!=NULL,"explicit setter retries after failure");writeFailure=true;CvStackingDiagnostics::Record(1,0,"FAIL","write");expect(failed&&output==NULL,"write failure latched and closed");writeFailure=false;
 fresh();logLocator=L"C:\\"+wstring(400,L'x')+L"\\locator.log";CvStackingDiagnostics::SetLevel(1);expect(failed&&opens==0,"oversized engine path fails before open");fresh();GetFullPathNameW(L"logs\\",MAX_PATH,directory,NULL);wcsncat_s(directory,MAX_PATH,wstring(190,L'x').c_str(),_TRUNCATE);strcpy_s(prefix,sizeof(prefix),"long-test-prefix-long-test-prefix-long-test-prefix");CvStackingDiagnostics::SetLevel(1);expect(failed&&opens==0,"filename formatting truncation fails before open");
 fresh();CvStackingDiagnostics::SetLevel(2);HANDLE t=CreateThread(NULL,0,concurrentStatus,NULL,0,NULL);for(int i=0;i<100;++i)CvStackingDiagnostics::Record(1,0,"THREAD","row=%d",i);DWORD result=1;expect(t!=NULL&&WaitForSingleObject(t,10000)==WAIT_OBJECT_0,"concurrent recursive logging lock completes");if(t){GetExitCodeThread(t,&result);CloseHandle(t);}expect(result==0,"TLS status remains valid during concurrent toggles");CvStackingDiagnostics::Reset();expect(CvStackingDiagnostics::GetLevel()==0&&prefix[0]==0&&!output,"reset restores XML default and starts new identity next use");
 printf("diagnostics core policy regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
"""
cpp=out/'diagnostics-policy-source-test.cpp';cpp.write_text(head+actual+tail,encoding='utf-8');vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for k in ('CL','_CL_','LINK'):env.pop(k,None)
exe=out/'diagnostics-policy-source-test.exe';cmd=[str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'diagnostics-policy-source-test.obj'),'/Fe'+str(exe)]
c=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True);(out/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='');res={'source_sha256':hashlib.sha256((root/'CvGameCoreDLL_Expansion2/CvStackingDiagnostics.cpp').read_bytes()).hexdigest().upper(),'extracted_sha256':hashlib.sha256(actual.encode()).hexdigest().upper(),'compile_returncode':c.returncode,'test_returncode':r.returncode,'output':r.stdout+r.stderr,'scope':'actual logger helpers Reset/GetLevel/Enabled/GetStatus/SetLevel/Record; real VC9 CRT file IO and threads, deterministic engine/DB getters and injected failures; OnPlayerTurn/CombatScope source-reviewed only'};(out/'result.json').write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8');sys.exit(r.returncode)
