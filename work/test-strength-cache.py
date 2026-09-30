"""Exercise actual strength-cache module, keys and wrappers using native VC9.
Engine services are deterministic substitutes; combat bodies are checked byte for
byte against the pre-cache commit. This is not a whole-game speed benchmark.
"""
from pathlib import Path
import hashlib, json, os, subprocess, sys
root=Path(__file__).resolve().parents[1]
out=root/'work/strength-cache-regression';out.mkdir(exist_ok=True)
unit=(root/'CvGameCoreDLL_Expansion2/CvUnit.cpp').read_text(encoding='utf-8-sig')
header=(root/'CvGameCoreDLL_Expansion2/CvStackingStrengthCache.h').read_text()
module=(root/'CvGameCoreDLL_Expansion2/CvStackingStrengthCache.cpp').read_text()
def function(text,name):
    start=text.index(name); opening=text.index('{',start); depth=1; end=opening+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end],text[opening:end]
reference=subprocess.check_output(['git','show','c6067cda5:CvGameCoreDLL_Expansion2/CvUnit.cpp'],cwd=root).decode('utf-8-sig')
for name in ('GetGenericMeleeStrengthModifier','GetMaxRangedCombatStrength'):
    assert function(unit,'int CvUnit::'+name+'Uncached(')[1]==function(reference,'int CvUnit::'+name+'(')[1],name+' math changed'
actual_key=function(unit,'static CvStackingStrengthCache::Key MakeStackStrengthKey(')[0]
wrappers='\n'.join(function(unit,'int CvUnit::'+name+'(')[0] for name in ('GetGenericMeleeStrengthModifier','GetMaxRangedCombatStrength'))
module='\n'.join(line for line in module.splitlines() if line not in ('#include "CvGameCoreDLLPCH.h"','#include "CvStackingStrengthCache.h"','#include "LintFree.h"'))
prefix=r'''
#include <windows.h>
#include <cstdio>
#include <algorithm>
#include <map>
#include <climits>
using namespace std;
#define VALIDATE_OBJECT() ((void)0)
typedef int PlayerTypes;
struct CvPlot {int index,bonus; CvPlot(int i=0):index(i),bonus(i%13){} int GetPlotIndex()const{return index;}};
struct CvCity {int owner,id,damage,attacked;CvPlot* at;CvCity():owner(2),id(4),damage(0),attacked(0),at(NULL){}int getOwner()const{return owner;}int GetID()const{return id;}int getDamage()const{return damage;}CvPlot* plot()const{return at;}int GetNumTimesAttackedThisTurn(int)const{return attacked;}};
struct CvUnit {int owner,id,damage,hp,worldStrength;CvPlot* at;CvUnit(int i=0):owner(0),id(i),damage(0),hp(100),worldStrength(15),at(NULL){}int getOwner()const{return owner;}int GetID()const{return id;}CvPlot* plot()const{return at;}int getDamage()const{return damage;}int GetMaxHitPoints()const{return hp;}int GetNumTimesAttackedThisTurn(int)const{return damage%3;}
 int GetGenericMeleeStrengthModifier(const CvUnit*,const CvPlot*,bool,bool,const CvPlot*,bool)const;
 int GetGenericMeleeStrengthModifierUncached(const CvUnit*,const CvPlot*,bool,bool,const CvPlot*,bool)const;
 int GetMaxRangedCombatStrength(const CvUnit*,const CvCity*,bool,const CvPlot*,const CvPlot*,bool,bool,int,int)const;
 int GetMaxRangedCombatStrengthUncached(const CvUnit*,const CvCity*,bool,const CvPlot*,const CvPlot*,bool,bool,int,int)const;
};
'''
services=r'''
int meleeCalls=0,rangedCalls=0; bool invalidateDuringCompute=false;
int CvUnit::GetGenericMeleeStrengthModifierUncached(const CvUnit* other,const CvPlot* target,bool attack,bool ignore,const CvPlot* from,bool quick)const{
 ++meleeCalls;if(invalidateDuringCompute)CvStackingStrengthCache::Invalidate();if(!from)from=at;
 return worldStrength*100+owner*31+(other?other->worldStrength+other->owner*23:0)+(target?target->bonus:0)+from->bonus+(attack?17:0)+(ignore?29:0)+(quick?43:0);
}
int CvUnit::GetMaxRangedCombatStrengthUncached(const CvUnit* other,const CvCity* city,bool attack,const CvPlot* from,const CvPlot* target,bool ignore,bool quick,int extra,int extraOther)const{
 ++rangedCalls;if(invalidateDuringCompute)CvStackingStrengthCache::Invalidate();if(!from)from=at;if(!target)target=other?other->at:(city?city->at:NULL);
 const int otherHP=other?max(0,other->hp-other->damage-extraOther):0;
 return max(1,worldStrength*100+(other?other->worldStrength:0)+(city?city->owner*7+city->attacked:0)+from->bonus+(target?target->bonus:0)-(damage+extra)*5+otherHP+(attack?127:0)+(ignore?129:0)+(quick?143:0));
}
'''
tests=r'''
using namespace CvStackingStrengthCache;
int checks=0, failures=0;
void expect(const char* name,bool okay){++checks;if(!okay){++failures;if(failures<20)printf("FAIL %s\n",name);}}
unsigned int seed=0x51a5;
unsigned int randomValue(){seed=seed*1664525u+1013904223u;return seed;}
Key make(int id){Key k;for(int i=0;i<20;++i)k.values[i]=i*19;k.values[0]=id%2;k.values[2]=id;return k;}
DWORD WINAPI foreign(void*){long token;DWORD failures=0;if(Context(token))failures|=1;Scope skipped(16);if(Context(token))failures|=2;int value=0;if(Lookup(make(1),0,value))failures|=4;Store(make(1),0,333);Invalidate();return failures;}
int main(){
 expect("native x86",sizeof(void*)==4&&sizeof(long)==4);
 long token=0;int value=0;Key k=make(1);
 expect("inactive bypass",!Context(token));Store(k,token,55);expect("inactive miss",!Lookup(k,token,value));
 long scene=SceneEpoch();Invalidate();expect("scene revision readable outside cache",SceneEpoch()!=scene);
 {Scope disabled(0);expect("zero disabled",!Context(token));scene=SceneEpoch();Invalidate();expect("scene revision independent of strength setting",SceneEpoch()!=scene);}
 {Scope s(8);expect("scope available",Context(token));expect("scene revision matches cache generation",SceneEpoch()==token);expect("empty miss",!Lookup(k,token,value));Store(k,token,55);expect("repeat hit",Lookup(k,token,value)&&value==55);
  for(int i=0;i<20;++i){Key different=k;++different.values[i];expect("every word compared",!(different==k));expect("every word affects lookup",!Lookup(different,token,value));}
  {Scope nested(8);expect("nested preview bypass",!Context(token));Store(k,token,66);}
  expect("outer restored",Context(token));expect("nested results not reused",!Lookup(k,token,value));Store(k,token,77);
  HANDLE t=CreateThread(NULL,0,foreign,NULL,0,NULL);expect("foreign thread created",t!=NULL);if(t){expect("foreign thread finishes",WaitForSingleObject(t,10000)==WAIT_OBJECT_0);DWORD code=STILL_ACTIVE;GetExitCodeThread(t,&code);expect("UI thread bypasses Context",!(code&1));expect("UI search bypasses AI table",!(code&2));expect("UI thread cannot lookup",!(code&4));CloseHandle(t);}
  expect("foreign invalidation changes epoch",Context(token));expect("foreign change removes stale result",!Lookup(k,token,value));
  long old=token;Invalidate();Store(k,old,88);expect("stale compute not stored",Context(token)&&!Lookup(k,token,value));
  for(int i=0;i<12000;++i){Key next=make(i);Context(token);Store(next,token,i*7);expect("bounded FIFO finds admitted result",Lookup(next,token,value)&&value==i*7);expect("bounded FIFO memory",GetStats().entries<=8);}
  expect("FIFO actual eviction count",GetStats().evictions==11992);expect("peak bound",GetStats().peakEntries==8);
 }
 expect("scope exited",!Context(token));{Scope fresh(1);Context(token);expect("no previous search data",!Lookup(k,token,value));}
 {Scope maximum(1000000);expect("hard cap",GetStats().limit==65536);}
 CvPlot plots[13];for(int i=0;i<13;++i)plots[i]=CvPlot(i);
 CvUnit a(7),b(8);a.at=&plots[2];b.at=&plots[5];b.owner=1;
 CvCity city;city.at=&plots[7];
 {Scope s(4096);
  for(int i=0;i<18000;++i){int x=randomValue()%13,y=randomValue()%13,flags=randomValue()%8,damage=randomValue()%99,otherDamage=randomValue()%99;
   const CvUnit* other=(i%3==0)?NULL:&b;const CvCity* c=(i%4==0)?&city:NULL;const CvPlot* from=(i%5==0)?NULL:&plots[x];const CvPlot* target=(i%7==0)?NULL:&plots[y];bool attack=(flags&1)!=0,ignore=(flags&2)!=0,quick=(flags&4)!=0;
   int m=a.GetGenericMeleeStrengthModifierUncached(other,target,attack,ignore,from,quick);
   expect("melee equals uncached",a.GetGenericMeleeStrengthModifier(other,target,attack,ignore,from,quick)==m);
   int before=meleeCalls;expect("melee repeated exact context",a.GetGenericMeleeStrengthModifier(other,target,attack,ignore,from,quick)==m&&meleeCalls==before);
   int r=a.GetMaxRangedCombatStrengthUncached(other,c,attack,from,target,ignore,quick,damage,otherDamage);
   expect("ranged equals uncached",a.GetMaxRangedCombatStrength(other,c,attack,from,target,ignore,quick,damage,otherDamage)==r);
   before=rangedCalls;expect("ranged repeated exact context",a.GetMaxRangedCombatStrength(other,c,attack,from,target,ignore,quick,damage,otherDamage)==r&&rangedCalls==before);
   if(i%150==0){++a.worldStrength;Invalidate();} // Player/promotions/auras not encoded: scene change invalidates.
   if(i%91==0){a.damage=(a.damage+1)%30;b.hp=100+i%20;b.damage=i%30;}
  }
  expect("real wrappers reuse both classes",GetStats().meleeHits>18000&&GetStats().rangedHits>=18000);expect("wrapper budget",GetStats().peakEntries<=4096);
  Invalidate();Context(token);int before=meleeCalls;
  int result=a.GetGenericMeleeStrengthModifier(&b,&plots[5],true,false,NULL,false);
  expect("null source normalization",a.GetGenericMeleeStrengthModifier(&b,&plots[5],true,false,a.at,false)==result&&meleeCalls==before+1);
  before=rangedCalls;result=a.GetMaxRangedCombatStrength(&b,NULL,true,NULL,NULL,false,false,1,2);
  expect("null ranged normalization",a.GetMaxRangedCombatStrength(&b,NULL,true,a.at,b.at,false,false,1,2)==result&&rangedCalls==before+1);
  invalidateDuringCompute=true;before=rangedCalls;a.GetMaxRangedCombatStrength(&b,NULL,true,a.at,b.at,false,false,13,17);a.GetMaxRangedCombatStrength(&b,NULL,true,a.at,b.at,false,false,13,17);expect("callback-invalidated compute never reused",rangedCalls==before+2);invalidateDuringCompute=false;
 }
 // Find a genuine production-hash collision, then check full-key separation.
 {map<size_t,Key> hashes;Hash hash;bool collision=false;Key left,right;
  for(int i=0;i<200000&&!collision;++i){Key candidate=make(i);candidate.values[3]=(int)randomValue();size_t h=hash(candidate);map<size_t,Key>::iterator hit=hashes.find(h);if(hit!=hashes.end()&&!(candidate==hit->second)){left=hit->second;right=candidate;collision=true;}else hashes[h]=candidate;}
  expect("genuine hash collision fixture",collision);
  if(collision){Scope s(8);Context(token);Store(left,token,11);Store(right,token,22);expect("collision left exact",Lookup(left,token,value)&&value==11);expect("collision right exact",Lookup(right,token,value)&&value==22);}
 }
 printf("strength cache actual-source checks: %d checks, %d failures; combat bodies unchanged; engine services are substitutes\n",checks,failures);return failures?1:0;
}
'''
cpp=out/'strength-cache-test.cpp';cpp.write_text(prefix+header.replace('#pragma once','')+module+services+actual_key+wrappers+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'strength-cache-test.exe'
compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'strength-cache-test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);print(run.stdout+run.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(compile_returncode=compiled.returncode,test_returncode=run.returncode,output=run.stdout+run.stderr,module_sha256=hashlib.sha256(module.encode()).hexdigest(),key_sha256=hashlib.sha256(actual_key.encode()).hexdigest(),scope='Actual native32bit VC9 cache/keys/wrappers with deterministic engine substitutes; unchanged combat body source checked against commit c6067cda5; not a DLL/game timing test'),indent=2))
sys.exit(run.returncode)
