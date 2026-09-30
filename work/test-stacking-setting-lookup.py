"""Compile the real stacking settings loader/lookup with native x86 VC9.

Database services are deterministic substitutes, including row text that is
replaced at every Step(). This validates ownership, defaults, clamps and cache
lifecycle; allocation counts cover lookup only, not DLL/game timing.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root / "work/stacking-setting-lookup-regression"
out.mkdir(exist_ok=True)
source = (root / "CvGameCoreDLL_Expansion2/CvStackingRules.cpp").read_text(encoding="utf-8-sig")


def function(text, name):
    start = text.index(name)
    opening = text.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


# Keep the actual defaults, map type, loader and reset/lookup bodies verbatim.
implementation = source[source.index("namespace\n{"):source.index("\tbool Lookup(")] + "}\n"
implementation += "namespace CvStacking {\n"
implementation += function(source, "void ResetCache()") + "\n"
implementation += function(source, "int GetInt(") + "\n}\n"

prefix = r'''
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cstdarg>
#include <cstring>
#include <string>
#include <vector>
#include <map>
#include <climits>
#include <algorithm>
#include <new>
using namespace std;
static const int MAX_PLAYERS = 64;
static bool countAllocations = false;
static unsigned long allocations = 0;
void* operator new(size_t size) {if(countAllocations)++allocations;void* p=malloc(size?size:1);if(!p)throw bad_alloc();return p;}
void* operator new[](size_t size) {if(countAllocations)++allocations;void* p=malloc(size?size:1);if(!p)throw bad_alloc();return p;}
void operator delete(void* p) {free(p);}
void operator delete[](void* p) {free(p);}
static int logCount=0, diagnosticsResets=0, aiResets=0;
static void fixtureLog(const char*, ...) {++logCount;}
#define CUSTOMLOG fixtureLog
namespace CvStackingDiagnostics {void Reset(){++diagnosticsResets;}}
namespace CvStackingAI {void Reset(){++aiResets;}}
struct CvString: string {
 void Format(const char* format, ...) {char buffer[4096];va_list args;va_start(args,format);vsprintf_s(buffer,sizeof(buffer),format,args);va_end(args);assign(buffer);}
};
namespace Database {
 struct Row {string name;int value;Row(const string& n="",int v=0):name(n),value(v){}};
 struct Results {
  vector<Row> rows;size_t next;string rowText;int rowValue;
  Results():next(0),rowValue(0){}
  bool Step(){rowText.assign(128,'!');if(next>=rows.size())return false;rowText=rows[next].name;rowValue=rows[next].value;++next;return true;}
  const char* GetText(const char*){return rowText.c_str();}
  int GetInt(const char*){return rowValue;}
 };
 struct Connection {
  bool schema,failSettings;int executes;vector<Row> settings;
  Connection():schema(true),failSettings(false),executes(0){}
  bool Execute(Results& result,const char* query){++executes;
   if(strstr(query,"sqlite_master")){if(schema)result.rows.push_back(Row("Stacking_Settings"));return true;}
   if(strstr(query,"SELECT Name, Value FROM Stacking_Settings")){if(failSettings)return false;result.rows=settings;return true;}
   return true;
  }
 };
}
struct Globals {Database::Connection* database;Globals():database(NULL){}Database::Connection* GetGameDatabase(){return database;}} GC;
'''

tests = r'''
static int checks=0,failures=0;
void expect(const char* name,bool okay){++checks;if(!okay){++failures;if(failures<25)printf("FAIL %s\n",name);}}
static const size_t settingCount=sizeof(SETTINGS)/sizeof(SETTINGS[0]);
void checkLiteralOwnership(){
 expect("map holds one row per known setting",Cache().settings.size()==settingCount);
 for(SettingMap::const_iterator it=Cache().settings.begin();it!=Cache().settings.end();++it){bool persistent=false;
  for(size_t i=0;i<settingCount;++i)if(it->first==SETTINGS[i].name){persistent=true;break;}
  expect("retained key is process-lifetime SETTINGS literal",persistent);
 }
}
void checkAllValues(int mode){
 for(size_t i=0;i<settingCount;++i){string copy(SETTINGS[i].name);const int expected=mode<0?SETTINGS[i].minimum:mode>0?SETTINGS[i].maximum:SETTINGS[i].value;
  expect("content-equal caller differs in pointer",copy.c_str()!=SETTINGS[i].name);
  expect("actual GetInt exact value",CvStacking::GetInt(copy.c_str(),-937)==expected);
 }
}
int main(){
 expect("native x86 VC9",sizeof(void*)==4);
 expect("no database yields fallback",CvStacking::GetInt("DefenderSelectionEnabled",-33)==-33);
 expect("no database stays retryable",!Cache().loaded);
 expect("null name gives its fallback",CvStacking::GetInt(NULL,72)==72);
 Database::Connection db;GC.database=&db;
 checkAllValues(0);checkLiteralOwnership();
 expect("empty unknown fallback",CvStacking::GetInt("",10)==10);
 expect("case remains significant",CvStacking::GetInt("defenderselectionenabled",11)==11);
 expect("long unknown fallback",CvStacking::GetInt("NotAnExistingStackingSettingWithALongName",12)==12);
 expect("non-ASCII unknown fallback",CvStacking::GetInt("\xc3\xa9" "UnknownSetting",13)==13);
 const int queriesBefore=db.executes;for(int i=0;i<100;++i)CvStacking::GetInt("MaximumCapacity",-1);
 expect("loaded cache avoids database repeat",db.executes==queriesBefore);
 for(int mode=-1;mode<=1;mode+=2){
  db.settings.clear();for(size_t i=0;i<settingCount;++i)db.settings.push_back(Database::Row(string(SETTINGS[i].name),mode<0?INT_MIN:INT_MAX));
  db.settings.push_back(Database::Row("UnknownDatabaseSetting",87));CvStacking::ResetCache();checkAllValues(mode);checkLiteralOwnership();
  expect("unknown DB setting ignored",CvStacking::GetInt("UnknownDatabaseSetting",-19)==-19);
 }
 // New game/database reset must replace values and discard every retained node.
 db.settings.clear();db.settings.push_back(Database::Row("AITacticalStrengthCacheEntries",321));CvStacking::ResetCache();
 expect("new configured value",CvStacking::GetInt("AITacticalStrengthCacheEntries",-1)==321);checkLiteralOwnership();
 db.settings[0].name.assign(256,'?');db.settings.clear();
 expect("row buffers and DB rows no longer needed",CvStacking::GetInt("AITacticalStrengthCacheEntries",-1)==321);
 CvStacking::ResetCache();checkAllValues(0);checkLiteralOwnership();
 db.failSettings=true;CvStacking::ResetCache();checkAllValues(0);db.failSettings=false;
 // Missing schema disables only Enabled; other queries retain caller fallbacks.
 db.schema=false;CvStacking::ResetCache();
 expect("missing schema disables feature",CvStacking::GetInt("Enabled",77)==0);
 expect("missing schema other caller fallback",CvStacking::GetInt("MaximumCapacity",78)==78);
 expect("missing schema null fallback",CvStacking::GetInt(NULL,79)==79);
 expect("missing schema holds one literal",Cache().settings.size()==1 && strcmp(Cache().settings.begin()->first,"Enabled")==0);
 db.schema=true;expect("schema appearance needs explicit reset",CvStacking::GetInt("MaximumCapacity",80)==80);
 CvStacking::ResetCache();checkAllValues(0);checkLiteralOwnership();
 expect("reset keeps related lifecycle hooks",diagnosticsResets==aiResets&&aiResets>=7);
 // A reference string-keyed map checks all lookup semantics and proves our
 // allocation counter detects the original temporary long-string lookup.
 map<string,int> reference;for(size_t i=0;i<settingCount;++i)reference[SETTINGS[i].name]=SETTINGS[i].value;
 for(size_t i=0;i<settingCount;++i){string copy(SETTINGS[i].name);expect("matches original content-keyed result",CvStacking::GetInt(copy.c_str(),-1)==reference.find(copy.c_str())->second);}
 const char* longName="AITacticalStrengthCacheEntries";volatile unsigned long checksum=0;
 allocations=0;countAllocations=true;for(int i=0;i<100000;++i)checksum+=reference.find(longName)->second;countAllocations=false;
 const unsigned long referenceAllocations=allocations;expect("counter observes original temporary allocations",referenceAllocations>=100000);
 allocations=0;countAllocations=true;for(int i=0;i<100000;++i){checksum+=CvStacking::GetInt(longName,-1);checksum+=CvStacking::GetInt("NotAnExistingStackingSettingWithALongName",17);checksum+=CvStacking::GetInt(NULL,19);}countAllocations=false;
 const unsigned long lookupAllocations=allocations;expect("300000 actual GetInt calls allocate no heap storage",lookupAllocations==0);
 allocations=0;countAllocations=true;for(int repeat=0;repeat<100;++repeat)for(size_t i=0;i<settingCount;++i)checksum+=CvStacking::GetInt(SETTINGS[i].name,-1);countAllocations=false;
 expect("every known setting allocates no lookup storage",allocations==0);
 expect("lookups evaluated",checksum!=0);
 printf("stacking settings actual-source checks: %d checks, %d failures; lookup allocations %lu vs %lu reference; %u known settings; database services substituted\n",checks,failures,lookupAllocations,referenceAllocations,(unsigned int)settingCount);
 return failures?1:0;
}
'''

cpp = out / "stacking-setting-lookup-test.cpp"
cpp.write_text(prefix + implementation + tests, encoding="utf-8")
vc = root / "work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0"
sdk = root / "work/toolchain/sdk/windows"
env = os.environ.copy()
env["PATH"] = str(vc / "Vc7/bin") + ";" + str(vc / "Common7/IDE") + ";" + env.get("PATH", "")
env["INCLUDE"] = str(root / "work/toolchain/sdk/vc9/include") + ";" + str(sdk / "Include")
env["LIB"] = str(root / "work/toolchain/sdk/vc9/lib") + ";" + str(sdk / "Lib")
for name in ("CL", "_CL_", "LINK"):
    env.pop(name, None)
exe = out / "stacking-setting-lookup-test.exe"
compiled = subprocess.run([
    str(vc / "Vc7/bin/cl.exe"), "/nologo", "/EHsc", "/MT", "/O2", "/Z7",
    "/D_SECURE_SCL=0", "/D_HAS_ITERATOR_DEBUGGING=0", str(cpp),
    "/Fo" + str(out / "stacking-setting-lookup-test.obj"), "/Fe" + str(exe),
], cwd=out, env=env, capture_output=True, text=True, timeout=60)
(out / "compile.log").write_text(compiled.stdout + compiled.stderr, encoding="utf-8")
if compiled.returncode:
    print(compiled.stdout + compiled.stderr)
    sys.exit(compiled.returncode)
run = subprocess.run([str(exe)], cwd=out, env=env, capture_output=True, text=True, timeout=60)
print(run.stdout + run.stderr, end="")
(out / "result.json").write_text(json.dumps({
    "compile_returncode": compiled.returncode,
    "test_returncode": run.returncode,
    "output": run.stdout + run.stderr,
    "implementation_sha256": hashlib.sha256(implementation.encode()).hexdigest(),
    "scope": "Actual native x86 VC9 settings data, loader, reset and lookup with deterministic database services; lookup heap-allocation regression, not DLL/game timing",
}, indent=2), encoding="utf-8")
sys.exit(run.returncode)
