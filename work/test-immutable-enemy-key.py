"""Actual-source staged enemy-key differential; --prepare-only never compiles/runs."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / 'work' / 'immutable-enemy-key-staged'
OUT = ROOT / 'work' / 'immutable-enemy-key-regression'
CONTROL = 'ee180b91d'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--prepare-only', action='store_true')
parser.add_argument('--production', action='store_true')
args = parser.parse_args()

def block(text, signature, semicolon=False):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    if semicolon:
        assert text[end] == ';'
        end += 1
    return text[start:end]

old = subprocess.check_output(['git', 'show', f'{CONTROL}:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'], cwd=ROOT).decode('utf-8')
staged = (STAGED / 'CvTacticalAI.cpp').read_text(encoding='utf-8')
new = (ROOT / 'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_text(encoding='utf-8') if args.production else staged
assert new == staged, 'Current production differs from reviewed staged candidate'
unit_header = subprocess.check_output(['git', 'show', f'{CONTROL}:CvGameCoreDLL_Expansion2/CvUnit.h'], cwd=ROOT).decode('utf-8')
values = block(unit_header, 'struct SUnitIDValueContainer', True)
proof = json.loads((STAGED / 'staging-proof.json').read_text(encoding='utf-8'))
assert proof['source_sha256'] == hashlib.sha256(old.encode()).hexdigest()
assert proof['candidate_sha256'] == hashlib.sha256(new.encode()).hexdigest()
assert proof['source_restored_byte_exact'] and not proof['production_applied']

# Complete actual storage/context/loan/key builders and scalar memo wrapper.
old_cache = old[old.index('struct StackForecastKey\n'):old.index('// Bind immutable inputs only')]
new_cache = new[new.index('struct StackForecastKey\n'):new.index('// Bind immutable inputs only')]
old_scalar = block(old, 'static int GetCachedStackDanger(')
new_scalar = block(new, 'static int GetCachedStackDanger(')
assert old_scalar == new_scalar
bind = '\tStackImmutableEnemyDamageScope immutableEnemyDamage(GetUnitDamageDealt());\n\n'
old_preferred = block(old, 'void CvTacticalPosition::getPreferredAssignmentsForUnit(')
new_preferred = block(new, 'void CvTacticalPosition::getPreferredAssignmentsForUnit(')
assert new_preferred.count(bind) == 1 and new_preferred.replace(bind, '', 1) == old_preferred
assert new_preferred.index(bind) > new_preferred.index('if (!pUnit || !assumedUnitPlot)')
assert new_preferred.index(bind) < new_preferred.index('CvTacticalPosition tempPosition;')

prefix = r'''
#define NOMINMAX
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <windows.h>
#include <vector>
#include <deque>
#include <map>
#include <unordered_map>
#include <algorithm>
#include <utility>
#include <cstdio>
#include <cstdlib>
#include <climits>
#include <new>
static size_t allocations=0;
void* operator new(size_t n)throw(std::bad_alloc){++allocations;void*p=malloc(n?n:1);if(!p)throw std::bad_alloc();return p;}
void operator delete(void*p)throw(){free(p);}
using namespace std;
namespace CvStackingStrengthCache{
 static volatile LONG epoch=1;
 long SceneEpoch(){return InterlockedCompareExchange(&epoch,0,0);}
 void Invalidate(){InterlockedIncrement(&epoch);}
}
typedef int PlayerTypes;typedef int TeamTypes;
const int TACTSIM_MAX_UNITS=13;
struct Storage{int getSizeLimit()const{return 6000;}}gTactPosStorage;
struct CvUnit{int id,owner;CvUnit(int i=0,int o=0):id(i),owner(o){}int GetID()const{return id;}int getOwner()const{return owner;}};
struct CvCity{int protection;CvCity(int p=0):protection(p){}};
struct CvPlot{int index;CvCity*city;CvPlot(int i=0):index(i),city(NULL){}int GetPlotIndex()const{return index;}bool isCity()const{return city!=NULL;}CvCity*getPlotCity()const{return city;}};
namespace CvStacking{enum HotSettingKey{HOT_DefenderSelectionEnabled};bool IsEnabled(){return true;}int GetInt(const char*,int d){return d;}int GetIntByKey(HotSettingKey,int d){return d;}int GetCityProtection(const CvCity*c){return c?c->protection:0;}}
namespace CvStackingDiagnostics{
 enum{PLAN_DANGER_KEY=1,PLAN_DANGER_LEAF=2};
 struct PlanSampleScope{PlanSampleScope(int,bool=true){}void Finish(){}};
}
'''

services = r'''
struct CvDangerPlots{
 vector<int>ids;bool metadata,dirty,sourceInvalidate,leafInvalidate,fixed;
 int metadataCalls,leafCalls,updates;
 CvDangerPlots():metadata(true),dirty(false),sourceInvalidate(false),leafInvalidate(false),fixed(false),metadataCalls(0),leafCalls(0),updates(0){}
 const vector<int>*GetStackDangerDamageIDs(const CvPlot&){
  ++metadataCalls;
  if(dirty){++updates;dirty=false;ids.clear();ids.push_back(-6);ids.push_back(42);CvStackingStrengthCache::Invalidate();}
  if(sourceInvalidate){sourceInvalidate=false;CvStackingStrengthCache::Invalidate();}
  return metadata?&ids:NULL;
 }
 bool TryGetFixedStackDanger(const CvPlot&,const CvUnit*,int&out){if(!fixed)return false;out=31;return true;}
 int GetStackDanger(const CvPlot&,const CvUnit*u,const vector<const CvUnit*>&c,const SUnitIDValueContainer&f,const SUnitIDValueContainer&e){
  ++leafCalls;unsigned int v=37u+(unsigned int)u->id+f.GetValue(u->id);
  for(size_t i=0;i<c.size();++i)if(c[i])v=v*33u+(unsigned int)c[i]->id+(unsigned int)f.GetValue(c[i]->id);
  for(SUnitIDValueContainer::const_iterator it=e.begin();it!=e.end();++it){SUnitIDValueContainer::value_type p=*it;if(p.second&&(!metadata||binary_search(ids.begin(),ids.end(),p.first)))v+=((unsigned int)p.first*17u)^(unsigned int)p.second;}
  if(leafInvalidate){leafInvalidate=false;CvStackingStrengthCache::Invalidate();}
  return (int)(v&0x7fffffffu);
 }
};
struct Player{CvDangerPlots danger;CvDangerPlots*GetDangerPlots(){return &danger;}}players[3];
#define GET_PLAYER(x) players[x]
'''

namespace_stub = r'''
static size_t sortCalls=0;
template<class Iter>void FixtureSort(Iter b,Iter e){++sortCalls;std::sort(b,e);}
struct StackDangerOutcomeBatch{
 bool TryGet(const CvUnit*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&,int&){return false;}
};
'''
pieces = [prefix, values, services]
for name, cache, scalar in (('Original', old_cache, old_scalar), ('Candidate', new_cache, new_scalar)):
    # Instrument std::sort calls only; no complete body statement is removed.
    pieces.append('namespace ' + name + '{\n' + namespace_stub + cache.replace('std::sort(', 'FixtureSort(') + scalar + '\n}\n')

tests = r'''
static int checks=0,failures=0;
static void Expect(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<24)printf("FAIL %s\n",n);}}
static unsigned int seed=7329;static unsigned int Next(){seed=1664525u*seed+1013904223u;return seed;}
static void IDs(int count){players[0].danger.ids.clear();for(int i=0;i<count;++i)players[0].danger.ids.push_back((int)(Next()%81)-40);sort(players[0].danger.ids.begin(),players[0].danger.ids.end());players[0].danger.ids.erase(unique(players[0].danger.ids.begin(),players[0].danger.ids.end()),players[0].danger.ids.end());}
static void SameProjected(const SUnitIDValueContainer&damage,const CvUnit&u,const CvPlot&p,const vector<const CvUnit*>&members,const SUnitIDValueContainer&friendly,bool canonical){
 Original::StackForecastKey old;Candidate::StackForecastKey current;
 old.state.push_back(999);current.state.push_back(999);
 Original::AppendStackCandidates(old,members,friendly,canonical);Candidate::AppendStackCandidates(current,members,friendly,canonical);
 int before=players[u.owner].danger.metadataCalls;
 Original::AppendStackDamageProjected(old,damage,&u,&p);
 Candidate::AppendStackDamageProjected(current,damage,&u,&p);
 Expect("actual projected complete key exact",old.state==current.state);
 Expect("fresh metadata obtained independently eachquery",players[u.owner].danger.metadataCalls==before+2);
}
static SUnitIDValueContainer*foreignDamage=NULL;static CvUnit*foreignUnit=NULL;static CvPlot*foreignPlot=NULL;
static DWORD WINAPI Foreign(void*){
 Candidate::StackForecastKey current;Candidate::AppendStackDamageProjected(current,*foreignDamage,foreignUnit,foreignPlot);
 Candidate::StackImmutableEnemyDamageScope foreign(*foreignDamage);
 return foreign.registered||foreign.borrowed?1:0;
}
int main(){
 Expect("native VC9 x86 fixture",sizeof(void*)==4&&sizeof(size_t)==4);
 CvUnit unit(12,0),a(1,0),b(2,0);CvPlot plot(4);CvCity city(37);
 vector<const CvUnit*>members;members.push_back(&b);members.push_back(NULL);members.push_back(&a);members.push_back(&b);
 SUnitIDValueContainer friendly;friendly.SetValue(1,4);friendly.SetValue(2,17);
 for(int trial=0;trial<1200;++trial){
  SUnitIDValueContainer damage;for(int i=0;i<64;++i)damage.SetValue((int)(Next()%81)-40,(int)(Next()%251)-100);
  if(trial%7==0){damage.m_bHasValue=true;damage.m_aExtraStorage.push_back(make_pair(7,13));damage.m_aExtraStorage.push_back(make_pair(7,-11));}
  Original::StackForecastScope oldScene;Candidate::StackForecastScope scene;
  Candidate::StackImmutableEnemyDamageScope bound(damage);
  Expect("holder registered lexical ownedscene",bound.registered&&bound.borrowed&&!bound.ready);
  for(int i=0;i<11;++i){IDs(i*3);players[0].danger.metadata=i%4!=0;plot.city=i%3==0?&city:NULL;SameProjected(damage,unit,plot,members,friendly,!plot.isCity());}
  Expect("retained scratch bounded",Candidate::gStackImmutableEnemyDamageScratch.capacity()*sizeof(pair<int,int>)<=Candidate::gStackKeyPayloadLimit);
 }
 Expect("search releases dedicated scratch",Candidate::gStackImmutableEnemyDamageScratch.capacity()==0&&!Candidate::gStackImmutableEnemyDamageScratchBusy&&Candidate::gStackImmutableEnemyDamageScope==NULL);
 {
  SUnitIDValueContainer damage;damage.SetValue(-6,12);damage.SetValue(42,19);damage.SetValue(7,25);
  Original::StackForecastScope oldScene;Candidate::StackForecastScope scene;Candidate::StackImmutableEnemyDamageScope bound(damage);
  players[0].danger.metadata=true;players[0].danger.ids.clear();players[0].danger.ids.push_back(7);
  SameProjected(damage,unit,plot,members,friendly,true);
  const vector<int>*sameVector=&players[0].danger.ids;players[0].danger.ids.clear();players[0].danger.ids.push_back(-6);players[0].danger.ids.push_back(42);
  SameProjected(damage,unit,plot,members,friendly,true);Expect("source IDs changed in samevector",sameVector==&players[0].danger.ids);
  CvUnit otherOwner(12,1);players[1].danger.ids.push_back(42);SameProjected(damage,otherOwner,plot,members,friendly,true);
  SUnitIDValueContainer temporary=damage;temporary.SetValue(42,99);Candidate::StackForecastKey probe;
  Expect("different temporary ledger cannotreuse",!Candidate::AppendImmutableEnemyDamage(probe,temporary,&players[0].danger.ids));
  SameProjected(temporary,unit,plot,members,friendly,true);temporary.clear();temporary.SetValue(-6,-100);
  SameProjected(temporary,unit,plot,members,friendly,true);
  {Candidate::StackImmutableEnemyDamageScope child(temporary);Expect("busy nested helper loan bypasses",child.registered&&!child.borrowed);SameProjected(damage,unit,plot,members,friendly,true);}
  Expect("outer lexical loan restored",Candidate::gStackImmutableEnemyDamageScope==&bound&&Candidate::gStackImmutableEnemyDamageScratchBusy);
  {Candidate::StackForecastPairQuery pairs;Expect("shared membership sort loan remains available",pairs.borrowed);}
  {Candidate::StackForecastScope nested;Candidate::StackImmutableEnemyDamageScope child(damage);Expect("nested search holder disabled",!child.registered&&!child.borrowed);SameProjected(damage,unit,plot,members,friendly,true);}
  probe.state.clear();Expect("nested invalidation cancels oldimmutable loan",!Candidate::AppendImmutableEnemyDamage(probe,damage,&players[0].danger.ids));
 }
 {
  SUnitIDValueContainer damage;damage.SetValue(-6,12);damage.SetValue(42,19);
  Candidate::StackForecastScope scene;Candidate::StackImmutableEnemyDamageScope bound(damage);
  Candidate::StackForecastKey key;players[0].danger.metadata=true;players[0].danger.ids.clear();players[0].danger.ids.push_back(42);
  Candidate::AppendStackDamageProjected(key,damage,&unit,&plot);const unsigned long revision=Candidate::gStackForecastRevision;
  players[0].danger.dirty=true;key.state.clear();Candidate::AppendStackDamageProjected(key,damage,&unit,&plot);
  Expect("dirty refresh observed and holder canceled",players[0].danger.updates>0&&Candidate::gStackForecastRevision!=revision);
  Expect("new dirty source rows reflected",key.state.size()==5&&key.state[1]==-6&&key.state[2]==12&&key.state[3]==42&&key.state[4]==19);
 }
 {
  SUnitIDValueContainer damage;for(int i=0;i<80;++i)damage.SetValue(i,i+1);
  Original::StackForecastScope oldScene;Candidate::StackForecastScope scene;Candidate::gStackKeyPayloadLimit=32;
  Candidate::StackImmutableEnemyDamageScope bound(damage);IDs(15);players[0].danger.metadata=true;
  SameProjected(damage,unit,plot,members,friendly,true);Expect("oversized fragment fallsback",bound.oversized&&!bound.ready&&Candidate::gStackImmutableEnemyDamageScratch.empty());
 }
 {
  SUnitIDValueContainer damage;damage.SetValue(7,11);Candidate::StackForecastScope scene;Candidate::StackImmutableEnemyDamageScope bound(damage);
  Candidate::StackForecastKey key;players[0].danger.fixed=true;
  int before=players[0].danger.metadataCalls;int result=Candidate::GetCachedStackDanger(&unit,&plot,members,friendly,damage);
  Expect("fixedhazard nofragment/source fetch",result==31&&!bound.ready&&players[0].danger.metadataCalls==before);
  players[0].danger.fixed=false;
  foreignDamage=&damage;foreignUnit=&unit;foreignPlot=&plot;HANDLE thread=CreateThread(NULL,0,Foreign,NULL,0,NULL);Expect("foreign test thread created",thread!=NULL);
  if(thread){Expect("foreign test thread finishes",WaitForSingleObject(thread,10000)==WAIT_OBJECT_0);DWORD rc=~0u;GetExitCodeThread(thread,&rc);Expect("foreign holder cannotread orborrow owner scratch",rc==0);CloseHandle(thread);}
  Expect("foreign call preserves outerloan",Candidate::gStackImmutableEnemyDamageScope==&bound&&Candidate::gStackImmutableEnemyDamageScratchBusy&&!bound.ready);
 }
 {
  SUnitIDValueContainer damage;for(int i=0;i<23;++i)damage.SetValue(i,i+2);players[0].danger.ids.clear();for(int i=0;i<23;++i)players[0].danger.ids.push_back(i);players[0].danger.metadata=true;
  Original::StackForecastScope oldScene;Candidate::StackForecastScope scene;Candidate::StackImmutableEnemyDamageScope bound(damage);
  size_t oldSort=Original::sortCalls,newSort=Candidate::sortCalls;int oldMiss=0,newMiss=0;
  for(int i=0;i<1100;++i){int leaf=players[0].danger.leafCalls;int oldValue=Original::GetCachedStackDanger(&unit,&plot,members,friendly,damage);oldMiss+=players[0].danger.leafCalls-leaf;
   leaf=players[0].danger.leafCalls;int value=Candidate::GetCachedStackDanger(&unit,&plot,members,friendly,damage);newMiss+=players[0].danger.leafCalls-leaf;
   Expect("actual memo result and key admission equal",oldValue==value&&Original::gStackDangerForecasts.size()==Candidate::gStackDangerForecasts.size());}
  Expect("same firstmiss and warmed hits",oldMiss==1&&newMiss==1&&Original::gStackDangerHits==Candidate::gStackDangerHits);
  Expect("repeat enemies sortonce no query sortclone",Original::sortCalls-oldSort==2200&&Candidate::sortCalls-newSort==1101);
  size_t allocationBefore=allocations;for(int i=0;i<1000;++i)Candidate::GetCachedStackDanger(&unit,&plot,members,friendly,damage);
  Expect("warm repeated key path no allocation",allocations==allocationBefore);
  printf("workcount repeated1100 queries: original sorts%u, candidate sorts%u; no native speed claim\n",(unsigned)(Original::sortCalls-oldSort),(unsigned)(Candidate::sortCalls-newSort-1000));
 }
 {
  SUnitIDValueContainer damage;damage.SetValue(42,19);players[0].danger.ids.clear();players[0].danger.ids.push_back(42);players[0].danger.metadata=true;
  Candidate::StackForecastScope scene;Candidate::StackImmutableEnemyDamageScope bound(damage);
  players[0].danger.sourceInvalidate=true;int value=Candidate::GetCachedStackDanger(&unit,&plot,members,friendly,damage);
  Expect("post-key scenechange no stale admission",value>=0&&Candidate::gStackDangerForecasts.empty()&&!bound.ready);
  players[0].danger.leafInvalidate=true;value=Candidate::GetCachedStackDanger(&unit,&plot,members,friendly,damage);
  Expect("post-leaf scenechange no stale admission",value>=0&&Candidate::gStackDangerForecasts.empty());
 }
 printf("actual immutable enemy-key differential: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
fixture = '\n'.join(pieces) + tests
OUT.mkdir(exist_ok=True)
(OUT / 'test.cpp').write_text(fixture, encoding='utf-8')
scaffold = {
    'control': CONTROL, 'production_applied': args.production,
    'fixture_sha256': hashlib.sha256(fixture.encode()).hexdigest(),
    'candidate_sha256': hashlib.sha256(new.encode()).hexdigest(),
    'source_scalar_wrapper_byte_exact': old_scalar == new_scalar,
    'source_preferred_only_lexical_holder': True,
    'scope': 'Complete actual old/staged forecast context/storage/key builders and unchanged scalar wrapper; actual value container; deterministic danger/source services; VC9 x86, no game.',
    'compiled': False,
}
(OUT / 'scaffold.json').write_text(json.dumps(scaffold, indent=2) + '\n', encoding='utf-8')
if args.prepare_only:
    print(json.dumps(scaffold))
    raise SystemExit(0)

vc = ROOT / 'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
sdk = ROOT / 'work/toolchain/sdk/windows'
env = os.environ.copy()
env['PATH'] = str(vc/'Vc7/bin') + ';' + str(vc/'Common7/IDE') + ';' + env.get('PATH', '')
env['INCLUDE'] = str(ROOT/'work/toolchain/sdk/vc9/include') + ';' + str(sdk/'Include')
env['LIB'] = str(ROOT/'work/toolchain/sdk/vc9/lib') + ';' + str(sdk/'Lib')
for key in ('CL', '_CL_', 'LINK'):
    env.pop(key, None)
exe = OUT / 'test.exe'
compiled = subprocess.run([str(vc/'Vc7/bin/cl.exe'), '/nologo', '/EHsc', '/MT', '/O2', '/Z7', str(OUT/'test.cpp'), '/Fo'+str(OUT/'test.obj'), '/Fe'+str(exe)], cwd=OUT, env=env, capture_output=True, text=True, timeout=60)
(OUT / 'compile.log').write_text(compiled.stdout+compiled.stderr, encoding='utf-8')
if compiled.returncode:
    print(compiled.stdout+compiled.stderr)
    raise SystemExit(compiled.returncode)
run = subprocess.run([str(exe)], cwd=OUT, capture_output=True, text=True, timeout=60)
print(run.stdout+run.stderr, end='')
report = dict(scaffold, compiled=True, returncode=run.returncode, output=run.stdout+run.stderr)
(OUT / 'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
raise SystemExit(run.returncode)
