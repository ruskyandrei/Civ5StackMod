"""Actual-source production policy/budget/claims and native sanity-boundary fixture.

Compiles changed complete production helpers and unchanged claim lifecycle bodies
against explicit player/city/unit services. Executes original maintenance/resource
blocks plus the staged recommendation gate; whole-file reversal protects the
remaining native1600-line sanity body. Does not claim that remainder is executed.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/ai-production-policy-regression'
P=argparse.ArgumentParser(description=__doc__);P.add_argument('--emit-only',action='store_true');args=P.parse_args()
spec=importlib.util.spec_from_file_location('production_stage',ROOT/'work/stage-ai-production-policy.py');stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
old,new,proof=stage.generate();fn=stage.function
source=new['CvStackingOffensiveAI.cpp']
models=r'''
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <map>
#include <set>
#include <vector>
#include <new>
#include <climits>
#include <cstdio>
using namespace std;
typedef int PlayerTypes;typedef int DomainTypes;typedef int UnitTypes;typedef int UnitAITypes;typedef int PromotionTypes;typedef int TechTypes;typedef int UnitCombatTypes;typedef int UnitClassTypes;typedef int ResourceTypes;
const int MAX_PLAYERS=4,NO_PLAYER=-1,NO_UNIT=-1,NO_DOMAIN=-1,NO_UNITCOMBAT=-1,NO_UNITCLASS=-1,NO_TECH=-1,NO_RESOURCE=-1;
const int DOMAIN_LAND=0,DOMAIN_SEA=1,DOMAIN_AIR=2,UNITAI_ATTACK=1,UNITAI_DEFENSE=2,UNITAI_COUNTER=3,UNITAI_FAST_ATTACK=4,UNITAI_ATTACK_SEA=5,UNITAI_CITY_BOMBARD=6,UNITAI_RANGED=7,UNITAI_EXPLORE=8,UNITAI_ASSAULT_SEA=9;
const int SR_UNITSUPPLY=-2,SR_MAINTENANCE=-3,SR_IMPOSSIBLE=-4,SR_STRATEGY=-5,NO_PROJECT=-1;
struct CvCity;
namespace CvStackingOffensiveAI { API }
static unsigned checks=0,failures=0,softReads=0,cityVisits=0,unitVisits=0,diagnosticRows=0,allocationAttempts=0;
static int turn=12;static bool modEnabled=true,diagnostics=false,failAllocation=false;
void*operator new(size_t n){++allocationAttempts;if(failAllocation)throw bad_alloc();void*p=malloc(n?n:1);if(!p)throw bad_alloc();return p;}
void operator delete(void*p){free(p);}void*operator new[](size_t n){return ::operator new(n);}void operator delete[](void*p){::operator delete(p);}
static void Check(const char*name,bool okay){++checks;if(!okay){++failures;if(failures<25)printf("FAIL %s\n",name);}}
struct CvUnitEntry{int domain,combat,ranged,range,role,moves,resource,requirement;bool military,noSupply,freeNoCapture,eraUpgrade,noMaintenance,trade,train;
 CvUnitEntry():domain(DOMAIN_LAND),combat(20),ranged(0),range(0),role(UNITAI_ATTACK),moves(2),resource(NO_RESOURCE),requirement(1),military(true),noSupply(false),freeNoCapture(false),eraUpgrade(false),noMaintenance(false),trade(false),train(true){}
 int GetDomainType()const{return domain;}int GetCombat()const{return combat;}int GetRangedCombat()const{return ranged;}int GetRange()const{return range;}int GetDefaultUnitAIType()const{return role;}int GetMoves()const{return moves;}
 bool IsMilitarySupport()const{return military;}bool IsNoSupply()const{return noSupply;}bool GetFreePromotions(int p)const{return p==0&&freeNoCapture;}int GetUnitCombatType()const{return 1;}int GetUnitClassType()const{return 2;}bool IsUnitEraUpgrade()const{return eraUpgrade;}int GetUnitNewEraPromotions(int p,int era)const{return p==0&&era>=2?1:0;}
 bool IsNoMaintenance()const{return noMaintenance;}bool IsTrade()const{return trade;}int GetResourceType()const{return resource;}int GetResourceQuantityRequirement(int)const{return requirement;}int GetSpaceshipProject()const{return NO_PROJECT;}
};
struct CvPromotionEntry{bool noCapture,onlyDefensive;CvPromotionEntry():noCapture(false),onlyDefensive(false){}bool IsNoCapture()const{return noCapture;}bool IsOnlyDefensive()const{return onlyDefensive;}int GetTechPrereq()const{return 2;}};
struct CvCity;
struct CvPlot{int index,x,y,owner;CvCity*city;CvPlot(int i=0):index(i),x(i),y(0),owner(1),city(NULL){}int GetPlotIndex()const{return index;}bool isCity()const{return city!=NULL;}int getOwner()const{return owner;}CvCity*getPlotCity()const{return city;}};
int plotDistance(const CvPlot&a,const CvPlot&b){return abs(a.x-b.x)+abs(a.y-b.y);}
struct CvUnit{int id,owner,type,domain,hp,maxhp,goal,ai;bool ranged,siege,capture,healthy,usable;
 CvUnit(int i=0):id(i),owner(0),type(0),domain(DOMAIN_LAND),hp(100),maxhp(100),goal(20),ai(UNITAI_ATTACK),ranged(false),siege(false),capture(true),healthy(true),usable(true){}
 int GetID()const{return id;}int getOwner()const{return owner;}int getUnitType()const{return type;}int getDomainType()const{return domain;}int GetCurrHitPoints()const{return hp;}int GetMaxHitPoints()const{return maxhp;}bool IsCanAttackRanged()const{return ranged;}void AI_setUnitAIType(UnitAITypes t){ai=t;}int baseMoves(bool)const{return 2;}CvPlot*plot()const;
 const CvUnitEntry&getUnitInfo()const;
};
struct CvCity{int owner,id,unit,operation,turns;bool siege,puppet,legalPurchase;CvPlot at;vector<PromotionTypes>birth;
 CvCity(int i=0):owner(0),id(i),unit(NO_UNIT),operation(-1),turns(4),siege(false),puppet(false),legalPurchase(true),at(2){at.city=this;at.owner=0;}
 int getOwner()const{return owner;}int GetID()const{return id;}int getProductionUnit()const{return unit;}bool IsBuildingUnitForOperation()const{return operation>=0;}int GetUnitProductionOperation()const{return operation;}
 int getProductionTurnsLeft(UnitTypes,int)const{return turns;}int getProductionTurnsLeft()const{return turns;}CvPlot*plot()const{return const_cast<CvPlot*>(&at);}bool isUnderSiege()const{return siege;}
 vector<PromotionTypes>getFreePromotions()const{return birth;}bool canTrain(UnitTypes type,bool continuation)const;
};
struct Traits{bool combatFree,classFree;Traits():combatFree(false),classFree(false){}bool HasFreePromotionUnitCombat(int p,int)const{return p==0&&combatFree;}bool HasFreePromotionUnitClass(int p,int)const{return p==0&&classFree;}};
struct Economy{int cap;Economy():cap(40){}int GetSoftSupplyCap(){++softReads;return cap;}};
struct Military{int land,sea,explore;Military():land(20),sea(20),explore(0){}int GetRecommendedMilitarySize()const{return land+sea+explore;}int GetRecommendLandArmySize()const{return land;}int GetRecommendNavySize()const{return sea;}int GetRecommendedExplorers()const{return explore;}};
struct Treasury{int maintenance;Treasury():maintenance(20){}int GetExpensePerTurnUnitMaintenance()const{return maintenance;}};
struct Diplomacy{bool spaceship;Diplomacy():spaceship(false){}bool IsGoingForSpaceshipVictory()const{return spaceship;}bool IsCloseToSpaceshipVictory()const{return spaceship;}};
struct CvAIOperation{int id;CvAIOperation():id(5){}int GetID()const{return id;}int GetEnemy()const{return 1;}};
struct CvPlayer{vector<CvCity*>cities;vector<CvUnit*>units;Economy economy;Military military;Traits traits;Treasury treasury;Diplomacy diplomacy;
 int supplied,demand,land,sea,bankrupt,resource,other;bool minor,freePromotion,tech,war;CvAIOperation op;
 CvPlayer():supplied(50),demand(0),land(0),sea(0),bankrupt(50),resource(5),other(0),minor(false),freePromotion(false),tech(true),war(true){}
 int getNumCities()const{return (int)cities.size();}CvCity*firstCity(int*i){*i=0;++cityVisits;return cities.empty()?NULL:cities[0];}CvCity*nextCity(int*i){++*i;++cityVisits;return (size_t)*i<cities.size()?cities[*i]:NULL;}CvCity*getCity(int id)const{for(size_t i=0;i<cities.size();++i)if(cities[i]->id==id)return cities[i];return NULL;}
 CvUnit*firstUnit(int*i){*i=0;++unitVisits;return units.empty()?NULL:units[0];}CvUnit*nextUnit(int*i){++*i;++unitVisits;return (size_t)*i<units.size()?units[*i]:NULL;}
 Economy*GetEconomicAI(){return &economy;}Military*GetMilitaryAI(){return &military;}Traits*GetPlayerTraits(){return &traits;}Treasury*GetTreasury(){return &treasury;}Diplomacy*GetDiplomacyAI(){return &diplomacy;}
 int GetNumUnitsSupplied()const{return supplied;}int GetNumUnitsToSupply()const{return demand;}int getNumMilitaryLandUnits()const{return land;}int getNumMilitarySeaUnits()const{return sea;}bool isMinorCiv()const{return minor;}int getTeam()const{return 0;}
 bool HasTech(int)const{return tech;}bool IsFreePromotion(int p)const{return p==0&&freePromotion;}int getNumUnits()const{return max(1,land+sea+other);}int getTurnsToBankruptcy(int)const{return bankrupt;}int getNumResourceAvailable(int,bool)const{return resource;}int GetNumAluminumStillNeededForSpaceship()const{return 0;}int GetNumAluminumStillNeededForCoreCities()const{return 0;}
 CvAIOperation*getAIOperation(int id){return id==5?&op:NULL;}bool IsAtWarWith(int)const{return war;}
}players[MAX_PLAYERS];
typedef CvPlayer CvPlayerAI;
#define GET_PLAYER(owner) players[owner]
struct Team{int era;Team():era(1){}int GetCurrentEra()const{return era;}}team;
#define GET_TEAM(teamID) team
struct Game{int getGameTurn()const{return turn;}};
struct Map{vector<CvPlot*>plots;CvPlot*plotByIndexUnchecked(int index){for(size_t i=0;i<plots.size();++i)if(plots[i]->index==index)return plots[i];return NULL;}};
struct Globals{CvUnitEntry types[12];CvPromotionEntry promotions[2];Game game;Map map;Game&getGame(){return game;}Map&getMap(){return map;}CvUnitEntry*getUnitInfo(UnitTypes unit){return unit>=0&&unit<12?&types[unit]:NULL;}int getNumPromotionInfos()const{return 2;}CvPromotionEntry*getPromotionInfo(int p){return p>=0&&p<2?&promotions[p]:NULL;}int getNumEraInfos()const{return 4;}int getInfoTypeForString(const char*,bool){return 0;}}GC;
bool CvCity::canTrain(UnitTypes type,bool)const{return GC.types[type].train&&(GC.types[type].resource==NO_RESOURCE||players[owner].resource>=GC.types[type].requirement);}
CvPlot unitPlot(3);CvPlot*CvUnit::plot()const{return &unitPlot;}const CvUnitEntry&CvUnit::getUnitInfo()const{return GC.types[type];}
bool IsPromotionValidForUnitCombatType(int,UnitTypes unit){return GC.types[unit].combat>0;}bool IsPromotionValidForCivilianUnitType(int,UnitTypes){return false;}
namespace CvStackingDiagnostics{bool Enabled(int,PlayerTypes){return diagnostics;}void Record(int,PlayerTypes,const char*,const char*,...){++diagnosticRows;}}
struct SettingLess{bool operator()(const char*a,const char*b)const{return strcmp(a,b)<0;}};
static map<const char*,int,SettingLess>settings;
static int Setting(const char*name,int fallback){map<const char*,int,SettingLess>::const_iterator i=settings.find(name);return i==settings.end()?fallback:i->second;}
namespace CvStackingOffensiveAI{
 bool Enabled(PlayerTypes owner){return modEnabled&&owner>=0&&owner<MAX_PLAYERS&&!players[owner].minor;}
 bool RouteBlocked(PlayerTypes,CvPlot*,bool){return false;}bool IsSiegeUnit(const CvUnit*u){return u&&u->siege;}
 bool CanCapture(const CvUnit*u,const CvPlot*){return u&&u->capture&&u->usable;}
 int DesiredAssaultUnits(PlayerTypes,const CvCity*,DomainTypes){return 12;}int DesiredSiegeUnits(PlayerTypes,const CvCity*,DomainTypes domain){return domain==DOMAIN_LAND?2:4;}
 CvPlot*CityTarget(const CvAIOperation*);
}
typedef pair<int,int>Key;
struct ObjectiveKey{int owner,target,domain;ObjectiveKey(int o=0,int t=-1,int d=DOMAIN_LAND):owner(o),target(t),domain(d){}bool operator<(const ObjectiveKey&b)const{return owner!=b.owner?owner<b.owner:target!=b.target?target<b.target:domain<b.domain;}bool operator==(const ObjectiveKey&b)const{return owner==b.owner&&target==b.target&&domain==b.domain;}};
struct Objective{int enemy,operation,staffTurn,staffUnits,staffSiege,staffRanged,staffCapture,lastUsefulTurn,productionTurn,productionUnits,productionSiege,productionRanged,productionCapture,productionQueued;unsigned long productionGeneration;vector<int>productionCaptureQueues;
 Objective():enemy(1),operation(5),staffTurn(-1),staffUnits(0),staffSiege(0),staffRanged(0),staffCapture(0),lastUsefulTurn(-1),productionTurn(-1),productionUnits(0),productionSiege(0),productionRanged(0),productionCapture(0),productionQueued(0),productionGeneration(0){}
};
struct ProductionClaim{ObjectiveKey goal;int unit,started,progress,turns;ProductionClaim():unit(-1),started(-1),progress(-1),turns(INT_MAX){}};
map<ObjectiveKey,Objective>objectives;map<Key,ProductionClaim>production;
static int currentTurn=12;static unsigned transfers=0;static bool shuttingDown=false;
static bool Usable(const CvUnit*u){return u&&u->usable;}static bool Live(CvAIOperation*op){return op!=NULL;}
static void Sync(PlayerTypes){currentTurn=turn;}static bool Matches(CvUnit*u,const ObjectiveKey&key,const Objective&){return u&&u->usable&&u->owner==key.owner&&u->domain==key.domain&&u->goal==key.target;}
static bool ProductionQueueStalled(const CvCity*,const Key&){return false;}
namespace CvStackingOffensiveAI{void RecordTransfer(CvUnit*,int,int,int){++transfers;}}
'''
api=(ROOT/'work/ai-production-policy-api.h').read_text();models=models.replace(' API ',api)
models=models.replace('#include <cstdio>','#include <cstdio>\n#include <string>\n#include <cstdlib>\n#include <cstring>')
roles='\n'.join(fn(source,'    bool '+name+'(') for name in ('EntryRanged','EntrySiege','EntryCapture'))
budget=(ROOT/'work/ai-production-policy-budget.cpp').read_text();choice=(ROOT/'work/ai-production-policy-choice.cpp').read_text();public=(ROOT/'work/ai-production-policy-public.cpp').read_text()
lifecycle='\n'.join(fn(source,'    void '+name+'(') for name in ('RecordProduction','UnitProduced'))
maintenance=fn(new['CvUnitProductionAI.cpp'],'int CvUnitProductionAI::CheckUnitBuildSanity(')
a=maintenance.index('\tif (!bDesperate && !bFree)');b=maintenance.index('\n\t//don\'t build land/sea',a);maintenance_block=maintenance[a:b]
sanity=fn(new['CvUnitProductionAI.cpp'],'int CvUnitProductionAI::CheckUnitBuildSanity(')
a=sanity.index('\tCvStackingOffensiveAI::ProductionIntent stackingIntent;');b=sanity.index('\n\t//only war with majors count',a);quota_block=sanity[a:b]
a=sanity.index('\t\t//Check for special unlimited');b=sanity.index('\n\t\t///////////////\n\t\t//UNIT TYPE CHECKS',a);resource_block=sanity[a:b]
shell='''static int SanityBoundary(CvCity*m_pCity,UnitTypes eUnit,bool bForPurchase=false,bool bFree=false){
 CvUnitEntry*pkUnitEntry=GC.getUnitInfo(eUnit);CvPlayerAI&kPlayer=GET_PLAYER(m_pCity->getOwner());
 bool bDesperate=m_pCity->isUnderSiege(),bCombat=pkUnitEntry->GetCombat()>0||pkUnitEntry->GetRangedCombat()>0;
 bool bNeedsSupply=bCombat&&!pkUnitEntry->IsNoSupply();int iBonus=0;
 if(!bFree&&!m_pCity->canTrain(eUnit,m_pCity->getProductionUnit()==eUnit))return SR_IMPOSSIBLE;
 MAINTENANCE
 const ProductionQueueState own=ReadProductionQueue(m_pCity);
 int iNumLandUnits=kPlayer.land+productionPolicy[m_pCity->owner].land-(bForPurchase?0:own.land);
 int iNumSeaUnits=kPlayer.sea+productionPolicy[m_pCity->owner].sea-(bForPurchase?0:own.sea);
 int iNumExplorers=0;
 QUOTA
 if(!kPlayer.isMinorCiv()){RESOURCE}
 return 1;
}'''.replace('MAINTENANCE',maintenance_block).replace('QUOTA',quota_block).replace('RESOURCE',resource_block)
tests=r'''
static CvCity targetCity(99),factory(10),second(11);static CvPlot target(20);static CvUnit troops[40];
CvPlot*CvStackingOffensiveAI::CityTarget(const CvAIOperation*){return &target;}
static void Setup(int count=8){failAllocation=false;
 turn=12;currentTurn=turn;modEnabled=true;diagnostics=false;settings.clear();objectives.clear();production.clear();CvStackingOffensiveAI::ResetProductionPolicy();players[0]=CvPlayer();
 factory=CvCity(10);second=CvCity(11);targetCity=CvCity(99);target.city=&targetCity;target.owner=1;GC.map.plots.clear();GC.map.plots.push_back(&target);
 players[0].cities.push_back(&factory);players[0].cities.push_back(&second);players[0].land=players[0].demand=count;
 for(int i=0;i<count;++i){troops[i]=CvUnit(i);players[0].units.push_back(&troops[i]);}
 for(int i=0;i<12;++i)GC.types[i]=CvUnitEntry();GC.promotions[0]=CvPromotionEntry();GC.promotions[1]=CvPromotionEntry();GC.promotions[0].noCapture=true;
 GC.types[1].ranged=20;GC.types[1].range=2;GC.types[1].role=UNITAI_CITY_BOMBARD;
 GC.types[2].ranged=15;GC.types[2].range=2;GC.types[2].role=UNITAI_RANGED;
 GC.types[3].freeNoCapture=true;GC.types[4].domain=DOMAIN_AIR;GC.types[4].combat=0;GC.types[4].ranged=30;
 GC.types[5].domain=DOMAIN_SEA;GC.types[5].role=UNITAI_ATTACK_SEA;GC.types[6].noSupply=true;GC.types[7].role=UNITAI_EXPLORE;
 objectives[ObjectiveKey(0,20,DOMAIN_LAND)]=Objective();team.era=1;cityVisits=unitVisits=softReads=diagnosticRows=transfers=0;
}
int main(){setvbuf(stdout,NULL,_IONBF,0);Check("VC9 native x86",sizeof(void*)==4);
 Setup(18);players[0].military.land=18;players[0].military.sea=12;players[0].economy.cap=30;
 CvStackingOffensiveAI::ProductionIntent intent;Check("missing true siege intent",CvStackingOffensiveAI::GetProductionIntent(&factory,1,intent)&&intent.missingRole&&intent.quotaEligible);
 Check("domain full but affordable missing role permitted",SanityBoundary(&factory,1)==1);
 Check("redundant extra melee not given quota",SanityBoundary(&factory,0)==SR_UNITSUPPLY);
 unsigned visits=unitVisits,cities=cityVisits,soft=softReads;for(int i=0;i<80;++i){CvStackingOffensiveAI::GetProductionIntent(&factory,1,intent);SanityBoundary(&factory,1);}
 Check("no extra full unit or city scans per type",unitVisits==visits&&cityVisits==cities&&softReads==soft);
 settings["AIOffensiveProductionRecommendationSlack"]=0;Check("XML zero recommendation slack disables exception",SanityBoundary(&factory,1)==SR_UNITSUPPLY);settings.clear();
 players[0].supplied=players[0].demand;Check("actual supply full rejects exception",SanityBoundary(&factory,1)==SR_UNITSUPPLY);
 players[0].supplied=50;players[0].economy.cap=18;CvStackingOffensiveAI::ProductionCitiesChanged(0);Check("actual affordable budget full rejects exception",SanityBoundary(&factory,1)==SR_UNITSUPPLY);
 factory.unit=0;players[0].land=players[0].demand=17;CvStackingOffensiveAI::ProductionQueueChanged(&factory);
 Check("same current queued slot may be switched to missing role",SanityBoundary(&factory,1)==1);
 Check("purchase cannot borrow queue replacement credit",SanityBoundary(&factory,1,true)==SR_UNITSUPPLY);
 players[0].bankrupt=8;Check("native bankruptcy boundary remains hard",SanityBoundary(&factory,1)==SR_MAINTENANCE);players[0].bankrupt=50;
 GC.types[1].resource=0;players[0].resource=0;Check("native resource/train precheck remains hard",SanityBoundary(&factory,1)==SR_IMPOSSIBLE);GC.types[1].resource=NO_RESOURCE;players[0].resource=5;
 factory.siege=true;CvStackingOffensiveAI::GetProductionIntent(&factory,1,intent);Check("homefront siege no offensive bonus or quota",!intent.quotaEligible&&intent.bonus==0);
 Check("homefront native under-cap production remains allowed",SanityBoundary(&factory,1)==1);players[0].land=18;Check("homefront cannot waive filled domain quota",SanityBoundary(&factory,1)==SR_UNITSUPPLY);factory.siege=false;
 Setup();CvStackingOffensiveAI::ProductionBudget budget;Check("budget initializes",CvStackingOffensiveAI::GetProductionBudget(0,budget));
 unsigned softBefore=softReads,cityBefore=cityVisits;players[0].other=1;players[0].economy.cap=39;CvStackingOffensiveAI::ProductionBudget intentBudget;CvStackingOffensiveAI::InvalidateProductionOwner(0);Check("birth/loss changes budget generation",CvStackingOffensiveAI::GetProductionBudget(0,intentBudget)&&intentBudget.generation>budget.generation);
 Check("changed live count refreshes affordable budget once",softReads==softBefore+1&&cityVisits==cityBefore&&intentBudget.affordableAvailable==31);
 softBefore=softReads;players[0].economy.cap=38;CvStackingOffensiveAI::ProductionEconomyChanged(0);Check("same-count construction economy refresh",CvStackingOffensiveAI::GetProductionBudget(0,intentBudget)&&intentBudget.affordableAvailable==30&&softReads==softBefore+1&&cityVisits==cityBefore);
 second.unit=4;CvStackingOffensiveAI::ProductionQueueChanged(&second);Check("ranged-only AIR queue consumes supply",CvStackingOffensiveAI::GetProductionBudget(0,budget)&&budget.queuedSupply==1&&budget.queuedLand==0);
 second.unit=6;CvStackingOffensiveAI::ProductionQueueChanged(&second);Check("type NoSupply queue exemption explicit",CvStackingOffensiveAI::GetProductionBudget(0,budget)&&budget.queuedSupply==0&&budget.queuedLand==1);
 Check("XML NoCapture promotion never promised capturer",(ProductionEntryRoles(&factory,3)&CvStackingOffensiveAI::PRODUCTION_CAPTURE)==0);
 players[0].traits.combatFree=true;Check("trait combat NoCapture birth promotion",(ProductionEntryRoles(&factory,0)&CvStackingOffensiveAI::PRODUCTION_CAPTURE)==0);players[0].traits.combatFree=false;
 factory.birth.push_back(0);Check("city/religious birth NoCapture promotion",(ProductionEntryRoles(&factory,0)&CvStackingOffensiveAI::PRODUCTION_CAPTURE)==0);factory.birth.clear();
 GC.types[0].eraUpgrade=true;team.era=2;Check("era birth NoCapture promotion",(ProductionEntryRoles(&factory,0)&CvStackingOffensiveAI::PRODUCTION_CAPTURE)==0);GC.types[0].eraUpgrade=false;
 GC.promotions[0].noCapture=false;GC.promotions[0].onlyDefensive=true;Check("only-defensive birth cannot melee capture",(ProductionEntryRoles(&factory,3)&CvStackingOffensiveAI::PRODUCTION_CAPTURE)==0);
 Setup(0);factory.unit=0;CvStackingOffensiveAI::ProductionQueueChanged(&factory);CvStackingOffensiveAI::RecordProduction(&factory,0);
 Check("queued capturer initially credited",CvStackingOffensiveAI::GetProductionIntent(&second,0,intent)&&intent.missingCapture==1);
 factory.birth.push_back(0);Check("same-head changed birth flag loses capture credit",CvStackingOffensiveAI::GetProductionIntent(&second,0,intent)&&intent.missingCapture==2);
 Check("replacement never subtracts fresh flags from stale totals",CvStackingOffensiveAI::GetProductionIntent(&factory,1,intent)&&intent.missingCapture==2);
 Setup(0);CvStackingOffensiveAI::GetProductionBudget(0,budget);failAllocation=true;bool failedBirth=CvStackingOffensiveAI::GetProductionIntent(&factory,0,intent);Check("sparse birth metadata allocation fails safely",!failedBirth&&intent.bonus==0);failAllocation=false;
 Check("birth metadata proof can recover",CvStackingOffensiveAI::GetProductionIntent(&factory,0,intent)&&intent.bonus>0);
 factory.birth.push_back(1);failAllocation=true;bool failedCity=CvStackingOffensiveAI::GetProductionIntent(&factory,0,intent);Check("city birth-vector allocation fails safely",!failedCity&&intent.bonus==0);failAllocation=false;
 Setup(32);players[0].supplied=60;players[0].economy.cap=60;players[0].military.land=40;players[0].military.sea=20;
 Check("full objective admits bounded missing siege repair",CvStackingOffensiveAI::GetProductionIntent(&factory,1,intent)&&intent.bonus>0);
 factory.unit=1;CvStackingOffensiveAI::ProductionQueueChanged(&factory);CvStackingOffensiveAI::RecordProduction(&factory,1);
 second.unit=1;CvStackingOffensiveAI::ProductionQueueChanged(&second);CvStackingOffensiveAI::RecordProduction(&second,1);
 CvCity third(12);players[0].cities.push_back(&third);CvStackingOffensiveAI::ProductionCitiesChanged(0);
 Check("bounded objective repair quota stops third addition",CvStackingOffensiveAI::GetProductionIntent(&third,1,intent)&&intent.reason==CvStackingOffensiveAI::PRODUCTION_FORCE_LIMIT&&intent.bonus==0);
 Check("each support queue credited once",intent.queued==2);
 second.operation=5;CvStackingOffensiveAI::ProductionQueueChanged(&second);CvStackingOffensiveAI::GetProductionIntent(&third,1,intent);
 Check("formation takeover does not double credit support claim",intent.queued==2);
 diagnosticRows=0;diagnostics=true;CvStackingOffensiveAI::RecordProductionRejection(&third,1,intent,6);CvStackingOffensiveAI::RecordProductionRejection(&third,2,intent,6);Check("one rejection row per city reason",diagnosticRows==1);
 Setup();factory.unit=1;CvStackingOffensiveAI::ProductionQueueChanged(&factory);CvStackingOffensiveAI::RecordProduction(&factory,1);Check("one city one support claim",production.size()==1);CvStackingOffensiveAI::RecordProduction(&factory,1);Check("duplicate recording idempotent",production.size()==1);
 CvUnit made(200);made.type=1;made.ranged=true;made.siege=true;CvStackingOffensiveAI::UnitProduced(&factory,&made);Check("completion consumes claim once",production.empty()&&transfers==1);CvStackingOffensiveAI::UnitProduced(&factory,&made);Check("duplicate completion cannot dispatch twice",transfers==1);
 objectives[ObjectiveKey(0,20,DOMAIN_LAND)].staffTurn=turn;objectives[ObjectiveKey(0,20,DOMAIN_LAND)].productionTurn=turn;CvStackingOffensiveAI::UnitProduced(&factory,&made);Check("native birth without support claim invalidates staff",objectives[ObjectiveKey(0,20,DOMAIN_LAND)].staffTurn==-1&&objectives[ObjectiveKey(0,20,DOMAIN_LAND)].productionTurn==-1);
 Setup();factory.unit=1;CvStackingOffensiveAI::GetProductionBudget(0,budget);failAllocation=true;CvStackingOffensiveAI::ProductionCitiesChanged(0);Check("failed optional metadata initialization rejects proof",!CvStackingOffensiveAI::GetProductionBudget(0,budget));failAllocation=false;Check("later safe budget rebuild recovers",CvStackingOffensiveAI::GetProductionBudget(0,budget));
 for(int owner=0;owner<MAX_PLAYERS;++owner){ProductionPolicyState& state=productionPolicy[owner];state.turn=12;state.cityCount=2;state.observedUnits=18;state.softCap=40;state.land=8;state.sea=3;state.supply=11;state.generation=17;state.ready=state.busy=state.softDirty=true;state.cities[100+owner]=ProductionQueueState();state.rejections.insert(make_pair(owner,6));}
 noCapturePromotions.push_back(0);noCapturePromotionCount=2;
 failAllocation=true;bool legacyResetThrows=false;try{ProductionPolicyState legacyEmpty;}catch(const bad_alloc&){legacyResetThrows=true;}
 Check("VC9 legacy empty map/set construction really fails under persistent OOM",legacyResetThrows);
 const unsigned resetAttempts=allocationAttempts;bool resetThrew=false;try{CvStackingOffensiveAI::ResetProductionPolicy();}catch(const bad_alloc&){resetThrew=true;}
 Check("reset and cleanup make zero allocation attempts during persistent OOM",!resetThrew&&allocationAttempts==resetAttempts);
 bool defaultStates=true;for(int owner=0;owner<MAX_PLAYERS;++owner){const ProductionPolicyState& state=productionPolicy[owner];defaultStates=defaultStates&&state.cities.empty()&&state.rejections.empty()&&state.turn==-1&&state.cityCount==-1&&state.observedUnits==-1&&state.softCap==0&&state.land==0&&state.sea==0&&state.supply==0&&state.generation==0&&!state.ready&&!state.busy&&!state.softDirty;}
 Check("reset clears all cached payload and ready/busy generations",defaultStates&&noCapturePromotions.empty()&&noCapturePromotions.capacity()==0&&noCapturePromotionCount==-1);
 CvStackingOffensiveAI::ResetProductionPolicy();Check("repeated empty cleanup stays allocation-free",allocationAttempts==resetAttempts);failAllocation=false;
 Check("fresh budget after OOM cleanup rebuilds normally",CvStackingOffensiveAI::GetProductionBudget(0,budget)&&budget.ready);
 modEnabled=false;Check("mod-off has no optional quota",!CvStackingOffensiveAI::GetProductionIntent(&factory,1,intent));
 printf("ACTUAL PRODUCTION POLICY: %u checks, %u failures\n",checks,failures);return failures?1:0;
}
'''
cpp=models+roles+'\n'+budget+'\n'+choice+'\nnamespace CvStackingOffensiveAI{\n'+public+'\n'+lifecycle+'\n}\n'+shell+'\n'+tests
OUT.mkdir(exist_ok=True);(OUT/'test.cpp').write_text(cpp,encoding='utf-8')
report=dict(proof);report.update(fixture_sha256=hashlib.sha256(cpp.encode()).hexdigest(),scope='Changed complete actual-source budget/choice/public and claim insert/completion, original maintenance/resource blocks, staged native recommendation gate. Explicit city/player/type/Matches/route/supply services; complete rest of sanity protected by source reversal, not executed; no native performance claim.')
(OUT/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
if args.emit_only:print(json.dumps(dict(emitted=True,fixtureSHA256=report['fixture_sha256'],gameCalls=0)));sys.exit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
built=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/GS','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(OUT/'test.cpp'),'/Fo'+str(OUT/'test.obj'),'/Fe'+str(OUT/'test.exe')],cwd=OUT,env=env,capture_output=True,text=True,timeout=45);(OUT/'compile.log').write_text(built.stdout+built.stderr)
if built.returncode:print(built.stdout+built.stderr);sys.exit(built.returncode)
run=subprocess.run([str(OUT/'test.exe')],cwd=OUT,capture_output=True,text=True,timeout=20);report.update(compile_returncode=built.returncode,test_returncode=run.returncode,output=run.stdout+run.stderr);(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(run.stdout+run.stderr,end='');sys.exit(run.returncode)
