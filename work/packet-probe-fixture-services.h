// Deterministic engine services for the packet diagnostic fixture only.
// Production containers, forecast/selector math and typed-name bindings are
// extracted afresh by test-packet-probe.py. No generated scaffold prerequisite.
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <cstring>
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
static unsigned long valueReads=0,changes=0,zeroChanges=0,hpReads=0,aoeReads=0;
static vector<int> trace;
static void OnLeaf();static void Record(int a,int b,int c){trace.push_back(a);trace.push_back(b);trace.push_back(c);}
struct CvUnit;struct CvCity;
struct CvPlot{
 int index,x,y,owner,terrain,feature;bool friendly,embark;CvCity*city;
 CvPlot(int i=0):index(i),x(i%9),y(i/9),owner(0),terrain(8),feature(6),friendly(false),embark(false),city(NULL){}
 int getTeam()const;int GetPlotIndex()const{return index;}bool isOwned()const{return owner>=0;}int getOwner()const{return owner;}
 bool IsFriendlyTerritory(int p)const{return owner==p;}int getFeatureType()const{return feature;}bool isCity()const{return city!=NULL;}
 bool isFriendlyCity(const CvUnit&)const;CvCity*getPlotCity()const{return city;}
 bool needsEmbarkation(const CvUnit*)const{return embark;}
 int getTurnDamage(bool t,bool f,int et,int ef)const{return (t?0:terrain+et)+(f?0:feature+ef);}
};
static int plotDistance(const CvPlot&a,const CvPlot&b){return abs(a.x-b.x)+abs(a.y-b.y);}
struct CvUnit{
 int id,owner,team,combatOwner,domain,hp,maxHP,chance,evasion,attempts,made,range,strength,modifier,defenseModifier,aoe,collateralLimit;
 bool defend,cargo,flank,flankTarget,anti;int defense;bool alive,delayed,active,invisible,ranged,noCapture,civilian,trade,terrainIgnore,featureIgnore;CvPlot*location;
 CvUnit(int i=0,int o=0,CvPlot*p=NULL):id(i),owner(o),team(o),combatOwner(-1),domain(DOMAIN_LAND),hp(100),maxHP(100),chance(100),evasion(0),attempts(1),made(0),range(5),strength(100),modifier(0),defenseModifier(0),aoe(0),collateralLimit(2),defend(true),cargo(false),flank(false),flankTarget(false),anti(false),defense(25),alive(true),delayed(false),active(true),invisible(false),ranged(false),noCapture(false),civilian(false),trade(false),terrainIgnore(false),featureIgnore(false),location(p){}
 int GetID()const{return id;}int getOwner()const{return owner;}int getTeam()const{return team;}int getCombatOwner(int,const CvPlot&)const{return combatOwner<0?owner:combatOwner;}int getDomainType()const{return domain;}
 bool IsCombatUnit()const{return !civilian&&!trade;}bool CanGarrison()const{return !civilian&&!trade&&domain!=DOMAIN_AIR;}int GetBaseCombatStrength()const{return strength;}int GetBaseRangedCombatStrength()const{return ranged?strength:0;}bool isNativeDomain(const CvPlot*)const{return !cargo&&domain!=DOMAIN_AIR;}bool IsCanDefend()const{return defend;}bool isCargo()const{return cargo;}bool IsDead()const{return !alive;}bool isDelayedDeath()const{return delayed;}bool canInterceptNow()const{return active&&made<attempts;}
 bool isInvisible(int,bool,bool=false)const{return invisible;}int getInvisibleType()const{return 1;}int GetCurrHitPoints()const{++hpReads;return hp;}int GetMaxHitPoints()const{return maxHP;}
 int GetNumInterceptions()const{return attempts;}int getMadeInterceptionCount()const{return made;}CvPlot*plot()const{return location;}
 int GetAirInterceptRange()const{return range;}int getInterceptChance()const{return chance;}int evasionProbability()const{return evasion;}
 int GetInterceptionCombatModifier()const{return modifier;}int GetInterceptionDefenseDamageModifier()const{return defenseModifier;}
 int GetRangeCombatDamage(const CvUnit*d,const CvCity*,int,int&,bool,int extra,int other,const CvPlot*,const CvPlot*,bool,bool)const{return max(0,strength-extra/5-d->defense/2+other/4);}
 int GetAirStrikeDefenseDamage(const CvUnit*,bool,const CvPlot*)const{return defense/3;}
 int GetMaxDefenseStrength(const CvPlot*,const CvUnit*,const CvPlot*,bool,bool,int extra)const{return max(1,defense-extra/5);}
 int getMeleeCombatDamage(int a,int d,int&ret,bool,const CvUnit*,int,int)const{ret=max(0,d-a/2);return max(0,a-d/2);}
 bool isBetterDefenderThan(const CvUnit*u,const CvUnit*)const{return !u||defense>u->defense;}
 int GetMaxRangedCombatStrength(const CvUnit*,const void*,bool,const CvPlot*,const CvPlot*,bool,bool,int extra=0,int=0)const{return max(1,strength-extra);}
 int GetMaxAttackStrength(const CvPlot*,const CvPlot*,const CvUnit*,bool,bool,int extra=0,int=0)const{return max(1,strength-extra);}
 bool IsCanAttackRanged()const{return ranged||domain==DOMAIN_AIR;}int GetRange()const{return range;}bool isNoCapture()const{return noCapture;}
 int getAoEDamageOnMove()const{++aoeReads;return aoe;}bool IsCivilianUnit()const{return civilian;}bool isTrade()const{return trade;}
 bool isEnemy(int team,const CvPlot*)const{return owner!=team;}bool ignoreTerrainDamage()const{return terrainIgnore;}bool ignoreFeatureDamage()const{return featureIgnore;}
 int extraTerrainDamage()const{return id%3;}int extraFeatureDamage()const{return id%2;}
};
struct CvCity{
 int id,owner,hp,maxHP,protection;CvUnit*garrison;CvPlot*location;CvCity(int i=0,int o=0,CvPlot*p=NULL):id(i),owner(o),hp(180),maxHP(300),protection(45),garrison(NULL),location(p){}
 CvUnit*GetGarrisonedUnit()const{return garrison;}int GetID()const{return id;}int getOwner()const{return owner;}int getTeam()const;CvPlot*plot()const{return location;}
 int GetMaxHitPoints()const{return maxHP;}int getDamage()const{return maxHP-hp;}
 int rangeCombatDamage(const CvUnit*unit,bool,const CvPlot*,bool,int wounds)const{return max(0,11+id%7+(unit->hp-wounds)/13);}
};

struct CvDangerPlots;

// ACTUAL_CONTAINER_INSERT
typedef vector<pair<PlayerTypes,int> >DangerUnitVector;typedef DangerUnitVector DangerCityVector;
struct CvPlayer{
 CvDangerPlots*GetDangerPlots()const;int id,team;vector<int>enemies;vector<pair<int,int> >possible;map<int,CvUnit*>units;map<int,CvCity*>cities;
 int GetID()const{return id;}int getTeam()const{return team;}bool IsAtWarWith(int p)const{return find(enemies.begin(),enemies.end(),p)!=enemies.end();}
 const vector<int>&GetPlayersAtWarWith()const{return enemies;}const vector<pair<int,int> >&GetPossibleInterceptors()const{return possible;}
 const CvUnit*getUnit(int i)const{map<int,CvUnit*>::const_iterator it=units.find(i);return it==units.end()?NULL:it->second;}
 const CvCity*getCity(int i)const{map<int,CvCity*>::const_iterator it=cities.find(i);return it==cities.end()?NULL:it->second;}
};
static CvPlayer players[4];
#define GET_PLAYER(x) players[x]
namespace CvStacking{
 static bool enabled=true,selectionEnabled=true,cityEnabled=true;bool CityRangedAttacksEnabled(){return cityEnabled;}bool IsEnabled(){return enabled;}bool CanFlank(const CvUnit*u){return u->flank;}bool IsAntiCavalry(const CvUnit*u){return u->anti;}bool IsFlankTarget(const CvUnit*u){return u->flankTarget;}
 int GetCollateralTargetLimit(const CvUnit*u){return u->collateralLimit;}
 int GetInt(const char*n,int d){return !strcmp(n,"DefenderSelectionEnabled")?(selectionEnabled?1:0):d;}bool IsCollateralTargetDomain(int domain){return domain!=DOMAIN_AIR;}
 int GetCityProtection(const CvCity*c,int extra=0){return c?c->protection*max(0,c->hp-max(0,extra))/max(1,c->maxHP):0;}
}
namespace CvUnitCombat{
 int DoDamageMath(int interceptor,int bomber,int minimum,int,bool,const CvSeeder&,int modifier){return modifier<=-100?0:max(0,minimum+(interceptor-bomber)*5);}
 const CvUnit*SelectStackDefender(const CvUnit*,const CvPlot*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,bool,int);
 const CvUnit*SelectStackDefenderForCity(const CvCity*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&);
 vector<pair<const CvUnit*,int> >GetStackCollateralDamage(const CvUnit*,const CvPlot*,const CvUnit*,int,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const CvUnit* = NULL,int=0,int=0);
}

struct StackCollateralOrder{
 bool operator()(const pair<const CvUnit*,int>&a,const pair<const CvUnit*,int>&b)const{
  if(a.second!=b.second)return a.second>b.second;if(a.first->owner!=b.first->owner)return a.first->owner<b.first->owner;return a.first->id<b.first->id;
 }
};
namespace TacticalAIHelpers{
 const CvUnit*GetSimulatedGarrison(const CvCity*,const vector<const CvUnit*>&,const SUnitIDValueContainer&);
 int GetSimulatedDamageFromAttackOnCity(const CvCity*,const CvUnit*a,const CvPlot*,int&retaliation,int&garrison,bool,int wounds,int cityWounds,int garrisonWounds,bool,bool,const CvUnit*guard){
  OnLeaf();Record(1,a->id,wounds);Record(2,guard?guard->id:-999,garrisonWounds);retaliation=7;int hit=max(0,35+a->id%9-wounds/4+cityWounds/19);garrison=guard?max(0,hit/3+garrisonWounds/20):0;return hit;
 }
 int GetSimulatedDamageFromAttackOnUnit(const CvUnit*d,const CvUnit*a,const CvPlot*,const CvPlot*,int&retaliation,bool,int wounds,int defenderWounds,bool,bool){OnLeaf();Record(3,a->id,d->id);Record(4,wounds,defenderWounds);retaliation=6;return max(0,23+a->id%11+d->id%7-wounds/3+defenderWounds/9);}
}
