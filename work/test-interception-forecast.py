"""Run the actual extracted CvDangerPlots interception helpers with deterministic engine stubs.
This compiles only a work-directory test executable, never the VP DLL or a game process.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[1]
work=root/'work'/'interception-regression';work.mkdir(exist_ok=True)
source=(root/'CvGameCoreDLL_Expansion2/CvDangerPlots.cpp').read_text(encoding='utf-8-sig')
start=source.index('static int StackAirStrikeChance(')
end=source.index('// City and occupant forecasts must share',start)
actual=source[start:end]
prefix=r'''
#include <vector>
#include <map>
#include <algorithm>
#include <climits>
#include <cstdio>
#include <cstdlib>
using namespace std;
typedef __int64 int64;
typedef int PlayerTypes;
enum {DOMAIN_LAND=0,DOMAIN_AIR=1,DOMAIN_SEA=2};
#define GD_INT_GET(x) 2400
struct CvSeeder {};
struct SUnitIDValueContainer { map<int,int> data; int GetValue(int id)const{map<int,int>::const_iterator i=data.find(id);return i==data.end()?0:i->second;} void ChangeValue(int id,int n){data[id]+=n;} };
struct CvPlot {
 int x,y,owner; CvPlot(int xx=0,int yy=0,int p=0):x(xx),y(yy),owner(p){}
 bool isOwned()const{return owner>=0;}int getOwner()const{return owner;}
 bool IsFriendlyTerritory(int p)const{return owner==p;}
};
static int plotDistance(const CvPlot&a,const CvPlot&b){return abs(a.x-b.x)+abs(a.y-b.y);}
struct CvUnit {
 int id,owner,domain,hp,maxHP,chance,evasion,attempts,made,range,strength,modifier,defenseModifier;bool alive,delayed,active,invisible;CvPlot* location;
 CvUnit(int i,int o,CvPlot*p):id(i),owner(o),domain(DOMAIN_LAND),hp(100),maxHP(100),chance(100),evasion(0),attempts(1),made(0),range(5),strength(100),modifier(0),defenseModifier(0),alive(true),delayed(false),active(true),invisible(false),location(p){}
 int GetID()const{return id;}int getOwner()const{return owner;}int getDomainType()const{return domain;}
 bool IsDead()const{return !alive;}bool isDelayedDeath()const{return delayed;}bool canInterceptNow()const{return active&&made<attempts;}
 bool isInvisible(int,bool,bool)const{return invisible;}int GetCurrHitPoints()const{return hp;}int GetMaxHitPoints()const{return maxHP;}
 int GetNumInterceptions()const{return attempts;}int getMadeInterceptionCount()const{return made;}CvPlot*plot()const{return location;}
 int GetAirInterceptRange()const{return range;}int getInterceptChance()const{return chance;}int evasionProbability()const{return evasion;}
 int GetInterceptionCombatModifier()const{return modifier;}int GetInterceptionDefenseDamageModifier()const{return defenseModifier;}
 int GetMaxRangedCombatStrength(const CvUnit*,const void*,bool,const CvPlot*,const CvPlot*,bool,bool,int extra=0,int=0)const{return max(1,strength-extra);}
 int GetMaxAttackStrength(const CvPlot*,const CvPlot*,const CvUnit*,bool,bool,int extra=0,int=0)const{return max(1,strength-extra);}
};
struct CvPlayer {
 int id;vector<int>enemies;vector<pair<int,int> >possible;map<int,CvUnit*>units;
 int GetID()const{return id;}int getTeam()const{return id;}bool IsAtWarWith(int p)const{return find(enemies.begin(),enemies.end(),p)!=enemies.end();}
 const vector<int>&GetPlayersAtWarWith()const{return enemies;}const vector<pair<int,int> >&GetPossibleInterceptors()const{return possible;}
 const CvUnit*getUnit(int id)const{map<int,CvUnit*>::const_iterator i=units.find(id);return i==units.end()?NULL:i->second;}
};
static CvPlayer players[3];
#define GET_PLAYER(x) players[x]
struct CvUnitCombat {static int DoDamageMath(int,int,int minimum,int,bool,const CvSeeder&,int modifier){return modifier<=-100?0:minimum;}};
'''
tests=r'''
static int checks=0,failures=0;
static void expect(const char*name,int actual,int expected){++checks;if(actual!=expected){++failures;printf("FAIL %s actual=%d expected=%d\n",name,actual,expected);}}
struct Fixture {
 CvPlot target,near,far;CvUnit bomber,aa,second;vector<const CvUnit*>candidates;SUnitIDValueContainer damage,used;
 Fixture():target(0,0,0),near(1,0,0),far(20,0,0),bomber(100,1,&far),aa(10,0,&near),second(11,0,&near){
  for(int i=0;i<3;++i){players[i]=CvPlayer();players[i].id=i;}
  players[1].enemies.push_back(0);players[0].enemies.push_back(1);bomber.domain=DOMAIN_AIR;
  add(aa);
 }
 void add(CvUnit&u){players[u.owner].units[u.id]=&u;players[u.owner].possible.push_back(make_pair(u.id,0));}
 int strike(){return StackAirStrikeChance(&bomber,&target,0,candidates,damage,0,used);}
};
int main(){
 {Fixture f;expect("one AA first bomber abort",f.strike(),0);expect("one AA second bomber hits",f.strike(),10000);expect("virtual attempts bounded",f.used.GetValue(10),1);expect("live count untouched",f.aa.made,0);}
 {Fixture f;f.damage.ChangeValue(10,100);expect("virtually killed AA excluded",f.strike(),10000);expect("dead AA consumes no attempt",f.used.GetValue(10),0);}
 {Fixture f;f.aa.chance=50;expect("partial chance retained",f.strike(),5000);expect("miss-capable attempt consumed",f.strike(),10000);}
 {Fixture f;f.bomber.evasion=100;expect("certain evasion",f.strike(),10000);f.bomber.evasion=0;expect("evasion still consumed AA attempt",f.strike(),10000);}
 {Fixture f;f.aa.chance=250;f.bomber.evasion=50;expect("clamp rolls separately",f.strike(),5000);}
 {Fixture f;f.aa.hp=49;f.aa.chance=3;f.damage.ChangeValue(10,15);expect("recompute HP probability before truncation",f.strike(),9900);}
 {Fixture f;f.aa.attempts=2;f.aa.made=1;expect("one remaining live attempt",f.strike(),0);expect("live plus virtual exhausted",f.strike(),10000);expect("original live count preserved",f.aa.made,1);}
 {Fixture f;f.second.chance=50;f.add(f.second);expect("best AA chosen first",f.strike(),0);expect("second AA chosen after exhaustion",f.strike(),5000);expect("both AAs exhausted",f.strike(),10000);}
 {Fixture f;f.aa.location=&f.target;expect("departed same-plot AA omitted",f.strike(),10000);f.candidates.push_back(&f.aa);expect("same-plot AA included",f.strike(),0);}
 {Fixture f;f.aa.location=&f.far;f.candidates.push_back(&f.aa);expect("virtual arrival supplies range",f.strike(),0);}
 {Fixture f;f.aa.location=&f.target;f.aa.domain=DOMAIN_AIR;expect("absent combat candidates do not discard fighter",f.strike(),0);}
 {Fixture f;f.bomber.defenseModifier=-100;expect("zero minimum interception damage gets no abort credit",f.strike(),10000);expect("zero damage attempt consumed",f.used.GetValue(10),1);}
 {Fixture f;f.target.owner=2;expect("neutral airspace retained",f.strike(),10000);}
 {Fixture f;f.bomber.invisible=true;expect("stealth retained",f.strike(),10000);}
 {Fixture f;f.aa.location=&f.far;f.aa.range=50;expect("same live eleven-hex guard",f.strike(),10000);}
 {Fixture f;f.second.strength=f.aa.strength;f.add(f.second);f.strike();expect("stable equal tie uses first",f.used.GetValue(10),1);}
 {Fixture f;f.aa.hp=50;f.aa.domain=DOMAIN_AIR;f.second.hp=50;f.add(f.second);f.strike();expect("air health double-weight matches live selector",f.used.GetValue(11),1);}
 expect("certain strike exact",StackExpectedStrikeDamage(25,10000),25);
 expect("certain abort exact",StackExpectedStrikeDamage(25,0),0);
 expect("fractional harm rounds up",StackExpectedStrikeDamage(25,5000),13);
 expect("small risk is not rounded to zero",StackExpectedStrikeDamage(1,1),1);
 expect("nonpositive hit",StackExpectedStrikeDamage(-1,10000),0);
 printf("interception regression: %d checks, %d failures\n",checks,failures);
 return failures?1:0;
}
'''
cpp=work/'interception-source-test.cpp';cpp.write_text(prefix+actual+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
inc=root/'work/toolchain/sdk/vc9/include';lib=root/'work/toolchain/sdk/vc9/lib';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','')
env['INCLUDE']=str(inc)+';'+str(sdk/'Include');env['LIB']=str(lib)+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=work/'interception-source-test.exe'
cmd=[str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/Od','/Z7',str(cpp),'/Fo'+str(work/'interception-source-test.obj'),'/Fe'+str(exe)]
compiled=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True)
(work/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=work,env=env,capture_output=True,text=True)
print(run.stdout+run.stderr,end='')
result={'source_sha256':hashlib.sha256(source.encode()).hexdigest().upper(),'extracted_helpers_sha256':hashlib.sha256(actual.encode()).hexdigest().upper(),'compile_returncode':compiled.returncode,'test_returncode':run.returncode,'output':run.stdout+run.stderr,'scope':'actual extracted C++ helpers with deterministic engine stubs; no VP DLL build and no live runtime proof'}
(work/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
sys.exit(run.returncode)