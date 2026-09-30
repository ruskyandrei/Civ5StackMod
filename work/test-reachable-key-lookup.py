"""Native VC9 regression for actual tactical reachable-cache lookup keys.

Extract the current key/hash and getReachablePlotsForUnit without rewriting
their bodies. Compare against the previous owning key, including forced hash
collisions, ordered duplicate IDs, borrowed-to-owned lifetime and allocations.
This tests key/cache plumbing, not game pathfinding or campaign timing.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root / "work/reachable-key-lookup-regression"
out.mkdir(exist_ok=True)
core = root / "CvGameCoreDLL_Expansion2"
header = (core / "CvTacticalAI.h").read_text(encoding="utf-8-sig")
source = (core / "CvTacticalAI.cpp").read_text(encoding="utf-8-sig")
baseline = "e831746c6237fb1407f4c7524a96ba81871bdc47"
original_header = subprocess.check_output(
    ["git", "show", baseline + ":CvGameCoreDLL_Expansion2/CvTacticalAI.h"], cwd=root
).decode("utf-8-sig")


def key_definitions(text):
    return text[text.index("struct SPathFinderStartPos\n"):text.index("struct SIntPairHash\n")]


def function(text, name):
    start = text.index(name)
    opening = text.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


implementation = key_definitions(header)
control = key_definitions(original_header).replace("SPathFinderStartPos", "OriginalSPathFinderStartPos")
lookup = function(source, "const ReachablePlots& CvBasePosition::getReachablePlotsForUnit(")
assert source.count("SPathFinderStartPos::LookupOnly()") == 3, "all three query sites must borrow"
assert source.count("gReachablePlotsLookup[SPathFinderStartPos(unit, freedPlots_r)]") == 2, "both admissions must own"

prefix = r'''
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <climits>
#include <algorithm>
#include <new>
#include <vector>
#include <unordered_map>
using namespace std;
typedef vector<int> PlotIndexContainer;
typedef vector<int> ReachablePlots;
struct SUnitStats {
 int iUnitID,iPlotIndex,iMovesLeft;
 SUnitStats(int unit=0,int plot=0,int moves=0):iUnitID(unit),iPlotIndex(plot),iMovesLeft(moves){}
};
static bool countAllocations=false;
static unsigned long allocations=0;
void* operator new(size_t size){if(countAllocations)++allocations;void* p=malloc(size?size:1);if(!p)throw bad_alloc();return p;}
void* operator new[](size_t size){if(countAllocations)++allocations;void* p=malloc(size?size:1);if(!p)throw bad_alloc();return p;}
void operator delete(void* p){free(p);}
void operator delete[](void* p){free(p);}
static int checks=0,failures=0;
void expect(const char* name,bool okay){++checks;if(!okay){++failures;if(failures<25)printf("FAIL %s\n",name);}}
'''

harness = r'''
typedef tr1::unordered_map<SPathFinderStartPos,ReachablePlots,SPathFinderStartPosHash> TCachedMovePlots;
TCachedMovePlots gReachablePlotsLookup;
struct CvBasePosition {
 struct Field {PlotIndexContainer plots;const PlotIndexContainer& read()const{return plots;}} freedPlots;
 const ReachablePlots& getReachablePlotsForUnit(const SUnitStats&)const;
};
struct CollisionHash {size_t operator()(const SPathFinderStartPos&)const{return 7;}};
typedef tr1::unordered_map<SPathFinderStartPos,int,CollisionHash> CollisionMap;
typedef tr1::unordered_map<OriginalSPathFinderStartPos,ReachablePlots,OriginalSPathFinderStartPosHash> OriginalMap;
static unsigned long randomState=88172645;
unsigned long randomValue(){randomState=randomState*1664525+1013904223;return randomState;}
PlotIndexContainer plotList(int a,int b,int c){PlotIndexContainer result;result.push_back(a);result.push_back(b);result.push_back(c);return result;}
SPathFinderStartPos copyFromLocalBorrow(){
 PlotIndexContainer local=plotList(7,7,-3);SUnitStats stats(17,29,60);
 SPathFinderStartPos borrowed(stats,local,SPathFinderStartPos::LookupOnly());
 SPathFinderStartPos owned(borrowed);return owned;
}
'''

tests = r'''
void comparisonTests(){
 SPathFinderStartPosHash hash;OriginalSPathFinderStartPosHash oldHash;
 for(int n=0;n<16000;++n){
  SUnitStats left((int)(randomValue()%13),(int)(randomValue()%41),(int)(randomValue()%180));
  SUnitStats right=left;
  PlotIndexContainer a,b;
  const int count=(int)(randomValue()%11);
  for(int i=0;i<count;++i)a.push_back((int)(randomValue()%9)-4);
  b=a;
  switch(n%8){
   case 0:right.iUnitID++;break;case 1:right.iPlotIndex--;break;case 2:right.iMovesLeft++;break;
   case 3:b.push_back(3);break;case 4:if(!b.empty())b[0]++;break;
   case 5:reverse(b.begin(),b.end());break;case 6:if(!b.empty())b.push_back(b[0]);break;
  }
  SPathFinderStartPos ownLeft(left,a),ownRight(right,b);
  SPathFinderStartPos viewLeft(left,a,SPathFinderStartPos::LookupOnly()),viewRight(right,b,SPathFinderStartPos::LookupOnly());
  OriginalSPathFinderStartPos oldLeft(left,a),oldRight(right,b);
  expect("owning hash matches original exactly",hash(ownLeft)==oldHash(oldLeft));
  expect("borrowed hash matches original exactly",hash(viewLeft)==oldHash(oldLeft));
  expect("borrowed equality matches ordered original",(viewLeft==viewRight)==(oldLeft==oldRight));
  expect("mixed equality matches ordered original",(ownLeft==viewRight)==(oldLeft==oldRight));
  expect("borrowed ordering matches original",(viewLeft<viewRight)==(oldLeft<oldRight));
  expect("mixed ordering matches original",(viewRight<ownLeft)==(oldRight<oldLeft));
  expect("lookup key retains no owned vector",viewLeft.freedPlots.empty());
 }
 SUnitStats stats(1,2,3);PlotIndexContainer a=plotList(4,4,9),b=plotList(4,9,4),c=plotList(4,9,9);
 SPathFinderStartPos ka(stats,a,SPathFinderStartPos::LookupOnly()),kb(stats,b,SPathFinderStartPos::LookupOnly()),kc(stats,c,SPathFinderStartPos::LookupOnly());
 expect("order is not canonicalized",!(ka==kb));expect("duplicate IDs remain significant",!(ka==kc));
 CollisionMap collision;collision.insert(make_pair(ka,101));collision.insert(make_pair(kb,202));collision.insert(make_pair(kc,303));
 expect("colliding ordered keys remain distinct",collision.size()==3);
 expect("collision lookup selects full first key",collision.find(ka)->second==101);
 expect("collision lookup selects full second key",collision.find(kb)->second==202);
 expect("collision lookup selects full third key",collision.find(kc)->second==303);
 PlotIndexContainer missing=plotList(9,4,4);SPathFinderStartPos absent(stats,missing,SPathFinderStartPos::LookupOnly());
 expect("hash collision cannot turn ordered miss into hit",collision.find(absent)==collision.end());
}
void lifetimeTests(){
 SUnitStats stats(17,29,60);PlotIndexContainer source=plotList(7,7,-3),expected=source,empty;
 SPathFinderStartPos view(stats,source,SPathFinderStartPos::LookupOnly());
 SPathFinderStartPos copied(view),assigned(SUnitStats(-1,-1,-1),empty);
 assigned=view;
 SPathFinderStartPos assignIntoView(stats,source,SPathFinderStartPos::LookupOnly());assignIntoView=copied;
 CollisionMap collision;collision.insert(make_pair(view,404));
 const size_t beforeHash=SPathFinderStartPosHash()(copied);
 source.assign(64,999);source.clear();PlotIndexContainer().swap(source);
 expect("copy owns borrowed values after source destruction",copied.GetFreedPlots()==expected&&copied.freedPlots==expected);
 expect("assignment owns borrowed values after source destruction",assigned.GetFreedPlots()==expected&&assigned.freedPlots==expected);
 expect("assignment clears destination borrowing",assignIntoView.GetFreedPlots()==expected&&assignIntoView.freedPlots==expected);
 expect("stored borrowed key owns ordered values",collision.begin()->first.GetFreedPlots()==expected&&collision.begin()->first.freedPlots==expected);
 expect("copy hash survives source destruction",SPathFinderStartPosHash()(copied)==beforeHash);
 expect("stored key lookup survives source destruction",collision.find(copied)!=collision.end()&&collision.find(copied)->second==404);
 SPathFinderStartPos fromLocal=copyFromLocalBorrow();expect("copy survives local borrowed list lifetime",fromLocal==copied);
 assigned=assigned;expect("owned self assignment preserves full list",assigned==copied);
 PlotIndexContainer live=plotList(4,4,9);SPathFinderStartPos selfView(stats,live,SPathFinderStartPos::LookupOnly());selfView=selfView;
 expect("borrowed self assignment remains valid during lookup",selfView.GetFreedPlots()==live&&selfView.freedPlots.empty());
 SPathFinderStartPos replacement(SUnitStats(5,6,7),plotList(8,8,8));assigned=replacement;
 expect("owning assignment replaces scalars and ordered list",assigned==replacement);
 // Owned container keys must never borrow a synchronous query, even on rehash.
 for(int i=0;i<300;++i){PlotIndexContainer transient=plotList(i,i+1,i);SUnitStats unit(i,i+2,i+3);SPathFinderStartPos query(unit,transient,SPathFinderStartPos::LookupOnly());collision.insert(make_pair(query,i));}
 collision.rehash(2048);
 for(int i=0;i<300;++i){PlotIndexContainer transient=plotList(i,i+1,i);SPathFinderStartPos query(SUnitStats(i,i+2,i+3),transient,SPathFinderStartPos::LookupOnly());expect("rehash retains independently owned keys",collision.find(query)!=collision.end()&&collision.find(query)->second==i);}
}
void lookupAndAllocationTests(){
 SUnitStats stats(42,53,120);CvBasePosition position;position.freedPlots.plots=plotList(9,2,9);
 ReachablePlots value=plotList(111,222,333);
 gReachablePlotsLookup.insert(make_pair(SPathFinderStartPos(stats,position.freedPlots.read()),value));
 expect("actual reachable lookup returns cached value",position.getReachablePlotsForUnit(stats)==value);
 expect("actual reachable miss returns empty",position.getReachablePlotsForUnit(SUnitStats(43,53,120)).empty());
 OriginalMap original;original.insert(make_pair(OriginalSPathFinderStartPos(stats,position.freedPlots.read()),value));
 volatile unsigned long checksum=0;
 allocations=0;countAllocations=true;
 for(int i=0;i<100000;++i){OriginalSPathFinderStartPos key(stats,position.freedPlots.read());checksum+=original.find(key)->second[0];}
 countAllocations=false;const unsigned long originalAllocations=allocations;
 expect("original owning lookup control detects allocation",originalAllocations>=100000);
 allocations=0;countAllocations=true;
 for(int i=0;i<100000;++i){checksum+=position.getReachablePlotsForUnit(stats)[0];checksum+=position.getReachablePlotsForUnit(SUnitStats(43,53,120)).size();SPathFinderStartPos key(stats,position.freedPlots.read(),SPathFinderStartPos::LookupOnly());checksum+=gReachablePlotsLookup.find(key)->second[1];}
 countAllocations=false;const unsigned long lookupAllocations=allocations;
 expect("300000 borrowed actual/direct hits and misses allocate nothing",lookupAllocations==0);
 expect("native lookup loops evaluated",checksum!=0);
 CvBasePosition emptyPosition;SUnitStats emptyStats(71,0,0);gReachablePlotsLookup.insert(make_pair(SPathFinderStartPos(emptyStats,emptyPosition.freedPlots.read()),value));
 expect("actual empty-list cache hit works",emptyPosition.getReachablePlotsForUnit(emptyStats)==value);
 position.freedPlots.plots.push_back(9);expect("duplicate list extension is a cache miss",position.getReachablePlotsForUnit(stats).empty());
 position.freedPlots.plots=plotList(9,9,2);expect("list reordering is a cache miss",position.getReachablePlotsForUnit(stats).empty());
 position.freedPlots.plots=plotList(9,2,9);expect("original ordered list restores exact hit",position.getReachablePlotsForUnit(stats)==value);
 printf("reachable lookup allocations: %lu borrowed vs %lu original for 300000/100000 queries\n",lookupAllocations,originalAllocations);
}
int main(){expect("native x86 VC9",sizeof(void*)==4);comparisonTests();lifetimeTests();lookupAndAllocationTests();printf("reachable key: %d checks, %d failures\n",checks,failures);return failures?1:0;}
'''

cpp = out / "reachable-key-test.cpp"
cpp.write_text(prefix + implementation + control + harness + lookup + tests, encoding="utf-8")
vc = root / "work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0"
sdk = root / "work/toolchain/sdk/windows"
env = os.environ.copy()
env["PATH"] = str(vc / "Vc7/bin") + ";" + str(vc / "Common7/IDE") + ";" + env.get("PATH", "")
env["INCLUDE"] = str(root / "work/toolchain/sdk/vc9/include") + ";" + str(sdk / "Include")
env["LIB"] = str(root / "work/toolchain/sdk/vc9/lib") + ";" + str(sdk / "Lib")
for name in ("CL", "_CL_", "LINK"):
    env.pop(name, None)
exe = out / "reachable-key-test.exe"
compiled = subprocess.run([
    str(vc / "Vc7/bin/cl.exe"), "/nologo", "/EHsc", "/MT", "/O2", "/Z7",
    "/D_SECURE_SCL=0", "/D_HAS_ITERATOR_DEBUGGING=0", str(cpp),
    "/Fo" + str(out / "reachable-key-test.obj"), "/Fe" + str(exe),
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
    "key_and_lookup_sha256": hashlib.sha256((implementation + lookup).encode()).hexdigest(),
    "original_control_commit": baseline,
    "scope": "Actual native x86 VC9 reachable key/hash and lookup, ordered collision semantics, lifetime/rehash and allocation regression; no pathfinding or DLL/game timing",
}, indent=2), encoding="utf-8")
sys.exit(run.returncode)
