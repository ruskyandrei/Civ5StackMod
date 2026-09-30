"""Actual stack/city/air/collateral forecasts agree after exact enemy-HP projection."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys

root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2'
out=root/'work/projected-stack-danger-regression';out.mkdir(exist_ok=True)
danger=(core/'CvDangerPlots.cpp').read_text(encoding='utf-8-sig')
header=(core/'CvDangerPlots.h').read_text(encoding='utf-8-sig')
combat=(core/'CvUnitCombat.cpp').read_text(encoding='utf-8-sig')
unit=(core/'CvUnit.h').read_text(encoding='utf-8-sig')
def function(text,signature):
 start=text.index(signature);end=text.index('{',start)+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
air=function(danger,'static int StackAirStrikeChance(')
expected=function(danger,'static int StackExpectedStrikeDamage(')
city=function(danger,'static int SimulateStackCityThreats(')
stack=function(danger,'int CvDangerPlotContents::GetStackDanger(')
collateral=function(combat,'std::vector<std::pair<const CvUnit*, int> > CvUnitCombat::GetStackCollateralDamage(')
# This projection contract must be revisited if a helper gains a new enemy-HP dependency.
assert re.findall(r'enemyDamage\.GetValue\((.*?)\)',city+stack)==['attacker->GetID(', 'attacker->GetID(', '-it->second']
assert 'enemyDamage' not in air+collateral
assert city.count('enemyDamage')==2 and stack.count('enemyDamage')==4
assert 'friendlyDamage' in air and 'extraDamage.GetValue(pUnit->GetID())' in collateral
container=unit[unit.index('struct SUnitIDValueContainer\n'):unit.index('\nnamespace std {',unit.index('struct SUnitIDValueContainer\n'))]
contents=header[header.index('struct CvDangerPlotContents\n'):header.index('//++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++',header.index('struct CvDangerPlotContents\n'))]
metadata='\n'.join(function(danger,s) for s in ('const std::vector<int>* CvDangerPlots::GetStackDangerDamageIDs(', 'const std::vector<int>& CvDangerPlotContents::GetStackDangerDamageIDs(', 'void CvDangerPlots::AssignUnitDangerValue(', 'void CvDangerPlots::AssignCityDangerValue('))

prefix=r'''
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <vector>
#include <map>
#include <set>
#include <utility>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <climits>
#include <new>
static size_t allocationCalls=0;
void* operator new(size_t n)throw(std::bad_alloc){++allocationCalls;void*p=malloc(n?n:1);if(!p)throw std::bad_alloc();return p;}
void operator delete(void*p)throw(){free(p);}
using namespace std;
typedef __int64 int64;typedef int PlayerTypes;typedef int TeamTypes;typedef int AirActionType;
enum{DOMAIN_LAND=0,DOMAIN_SEA=1,DOMAIN_AIR=2,AIR_ACTION_ATTACK=0};
const int MAX_DAMAGE_MEMBER_COUNT=32;
#define GD_INT_GET(x) 2400
#define FOG_DEFAULT_DANGER (1)
struct CvSeeder{};
struct CvUnit;struct CvCity;
struct CvPlot{
 int index,x,y,owner,terrain,feature;bool friendly,embark;CvCity*city;
 CvPlot(int i=0):index(i),x(i%9),y(i/9),owner(0),terrain(8),feature(6),friendly(false),embark(false),city(NULL){}
 int GetPlotIndex()const{return index;}bool isOwned()const{return owner>=0;}int getOwner()const{return owner;}
 bool IsFriendlyTerritory(int p)const{return owner==p;}bool isCity()const{return city!=NULL;}
 bool isFriendlyCity(const CvUnit&)const;CvCity*getPlotCity()const{return city;}
 bool needsEmbarkation(const CvUnit*)const{return embark;}
 int getTurnDamage(bool t,bool f,int et,int ef)const{return (t?0:terrain+et)+(f?0:feature+ef);}
};
static int plotDistance(const CvPlot&a,const CvPlot&b){return abs(a.x-b.x)+abs(a.y-b.y);}
struct CvUnit{
 int id,owner,domain,hp,maxHP,chance,evasion,attempts,made,range,strength,modifier,defenseModifier,aoe,collateralLimit;
 bool alive,delayed,active,invisible,ranged,noCapture,civilian,trade,terrainIgnore,featureIgnore;CvPlot*location;
 CvUnit(int i=0,int o=0,CvPlot*p=NULL):id(i),owner(o),domain(DOMAIN_LAND),hp(100),maxHP(100),chance(100),evasion(0),attempts(1),made(0),range(5),strength(100),modifier(0),defenseModifier(0),aoe(0),collateralLimit(2),alive(true),delayed(false),active(true),invisible(false),ranged(false),noCapture(false),civilian(false),trade(false),terrainIgnore(false),featureIgnore(false),location(p){}
 int GetID()const{return id;}int getOwner()const{return owner;}int getTeam()const{return owner;}int getDomainType()const{return domain;}
 bool IsDead()const{return !alive;}bool isDelayedDeath()const{return delayed;}bool canInterceptNow()const{return active&&made<attempts;}
 bool isInvisible(int,bool,bool)const{return invisible;}int GetCurrHitPoints()const{return hp;}int GetMaxHitPoints()const{return maxHP;}
 int GetNumInterceptions()const{return attempts;}int getMadeInterceptionCount()const{return made;}CvPlot*plot()const{return location;}
 int GetAirInterceptRange()const{return range;}int getInterceptChance()const{return chance;}int evasionProbability()const{return evasion;}
 int GetInterceptionCombatModifier()const{return modifier;}int GetInterceptionDefenseDamageModifier()const{return defenseModifier;}
 int GetMaxRangedCombatStrength(const CvUnit*,const void*,bool,const CvPlot*,const CvPlot*,bool,bool,int extra=0,int=0)const{return max(1,strength-extra);}
 int GetMaxAttackStrength(const CvPlot*,const CvPlot*,const CvUnit*,bool,bool,int extra=0,int=0)const{return max(1,strength-extra);}
 bool IsCanAttackRanged()const{return ranged||domain==DOMAIN_AIR;}int GetRange()const{return range;}bool isNoCapture()const{return noCapture;}
 int getAoEDamageOnMove()const{return aoe;}bool IsCivilianUnit()const{return civilian;}bool isTrade()const{return trade;}
 bool isEnemy(int team,const CvPlot*)const{return owner!=team;}bool ignoreTerrainDamage()const{return terrainIgnore;}bool ignoreFeatureDamage()const{return featureIgnore;}
 int extraTerrainDamage()const{return id%3;}int extraFeatureDamage()const{return id%2;}
};
struct CvCity{
 int id,owner,hp,maxHP,protection;CvPlot*location;CvCity(int i=0,int o=0,CvPlot*p=NULL):id(i),owner(o),hp(180),maxHP(300),protection(45),location(p){}
 int GetID()const{return id;}int getOwner()const{return owner;}int getTeam()const{return owner;}CvPlot*plot()const{return location;}
 int GetMaxHitPoints()const{return maxHP;}int getDamage()const{return maxHP-hp;}
 int rangeCombatDamage(const CvUnit*unit,bool,const CvPlot*,bool,int wounds)const{return max(0,11+id%7+(unit->hp-wounds)/13);}
};
bool CvPlot::isFriendlyCity(const CvUnit&unit)const{return friendly&&city&&city->owner==unit.owner;}
'''
services=r'''
typedef vector<pair<PlayerTypes,int> >DangerUnitVector;typedef DangerUnitVector DangerCityVector;
struct CvPlayer{
 int id;vector<int>enemies;vector<pair<int,int> >possible;map<int,CvUnit*>units;map<int,CvCity*>cities;
 int GetID()const{return id;}int getTeam()const{return id;}bool IsAtWarWith(int p)const{return find(enemies.begin(),enemies.end(),p)!=enemies.end();}
 const vector<int>&GetPlayersAtWarWith()const{return enemies;}const vector<pair<int,int> >&GetPossibleInterceptors()const{return possible;}
 const CvUnit*getUnit(int i)const{map<int,CvUnit*>::const_iterator it=units.find(i);return it==units.end()?NULL:it->second;}
 const CvCity*getCity(int i)const{map<int,CvCity*>::const_iterator it=cities.find(i);return it==cities.end()?NULL:it->second;}
};
static CvPlayer players[4];
#define GET_PLAYER(x) players[x]
namespace CvStacking{
 static bool cityEnabled=true;bool CityRangedAttacksEnabled(){return cityEnabled;}bool IsEnabled(){return true;}
 int GetCollateralTargetLimit(const CvUnit*u){return u->collateralLimit;}
 int GetInt(const char*,int d){return d;}bool IsCollateralTargetDomain(int domain){return domain!=DOMAIN_AIR;}
 int GetCityProtection(const CvCity*c,int extra=0){return c?c->protection*max(0,c->hp-max(0,extra))/max(1,c->maxHP):0;}
}
namespace CvUnitCombat{
 int DoDamageMath(int interceptor,int bomber,int minimum,int,bool,const CvSeeder&,int modifier){return modifier<=-100?0:max(0,minimum+(interceptor-bomber)*5);}
 const CvUnit*SelectStackDefender(const CvUnit*,const CvPlot*,const CvPlot*,const vector<const CvUnit*>&c,const SUnitIDValueContainer&d,bool,int){
  const CvUnit*best=NULL;int bestValue=INT_MIN;for(size_t i=0;i<c.size();++i){if(!c[i])continue;int hp=c[i]->hp-d.GetValue(c[i]->id);if(hp<=0)continue;int value=hp+c[i]->strength;if(value>bestValue){best=c[i];bestValue=value;}}return best;
 }
 const CvUnit*SelectStackDefenderForCity(const CvCity*,const CvPlot*p,const vector<const CvUnit*>&c,const SUnitIDValueContainer&d){return SelectStackDefender(NULL,NULL,p,c,d,true,0);}
 vector<pair<const CvUnit*,int> >GetStackCollateralDamage(const CvUnit*,const CvPlot*,const CvUnit*,int,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const CvUnit* = NULL,int=0,int=0);
}
static bool IsStackCombatCandidate(const CvUnit*u,const SUnitIDValueContainer&d){return u&&u->alive&&!u->delayed&&u->hp>d.GetValue(u->id);}
struct StackCollateralOrder{
 bool operator()(const pair<const CvUnit*,int>&a,const pair<const CvUnit*,int>&b)const{
  if(a.second!=b.second)return a.second>b.second;if(a.first->owner!=b.first->owner)return a.first->owner<b.first->owner;return a.first->id<b.first->id;
 }
};
namespace TacticalAIHelpers{
 const CvUnit*GetSimulatedGarrison(const CvCity*,const vector<const CvUnit*>&c,const SUnitIDValueContainer&d){return CvUnitCombat::SelectStackDefender(NULL,NULL,NULL,c,d,false,0);}
 int GetSimulatedDamageFromAttackOnCity(const CvCity*,const CvUnit*a,const CvPlot*,int&retaliation,int&garrison,bool,int wounds,int cityWounds,int garrisonWounds,bool,bool,const CvUnit*guard){
  retaliation=7;int hit=max(0,35+a->id%9-wounds/4+cityWounds/19);garrison=guard?max(0,hit/3+garrisonWounds/20):0;return hit;
 }
 int GetSimulatedDamageFromAttackOnUnit(const CvUnit*d,const CvUnit*a,const CvPlot*,const CvPlot*,int&retaliation,bool,int wounds,int defenderWounds,bool,bool){retaliation=6;return max(0,23+a->id%11+d->id%7-wounds/3+defenderWounds/9);}
}
'''
wrapper=r'''
struct CvDangerPlots{
 bool m_bDirty;vector<CvDangerPlotContents>m_DangerPlots;int updates;bool addOnUpdate;
 CvDangerPlots():m_bDirty(false),updates(0),addOnUpdate(false){}
 void UpdateDanger(){++updates;m_bDirty=false;if(addOnUpdate&&!m_DangerPlots.empty()){m_DangerPlots[0].reset();m_DangerPlots[0].m_apUnits.push_back(make_pair(1,77));m_DangerPlots[0].InvalidateStackDangerDamageIDs();}}
 const vector<int>*GetStackDangerDamageIDs(const CvPlot&);
 void AssignUnitDangerValue(const CvUnit*,CvPlot*);void AssignCityDangerValue(const CvCity*,CvPlot*);
};
'''
tests=r'''
static int checks=0,failures=0;
static void expect(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<20)printf("FAIL %s\n",n);}}
static unsigned int seed=4371;static unsigned int next(){seed=seed*1664525u+1013904223u;return seed;}
static SUnitIDValueContainer project(const SUnitIDValueContainer&damage,const vector<int>&ids){SUnitIDValueContainer result;for(size_t i=0;i<ids.size();++i){int value=damage.GetValue(ids[i]);if(value)result.SetValue(ids[i],value);}return result;}
static vector<int> oracle(const CvDangerPlotContents&c){set<int>ids;for(size_t i=0;i<c.m_apUnits.size();++i)ids.insert(c.m_apUnits[i].second);for(size_t i=0;i<c.m_apCities.size();++i)ids.insert(-c.m_apCities[i].second);return vector<int>(ids.begin(),ids.end());}
int main(){
 expect("native32bit",sizeof(void*)==4&&sizeof(size_t)==4);
 CvPlot target(0),near(1),far(17);CvCity defended(0,0,&target);target.city=&defended;CvUnit defenders[5],attackers[10];CvCity enemyCities[3];
 for(int trial=0;trial<24000;++trial){
  for(int p=0;p<4;++p){players[p]=CvPlayer();players[p].id=p;for(int q=0;q<4;++q)if(q!=p)players[p].enemies.push_back(q);}
  CvDangerPlotContents c;c.m_pPlot=&target;c.m_iFogCount=next()%6;c.m_iImprovementDamage=next()%26;c.m_bFlatPlotDamage=next()%2!=0;
  defended.hp=next()%301;defended.protection=next()%91;target.friendly=trial%3==0;target.embark=trial%13==0;
  vector<const CvUnit*> candidates;SUnitIDValueContainer friendly,full;
  for(int i=0;i<5;++i){defenders[i]=CvUnit(i,0,&target);defenders[i].hp=20+next()%81;defenders[i].strength=40+next()%190;defenders[i].ranged=next()%2!=0;defenders[i].domain=i==4?DOMAIN_AIR:DOMAIN_LAND;defenders[i].chance=next()%151;defenders[i].attempts=1+next()%3;defenders[i].terrainIgnore=next()%2!=0;defenders[i].featureIgnore=next()%2!=0;players[0].units[i]=&defenders[i];players[0].possible.push_back(make_pair(i,0));if(i<4)candidates.push_back(&defenders[i]);friendly.SetValue(i,(int)(next()%121));}
  for(int i=0;i<10;++i){int owner=1+i%2,id=i%5;attackers[i]=CvUnit(id,owner,(trial+i)%11==0?&target:&near);attackers[i].hp=20+next()%81;attackers[i].strength=30+next()%180;attackers[i].ranged=next()%2!=0;attackers[i].domain=i%4==0?DOMAIN_AIR:DOMAIN_LAND;attackers[i].alive=(trial+i)%19!=0;attackers[i].delayed=(trial+i)%17==0;attackers[i].noCapture=next()%3==0;attackers[i].aoe=next()%4;attackers[i].collateralLimit=next()%6;attackers[i].evasion=next()%101;players[owner].units[id]=&attackers[i];c.m_apUnits.push_back(make_pair(owner,id));if(next()%3==0)c.m_apUnits.push_back(make_pair(owner,id));}
  c.m_apUnits.push_back(make_pair(1,29)); // missing/dead sources remain in the conservative key
  for(int i=0;i<3;++i){enemyCities[i]=CvCity(i,i%2?2:1,&near);enemyCities[i].hp=next()%301;players[enemyCities[i].owner].cities[i]=&enemyCities[i];c.m_apCities.push_back(make_pair(enemyCities[i].owner,i));}
  c.m_apCities.push_back(make_pair(1,42));c.InvalidateStackDangerDamageIDs();
  for(int id=-45;id<41;++id)if(next()%2)full.SetValue(id,(int)(next()%181)-20);
  const vector<int>&ids=c.GetStackDangerDamageIDs();expect("rawsource canonical oracle including zero owner aliases and missing",ids==oracle(c));
  SUnitIDValueContainer projected=project(full,ids);
  int original=c.GetStackDanger(&defenders[0],candidates,friendly,full),reduced=c.GetStackDanger(&defenders[0],candidates,friendly,projected);
  expect("actual city stack air collateral forecast agrees with projected HP",original==reduced);
  SUnitIDValueContainer unrelated=full;unrelated.ChangeValue(99,100+trial%137);unrelated.ChangeValue(-99,50);expect("unrelated exactdamage changes leave forecast",c.GetStackDanger(&defenders[0],candidates,friendly,unrelated)==original);
  SUnitIDValueContainer wounded=full;wounded.ChangeValue(ids[next()%ids.size()],1);expect("relevant oneHP preserved",c.GetStackDanger(&defenders[0],candidates,friendly,wounded)==c.GetStackDanger(&defenders[0],candidates,friendly,project(wounded,ids)));
  size_t allocations=allocationCalls;for(int i=0;i<5;++i){const vector<int>&warm=c.GetStackDangerDamageIDs();expect("warm metadata exact",warm==ids);}expect("warm metadata no allocations",allocationCalls==allocations);
 }
 CvDangerPlots map;map.m_DangerPlots.resize(1);map.m_DangerPlots[0].m_pPlot=&target;
 expect("empty valid source list",map.GetStackDangerDamageIDs(target)&&map.GetStackDangerDamageIDs(target)->empty());
 CvUnit unit(6,1,&near),alias(6,2,&near);map.AssignUnitDangerValue(&unit,&target);vector<int>ids=*map.GetStackDangerDamageIDs(target);expect("unit insert invalidates",ids.size()==1&&ids[0]==6);
 size_t allocations=allocationCalls;map.AssignUnitDangerValue(&unit,&target);expect("duplicate source not rebuilt",*map.GetStackDangerDamageIDs(target)==ids&&allocationCalls==allocations);
 map.AssignUnitDangerValue(&alias,&target);expect("owner IDaliases canonicalized",map.GetStackDangerDamageIDs(target)->size()==1);
 CvCity city(7,2,&near);map.AssignCityDangerValue(&city,&target);ids=*map.GetStackDangerDamageIDs(target);expect("city insert includes negative ID",ids.size()==2&&ids[0]==-7&&ids[1]==6);
 CvStacking::cityEnabled=false;CvCity ignored(8,2,&near);map.AssignCityDangerValue(&ignored,&target);expect("disabled city source untouched",*map.GetStackDangerDamageIDs(target)==ids);CvStacking::cityEnabled=true;
 map.m_DangerPlots[0].reset();expect("reset invalidates metadata",map.GetStackDangerDamageIDs(target)->empty());
 map.addOnUpdate=true;map.m_bDirty=true;ids=*map.GetStackDangerDamageIDs(target);expect("dirty wrapper refreshes before metadata",map.updates==1&&!map.m_bDirty&&ids.size()==1&&ids[0]==77);
 CvPlot invalid(-1);expect("negative index fallback",map.GetStackDangerDamageIDs(invalid)==NULL);invalid.index=1;expect("outofbounds fallback",map.GetStackDangerDamageIDs(invalid)==NULL);
 map.m_DangerPlots[0].m_pPlot=NULL;expect("null contentsplot fallback",map.GetStackDangerDamageIDs(target)==NULL);map.m_DangerPlots.clear();expect("uninitialized map fallback",map.GetStackDangerDamageIDs(target)==NULL);
 printf("projected stack danger actual-source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
fixture=prefix+container+services+contents+wrapper+metadata+air+expected+collateral+city+stack+tests
cpp=out/'test.cpp';cpp.write_text(fixture,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=out/'test.exe';c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=60);print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(danger.encode()).hexdigest(),fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),returncode=r.returncode,output=r.stdout+r.stderr,scope='Actual source metadata/reset/insertion/wrapper, city/stack/air/collateral bodies; deterministic combat strength/selection services; 24000 random fullHP vs projectedHP states; no native DLLbuild or game run.'),indent=2),encoding='utf-8');sys.exit(r.returncode)
