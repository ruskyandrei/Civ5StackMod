#include "CvGameCoreDLLPCH.h"
#include "CvStackingOffensiveAI.h"
#include "CvUnitCombat.h"
#include "CvStackingAI.h"
#include "CvStackingAIPolicy.h"
#include "CvStackingRules.h"
#include "CvStackingDiagnostics.h"
#include "CvPlayerAI.h"
#include "CvDiplomacyAI.h"
#include "CvUnit.h"
#include "CvCity.h"
#include "CvPlot.h"
#include "CvMap.h"
#include "CvArmyAI.h"
#include "CvAIOperation.h"
#include "CvMilitaryAI.h"
#include "CvEconomicAI.h"
#include "CvTacticalAI.h"
#include "CvDangerPlots.h"
#include "CvTypes.h"
#include <map>
#include <set>
#include <algorithm>
#include "LintFree.h"

namespace
{
    typedef std::pair<int,int> Key;
    struct ObjectiveKey
    {
        int owner, target, domain;
        ObjectiveKey(int o=0,int t=-1,int d=DOMAIN_LAND):owner(o),target(t),domain(d){}
        bool operator<(const ObjectiveKey& b) const
        { return owner!=b.owner?owner<b.owner:target!=b.target?target<b.target:domain<b.domain; }
        bool operator==(const ObjectiveKey& b) const { return owner==b.owner && target==b.target && domain==b.domain; }
    };
// Bounded cached first-wave records; no serialized game-object fields.
struct AssaultWaveUnit
{
    int unit, army, eta, damage, sustain, strength, roles, hp, type, range, moves,plot,domain,remaining,available,spent,setup;
    AssaultWaveUnit(CvUnit* u,int turns,int hit,int retaliation,const CvPlot* target):
        unit(u->GetID()),army(u->getArmyID()),eta(turns),damage(hit),sustain(0),strength(CvStackingAI::UnitStrength(u)),
        roles((CvStackingOffensiveAI::CanCapture(u,target)?1:0)|(u->IsCanAttackRanged()?2:0)|
            ((u->getDomainType()==DOMAIN_SEA?u->IsCanAttackRanged():CvStackingOffensiveAI::IsSiegeUnit(u))?4:0)),
        hp(u->GetCurrHitPoints()),type(u->getUnitType()),range(u->GetRange()),moves(u->baseMoves(false)),plot(u->plot()->GetPlotIndex()),domain(u->getDomainType()),remaining(u->getMoves()),available(u->canUseNow()),spent(u->isOutOfAttacks()),setup(u->isSetUpForRangedAttack())
    {
        // A second-turn damage forecast must not reuse an attacker which its
        // first attack would leave below the same healthy-force threshold.
        if((long long)(hp-retaliation)*100>=
            (long long)u->GetMaxHitPoints()*CvStacking::GetInt("AIAssaultHealthyPercent",65)) sustain=hit;
    }
};
struct AssaultWave
{
    int units, siege, ranged, capture, strength, damage, sustain, first, last, own;
    unsigned failed;
    AssaultWave():units(0),siege(0),ranged(0),capture(0),strength(0),damage(0),sustain(0),first(INT_MAX),last(0),own(0),failed(0){}
};
enum AssaultFailure
{
    ASSAULT_CAPTURE=1,ASSAULT_SIEGE=2,ASSAULT_COUNT=4,ASSAULT_STRENGTH=8,
    ASSAULT_DAMAGE=16,ASSAULT_COHESION=32,ASSAULT_OWN_ARMY=64,ASSAULT_UNKNOWN=128
};

    struct Objective
    {
        int enemy, operation, staging, refreshed, created, coreUnits, coreStrength, captureTurn, captureID, noCaptureSince;
        int captureOwner, captureEta, captureProgress, capturePlot, captureDistance;
        CvStackingOffensiveAI::AssaultPlan assault;
        int assaultTurn, phaseSince, phaseLogged;
        int staffTurn, staffUnits, staffSiege, staffRanged, staffCapture;
        int productionTurn,productionUnits,productionSiege,productionRanged,productionCapture,productionQueued;
        unsigned long productionGeneration;
        std::vector<int> productionCaptureQueues;
        int lastUsefulTurn, lowestHP;
        int firstReadyTurn, lastCityProgress, lastCityAttack, cityAttempts, fieldContributions;
        bool captureKnown;
        std::vector<AssaultWaveUnit> waveRows;bool waveComplete,wavePathUnknown;
        Objective():enemy(-1),operation(-1),staging(-1),refreshed(-1),created(-1),coreUnits(0),coreStrength(0),
            captureTurn(-1),captureID(-1),noCaptureSince(-1),captureOwner(-1),captureEta(INT_MAX),captureProgress(-1),capturePlot(-1),captureDistance(INT_MAX),
            assaultTurn(-1),phaseSince(-1),phaseLogged(-1),staffTurn(-1),staffUnits(0),staffSiege(0),staffRanged(0),staffCapture(0),
            productionTurn(-1),productionUnits(0),productionSiege(0),productionRanged(0),productionCapture(0),productionQueued(0),productionGeneration(0),
            lastUsefulTurn(-1),lowestHP(INT_MAX),firstReadyTurn(-1),lastCityProgress(-1),lastCityAttack(-1),cityAttempts(0),fieldContributions(0),
            captureKnown(false),waveComplete(false),wavePathUnknown(false){}
    };
    struct Commitment
    {
        ObjectiveKey goal; int turn, lastProgress, plot, eta, bestDistance;
        int routeStage, routeDestination, routeFrom, routeTo, routeProgress;
        bool arrived, capturer, assembly;
        Commitment():turn(-1),lastProgress(-1),plot(-1),eta(INT_MAX),bestDistance(INT_MAX),routeStage(-1),routeDestination(-1),routeFrom(-1),routeTo(-1),routeProgress(-1),arrived(false),capturer(false),assembly(false){}
    };
    struct March
    {
        int turn, lastProgress, distance, target;
        March():turn(-1),lastProgress(-1),distance(INT_MAX),target(-1){}
    };
    struct Failure { int until, enemy; Failure():until(-1),enemy(-1){} };
    struct ProductionClaim
    {
        ObjectiveKey goal; int unit, started, progress, turns;
        ProductionClaim():unit(-1),started(-1),progress(-1),turns(INT_MAX){}
    };
    struct StalledProductionQueue
    {
        int unit, turns;
        StalledProductionQueue(int u=-1,int t=INT_MAX):unit(u),turns(t){}
    };
struct OpeningKey
{
    int owner,operation,army;
    OpeningKey(int o,int p,int a):owner(o),operation(p),army(a){}
    bool operator<(const OpeningKey& b)const{return owner!=b.owner?owner<b.owner:operation!=b.operation?operation<b.operation:army<b.army;}
};
struct OpeningForecast
{
    int turn,target,enemy,domain,filled,hp,strength;bool visible,ready,complete;
    std::vector<AssaultWaveUnit> rows;
    OpeningForecast():turn(-1),target(-1),enemy(-1),domain(-1),filled(-1),hp(-1),strength(-1),visible(false),ready(false),complete(false){}
};
static std::map<OpeningKey,OpeningForecast> openingForecasts;
static int openingForecastTurn=-1;

    std::map<ObjectiveKey,Objective> objectives;
    std::map<Key,Commitment> commitments;
    std::map<ObjectiveKey,Failure> failures;
    std::map<Key,March> marches;
    std::map<Key,std::pair<int,int> > captureRetries; // unit -> target, expiry
    std::map<Key,ProductionClaim> production;
    std::map<Key,StalledProductionQueue> stalledProduction;
    std::map<Key,int> assemblyHolds;
    std::map<Key,int> fireRefusals; // unit -> turn of its last logged FIRE_REFUSAL
    int currentTurn=-1, synced[MAX_PLAYERS], captureQueries[MAX_PLAYERS], extraBatches[MAX_PLAYERS], assaultQueries[MAX_PLAYERS];
    void AdvanceProductionGeneration(PlayerTypes owner);
    bool shuttingDown=false;
    unsigned long continuityGeneration=1;
    bool continuityGenerationExhausted=false;
    int Setting(const char* name,int value) { return CvStacking::GetInt(name,value); }
    bool Live(CvAIOperation* op)
    { return op && op->GetOperationState()!=AI_OPERATION_STATE_ABORTED && op->GetOperationState()!=AI_OPERATION_STATE_SUCCESSFUL_FINISH; }
    bool Usable(const CvUnit* u)
    { return u && u->plot() && u->GetCurrHitPoints()>0 && u->IsCombatUnit() && !u->IsStackingUnit() && !u->isCargo() && !u->isDelayedDeath() && u->getDomainType()!=DOMAIN_AIR; }
    // CvArmyAI::GetDomainType reports DOMAIN_SEA for a combined army, whose
    // embarked land troops are still part of the force.
    bool InArmyDomain(const CvArmyAI* army,const CvUnit* u)
    {
        const DomainTypes domain=u->getDomainType();
        return army->GetType()==ARMY_TYPE_COMBINED?domain==DOMAIN_LAND||domain==DOMAIN_SEA:domain==army->GetDomainType();
    }
    // Siege requirements of a combined army follow the land rules; its ranged
    // ships and land siege both fill the siege role (AssaultWaveUnit::roles).
    DomainTypes AssaultDomain(const CvArmyAI* army)
    { return army->GetType()==ARMY_TYPE_COMBINED?DOMAIN_LAND:army->GetDomainType(); }
    bool AssignedElsewhere(const CvUnit* unit,const ObjectiveKey& goal)
    {
        if(!unit || unit->getArmyID()==-1) return false;
        CvPlayer& player=GET_PLAYER(unit->getOwner());
        CvArmyAI* army=player.getArmyAI(unit->getArmyID());
        if(!army) return false;
        CvAIOperation* operation=player.getAIOperation(army->GetOperationID());
        CvPlot* target=CvStackingOffensiveAI::CityTarget(operation);
        return !target || target->GetPlotIndex()!=goal.target;
    }
    bool ProductionQueueStalled(const CvCity* city,const Key& key)
    {
        std::map<Key,StalledProductionQueue>::iterator stalled=stalledProduction.find(key);
        if(stalled==stalledProduction.end()) return false;
        if(!city || city->IsBuildingUnitForOperation() || city->getProductionUnit()!=stalled->second.unit)
        { stalledProduction.erase(stalled);return false; }
        const int remaining=city->getProductionTurnsLeft();
        if(remaining<stalled->second.turns)
        {
            CvStackingDiagnostics::Record(1,(PlayerTypes)key.first,"OFFENSIVE_PRODUCTION","city=%d unitType=%d remaining=%d action=resume reason=queue_progress",key.second,stalled->second.unit,remaining);
            stalledProduction.erase(stalled);return false;
        }
        // Cost/movement estimates can increase. Observe that value without
        // crediting it, so a later strict decrease is real queue progress.
        stalled->second.turns=remaining;
        return true;
    }
    bool EraseCommitment(std::map<Key,Commitment>::iterator i)
    {
        if(i==commitments.end())return false;
        const ObjectiveKey goal=i->second.goal;
        CvStackingOffensiveAI::InvalidateProductionStaff((PlayerTypes)goal.owner,goal.target,(DomainTypes)goal.domain);
        commitments.erase(i);return true;
    }
    bool EraseCommitment(const Key& key) { return EraseCommitment(commitments.find(key)); }
    void Refresh()
    {
        if(shuttingDown) return;
        const int turn=GC.getGame().getGameTurn();
        if(currentTurn==turn) return;
        currentTurn=turn;
        assemblyHolds.clear();
        fireRefusals.clear();
        for(int i=0;i<MAX_PLAYERS;++i) { synced[i]=-1; captureQueries[i]=0; extraBatches[i]=0; assaultQueries[i]=0; }
        // One scalar signature per live owned-city queue prevents Sync from
        // recreating the same stalled claim and renewing an abandoned siege.
        for(std::map<Key,StalledProductionQueue>::iterator i=stalledProduction.begin();i!=stalledProduction.end();)
        {
            const Key key=i->first;++i;
            ProductionQueueStalled(GET_PLAYER((PlayerTypes)key.first).getCity(key.second),key);
        }
        // Tactical movement need not pass through RecordTransfer. Observe real
        // positions before aging objectives, including a dispatch near expiry.
        for(std::map<Key,Commitment>::iterator i=commitments.begin();i!=commitments.end();++i)
        {
            const CvUnit* u=GET_PLAYER((PlayerTypes)i->first.first).getUnit(i->first.second);
            std::map<ObjectiveKey,Objective>::iterator goal=objectives.find(i->second.goal);
            if(!Usable(u) || goal==objectives.end() || AssignedElsewhere(u,i->second.goal)) continue;
            CvPlot* target=GC.getMap().plotByIndexUnchecked(i->second.goal.target);
            if(!target || !target->isCity() || target->getOwner()!=goal->second.enemy) continue;
            Commitment& c=i->second;
            const int distance=plotDistance(*u->plot(),*target);
            if(u->plot()->GetPlotIndex()!=c.plot && distance<c.bestDistance)
            { c.lastProgress=turn; c.bestDistance=distance; goal->second.lastUsefulTurn=turn; }
            c.plot=u->plot()->GetPlotIndex();
            CvPlot* stage=goal->second.assault.staging>=0?GC.getMap().plotByIndexUnchecked(goal->second.assault.staging):NULL;
            if(stage && goal->second.assault.phase!=1 && plotDistance(*u->plot(),*stage)<=Setting("AIAssaultStageCohesionRadius",2))
            {
                c.lastProgress=turn;
                if(!c.assembly)
                {
                    c.assembly=true;goal->second.lastUsefulTurn=turn;
                    CvStackingDiagnostics::Record(1,(PlayerTypes)i->first.first,"OFFENSIVE_SUPPORT","unit=%d target=%d stage=%d action=assembly_arrival",i->first.second,c.goal.target,stage->GetPlotIndex());
                }
            }
            if(distance<=Setting("AIOffensiveSupportLocalRadius",4))
            {
                c.lastProgress=turn;
                if(!c.arrived)
                {
                    c.arrived=true;
                    goal->second.lastUsefulTurn=turn;
                    CvStackingDiagnostics::Record(1,(PlayerTypes)i->first.first,"OFFENSIVE_SUPPORT","unit=%d target=%d action=front_arrival distance=%d; arrival is not proof of capture readiness",i->first.second,c.goal.target,distance);
                }
            }
            if(turn-c.lastProgress<=Setting("AIOffensiveSupportStallTurns",5))
                goal->second.refreshed=turn;
        }
        for(std::map<Key,ProductionClaim>::iterator i=production.begin();i!=production.end();)
        {
            CvCity* city=GET_PLAYER((PlayerTypes)i->first.first).getCity(i->first.second);
            std::map<ObjectiveKey,Objective>::iterator goal=objectives.find(i->second.goal);
            const bool valid=city && !city->IsBuildingUnitForOperation() && city->getProductionUnit()==i->second.unit && goal!=objectives.end();
            if(valid)
            {
                const int remaining=city->getProductionTurnsLeft();
                if(remaining<i->second.turns) { i->second.progress=turn;goal->second.lastUsefulTurn=turn; }
                i->second.turns=remaining;
                if(turn-i->second.progress<=Setting("AIOffensiveProductionStallTurns",6)) goal->second.refreshed=turn;
            }
            if(!valid || turn-i->second.progress>Setting("AIOffensiveProductionStallTurns",6))
            {
                if(valid)
                    stalledProduction[i->first]=StalledProductionQueue(i->second.unit,i->second.turns);
                CvStackingDiagnostics::Record(1,(PlayerTypes)i->first.first,"OFFENSIVE_PRODUCTION","city=%d target=%d unitType=%d action=cancel reason=%s",i->first.second,i->second.goal.target,i->second.unit,valid?"stalled":"queue_or_objective_changed");
                AdvanceProductionGeneration((PlayerTypes)i->first.first);
                production.erase(i++);
            }
            else ++i;
        }
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();)
        {
            CvPlot* p=GC.getMap().plotByIndexUnchecked(i->first.target);
            CvAIOperation* op=GET_PLAYER((PlayerTypes)i->first.owner).getAIOperation(i->second.operation);
            const bool active=Live(op) && CvStackingOffensiveAI::CityTarget(op)==p;
            // City ownership is already public game information. Never read hidden occupants.
            const char* reason=!p || !p->isCity()?"city_missing":p->getOwner()!=i->second.enemy?"ownership_changed":
                (op && CvStackingOffensiveAI::CityTarget(op)!=p)?"operation_retargeted":
                (!GET_PLAYER((PlayerTypes)i->first.owner).IsAtWarWith((PlayerTypes)i->second.enemy) && !active)?"peace":NULL;
            const bool invalid=reason!=NULL;
            if(invalid || (!active && turn-i->second.refreshed>Setting("AIOffensiveSupportMemoryTurns",12)))
            {
                CvStackingDiagnostics::Record(1,(PlayerTypes)i->first.owner,"OFFENSIVE_OBJECTIVE","target=%d domain=%d action=expire reason=%s operation=%d refreshedAge=%d",i->first.target,i->first.domain,reason?reason:"memory_timeout",i->second.operation,turn-i->second.refreshed);
                objectives.erase(i++);
            }
            else ++i;
        }
        for(std::map<Key,Commitment>::iterator i=commitments.begin();i!=commitments.end();)
        {
            const CvUnit* u=GET_PLAYER((PlayerTypes)i->first.first).getUnit(i->first.second);
            const char* reason=!Usable(u)?"unit_unusable":objectives.find(i->second.goal)==objectives.end()?"objective_expired":
                AssignedElsewhere(u,i->second.goal)?"operation_reassigned":
                turn-i->second.lastProgress>Setting("AIOffensiveSupportStallTurns",5)?"no_progress":NULL;
            if(reason)
            {
                CvStackingDiagnostics::Record(1,(PlayerTypes)i->first.first,"OFFENSIVE_SUPPORT","unit=%d target=%d action=release_stale reason=%s dispatchAge=%d progressAge=%d eta=%d",i->first.second,i->second.goal.target,reason,turn-i->second.turn,turn-i->second.lastProgress,i->second.eta);
                EraseCommitment(i++);
            }
            else ++i;
        }
        for(std::map<ObjectiveKey,Failure>::iterator i=failures.begin();i!=failures.end();)
            if(i->second.until<turn) failures.erase(i++); else ++i;
        for(std::map<Key,March>::iterator i=marches.begin();i!=marches.end();)
            if(turn-i->second.turn>2) marches.erase(i++); else ++i;
        for(std::map<Key,std::pair<int,int> >::iterator i=captureRetries.begin();i!=captureRetries.end();)
            if(i->second.second<turn || !Usable(GET_PLAYER((PlayerTypes)i->first.first).getUnit(i->first.second))) captureRetries.erase(i++); else ++i;
    }
    Objective* Touch(PlayerTypes owner,CvPlot* target,DomainTypes domain)
    {
        if(!target || !target->isCity() || target->getOwner()==NO_PLAYER ||
            GET_PLAYER(target->getOwner()).getTeam()==GET_PLAYER(owner).getTeam()) return NULL;
        Refresh(); const ObjectiveKey key(owner,target->GetPlotIndex(),domain);
        std::map<ObjectiveKey,Failure>::const_iterator failed=failures.find(key);
        if(failed!=failures.end() && failed->second.enemy==target->getOwner() && failed->second.until>=currentTurn) return NULL;
        std::map<ObjectiveKey,Objective>::iterator found=objectives.find(key);
        if(found==objectives.end())
        {
            int count=0;
            for(std::map<ObjectiveKey,Objective>::const_iterator i=objectives.begin();i!=objectives.end();++i) count+=i->first.owner==owner;
            if(count>=Setting("AIOffensiveSupportMaximumObjectives",8)) return NULL;
        }
        Objective& o=objectives[key];
        if(o.created<0 || o.enemy!=target->getOwner()) { o=Objective(); o.created=o.lastUsefulTurn=currentTurn; }
        o.enemy=target->getOwner(); o.refreshed=currentTurn;
        if(o.staging<0) o.staging=target->GetPlotIndex();
        return &o;
    }
    // Summary diagnostic only: where land combat and siege units are while
    // the player's land objectives gather (army, support commitment, in an
    // own city, healing, otherwise free) and how far from the nearest one.
    // Pure reads: no per-turn assessment cache is filled from here.
    void LogRoster(PlayerTypes owner)
    {
        const int interval=Setting("AIAssaultObjectiveSummaryInterval",5);
        if(interval<=0 || currentTurn%interval!=0 || !CvStackingDiagnostics::EnabledCategory(1,owner,"SIEGE_ROSTER")) return;
        CvPlayer& player=GET_PLAYER(owner);
        if(player.isMinorCiv() || player.isBarbarian()) return;
        std::vector<const CvPlot*> targets;
        for(std::map<ObjectiveKey,Objective>::const_iterator i=objectives.begin();i!=objectives.end();++i)
            if(i->first.owner==owner && i->first.domain==DOMAIN_LAND) targets.push_back(GC.getMap().plotByIndexUnchecked(i->first.target));
        if(targets.empty()) return;
        int count[2][9]={{0}}; // [siege] army, committed, retained, healing, free, within 4, 8, 15, farther
        int loop=0;
        for(CvUnit* u=player.firstUnit(&loop);u;u=player.nextUnit(&loop))
        {
            if(!Usable(u) || u->getDomainType()!=DOMAIN_LAND) continue;
            int* c=count[CvStackingOffensiveAI::IsSiegeUnit(u)?1:0];
            ++c[u->getArmyID()!=-1?0:commitments.find(Key(owner,u->GetID()))!=commitments.end()?1:
                u->plot()->isCity()&&u->plot()->getOwner()==owner?2:u->shouldHeal(false)?3:4];
            int nearest=INT_MAX;
            for(size_t t=0;t<targets.size();++t) nearest=min(nearest,plotDistance(*u->plot(),*targets[t]));
            ++c[nearest<=4?5:nearest<=8?6:nearest<=15?7:8];
        }
        CvStackingDiagnostics::Record(1,owner,"SIEGE_ROSTER","objectives=%d siegeArmy=%d siegeCommitted=%d siegeInCity=%d siegeHealing=%d siegeFree=%d siegeNear4=%d siegeNear8=%d siegeNear15=%d siegeFar=%d otherArmy=%d otherCommitted=%d otherInCity=%d otherHealing=%d otherFree=%d otherNear4=%d otherNear8=%d otherNear15=%d otherFar=%d",
            (int)targets.size(),count[1][0],count[1][1],count[1][2],count[1][3],count[1][4],count[1][5],count[1][6],count[1][7],count[1][8],
            count[0][0],count[0][1],count[0][2],count[0][3],count[0][4],count[0][5],count[0][6],count[0][7],count[0][8]);
    }
    void Sync(PlayerTypes owner)
    {
        Refresh(); if(synced[owner]==currentTurn) return;
        synced[owner]=currentTurn;
        CvPlayer& player=GET_PLAYER(owner);
        for(size_t i=0;i<player.getNumAIOperations();++i)
            CvStackingOffensiveAI::ObserveOperation(player.getAIOperationByIndex(i));
        // Reconstruct queue commitments after loading; each city owns one claim.
        int loop=0;
        for(CvCity* city=player.firstCity(&loop);city;city=player.nextCity(&loop))
            if(city->getProductionUnit()!=NO_UNIT && !city->IsBuildingUnitForOperation() && production.find(Key(owner,city->GetID()))==production.end())
                CvStackingOffensiveAI::RecordProduction(city,city->getProductionUnit());
        LogRoster(owner);
    }
    bool Matches(CvUnit* u,const ObjectiveKey& key,const Objective& o)
    {
        if(!Usable(u) || u->getDomainType()!=key.domain) return false;
        CvPlayer& player=GET_PLAYER((PlayerTypes)key.owner);
        CvArmyAI* army=player.getArmyAI(u->getArmyID());
        if(army) return army->GetOperationID()==o.operation;
        std::map<Key,Commitment>::const_iterator c=commitments.find(Key(key.owner,u->GetID()));
        if(c!=commitments.end()) return c->second.goal==key;
        if(u->shouldHeal(false) || CvStackingAI::RetainCityUnit(u)) return false;
        CvPlot* target=GC.getMap().plotByIndexUnchecked(key.target);
        if(plotDistance(*u->plot(),*target)>Setting("AIOffensiveSupportLocalRadius",4)) return false;
        // A nearby unassigned unit is credited to just one objective.
        for(std::map<ObjectiveKey,Objective>::const_iterator i=objectives.begin();i!=objectives.end();++i)
        {
            if(i->first.owner!=key.owner || i->first.domain!=key.domain || i->first==key) continue;
            CvPlot* other=GC.getMap().plotByIndexUnchecked(i->first.target);
            const int d=plotDistance(*u->plot(),*target),otherD=plotDistance(*u->plot(),*other);
            if(otherD<d || (otherD==d && i->first.target<key.target)) return false;
        }
        return true;
    }
    int EnemyStrength(PlayerTypes owner,CvPlot* target)
    {
        // Only use visible city strength; opening readiness still requires a healthy core when it is hidden.
        int total=0; const TeamTypes team=GET_PLAYER(owner).getTeam();
        if(target->isVisible(team)) total=target->getPlotCity()->getStrengthValue()/100;
        for(int i=0;i<RING2_PLOTS;++i)
        {
            CvPlot* p=iterateRingPlots(target,i);
            if(!p || !p->isVisible(team)) continue;
            for(int j=0;j<p->getNumUnits();++j)
            {
                const CvUnit* u=p->getUnitByIndex(j);
                if(Usable(u) && !u->isInvisible(team,false) && u->getOwner()==target->getOwner()) total+=CvStackingAI::UnitStrength(u);
            }
        }
        return total;
    }
    bool KnownFortified(PlayerTypes owner,const CvCity* city)
    {
        return city && city->plot()->isVisible(GET_PLAYER(owner).getTeam()) &&
            (city->getStrengthValue()/100>=Setting("AIAssaultStrongCityStrength",25) || CvStacking::GetCityProtection(city)>0);
    }
    int EssentialSiege(PlayerTypes owner,const CvCity* city,DomainTypes domain)
    {
        const int desired=CvStackingOffensiveAI::DesiredSiegeUnits(owner,city,domain);
        return domain==DOMAIN_SEA?desired:min(desired,Setting("AIAssaultEssentialSiegeUnits",2));
    }
    bool WaveRecordStillValid(PlayerTypes owner,const CvPlot* target,const AssaultWaveUnit& row)
    {
        const CvUnit* u=GET_PLAYER(owner).getUnit(row.unit);
        if(!Usable(u)||u->getArmyID()!=row.army||u->GetCurrHitPoints()!=row.hp||u->getUnitType()!=row.type||
            u->GetRange()!=row.range||u->baseMoves(false)!=row.moves||u->plot()->GetPlotIndex()!=row.plot||u->getDomainType()!=row.domain||u->getMoves()!=row.remaining||
            u->canUseNow()!=!!row.available||u->isOutOfAttacks()!=!!row.spent||u->isSetUpForRangedAttack()!=!!row.setup) return false;
        const int roles=(CvStackingOffensiveAI::CanCapture(u,target)?1:0)|(u->IsCanAttackRanged()?2:0)|
            ((u->getDomainType()==DOMAIN_SEA?u->IsCanAttackRanged():CvStackingOffensiveAI::IsSiegeUnit(u))?4:0);
        return roles==row.roles;
    }
    AssaultWave SelectFirstWave(const std::vector<AssaultWaveUnit>& rows,int minimum,int siege,int ranged,
        int enemy,int margin,int hp,int captureEta,int maxArrival,int spread,int army=-1,int ownMinimum=0)
    {
        AssaultWave best;bool found=false;
        // The existing XML maximum is bounded to ten; no new paths or search
        // branches are created. All work uses the already-simulated records.
        for(int start=0;start<=maxArrival;++start)
        {
            const int end=min(maxArrival,start+spread);AssaultWave wave;
            for(size_t i=0;i<rows.size();++i)
            {
                const AssaultWaveUnit& r=rows[i];
                if(r.eta<start||r.eta>end||(army>=0&&r.army!=-1&&r.army!=army))continue;
                ++wave.units;wave.siege+=(r.roles&4)!=0;wave.ranged+=(r.roles&2)!=0;wave.capture+=(r.roles&1)!=0;
                wave.strength+=r.strength;wave.damage+=r.damage;wave.sustain+=r.sustain;
                wave.first=min(wave.first,r.eta);wave.last=max(wave.last,r.eta);wave.own+=r.army==army;
            }
            // An already-arrived reserved capturer may wait for the wave.
            if(captureEta<0||captureEta==INT_MAX||captureEta>end||(captureEta!=0&&captureEta<start))wave.failed|=ASSAULT_CAPTURE;
            if(wave.siege<siege||wave.ranged<ranged)wave.failed|=ASSAULT_SIEGE;
            if(wave.units<minimum)wave.failed|=ASSAULT_COUNT;
            if(enemy<=0)wave.failed|=ASSAULT_UNKNOWN;
            else if((long long)wave.strength*100<(long long)enemy*margin)wave.failed|=ASSAULT_STRENGTH;
            if(wave.own<ownMinimum)wave.failed|=ASSAULT_OWN_ARMY;
            if(wave.first==INT_MAX||wave.last-wave.first>spread)wave.failed|=ASSAULT_COHESION;
            const unsigned relevant=ASSAULT_CAPTURE|ASSAULT_SIEGE|ASSAULT_COUNT|ASSAULT_STRENGTH|ASSAULT_OWN_ARMY|ASSAULT_UNKNOWN|ASSAULT_COHESION;
            const bool valid=(wave.failed&relevant)==0,bestValid=(best.failed&relevant)==0;
            const bool finish=wave.damage>=hp,bestFinish=best.damage>=hp;
            const bool betterRank=finish!=bestFinish?finish:wave.sustain!=best.sustain?wave.sustain>best.sustain:
                wave.damage!=best.damage?wave.damage>best.damage:wave.strength!=best.strength?wave.strength>best.strength:wave.first<best.first;
            if(!found||(valid&&!bestValid)||(valid==bestValid&&betterRank))
            {best=wave;found=true;}
        }
        return best;
    }
    bool WaveCanSustain(AssaultWave& wave,int hp,int healing,int horizon,bool complete)
    {
        const int confidence=complete?100:Setting("AIAssaultIncompleteDamagePercent",125);
        if(wave.damage<hp&&(long long)(wave.sustain-healing)*horizon*100<(long long)hp*confidence)wave.failed|=ASSAULT_DAMAGE;
        return wave.failed==0;
    }
    void CopyWave(CvStackingOffensiveAI::AssaultPlan& plan,const AssaultWave& wave)
    {
        plan.waveUnits=wave.units;plan.waveSiege=wave.siege;plan.waveCapturers=wave.capture;
        plan.waveStrength=wave.strength;plan.waveDamage=wave.damage;plan.waveSustain=wave.sustain;
        plan.waveFirstETA=wave.first==INT_MAX?-1:wave.first;plan.waveLastETA=wave.last;plan.failedMask=wave.failed;
    }

    bool EntryRanged(const CvUnitEntry* entry)
    { return entry && entry->GetRangedCombat()>0 && entry->GetRange()>0; }
    bool EntrySiege(const CvUnitEntry* entry)
    { return EntryRanged(entry) && entry->GetDomainType()==DOMAIN_LAND && entry->GetDefaultUnitAIType()==UNITAI_CITY_BOMBARD; }
    bool EntryCapture(const CvUnitEntry* entry)
    {
        if(!entry || EntryRanged(entry) || entry->GetCombat()<=0) return false;
        const UnitAITypes role=entry->GetDefaultUnitAIType();
        return role==UNITAI_ATTACK || role==UNITAI_DEFENSE || role==UNITAI_COUNTER || role==UNITAI_FAST_ATTACK || role==UNITAI_ATTACK_SEA;
    }
    struct ProductionQueueState
    {
        int unit,operation,land,sea,supply;bool valid;
        ProductionQueueState():unit(NO_UNIT),operation(-1),land(0),sea(0),supply(0),valid(true){}
        bool operator==(const ProductionQueueState& other)const
        {return unit==other.unit&&operation==other.operation&&land==other.land&&sea==other.sea&&supply==other.supply&&valid==other.valid;}
    };
    struct ProductionPolicyState
    {
        int turn,cityCount,softCap,land,sea,supply,observedUnits;
        unsigned long generation;
        bool ready,busy,softDirty;
        std::map<int,ProductionQueueState> cities;
        std::set<std::pair<int,int> > rejections;
        ProductionPolicyState():turn(-1),cityCount(-1),softCap(0),land(0),sea(0),supply(0),observedUnits(-1),generation(0),ready(false),busy(false),softDirty(false){}
    };
    ProductionPolicyState productionPolicy[MAX_PLAYERS];
    std::vector<PromotionTypes> noCapturePromotions;
    int noCapturePromotionCount=-1;

    void AdvanceProductionGeneration(PlayerTypes owner)
    {
        ProductionPolicyState& state=productionPolicy[owner];
        if(state.generation==static_cast<unsigned long>(-1))
        {state.ready=false;state.turn=-1;state.generation=0;}
        ++state.generation;
        // At most the configured small objective registry, never the unit/map lists.
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();++i)
            if(i->first.owner==owner)i->second.productionTurn=-1;
    }
    ProductionQueueState ReadProductionQueue(const CvCity* city)
    {
        ProductionQueueState value;
        if(!city)return value;
        value.unit=city->getProductionUnit();
        value.operation=city->IsBuildingUnitForOperation()?city->GetUnitProductionOperation():-1;
        const CvUnitEntry* entry=value.unit==NO_UNIT?NULL:GC.getUnitInfo((UnitTypes)value.unit);
        if(value.unit!=NO_UNIT&&!entry)value.valid=false;
        if(entry)
        {
            // Include ranged-only and military support types, including AIR for
            // supply. Future free-promotion/trait supply exemptions are not assumed.
            const bool military=entry->IsMilitarySupport()||entry->GetCombat()>0||entry->GetRangedCombat()>0;
            value.land=military&&entry->GetDomainType()==DOMAIN_LAND;
            value.sea=military&&entry->GetDomainType()==DOMAIN_SEA;
            value.supply=military&&!entry->IsNoSupply();
        }
        return value;
    }
    bool EnsureProductionPolicy(PlayerTypes owner)
    {
        if(owner<0||owner>=MAX_PLAYERS)return false;
        ProductionPolicyState& state=productionPolicy[owner];
        if(state.busy)return false;
        CvPlayer& player=GET_PLAYER(owner);
        const int turn=GC.getGame().getGameTurn();
        if(state.ready&&state.turn==turn&&state.cityCount==player.getNumCities())return true;
        state.busy=true;state.ready=false;
        try
        {
            state.cities.clear();state.rejections.clear();state.land=state.sea=state.supply=0;
            state.softCap=max(0,player.GetEconomicAI()->GetSoftSupplyCap());
            state.observedUnits=player.getNumUnits();
            state.softDirty=false;
            int loop=0;
            for(CvCity* city=player.firstCity(&loop);city;city=player.nextCity(&loop))
            {
                const ProductionQueueState value=ReadProductionQueue(city);
                if(!value.valid){state.cities.clear();state.busy=false;return false;}
                state.cities[city->GetID()]=value;
                state.land+=value.land;state.sea+=value.sea;state.supply+=value.supply;
            }
            state.turn=turn;state.cityCount=player.getNumCities();
            AdvanceProductionGeneration(owner);
            state.ready=true;state.busy=false;return true;
        }
        catch(const std::bad_alloc&)
        {state.cities.clear();state.land=state.sea=state.supply=0;state.busy=false;state.ready=false;return false;}
    }
    void ReadLiveProductionBudget(PlayerTypes owner,CvStackingOffensiveAI::ProductionBudget& result)
    {
        result=CvStackingOffensiveAI::ProductionBudget();
        if(!EnsureProductionPolicy(owner))return;
        ProductionPolicyState& state=productionPolicy[owner];CvPlayer& player=GET_PLAYER(owner);
        // Air/civilian births and losses also change VP's affordable land/sea
        // budget. Refresh only on a changed live count, never for each candidate.
        if(state.softDirty||state.observedUnits!=player.getNumUnits())
        {state.softCap=max(0,player.GetEconomicAI()->GetSoftSupplyCap());state.observedUnits=player.getNumUnits();state.softDirty=false;}
        result.turn=state.turn;result.generation=state.generation;
        result.queuedSupply=state.supply;result.queuedLand=state.land;result.queuedSea=state.sea;
        result.supplyAvailable=player.GetNumUnitsSupplied()-player.GetNumUnitsToSupply()-state.supply;
        const int budget=state.softCap;
        result.affordableAvailable=budget-player.getNumMilitaryLandUnits()-player.getNumMilitarySeaUnits()-state.land-state.sea;
        result.ready=true;
    }
    bool BirthCannotCapture(const CvCity* city,UnitTypes unit,const CvUnitEntry* entry)
    {
        if(noCapturePromotionCount!=GC.getNumPromotionInfos())
        {
            noCapturePromotions.clear();
            for(int i=0;i<GC.getNumPromotionInfos();++i)
            {const CvPromotionEntry* p=GC.getPromotionInfo((PromotionTypes)i);if(p&&(p->IsNoCapture()||p->IsOnlyDefensive()))noCapturePromotions.push_back((PromotionTypes)i);}
            noCapturePromotionCount=GC.getNumPromotionInfos();
        }
        if(noCapturePromotions.empty())return false;
        CvPlayer& player=GET_PLAYER(city->getOwner());
        // The existing city accessor includes religious birth promotions too.
        const std::vector<PromotionTypes> cityPromotions=city->getFreePromotions();
        for(size_t i=0;i<noCapturePromotions.size();++i)
        {
            const PromotionTypes promotion=noCapturePromotions[i];const CvPromotionEntry* info=GC.getPromotionInfo(promotion);
            if(!info)return true; // Unsupported metadata cannot certify a capturer.
            if(entry->GetFreePromotions(promotion))return true;
            if(entry->IsUnitEraUpgrade())
                for(int era=0;era<GC.getNumEraInfos();++era)
                    if(era<=(int)GET_TEAM(player.getTeam()).GetCurrentEra()&&entry->GetUnitNewEraPromotions(promotion,era)>0)return true;
            if(entry->GetUnitCombatType()!=NO_UNITCOMBAT&&player.GetPlayerTraits()->HasFreePromotionUnitCombat(promotion,(UnitCombatTypes)entry->GetUnitCombatType()))
            {const TechTypes tech=(TechTypes)info->GetTechPrereq();if(tech==NO_TECH||player.HasTech(tech))return true;}
            if(entry->GetUnitClassType()!=NO_UNITCLASS&&player.GetPlayerTraits()->HasFreePromotionUnitClass(promotion,(UnitClassTypes)entry->GetUnitClassType()))return true;
            if((player.IsFreePromotion(promotion)||std::find(cityPromotions.begin(),cityPromotions.end(),promotion)!=cityPromotions.end())&&
                (::IsPromotionValidForUnitCombatType(promotion,unit)||::IsPromotionValidForCivilianUnitType(promotion,unit)))return true;
        }
        return false;
    }
    int ProductionEntryRoles(const CvCity* city,UnitTypes unit)
    {
        const CvUnitEntry* entry=GC.getUnitInfo(unit);if(!entry)return 0;
        const bool ranged=entry->GetRangedCombat()>0&&entry->GetRange()>0;
        int roles=0;
        if(ranged)
        {
            if(entry->GetDomainType()==DOMAIN_SEA||EntrySiege(entry))roles|=CvStackingOffensiveAI::PRODUCTION_SIEGE;
            else roles|=CvStackingOffensiveAI::PRODUCTION_RANGED;
        }
        else if(EntryCapture(entry)&&!BirthCannotCapture(city,unit,entry))roles|=CvStackingOffensiveAI::PRODUCTION_CAPTURE;
        return roles;
    }

    bool ProductionQueueCredits(const Key& city,const ProductionQueueState& queue,const ObjectiveKey& key,const Objective& objective)
    {
        const CvUnitEntry* entry=queue.unit==NO_UNIT?NULL:GC.getUnitInfo((UnitTypes)queue.unit);
        if(!entry||entry->GetDomainType()!=key.domain)return false;
        if(queue.operation>=0)return queue.operation==objective.operation;
        std::map<Key,ProductionClaim>::const_iterator claim=production.find(city);
        return claim!=production.end()&&claim->second.unit==queue.unit&&claim->second.goal==key;
    }
    int ProductionChoice(const CvCity* city,UnitTypes unit,ObjectiveKey& chosen,CvStackingOffensiveAI::ProductionIntent* detail=NULL,bool replaceQueue=true)
    {
        try
        {
        const PlayerTypes owner=city->getOwner();CvPlayer& player=GET_PLAYER(owner);
        const CvUnitEntry* entry=GC.getUnitInfo(unit);
        if(!entry||(entry->GetCombat()<=0&&entry->GetRangedCombat()<=0)||entry->GetDomainType()==DOMAIN_AIR||
            city->getProductionTurnsLeft(unit,0)>Setting("AIOffensiveProductionMaximumTurns",12))return 0;
        CvStackingOffensiveAI::ProductionBudget budget;ReadLiveProductionBudget(owner,budget);
        if(!budget.ready)return 0; // Unknown optional proof never waives a native limit.
        ProductionPolicyState& state=productionPolicy[owner];const Key ownCity(owner,city->GetID());
        const int roles=ProductionEntryRoles(city,unit);int best=0,bestEvidence=INT_MIN;
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();++i)
        {
            const ObjectiveKey& key=i->first;Objective& o=i->second;
            if(key.owner!=owner||key.domain!=entry->GetDomainType())continue;
            CvPlot* target=GC.getMap().plotByIndexUnchecked(key.target);
            if(!target||!target->isCity()||target->getOwner()!=o.enemy||
                CvStackingOffensiveAI::RouteBlocked(owner,target,key.domain==DOMAIN_SEA)||
                plotDistance(*city->plot(),*target)>Setting("AIReinforcementMaximumTurns",12)*max(1,entry->GetMoves()))continue;
            if(o.staffTurn!=currentTurn)
            {
                o.staffTurn=currentTurn;o.staffUnits=o.staffSiege=o.staffRanged=o.staffCapture=0;
                int loop=0;
                for(CvUnit* u=player.firstUnit(&loop);u;u=player.nextUnit(&loop))
                {
                    if(!Matches(u,key,o)||u->GetCurrHitPoints()*100<u->GetMaxHitPoints()*Setting("AIAssaultHealthyPercent",65))continue;
                    ++o.staffUnits;o.staffSiege+=key.domain==DOMAIN_SEA?u->IsCanAttackRanged():CvStackingOffensiveAI::IsSiegeUnit(u);
                    o.staffRanged+=key.domain==DOMAIN_LAND&&u->IsCanAttackRanged()&&!CvStackingOffensiveAI::IsSiegeUnit(u);
                    o.staffCapture+=CvStackingOffensiveAI::CanCapture(u,target);
                }
                o.productionTurn=-1;
            }
            if(o.productionTurn!=currentTurn||o.productionGeneration!=state.generation)
            {
                o.productionUnits=o.staffUnits;o.productionSiege=o.staffSiege;
                o.productionRanged=o.staffRanged;o.productionCapture=o.staffCapture;o.productionQueued=0;o.productionCaptureQueues.clear();
                for(std::map<int,ProductionQueueState>::const_iterator q=state.cities.begin();q!=state.cities.end();++q)
                {
                    if(!ProductionQueueCredits(Key(owner,q->first),q->second,key,o))continue;
                    CvCity* factory=player.getCity(q->first);if(!factory)continue;
                    const CvUnitEntry* pending=GC.getUnitInfo((UnitTypes)q->second.unit);
                    const bool pendingSiege=key.domain==DOMAIN_SEA?EntryRanged(pending):EntrySiege(pending);
                    ++o.productionUnits;++o.productionQueued;
                    o.productionSiege+=pendingSiege;
                    o.productionRanged+=key.domain==DOMAIN_LAND&&EntryRanged(pending)&&!EntrySiege(pending);
                    if(EntryCapture(pending))o.productionCaptureQueues.push_back(q->first);
                }
                o.productionTurn=currentTurn;o.productionGeneration=state.generation;
            }
            int count=o.productionUnits,siege=o.productionSiege,ranged=o.productionRanged,capture=o.staffCapture,queued=o.productionQueued;
            // Birth metadata can change without a head/operation change. Only
            // these sparse already-credited queues need live capture checks.
            for(size_t q=0;q<o.productionCaptureQueues.size();++q)
            {
                const int id=o.productionCaptureQueues[q];if(replaceQueue&&id==city->GetID())continue;
                CvCity* factory=player.getCity(id);std::map<int,ProductionQueueState>::const_iterator pending=state.cities.find(id);
                if(factory&&pending!=state.cities.end()&&(ProductionEntryRoles(factory,(UnitTypes)pending->second.unit)&CvStackingOffensiveAI::PRODUCTION_CAPTURE))++capture;
            }
            std::map<int,ProductionQueueState>::const_iterator own=state.cities.find(city->GetID());
            int supplyCredit=0,affordableCredit=0;
            if(own!=state.cities.end())
            {
                if(replaceQueue){supplyCredit=own->second.supply;affordableCredit=own->second.land+own->second.sea;}
                if(replaceQueue&&ProductionQueueCredits(ownCity,own->second,key,o))
                {
                    const CvUnitEntry* current=GC.getUnitInfo((UnitTypes)own->second.unit);
                    --count;--queued;siege-=key.domain==DOMAIN_SEA?EntryRanged(current):EntrySiege(current);
                    ranged-=key.domain==DOMAIN_LAND&&EntryRanged(current)&&!EntrySiege(current);
                }
            }
            const int desired=CvStackingOffensiveAI::DesiredAssaultUnits(owner,target->getPlotCity(),(DomainTypes)key.domain)+Setting("AIOffensiveSupportReserveUnits",4);
            const int desiredSiege=CvStackingOffensiveAI::DesiredSiegeUnits(owner,target->getPlotCity(),(DomainTypes)key.domain);
            const int missingSiege=max(0,desiredSiege+(desiredSiege>0?Setting("AIOffensiveProductionSiegeReserves",2):0)-siege);
            const int missingCapture=max(0,Setting("AIOffensiveSupportMinimumCapturers",2)-capture);
            const int missingRanged=key.domain==DOMAIN_LAND?max(0,Setting("AIOffensiveSupportMinimumRanged",2)-ranged):0;
            const bool role=(missingSiege&&(roles&CvStackingOffensiveAI::PRODUCTION_SIEGE))||
                (missingCapture&&(roles&CvStackingOffensiveAI::PRODUCTION_CAPTURE))||(missingRanged&&(roles&CvStackingOffensiveAI::PRODUCTION_RANGED));
            if(!role&&(count>=desired||missingSiege||missingCapture||missingRanged))continue;
            const int score=Setting("AIOffensiveProductionPriority",400)+(role?Setting("AIOffensiveProductionRolePriority",400):0)-
                plotDistance(*city->plot(),*target)*Setting("AIReinforcementTravelWeight",15);
            CvStackingOffensiveAI::ProductionIntent intent;intent.target=key.target;intent.domain=key.domain;intent.roles=roles;
            intent.units=count;intent.queued=queued;intent.missingSiege=missingSiege;intent.missingRanged=missingRanged;intent.missingCapture=missingCapture;intent.missingRole=role;
            const int supplyCost=entry->IsNoSupply()?0:1;
            const int maximum=Setting("AIOffensiveSupportMaximumUnits",32)+(role?Setting("AIOffensiveProductionRoleRepairUnits",2):0);
            if(city->isUnderSiege())intent.reason=CvStackingOffensiveAI::PRODUCTION_HOME_DEFENSE;
            else if(queued>=Setting("AIOffensiveProductionMaximumUnits",4))intent.reason=CvStackingOffensiveAI::PRODUCTION_QUEUE_LIMIT;
            else if(count>=maximum)intent.reason=CvStackingOffensiveAI::PRODUCTION_FORCE_LIMIT;
            else if(budget.supplyAvailable+supplyCredit<supplyCost)intent.reason=CvStackingOffensiveAI::PRODUCTION_SUPPLY;
            else if(budget.affordableAvailable+affordableCredit<1)intent.reason=CvStackingOffensiveAI::PRODUCTION_AFFORDABILITY;
            else
            {
                intent.reason=CvStackingOffensiveAI::PRODUCTION_NONE;intent.bonus=max(0,score);
                intent.quotaUnits=Setting("AIOffensiveProductionRecommendationSlack",2);
                intent.quotaEligible=role&&intent.bonus>0&&intent.quotaUnits>0;
                if(score>best){best=score;chosen=key;if(detail)*detail=intent;}
            }
            if(best==0&&score>bestEvidence){bestEvidence=score;if(detail)*detail=intent;}
        }
        return max(0,best);
        }
        catch(const std::bad_alloc&)
        {
            CvStackingOffensiveAI::InvalidateProductionOwner(city->getOwner());
            if(detail)*detail=CvStackingOffensiveAI::ProductionIntent();
            return 0;
        }
    }
    CvPlot* AttackApproach(CvUnit* unit,CvPlot* target,int maximumTurns,int& eta)
    {
        const PlayerTypes owner=unit->getOwner();
        const bool ranged=unit->IsCanAttackRanged();
        const int budget=Setting("AIAssaultPathQueriesPerTurn",64);
        const int range=ranged?unit->GetRange():1;
        if(unit->isNativeDomain(unit->plot()) && plotDistance(*unit->plot(),*target)<=range &&
            (!ranged || unit->canEverRangeStrikeAt(target->getX(),target->getY(),unit->plot(),false)))
        { eta=0;return unit->plot(); }
        if(assaultQueries[owner]>=budget) return NULL;
        ++assaultQueries[owner];
        const int flags=(ranged?CvUnit::MOVEFLAG_APPROX_TARGET_RING2:CvUnit::MOVEFLAG_APPROX_TARGET_RING1)|
            CvUnit::MOVEFLAG_APPROX_TARGET_NATIVE_DOMAIN|CvUnit::MOVEFLAG_SAFE_EMBARK_ONLY;
        if(unit->GeneratePath(target,flags,maximumTurns,&eta) && eta<=maximumTurns)
        {
            CvPlot* end=unit->GetPathLastPlot();
            if(end && unit->isNativeDomain(end) && plotDistance(*end,*target)<=range &&
                (!ranged || unit->canEverRangeStrikeAt(target->getX(),target->getY(),end,false))) return end;
        }
        if(!ranged) return NULL;
        // A ring-two endpoint can have blocked line of sight or be outside a
        // unique unit's range. Try a bounded set of real legal firing positions.
        std::vector<std::pair<int,int> > candidates;
        const int radius=min(range,Setting("AIAssaultFiringPositionRadiusMaximum",6));
        const int scan=min(1+3*radius*(radius+1),Setting("AIAssaultFiringPositionScanPlots",96));
        for(int i=1;i<scan;++i)
        {
            CvPlot* p=iterateRingPlots(target,i);
            if(!p || !p->isVisible(GET_PLAYER(owner).getTeam()) || !unit->isNativeDomain(p) ||
                !unit->canMoveInto(*p,CvUnit::MOVEFLAG_DESTINATION) ||
                !unit->canEverRangeStrikeAt(target->getX(),target->getY(),p,false)) continue;
            candidates.push_back(std::make_pair(plotDistance(*unit->plot(),*p),p->GetPlotIndex()));
        }
        std::sort(candidates.begin(),candidates.end());
        for(size_t i=0;i<candidates.size() && i<(size_t)Setting("AIAssaultFiringPositionCandidates",6);++i)
        {
            if(assaultQueries[owner]>=budget) break;
            ++assaultQueries[owner];
            CvPlot* p=GC.getMap().plotByIndexUnchecked(candidates[i].second);
            if(unit->GeneratePath(p,CvUnit::MOVEFLAG_SAFE_EMBARK_ONLY,maximumTurns,&eta) && eta<=maximumTurns &&
                unit->GetPathLastPlot()==p) return p;
        }
        return NULL;
    }
    void CapturePlan(PlayerTypes owner,CvPlot* target,Objective& o,DomainTypes domain=DOMAIN_LAND)
    {
        if(o.captureTurn==currentTurn) return;
        const int previous=o.captureOwner==owner?o.captureID:-1;
        const int previousEta=o.captureEta;
        bool actualProgress=false;
        CvUnit* best=NULL; int bestEta=INT_MAX,bestScore=INT_MAX;
        o.captureTurn=currentTurn; o.captureID=-1; o.captureKnown=true;
        const int horizon=Setting("AICapturePlanMaximumTurns",6);
        CvPlayer& player=GET_PLAYER(owner);
        int loop=0;
        for(CvUnit* u=player.firstUnit(&loop);u;u=player.nextUnit(&loop))
        {
            if(u->getDomainType()!=domain || !CvStackingOffensiveAI::CanCapture(u,target) || CvStackingAI::RetainCityUnit(u) || u->IsCoveringFriendlyCivilian()) continue;
            const Key unitKey(owner,u->GetID());
            std::map<Key,std::pair<int,int> >::const_iterator retry=captureRetries.find(unitKey);
            if(retry!=captureRetries.end() && retry->second.first==target->GetPlotIndex() && retry->second.second>=currentTurn) continue;
            CvArmyAI* army=player.getArmyAI(u->getArmyID());
            if(army)
            {
                CvAIOperation* op=player.getAIOperation(army->GetOperationID());
                if(!Live(op) || CvStackingOffensiveAI::CityTarget(op)!=target) continue;
            }
            std::map<Key,Commitment>::const_iterator c=commitments.find(Key(owner,u->GetID()));
            if(c!=commitments.end() && c->second.goal.target!=target->GetPlotIndex()) continue;
            if(plotDistance(*u->plot(),*target)>horizon*max(1,u->baseMoves(false))+1) continue;
            if(captureQueries[owner]>=Setting("AICapturePlanPathQueriesPerTurn",32)) { o.captureKnown=false; break; }
            ++captureQueries[owner];
            const int flags=CvUnit::MOVEFLAG_APPROX_TARGET_RING1|CvUnit::MOVEFLAG_APPROX_TARGET_NATIVE_DOMAIN|CvUnit::MOVEFLAG_SAFE_EMBARK_ONLY;
            int eta=INT_MAX;
            if(!u->GeneratePath(target,flags,horizon,&eta))
            {
                CvStackingDiagnostics::Record(2,owner,"CAPTURE_CANDIDATE","target=%d unit=%d reason=no_legal_route",target->GetPlotIndex(),u->GetID());
                continue;
            }
            CvPlot* approach=u->GetPathLastPlot();
            // Successful approximate paths can have no nodes when already in
            // range. The current native adjacent tile is then the real approach.
            if(!approach && plotDistance(*u->plot(),*target)<=1 && u->isNativeDomain(u->plot()))
            { approach=u->plot();eta=0; }
            if(!approach || plotDistance(*approach,*target)>1 || !u->isNativeDomain(approach)) continue;
            // A one-turn ETA is not an arrival. Fast units can stay at a safe
            // assembly point indefinitely while still forecasting ETA one.
            if(u->GetID()==previous && plotDistance(*u->plot(),*target)>1 && o.captureProgress>=0 &&
                currentTurn-o.captureProgress>=Setting("AICaptureNoProgressTurns",6))
            {
                captureRetries[unitKey]=std::make_pair(target->GetPlotIndex(),currentTurn+Setting("AICaptureRetryTurns",4));
                EraseCommitment(unitKey);
                CvStackingDiagnostics::Record(1,owner,"CAPTURE_COMMITMENT","target=%d unit=%d action=release reason=no_arrival_progress eta=%d progressAge=%d",target->GetPlotIndex(),u->GetID(),eta,currentTurn-o.captureProgress);
                continue;
            }
            int retaliation=0,garrison=0;
            const int captureDamage=TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(target->getPlotCity(),u,approach,retaliation,garrison,false,0,
                max(0,target->getPlotCity()->GetMaxHitPoints()-target->getPlotCity()->getDamage()-1));
            const bool healthy=u->GetCurrHitPoints()*100>=u->GetMaxHitPoints()*Setting("AICapturePlanMinimumHPPercent",60);
            const bool survives=captureDamage>0 && retaliation<u->GetCurrHitPoints() &&
                (healthy || plotDistance(*u->plot(),*target)<=1);
            CvStackingDiagnostics::Record(1,owner,"CAPTURE_CANDIDATE","target=%d unit=%d domain=%d eta=%d approach=%d retaliation=%d hp=%d captureDamage=%d viable=%d",target->GetPlotIndex(),u->GetID(),u->getDomainType(),eta,approach->GetPlotIndex(),retaliation,u->GetCurrHitPoints(),captureDamage,survives);
            if(survives)
            {
                const int score=eta*100+retaliation-(u->GetID()==previous?Setting("AICaptureContinuityBonus",120):0);
                if(score<bestScore || (score==bestScore && best && u->GetID()<best->GetID()))
                { best=u; bestEta=eta; bestScore=score; }
                if(eta<=1 && u->GetID()==previous) break;
            }
        }
        if(best)
        {
            o.captureID=best->GetID(); o.captureOwner=owner; o.captureEta=bestEta;
            const int position=best->plot()->GetPlotIndex();
            const int distance=plotDistance(*best->plot(),*target);
            actualProgress=previous==o.captureID && ((o.capturePlot!=position && distance<o.captureDistance) || bestEta<previousEta);
            if(previous!=o.captureID || actualProgress) o.captureProgress=currentTurn;
            o.captureDistance=previous!=o.captureID?distance:min(o.captureDistance,distance);
            o.capturePlot=position;
            // A candidate becomes an exclusive objective commitment, not just a
            // yes/no permission for indefinite city bombardment.
            if(best->getArmyID()==-1)
            {
                const Key key(owner,best->GetID());
                const bool newlyCommitted=commitments.find(key)==commitments.end() || !commitments[key].capturer;
                if(newlyCommitted) CvStackingOffensiveAI::RecordTransfer(best,target->GetPlotIndex(),o.operation,bestEta);
                std::map<Key,Commitment>::iterator c=commitments.find(key);
                if(c!=commitments.end()) c->second.capturer=true;
                if(newlyCommitted || previous!=o.captureID)
                    CvStackingDiagnostics::Record(1,owner,"CAPTURE_COMMITMENT","target=%d unit=%d action=reserve eta=%d operation=%d",target->GetPlotIndex(),best->GetID(),bestEta,o.operation);
            }
            if(previous>=0 && previous!=o.captureID)
            {
                std::map<Key,Commitment>::iterator old=commitments.find(Key(owner,previous));
                if(old!=commitments.end() && old->second.capturer)
                { old->second.capturer=false; CvStackingDiagnostics::Record(1,owner,"CAPTURE_COMMITMENT","target=%d unit=%d action=replace replacement=%d",target->GetPlotIndex(),previous,o.captureID); }
            }
        }
        // Visible adjacent co-belligerents can make preparatory fire useful too.
        // This is not permission to inspect another civilization's hidden army.
        if(o.captureID<0)
            for(int i=1;i<RING1_PLOTS && o.captureID<0;++i)
            {
                CvPlot* p=iterateRingPlots(target,i);
                if(!p || !p->isVisible(player.getTeam())) continue;
                for(int j=0;j<p->getNumUnits();++j)
                {
                    const CvUnit* ally=p->getUnitByIndex(j);
                    if(!CvStackingOffensiveAI::CanCapture(ally,target) || ally->getOwner()==owner ||
                        ally->isInvisible(player.getTeam(),false) || player.IsAtWarWith(ally->getOwner()) ||
                        !GET_PLAYER(ally->getOwner()).IsAtWarWith(target->getOwner()) || !ally->isNativeDomain(p)) continue;
                    int retaliation=0,garrison=0;
                    TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(target->getPlotCity(),ally,p,retaliation,garrison,false,0,
                        max(0,target->getPlotCity()->GetMaxHitPoints()-target->getPlotCity()->getDamage()-1));
                    if(retaliation>=ally->GetCurrHitPoints()) continue;
                    o.captureID=ally->GetID();
                    o.captureOwner=ally->getOwner(); o.captureEta=0; o.captureProgress=currentTurn;
                    CvStackingDiagnostics::Record(1,owner,"CAPTURE_CANDIDATE","target=%d unit=%d unitOwner=%d reason=visible_adjacent_ally viable=1",target->GetPlotIndex(),ally->GetID(),ally->getOwner());
                    break;
                }
            }
        const bool adjacent=o.captureID>=0 && (o.captureOwner!=owner ||
            (best && plotDistance(*best->plot(),*target)<=1 && best->isNativeDomain(best->plot())));
        const bool credible=o.captureID>=0 && (adjacent ||
            (o.captureProgress>=0 && currentTurn-o.captureProgress<Setting("AICaptureNoProgressTurns",6)));
        // Changing the candidate alone does not restart a stalled siege clock.
        if(o.captureID>=0 && (adjacent || actualProgress)) o.noCaptureSince=-1;
        else if(o.captureKnown && o.noCaptureSince<0) o.noCaptureSince=currentTurn;
        CvStackingDiagnostics::Record(1,owner,"CAPTURE_PLAN","target=%d domain=%d unit=%d unitOwner=%d eta=%d known=%d credible=%d adjacent=%d progressAge=%d missingTurns=%d queries=%d",target->GetPlotIndex(),domain,o.captureID,o.captureOwner,o.captureEta,o.captureKnown,credible,adjacent,o.captureProgress<0?-1:currentTurn-o.captureProgress,o.noCaptureSince<0?0:currentTurn-o.noCaptureSince,captureQueries[owner]);
    }
}

namespace CvStackingOffensiveAI
{
    bool ConsumeAdditionalTacticalBatch(PlayerTypes owner)
    {
        if(!Enabled(owner)) return false;
        Refresh();
        if(extraBatches[owner]>=Setting("AIAssaultExtraBatchesPerTurn",16)) return false;
        ++extraBatches[owner]; return true;
    }
    bool Enabled(PlayerTypes owner)
    { return !shuttingDown && CvStackingAI::Enabled(owner) && Setting("AIOffensiveSupportEnabled",1)!=0; }
    bool IsSiegeUnit(const CvUnit* unit)
    {
        return Usable(unit) && unit->getDomainType()==DOMAIN_LAND && unit->IsCanAttackRanged() &&
            (unit->AI_getUnitAIType()==UNITAI_CITY_BOMBARD || unit->getUnitInfo().GetDefaultUnitAIType()==UNITAI_CITY_BOMBARD);
    }
    int DesiredAssaultUnits(PlayerTypes owner,const CvCity* city,DomainTypes domain)
    {
        const int capacity=CvStacking::GetCapacity(owner,domain,true);
        int result=Setting("AIAssaultBaseUnits",6)+max(0,capacity-1)*Setting("AIAssaultUnitsPerCapacity",2);
        if(city && city->plot()->isVisible(GET_PLAYER(owner).getTeam()))
        {
            if(KnownFortified(owner,city)) result+=Setting("AIAssaultStrongCityExtraUnits",4);
            if((city->GetMaxHitPoints()-city->getDamage())*100<=city->GetMaxHitPoints()*Setting("AIAssaultOpportunityHPPercent",30))
                result=min(result,Setting("AIAssaultOpportunityUnits",4));
        }
        return min(Setting("AIAssaultMaximumReadyUnits",24),max(Setting("AIAssaultMinimumReadyUnits",4),result));
    }
    int DesiredSiegeUnits(PlayerTypes owner,const CvCity* city,DomainTypes domain)
    {
        if(!city || !city->plot()->isVisible(GET_PLAYER(owner).getTeam())) return 0;
        if((city->GetMaxHitPoints()-city->getDamage())*100<=city->GetMaxHitPoints()*Setting("AIAssaultOpportunityHPPercent",30)) return 0;
        if(domain==DOMAIN_SEA) return Setting("AIAssaultNavalMinimumRanged",4);
        if(!KnownFortified(owner,city)) return 0;
        const int capacity=CvStacking::GetCapacity(owner,domain,true);
        return min(Setting("AIAssaultMaximumSiege",8),Setting("AIAssaultBaseSiege",2)+
            max(0,capacity-2)/max(1,Setting("AIAssaultCapacityPerExtraSiege",2))+Setting("AIAssaultStrongCityExtraSiege",2));
    }
    AssaultPlan AssessAssault(PlayerTypes owner,CvCity* city,DomainTypes domain)
    {
        AssaultPlan result;
        if(!city || !Enabled(owner) || Setting("AIAssaultCoordinationEnabled",1)==0)
        { result.ready=true; return result; }
        CvPlayer& player=GET_PLAYER(owner);
        CvPlot* target=city->plot();
        if(!player.IsAtWarWith(city->getOwner()) || !target->isVisible(player.getTeam()))
        { result.ready=true; return result; } // unknown defenses retain VP's normal scouting policy
        Sync(owner);
        if(domain==DOMAIN_SEA && objectives.find(ObjectiveKey(owner,target->GetPlotIndex(),domain))==objectives.end())
        {
            bool fleet=false;int fleetLoop=0;
            for(CvUnit* u=player.firstUnit(&fleetLoop);u;u=player.nextUnit(&fleetLoop))
                if(Usable(u) && u->getDomainType()==DOMAIN_SEA && plotDistance(*u->plot(),*target)<=Setting("AIAssaultStageRadius",6)) { fleet=true;break; }
            if(!fleet) return result; // do not invent a second offensive for every land siege
        }
        Objective* objective=Touch(owner,target,domain);
        if(!objective)
        {
            // An objective/work limit is not evidence that a second domain is
            // ready. Otherwise an unassessed fleet can bypass a gathering army.
            result.phase=2;result.reason=8;
            return result;
        }
        Objective& o=*objective;
        if(o.assaultTurn==currentTurn) return o.assault;
        o.assaultTurn=currentTurn;
        const ObjectiveKey key(owner,target->GetPlotIndex(),domain);
        const int previousPhase=o.assault.phase;
        o.waveRows.clear();o.waveComplete=true;o.wavePathUnknown=false;
        CapturePlan(owner,target,o,domain);
        result.captureUnit=o.captureID; result.captureOwner=o.captureOwner;
        result.desiredUnits=DesiredAssaultUnits(owner,city,domain);
        result.desiredSiege=DesiredSiegeUnits(owner,city,domain);
        result.enemyStrength=EnemyStrength(owner,target);
        const int approachTurns=Setting("AIAssaultApproachTurns",3);
        const int budget=Setting("AIAssaultPathQueriesPerTurn",64);
        int strength=0,loop=0,firstArrival=INT_MAX,lastArrival=0;
        CvUnit* probe=NULL;
        for(CvUnit* u=player.firstUnit(&loop);u;u=player.nextUnit(&loop))
        {
            if(!Matches(u,key,o)) continue;
            if(!probe || (IsSiegeUnit(u) && !IsSiegeUnit(probe)) ||
                (IsSiegeUnit(u)==IsSiegeUnit(probe) && u->baseMoves(false)<probe->baseMoves(false))) probe=u;
            if(u->GetCurrHitPoints()*100<u->GetMaxHitPoints()*Setting("AIAssaultHealthyPercent",65)) continue;
            if(plotDistance(*u->plot(),*target)>approachTurns*max(1,u->baseMoves(false))+u->GetRange())
            { ++result.inbound; continue; }
            int eta=INT_MAX;
            CvPlot* firing=AttackApproach(u,target,approachTurns,eta);
            if(!firing) { if(assaultQueries[owner]>=budget)o.wavePathUnknown=true; ++result.inbound;continue; }
            int retaliation=0,garrison=0;
            const int damage=TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(city,u,firing,retaliation,garrison);
            if(damage<=0 || retaliation>=u->GetCurrHitPoints()) continue;
            ++result.readyUnits; strength+=CvStackingAI::UnitStrength(u);
            firstArrival=min(firstArrival,eta);lastArrival=max(lastArrival,eta);
            result.siege+=domain==DOMAIN_SEA?u->IsCanAttackRanged():IsSiegeUnit(u);
            result.ranged+=u->IsCanAttackRanged();
            result.capturers+=CanCapture(u,target);
            result.cityDamage+=damage;
            if(o.waveComplete)
            {
                if(o.waveRows.size()>=(size_t)Setting("AIAssaultWaveMaximumRecords",64)) {o.waveComplete=false;o.waveRows.clear();}
                else try{o.waveRows.push_back(AssaultWaveUnit(u,eta,damage,retaliation,target));}
                catch(const std::bad_alloc&){o.waveComplete=false;o.waveRows.clear();}
            }
        }
        const int hp=max(1,city->GetMaxHitPoints()-city->getDamage());
        if(o.lowestHP!=INT_MAX && hp<o.lowestHP) o.lastCityProgress=currentTurn;
        if(hp<o.lowestHP || result.readyUnits>o.assault.readyUnits) o.lastUsefulTurn=currentTurn;
        o.lowestHP=min(o.lowestHP,hp);
        int waveCaptureETA=o.captureOwner!=owner&&o.captureID>=0?o.captureEta:INT_MAX;
        for(size_t i=0;i<o.waveRows.size();++i)if((o.waveRows[i].roles&1)!=0)waveCaptureETA=min(waveCaptureETA,o.waveRows[i].eta);
        AssaultWave wave=SelectFirstWave(o.waveRows,Setting("AIAssaultMinimumReadyUnits",4),EssentialSiege(owner,city,domain),
            domain==DOMAIN_SEA?Setting("AIAssaultNavalMinimumRanged",4):0,result.enemyStrength,Setting("AIAssaultStrengthPercent",125),hp,
            waveCaptureETA,Setting("AIAssaultFirstWaveMaximumTurns",1),Setting("AIAssaultWaveArrivalSpreadTurns",1));
        const int healing=city->GetAssaultHealingForecast(owner,o.waveComplete?wave.damage:result.cityDamage,&result.healingComplete);
        const bool captureSoon=o.captureID>=0 && o.captureEta<=approachTurns;
        const bool roles=result.siege>=result.desiredSiege && captureSoon;
        const bool damageEnough=result.cityDamage>=hp ||
            (result.cityDamage-healing)*Setting("AIAssaultDamageHorizon",4)>=hp;
        const bool strongEnough=strength*100>=result.enemyStrength*Setting("AIAssaultStrengthPercent",125);
        bool immediateCapture=false;
        if(o.captureOwner==owner && o.captureID>=0)
        {
            CvUnit* capturer=player.getUnit(o.captureID);
            CvPlot* approach=GetCaptureApproachNow(capturer,city);
            if(approach)
            {
                int retaliation=0,garrison=0;
                const int damage=TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(city,capturer,approach,retaliation,garrison);
                immediateCapture=damage>=hp && retaliation<capturer->GetCurrHitPoints();
            }
        }
        const bool cohesive=lastArrival-firstArrival<=Setting("AIAssaultWaveArrivalSpreadTurns",1);
        result.ready=immediateCapture || (roles && damageEnough && cohesive && (strongEnough || result.cityDamage>=hp) &&
            (result.readyUnits>=result.desiredUnits || (strongEnough && result.cityDamage>=hp)));
        if(o.waveComplete) result.ready=immediateCapture||WaveCanSustain(wave,hp,healing,Setting("AIAssaultDamageHorizon",4),result.healingComplete);
        else result.failedMask|=ASSAULT_UNKNOWN; // Memory/work uncertainty retains original policy.
        CopyWave(result,wave);if(!o.waveComplete)result.failedMask|=ASSAULT_UNKNOWN;
        result.reason=immediateCapture?0:!captureSoon?1:!roles?2:!damageEnough?3:!cohesive?6:!result.ready?4:0;
        // Committed waves remain committed while their core and essential roles
        // are still useful. Do not demand that replacements already be present.
        if(!o.waveComplete && previousPhase==1 && !result.ready && roles && damageEnough &&
            result.readyUnits>=Setting("AIAssaultMinimumReadyUnits",4)) result.ready=true;
        if(result.ready)result.reason=0;
        else if(o.waveComplete)result.reason=(wave.failed&ASSAULT_CAPTURE)?1:(wave.failed&ASSAULT_SIEGE)?2:(wave.failed&ASSAULT_DAMAGE)?3:(wave.failed&ASSAULT_COHESION)?6:4;
        if(!result.ready&&(o.wavePathUnknown||!o.captureKnown))result.failedMask|=ASSAULT_UNKNOWN;
        // Bombardment: while the capture wave gathers, ranged and siege units
        // within reach wear the city down, escorted by the rest of the force,
        // when that force can hold the field and their sustained fire outpaces
        // the city's healing. Melee city attacks still wait for readiness.
        const int bombardPercent=Setting("AIAssaultBombardStrengthPercent",60);
        if(!result.ready && bombardPercent>0 && o.waveComplete && result.enemyStrength>0)
        {
            int shooters=0,sustained=0;
            for(size_t i=0;i<o.waveRows.size();++i)
                if((o.waveRows[i].roles&2)!=0) { ++shooters; sustained+=o.waveRows[i].sustain; }
            result.bombard=shooters>=Setting("AIAssaultBombardMinimumRanged",2) && sustained>healing &&
                (long long)strength*100>=(long long)result.enemyStrength*bombardPercent;
        }
        if(result.ready && o.firstReadyTurn<0) o.firstReadyTurn=currentTurn;
        result.phase=result.ready?1:0;
        if(o.phaseSince<0 || (previousPhase==1)!=result.ready) o.phaseSince=currentTurn;
        if(!result.ready && currentTurn-o.phaseSince>=Setting("AIAssaultGatherTurns",6)) result.phase=2;
        if(!result.ready && probe)
        {
            // Ignore protection from current occupants: assembly must be outside
            // the enemy attack footprint, not merely safe behind a temporary screen.
            std::vector<const CvUnit*> alone(1,probe);
            const SUnitIDValueContainer noDamage;
            int bestScore=INT_MAX,checked=0;
            const int radius=Setting("AIAssaultStageRadius",6);
            CvPlot* prior=o.assault.staging>=0?GC.getMap().plotByIndexUnchecked(o.assault.staging):NULL;
            for(int i=-1;i<1+3*radius*(radius+1);++i)
            {
                CvPlot* p=i<0?prior:iterateRingPlots(target,i);
                if(!p || p==target || !p->isVisible(player.getTeam()) || !probe->isNativeDomain(p) ||
                    (p!=probe->plot() && !probe->canMoveInto(*p,CvUnit::MOVEFLAG_DESTINATION))) continue;
                if(++checked>Setting("AIAssaultStageCandidates",96)) break;
                const int danger=player.GetDangerPlots()->GetStackDanger(*p,probe,alone,noDamage,noDamage);
                if(danger>probe->GetCurrHitPoints()*Setting("AIAssaultStageDangerPercent",0)/100) continue;
                if(assaultQueries[owner]>=budget) break;
                ++assaultQueries[owner]; int eta=INT_MAX;
                if(!probe->GeneratePath(p,CvUnit::MOVEFLAG_SAFE_EMBARK_ONLY|CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER,
                    Setting("AIReinforcementMaximumTurns",12),&eta)) continue;
                const int score=eta*Setting("AIReinforcementTravelWeight",15)+plotDistance(*p,*target);
                if(score<bestScore) { bestScore=score; result.staging=p->GetPlotIndex(); result.routeKnown=true; }
                if(i<0 && result.routeKnown) break; // reuse a still-safe stage
            }
            if(result.staging>=0) o.staging=result.staging;
            else result.reason=5;
        }
        if(result.ready) result.routeKnown=true;
        if(o.phaseLogged!=result.phase || currentTurn%Setting("AIAssaultObjectiveSummaryInterval",5)==0)
        {
            int siegeEta[4]={0,0,0,0};
            for(size_t i=0;i<o.waveRows.size();++i)if((o.waveRows[i].roles&4)!=0)++siegeEta[min(3,max(0,o.waveRows[i].eta))];
            CvStackingDiagnostics::Record(1,owner,"ASSAULT_PLAN","target=%d domain=%d phase=%d reason=%d stage=%d ready=%d desired=%d siege=%d desiredSiege=%d ranged=%d capturers=%d inbound=%d damage=%d heal=%d hp=%d enemyStrength=%d captureUnit=%d captureOwner=%d captureEta=%d gatherAge=%d pathQueries=%d firstArrival=%d lastArrival=%d waveUnits=%d waveSiege=%d waveCapturers=%d waveStrength=%d waveDamage=%d waveSustain=%d waveFirstETA=%d waveLastETA=%d healingComplete=%d failedMask=%u siegeEta=%d/%d/%d/%d bombard=%d; readiness forecast only",
                key.target,domain,result.phase,result.reason,result.staging,result.readyUnits,result.desiredUnits,result.siege,result.desiredSiege,
                result.ranged,result.capturers,result.inbound,result.cityDamage,healing,hp,result.enemyStrength,o.captureID,o.captureOwner,o.captureEta,currentTurn-o.phaseSince,assaultQueries[owner],firstArrival==INT_MAX?-1:firstArrival,lastArrival,result.waveUnits,result.waveSiege,result.waveCapturers,result.waveStrength,result.waveDamage,result.waveSustain,result.waveFirstETA,result.waveLastETA,result.healingComplete,result.failedMask,siegeEta[0],siegeEta[1],siegeEta[2],siegeEta[3],result.bombard);
            o.phaseLogged=result.phase;
        }
        o.assault=result; return result;
    }
    CvPlot* GetStagingPlot(const CvUnit* unit,const CvPlot* cityTarget)
    {
        if(!unit || !cityTarget || !cityTarget->isCity() || !Enabled(unit->getOwner())) return NULL;
        const AssaultPlan plan=AssessAssault(unit->getOwner(),cityTarget->getPlotCity(),unit->getDomainType());
        return !plan.ready && plan.staging>=0?GC.getMap().plotByIndexUnchecked(plan.staging):NULL;
    }
    // A shot from the tile a unit already occupies leaves its exposure unchanged;
    // it only gives up a retreat. Allow it unless the forecast for the real stack
    // expects the shooter to lose more than AIStationaryFireDangerPercent of its
    // current HP (0 restores the AIAssaultStageDangerPercent rule).
    bool StationaryFireSafe(const CvUnit* unit,const CvPlot* cityTarget,const char* source)
    {
        const int percent=std::max(Setting("AIAssaultStageDangerPercent",0),Setting("AIStationaryFireDangerPercent",50));
        const int danger=unit->GetDanger();
        if(danger<=unit->GetCurrHitPoints()*percent/100) return true;
        const int turn=GC.getGame().getGameTurn();
        const Key key(unit->getOwner(),unit->GetID());
        std::map<Key,int>::iterator logged=fireRefusals.find(key);
        if(logged==fireRefusals.end() || logged->second!=turn)
        {
            fireRefusals[key]=turn;
            CvStackingDiagnostics::Record(1,unit->getOwner(),"FIRE_REFUSAL",
                "unit=%d target=%d plot=%d source=%s reason=danger danger=%d hp=%d limitPercent=%d",
                unit->GetID(),cityTarget->GetPlotIndex(),unit->plot()->GetPlotIndex(),source,
                danger==INT_MAX?-1:danger,unit->GetCurrHitPoints(),percent);
        }
        return false;
    }
    bool TryStationaryCityFire(CvUnit* unit,const CvPlot* cityTarget)
    {
        if(!Usable(unit) || !Enabled(unit->getOwner()) || !unit->canUseNow() || unit->TurnProcessed() || unit->isOutOfAttacks() ||
            !cityTarget || !cityTarget->isCity() || !GET_PLAYER(unit->getOwner()).IsAtWarWith(cityTarget->getOwner()) ||
            !cityTarget->isVisible(GET_PLAYER(unit->getOwner()).getTeam()) || CvStackingAI::RetainCityUnit(unit) ||
            (HasCommitment(unit) && !HasCommitment(unit,cityTarget))) return false;
        const PlayerTypes owner=unit->getOwner();CvPlayer& player=GET_PLAYER(owner);
        // This permits current-plot fire without advancing into another attack
        // footprint. Normal attack/setup/fortification rules still apply; the
        // real stack may protect a battery a singleton could not stage here.
        if(unit->IsCanAttackRanged() && unit->canRangeStrikeAt(cityTarget->getX(),cityTarget->getY()) &&
            StationaryFireSafe(unit,cityTarget,"immediate") &&
            ContinueSiege(owner,cityTarget->getPlotCity()))
        {
            const int id=unit->GetID();
            unit->PushMission(CvTypes::getMISSION_RANGE_ATTACK(),cityTarget->getX(),cityTarget->getY(),0,false,false,MISSIONAI_TACTMOVE);
            unit=player.getUnit(id);
            if(unit && !unit->isDelayedDeath() && !unit->canUseNow()) unit->SetTurnProcessed(true);
            return true;
        }
        return false;
    }
    // Runs once the tactical and homeland AI have finished a player's units. A
    // ranged unit that can still fire and has no queued mission is staying
    // where it is; firing from there leaves its exposure unchanged. Healing
    // units keep their rest. Target: a predicted kill first; otherwise siege
    // units prefer the weakest enemy city and other ranged units the defender
    // losing the largest share of its HP, each falling back to the other kind.
    // Futile sieges, cities at 1 HP and invisible or peaceful targets are skipped.
    int FireRemainingRangedShots(PlayerTypes owner)
    {
        if(!Enabled(owner) || Setting("AIEndTurnRangedFireEnabled",1)==0) return 0;
        CvPlayer& player=GET_PLAYER(owner);
        std::vector<int> units; int loop=0;
        for(CvUnit* u=player.firstUnit(&loop);u;u=player.nextUnit(&loop))
            if(Usable(u) && u->IsCanAttackRanged() && !u->isOutOfAttacks() && u->canMove() &&
                !u->IsBusy() && u->GetLengthMissionQueue()==0 && !u->shouldHeal(false))
                units.push_back(u->GetID());
        int shots=0;
        const int limit=Setting("AIOffensiveSupportMaximumUnits",32);
        std::vector<std::pair<const CvUnit*,int> > collateral;
        for(size_t i=0;i<units.size() && shots<limit;++i)
        {
            CvUnit* unit=player.getUnit(units[i]);
            if(!Usable(unit) || unit->isOutOfAttacks() || !unit->canMove()) continue;
            const int range=std::min(5,std::max(1,unit->GetRange()));
            CvPlot* city=NULL; int cityHP=INT_MAX;
            CvPlot* field=NULL; int fieldScore=-1; bool fieldKill=false;
            for(int j=1;j<RING_PLOTS[range];++j)
            {
                CvPlot* p=iterateRingPlots(unit->plot(),j);
                if(!p || !p->isVisible(player.getTeam())) continue;
                if(p->isCity())
                {
                    if(!player.IsAtWarWith(p->getOwner())) continue;
                    const CvCity* c=p->getPlotCity();
                    const int hp=c->GetMaxHitPoints()-c->getDamage();
                    if(hp<=1 || hp>=cityHP || !unit->canRangeStrikeAt(p->getX(),p->getY())) continue;
                    city=p; cityHP=hp;
                    continue;
                }
                if(!p->isEnemyUnit(owner,true,true) || !unit->canRangeStrikeAt(p->getX(),p->getY())) continue;
                CvUnit* defender=NULL; int damage=0;
                CvUnitCombat::GetStackAttackPreview(unit,p,true,defender,damage,collateral);
                if(!defender || damage<=0) continue;
                const int hp=std::max(1,defender->GetCurrHitPoints());
                const bool kill=damage>=hp;
                int splash=0;
                for(size_t k=0;k<collateral.size();++k) splash+=collateral[k].second;
                // Kills rank by the size of the unit removed, others by the share
                // of the defender's HP taken; collateral breaks ties.
                const int score=(kill?1000000+hp*100:std::min(damage,hp)*1000/hp*100)+std::min(99,splash);
                if(score>fieldScore) { field=p; fieldScore=score; fieldKill=kill; }
            }
            if(city && !ContinueSiege(owner,city->getPlotCity())) city=NULL;
            CvPlot* target=fieldKill?field:IsSiegeUnit(unit)?(city?city:field):(field?field:city);
            if(!target) continue;
            const int id=units[i],from=unit->plot()->GetPlotIndex();
            unit->PushMission(CvTypes::getMISSION_RANGE_ATTACK(),target->getX(),target->getY(),0,false,false,MISSIONAI_TACTMOVE);
            ++shots;
            unit=player.getUnit(id);
            if(unit && !unit->isDelayedDeath() && !unit->canMove()) unit->SetTurnProcessed(true);
            CvStackingDiagnostics::Record(1,owner,"END_TURN_FIRE","unit=%d plot=%d target=%d kind=%s predictedKill=%d cityHP=%d",
                id,from,target->GetPlotIndex(),target==city?"city":"unit",target==field&&fieldKill,target==city?cityHP:-1);
        }
        return shots;
    }
    // Called only after the existing native path has produced a real move.
    // A stable stage/destination and its verified first-turn endpoint permit
    // detours; no new path query or per-turn route search is performed.
    void RecordStageRouteProgress(CvUnit* unit,int target,int stage,int destination,int from,int expectedEnd)
    {
        if(!unit || !unit->plot() || !Enabled(unit->getOwner())) return;
        Refresh(); const Key key(unit->getOwner(),unit->GetID());
        std::map<Key,Commitment>::iterator found=commitments.find(key);
        if(found==commitments.end() || found->second.goal.target!=target) return;
        Commitment& c=found->second;
        const int after=unit->plot()->GetPlotIndex();
        const bool stable=c.routeStage==stage && c.routeDestination==destination;
        const bool reverse=c.routeFrom==after && c.routeTo==from;
        const bool progressed=stable && from!=after && after==expectedEnd && !reverse;
        c.routeStage=stage; c.routeDestination=destination;
        if(from!=after) { c.routeFrom=from; c.routeTo=after; }
        if(!progressed) return;
        c.routeProgress=c.lastProgress=currentTurn;
        std::map<ObjectiveKey,Objective>::iterator goal=objectives.find(c.goal);
        if(goal!=objectives.end()) goal->second.refreshed=currentTurn;
        // Route progress keeps valid support alive, not an ineffective siege.
        CvStackingDiagnostics::Record(1,unit->getOwner(),"OFFENSIVE_SUPPORT",
            "unit=%d target=%d stage=%d destination=%d from=%d after=%d action=route_progress; not assault progress",
            unit->GetID(),target,stage,destination,from,after);
    }
    bool IsCombatHistoryCurrent(unsigned long generation)
    { return !shuttingDown && !continuityGenerationExhausted && generation==continuityGeneration; }
    bool GetCombatObjective(const CvUnit* unit,int& target,DomainTypes& domain,unsigned long& generation)
    {
        if(continuityGenerationExhausted || !Usable(unit) || !Enabled(unit->getOwner())) return false;
        Refresh(); const PlayerTypes owner=unit->getOwner();
        std::map<Key,Commitment>::const_iterator c=commitments.find(Key(owner,unit->GetID()));
        ObjectiveKey goal;
        if(c!=commitments.end()) goal=c->second.goal;
        else
        {
            CvArmyAI* army=GET_PLAYER(owner).getArmyAI(unit->getArmyID());
            CvAIOperation* op=army?GET_PLAYER(owner).getAIOperation(army->GetOperationID()):NULL;
            CvPlot* city=Live(op)?CityTarget(op):NULL;
            if(!city) return false;
            goal=ObjectiveKey(owner,city->GetPlotIndex(),unit->getDomainType());
        }
        std::map<ObjectiveKey,Objective>::const_iterator o=objectives.find(goal);
        CvPlot* city=GC.getMap().plotByIndexUnchecked(goal.target);
        if(o==objectives.end() || !city || !city->isCity() || city->getOwner()!=o->second.enemy ||
            !GET_PLAYER(owner).IsAtWarWith(city->getOwner())) return false;
        target=goal.target; domain=(DomainTypes)goal.domain; generation=continuityGeneration; return true;
    }
    void RecordCombatContribution(PlayerTypes owner,int unit,int target,DomainTypes domain,
        int combatPlot,int defenderOwner,int fieldDamage,int cityDamage,bool captured)
    {
        if(!Enabled(owner) || shuttingDown) return;
        Refresh(); const ObjectiveKey key(owner,target,domain);
        std::map<ObjectiveKey,Objective>::iterator found=objectives.find(key);
        if(found==objectives.end()) return;
        Objective& o=found->second;
        const bool cityAttack=combatPlot==target;
        CvPlot* p=GC.getMap().plotByIndexUnchecked(combatPlot);
        CvPlot* goal=GC.getMap().plotByIndexUnchecked(target);
        const bool relevantField=p && goal && defenderOwner>=0 &&
            GET_PLAYER(owner).IsAtWarWith((PlayerTypes)defenderOwner) &&
            plotDistance(*p,*goal)<=Setting("AIOffensiveContributionRadius",2) && fieldDamage>0;
        if(!cityAttack && !relevantField) return;
        InvalidateProductionStaff(owner,target,domain); // Actual wounds/losses can expose a replacement-role deficit.
        if(cityAttack) { ++o.cityAttempts; o.lastCityAttack=currentTurn; }
        if(relevantField) ++o.fieldContributions;
        if(cityAttack && (cityDamage>0 || captured) && goal && goal->isCity() && goal->isVisible(GET_PLAYER(owner).getTeam()))
        {
            const int hp=goal->getPlotCity()->GetMaxHitPoints()-goal->getPlotCity()->getDamage();
            if(captured || hp<o.lowestHP) { o.lowestHP=hp; o.lastCityProgress=o.lastUsefulTurn=currentTurn; }
        }
        std::map<Key,Commitment>::iterator c=commitments.find(Key(owner,unit));
        if(c!=commitments.end() && c->second.goal==key && (cityDamage>0 || relevantField || captured))
            c->second.lastProgress=currentTurn;
        CvStackingDiagnostics::Record(1,owner,"OFFENSIVE_CONTRIBUTION",
            "unit=%d target=%d domain=%d plot=%d cityDamage=%d fieldDamage=%d captured=%d cityAttempts=%d fieldActions=%d netProgressTurn=%d",
            unit,target,domain,combatPlot,cityDamage,fieldDamage,captured,o.cityAttempts,o.fieldContributions,o.lastCityProgress);
    }
    bool StageUnit(CvUnit* unit,const CvPlot* cityTarget)
    {
        if(!Usable(unit) || !unit->canUseNow() || !cityTarget || !cityTarget->isCity()) return false;
        const PlayerTypes owner=unit->getOwner();CvPlayer& player=GET_PLAYER(owner);
        const AssaultPlan plan=AssessAssault(owner,cityTarget->getPlotCity(),unit->getDomainType());
        if(plan.ready) return false;
        if(TryStationaryCityFire(unit,cityTarget)) return true;
        if(plan.staging<0) return false;
        const int dangerLimit=unit->GetCurrHitPoints()*Setting("AIAssaultStageDangerPercent",0)/100;
        CvPlot* stage=GC.getMap().plotByIndexUnchecked(plan.staging);
        const std::vector<const CvUnit*> alone(1,unit);const SUnitIDValueContainer noDamage;
        const int currentDanger=player.GetDangerPlots()->GetStackDanger(*unit->plot(),unit,alone,noDamage,noDamage);
        const int radius=Setting("AIAssaultStageCohesionRadius",2);
        if(currentDanger<=dangerLimit && plotDistance(*unit->plot(),*stage)<=radius)
        {
            if(!HasCommitment(unit,cityTarget))
                RecordTransfer(unit,cityTarget->GetPlotIndex(),-1,plotDistance(*unit->plot(),*cityTarget)/max(1,unit->baseMoves(false)));
            assemblyHolds[Key(owner,unit->GetID())]=currentTurn;
            unit->SetTurnProcessed(true);return true;
        }
        std::vector<std::pair<int,int> > candidates;
        for(int i=0;i<1+3*radius*(radius+1);++i)
        {
            CvPlot* p=iterateRingPlots(stage,i);
            if(!p || !p->isVisible(player.getTeam()) || !unit->isNativeDomain(p) ||
                !unit->canMoveInto(*p,CvUnit::MOVEFLAG_DESTINATION)) continue;
            candidates.push_back(std::make_pair(plotDistance(*unit->plot(),*p),p->GetPlotIndex()));
        }
        std::sort(candidates.begin(),candidates.end());
        for(size_t i=0;i<candidates.size() && i<(size_t)Setting("AIAssaultStagePlacementCandidates",8);++i)
        {
            CvPlot* p=GC.getMap().plotByIndexUnchecked(candidates[i].second);
            if(player.GetDangerPlots()->GetStackDanger(*p,unit,alone,noDamage,noDamage)>dangerLimit) continue;
            if(assaultQueries[owner]>=Setting("AIAssaultPathQueriesPerTurn",64)) break;
            ++assaultQueries[owner];
            const int flags=CvUnit::MOVEFLAG_SAFE_EMBARK_ONLY|CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER;
            if(!unit->GeneratePath(p,flags,Setting("AIReinforcementMaximumTurns",12))) continue;
            CvPlot* end=unit->GetPathEndFirstTurnPlot();
            if(!end || end==unit->plot() || player.GetDangerPlots()->GetStackDanger(*end,unit,alone,noDamage,noDamage)>dangerLimit) continue;
            const int id=unit->GetID(),from=unit->plot()->GetPlotIndex();
            const int targetIndex=cityTarget->GetPlotIndex(),stageIndex=stage->GetPlotIndex(),destination=p->GetPlotIndex(),expectedEnd=end->GetPlotIndex();
            unit->PushMission(CvTypes::getMISSION_MOVE_TO(),p->getX(),p->getY(),flags,false,false,MISSIONAI_TACTMOVE);
            unit=player.getUnit(id);
            if(!unit || unit->isDelayedDeath()) return true;
            if(unit->plot()->GetPlotIndex()==from) continue;
            RecordTransfer(unit,targetIndex,-1,plotDistance(*unit->plot(),*cityTarget)/max(1,unit->baseMoves(false)));
            RecordStageRouteProgress(unit,targetIndex,stageIndex,destination,from,expectedEnd);
            assemblyHolds[Key(owner,id)]=currentTurn;
            unit->SetTurnProcessed(true);
            CvStackingDiagnostics::Record(2,owner,"ASSAULT_STAGE","unit=%d target=%d from=%d after=%d stage=%d",id,cityTarget->GetPlotIndex(),from,unit->plot()->GetPlotIndex(),stage->GetPlotIndex());
            return true;
        }
        return false;
    }
    bool HoldForAssembly(const CvUnit* unit,const CvPlot* tacticalTarget)
    {
        if(!Usable(unit) || !tacticalTarget || !Enabled(unit->getOwner()) || unit->GetDanger()>0) return false;
        Sync(unit->getOwner());
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();++i)
        {
            if(i->first.owner!=unit->getOwner() || i->first.domain!=unit->getDomainType()) continue;
            CvPlot* city=GC.getMap().plotByIndexUnchecked(i->first.target);
            if(!city || !city->isCity() || plotDistance(*city,*tacticalTarget)>2 ||
                !Matches(const_cast<CvUnit*>(unit),i->first,i->second)) continue;
            const AssaultPlan plan=AssessAssault(unit->getOwner(),city->getPlotCity(),unit->getDomainType());
            // Safe shots already available need not await the main assault.
            if(unit->IsCanAttackRanged() && unit->canRangeStrikeAt(tacticalTarget->getX(),tacticalTarget->getY())) return false;
            return !plan.ready && !(plan.bombard && unit->IsCanAttackRanged());
        }
        return false;
    }
    CvUnit* GetReservedCapturer(PlayerTypes owner,CvCity* city)
    {
        if(!city || !Enabled(owner) || !city->plot()->isVisible(GET_PLAYER(owner).getTeam())) return NULL;
        Sync(owner);
        CvUnit* result=NULL; int bestEta=INT_MAX;
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();++i)
        {
            if(i->first.owner!=owner || i->first.target!=city->plot()->GetPlotIndex()) continue;
            CapturePlan(owner,city->plot(),i->second,(DomainTypes)i->first.domain);
            if(i->second.captureOwner==owner && i->second.captureID>=0 && i->second.captureEta<bestEta)
            { result=GET_PLAYER(owner).getUnit(i->second.captureID); bestEta=i->second.captureEta; }
        }
        return result;
    }
    bool IsAssemblyHeld(const CvUnit* unit)
    {
        if(!unit) return false;
        Refresh();
        const std::map<Key,int>::const_iterator i=assemblyHolds.find(Key(unit->getOwner(),unit->GetID()));
        return i!=assemblyHolds.end() && i->second==currentTurn;
    }
    void ReleaseAssemblyHold(CvUnit* unit)
    {
        if(IsAssemblyHeld(unit))
        {
            assemblyHolds.erase(Key(unit->getOwner(),unit->GetID()));
            unit->SetTurnProcessed(false);
        }
    }
    CvPlot* GetCaptureApproachNow(CvUnit* unit,CvCity* city)
    {
        if(!city || !CanCapture(unit,city->plot()) || !unit->canMove() || unit->isOutOfAttacks() ||
            (!unit->canUseNow() && !IsAssemblyHeld(unit)) ||
            !unit->canMoveInto(*city->plot(),CvUnit::MOVEFLAG_ATTACK|CvUnit::MOVEFLAG_DESTINATION)) return NULL;
        if(plotDistance(*unit->plot(),*city->plot())<=1 && unit->isNativeDomain(unit->plot())) return unit->plot();
        Refresh();
        if(captureQueries[unit->getOwner()]>=Setting("AICapturePlanPathQueriesPerTurn",32)) return NULL;
        ++captureQueries[unit->getOwner()];
        const int flags=CvUnit::MOVEFLAG_ATTACK|CvUnit::MOVEFLAG_DESTINATION|CvUnit::MOVEFLAG_SAFE_EMBARK_ONLY;
        // Exact current-turn reach includes movement and the final attack; an
        // approximate arrival forecast may use movement from the following turn.
        if(!unit->GeneratePath(city->plot(),flags,1) || unit->GetPathEndFirstTurnPlot()!=city->plot()) return NULL;
        const CvPathNodeArray& path=unit->GetLastPath();
        CvPlot* approach=path.size()>1?path.GetPlotByIndex((int)path.size()-2):unit->plot();
        return approach && unit->isNativeDomain(approach) && plotDistance(*approach,*city->plot())<=1?approach:NULL;
    }
    bool AllowCityAttack(const CvUnit* unit,CvCity* city,const CvPlot* firing,bool capture,bool executing)
    {
        if(!unit || !city || !firing) return false;
        if(!Enabled(unit->getOwner()) || Setting("AIAssaultCoordinationEnabled",1)==0 || capture) return true;
        const AssaultPlan plan=AssessAssault(unit->getOwner(),city,unit->getDomainType());
        if(plan.ready) return true;
        if(!unit->IsCanAttackRanged()) return false;
        // The tactical search scores where a bombarding shooter ends its turn.
        if(plan.bombard) return ContinueSiege(unit->getOwner(),city);
        // Firing from the current tile does not advance into the attack footprint
        // and the search still scores where the shooter ends its turn, so a
        // gathering assault keeps these shots (see StationaryFireSafe).
        if(firing==unit->plot() && Setting("AIStationaryFireDangerPercent",50)>0)
        {
            if(!executing && !StationaryFireSafe(unit,city->plot(),"search")) return false;
            return ContinueSiege(unit->getOwner(),city);
        }
        // Generic combat searches may target a different city than their main
        // target. Enforce assembly on that actual city, preserving safe fire.
        const std::vector<const CvUnit*> alone(1,unit);const SUnitIDValueContainer noDamage;
        if(GET_PLAYER(unit->getOwner()).GetDangerPlots()->GetStackDanger(*firing,unit,alone,noDamage,noDamage)>
            unit->GetCurrHitPoints()*Setting("AIAssaultStageDangerPercent",0)/100) return false;
        return ContinueSiege(unit->getOwner(),city);
    }
    void ReviewObjectives(PlayerTypes owner)
    {
        if(!Enabled(owner)) return;
        Sync(owner);
        if(currentTurn%Setting("AIAssaultReviewInterval",3)!=0) return;
        std::vector<ObjectiveKey> stale;
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();++i)
        {
            if(i->first.owner!=owner) continue;
            CvPlot* p=GC.getMap().plotByIndexUnchecked(i->first.target);
            if(p && p->isCity() && p->isVisible(GET_PLAYER(owner).getTeam()))
            {
                const AssaultPlan plan=AssessAssault(owner,p->getPlotCity(),(DomainTypes)i->first.domain);
                Objective& o=i->second;
                if(plan.ready && o.firstReadyTurn<0) o.firstReadyTurn=currentTurn;
                const int attackClock=max(o.lastCityProgress,o.firstReadyTurn);
                const int attackStall=Setting("AIAssaultAttackProgressStallTurns",24);
                const bool noAttackProgress=attackStall>0 && o.firstReadyTurn>=0 && currentTurn-attackClock>=attackStall;
                if((plan.phase==2 && currentTurn-o.lastUsefulTurn>=Setting("AIAssaultAbandonTurns",24)) || noAttackProgress) stale.push_back(i->first);
            }
        }
        for(size_t i=0;i<stale.size();++i)
        {
            std::map<ObjectiveKey,Objective>::iterator found=objectives.find(stale[i]);
            if(found==objectives.end()) continue;
            const int operation=found->second.operation,enemy=found->second.enemy;
            CvStackingDiagnostics::Record(1,owner,"ASSAULT_REASSESS","target=%d domain=%d action=abandon reason=no_force_or_city_progress idle=%d",stale[i].target,stale[i].domain,currentTurn-found->second.lastUsefulTurn);
            for(std::map<Key,Commitment>::iterator c=commitments.begin();c!=commitments.end();)
                if(c->second.goal==stale[i])
                {
                    CvStackingDiagnostics::Record(1,owner,"OFFENSIVE_SUPPORT","unit=%d target=%d action=release_stale reason=assault_abandoned",c->first.second,stale[i].target);
                    commitments.erase(c++);
                }
                else ++c;
            objectives.erase(found);
            CvAIOperation* op=GET_PLAYER(owner).getAIOperation(operation);
            if(Live(op)) op->SetToAbort(AI_ABORT_TIMED_OUT);
            const int cooldown=Setting("AIOperationRouteRetryTurns",6);
            if(cooldown>0)
            { Failure& f=failures[stale[i]];f.until=currentTurn+cooldown-1;f.enemy=enemy; }
        }
    }
    void ResetProductionPolicy()
    {
        // VC9 empty map/set construction allocates sentinel nodes. Reset also
        // runs during cleanup and optional-allocation recovery, so retain the
        // existing container objects and clear their payload without allocating.
        for(int i=0;i<MAX_PLAYERS;++i)
        {
            ProductionPolicyState& state=productionPolicy[i];
            state.cities.clear();state.rejections.clear();
            state.turn=state.cityCount=state.observedUnits=-1;
            state.softCap=state.land=state.sea=state.supply=0;
            state.generation=0;
            state.ready=state.busy=state.softDirty=false;
        }
        std::vector<PromotionTypes>().swap(noCapturePromotions);noCapturePromotionCount=-1;
    }
    void ProductionCitiesChanged(PlayerTypes owner)
    {
        if(owner<0||owner>=MAX_PLAYERS)return;
        productionPolicy[owner].ready=false;AdvanceProductionGeneration(owner);
    }
    void InvalidateProductionStaff(PlayerTypes owner,int target,DomainTypes domain)
    {
        std::map<ObjectiveKey,Objective>::iterator i=objectives.find(ObjectiveKey(owner,target,domain));
        if(i!=objectives.end()){i->second.staffTurn=-1;i->second.productionTurn=-1;}
    }
    void InvalidateProductionOwner(PlayerTypes owner)
    {
        if(shuttingDown||owner<0||owner>=MAX_PLAYERS)return;
        productionPolicy[owner].softDirty=true;
        AdvanceProductionGeneration(owner);
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();++i)
            if(i->first.owner==owner){i->second.staffTurn=-1;i->second.productionTurn=-1;}
    }
    void ProductionEconomyChanged(PlayerTypes owner)
    {
        if(shuttingDown||owner<0||owner>=MAX_PLAYERS)return;
        productionPolicy[owner].softDirty=true;AdvanceProductionGeneration(owner);
    }
    void ProductionQueueChanged(const CvCity* city)
    {
        if(!city||city->getOwner()<0||city->getOwner()>=MAX_PLAYERS||!Enabled(city->getOwner()))return;
        const PlayerTypes owner=city->getOwner();ProductionPolicyState& state=productionPolicy[owner];
        if(state.busy){state.ready=false;AdvanceProductionGeneration(owner);return;}
        if(!state.ready||state.turn!=GC.getGame().getGameTurn()||state.cityCount!=GET_PLAYER(owner).getNumCities())
        {state.ready=false;AdvanceProductionGeneration(owner);return;}
        const ProductionQueueState value=ReadProductionQueue(city);
        if(!value.valid){state.ready=false;AdvanceProductionGeneration(owner);return;}
        std::map<int,ProductionQueueState>::iterator existing=state.cities.find(city->GetID());
        if(existing!=state.cities.end()&&existing->second==value)return;
        try
        {
            ProductionQueueState& old=state.cities[city->GetID()];
            state.land+=value.land-old.land;state.sea+=value.sea-old.sea;state.supply+=value.supply-old.supply;
            old=value;AdvanceProductionGeneration(owner);
        }
        catch(const std::bad_alloc&)
        {state.ready=false;state.cities.clear();state.land=state.sea=state.supply=0;AdvanceProductionGeneration(owner);}
    }
    bool GetProductionBudget(PlayerTypes owner,ProductionBudget& result)
    {
        result=ProductionBudget();if(owner<0||owner>=MAX_PLAYERS||!Enabled(owner))return false;
        Sync(owner);ReadLiveProductionBudget(owner,result);return result.ready;
    }
    bool GetProductionIntent(const CvCity* city,UnitTypes unit,ProductionIntent& result,bool replaceQueue)
    {
        result=ProductionIntent();
        if(!city||!Enabled(city->getOwner())||Setting("AIOffensiveProductionMaximumUnits",4)==0)return false;
        Sync(city->getOwner());ProductionQueueChanged(city);
        ObjectiveKey chosen;ProductionChoice(city,unit,chosen,&result,replaceQueue);
        return result.target>=0;
    }
    void RecordProductionRejection(const CvCity* city,UnitTypes unit,const ProductionIntent& intent,int reason)
    {
        if(!city||!intent.missingRole||intent.target<0||!CvStackingDiagnostics::Enabled(1,city->getOwner()))return;
        ProductionPolicyState& state=productionPolicy[city->getOwner()];
        if(!state.ready)return;
        // One already-computed reason per factory per turn, not a row for each type.
        try {if(!state.rejections.insert(std::make_pair(city->GetID(),reason)).second)return;}
        catch(const std::bad_alloc&){return;}
        CvStackingDiagnostics::Record(1,city->getOwner(),"OFFENSIVE_PRODUCTION","city=%d target=%d domain=%d unitType=%d action=reject reason=%d roles=%d units=%d queued=%d missingSiege=%d missingRanged=%d missingCapture=%d",
            city->GetID(),intent.target,intent.domain,unit,reason,intent.roles,intent.units,intent.queued,intent.missingSiege,intent.missingRanged,intent.missingCapture);
    }

    int ProductionBonus(const CvCity* city,UnitTypes unit)
    {
        ProductionIntent intent;GetProductionIntent(city,unit,intent);return intent.bonus;
    }
    void RecordProduction(CvCity* city,UnitTypes unit)
    {
        if(!city || !Enabled(city->getOwner()) || city->IsBuildingUnitForOperation() || city->getProductionUnit()!=unit ||
            Setting("AIOffensiveProductionMaximumUnits",4)==0) return;
        Sync(city->getOwner());
        if(ProductionQueueStalled(city,Key(city->getOwner(),city->GetID()))) return;
        ObjectiveKey chosen;
        if(!ProductionChoice(city,unit,chosen)) return;
        ProductionClaim& claim=production[Key(city->getOwner(),city->GetID())];
        if(claim.started>=0 && claim.unit==unit && claim.goal==chosen) return;
        claim.goal=chosen; claim.unit=unit; claim.started=claim.progress=currentTurn; claim.turns=city->getProductionTurnsLeft();
        AdvanceProductionGeneration(city->getOwner());
        objectives[chosen].lastUsefulTurn=currentTurn;
        CvStackingDiagnostics::Record(1,city->getOwner(),"OFFENSIVE_PRODUCTION","city=%d target=%d domain=%d unitType=%d remaining=%d action=queued",city->GetID(),chosen.target,chosen.domain,unit,claim.turns);
    }
    void UnitProduced(CvCity* city,CvUnit* unit)
    {
        if(!city || !Usable(unit) || !Enabled(city->getOwner())) return;
        InvalidateProductionOwner(city->getOwner());
        const Key key(city->getOwner(),city->GetID());
        std::map<Key,ProductionClaim>::iterator claim=production.find(key);
        if(claim==production.end() || claim->second.unit!=unit->getUnitType()) return;
        const ObjectiveKey goal=claim->second.goal;
        production.erase(claim); // completion must replace its pending credit exactly once
        AdvanceProductionGeneration(city->getOwner());
        if(city->IsBuildingUnitForOperation())
        {
            CvStackingDiagnostics::Record(1,unit->getOwner(),"OFFENSIVE_PRODUCTION","city=%d target=%d unit=%d action=cancel reason=formation_took_ownership",city->GetID(),goal.target,unit->GetID());
            return;
        }
        CvPlot* target=GC.getMap().plotByIndexUnchecked(goal.target);
        if(!target || !target->isCity()) return;
        std::map<ObjectiveKey,Objective>::const_iterator objective=objectives.find(goal);
        CvAIOperation* op=objective!=objectives.end()?GET_PLAYER(unit->getOwner()).getAIOperation(objective->second.operation):NULL;
        const bool preparing=Live(op) && CityTarget(op)==target && op->GetEnemy()==target->getOwner();
        if(!GET_PLAYER(unit->getOwner()).IsAtWarWith(target->getOwner()) && !preparing) return;
        unit->AI_setUnitAIType((UnitAITypes)unit->getUnitInfo().GetDefaultUnitAIType());
        RecordTransfer(unit,goal.target,preparing?op->GetID():-1,plotDistance(*unit->plot(),*target)/max(1,unit->baseMoves(false)));
        CvStackingDiagnostics::Record(1,unit->getOwner(),"OFFENSIVE_PRODUCTION","city=%d target=%d unitType=%d unit=%d action=completed",city->GetID(),goal.target,unit->getUnitType(),unit->GetID());
    }
    void TacticalForces(PlayerTypes owner,std::vector<TacticalForce>& result)
    {
        if(!Enabled(owner)) return;
        Sync(owner);CvPlayer& player=GET_PLAYER(owner);
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();++i)
        {
            if(i->first.owner!=owner) continue;
            CvPlot* target=GC.getMap().plotByIndexUnchecked(i->first.target);
            if(!target || !target->isCity() || !player.IsAtWarWith(target->getOwner()) || !target->isVisible(player.getTeam())) continue;
            TacticalForce force(i->first.target,i->first.domain);int loop=0;
            const size_t maximum=(size_t)Setting("AIOffensiveSupportMaximumUnits",32);
            std::vector<int> pool;bool complete=true;
            for(CvUnit* u=player.firstUnit(&loop);u;u=player.nextUnit(&loop))
            {
                if(u->getArmyID()!=-1 || !u->canUseNow() || u->shouldHeal(false) || CvStackingAI::RetainCityUnit(u) || !Matches(u,i->first,i->second)) continue;
                if(force.units.size()<maximum) force.units.push_back(u->GetID());
                if(complete)try{pool.push_back(u->GetID());}catch(const std::bad_alloc&){complete=false;std::vector<int>().swap(pool);}
                if(!complete && force.units.size()>=maximum)break; // Original bounded roster on optional failure.
            }
            // A full first-N roster must not hide late-created essential roles.
            // Select nearby capture/siege/ranged coverage, then retain original
            // ID enumeration for the remaining unchanged actor budget.
            if(complete && pool.size()>maximum)
            try
            {
                std::vector<int> selected;selected.reserve(maximum);
                const int healthy=max(Setting("AIOffensiveProductionHealthyPercent",65),Setting("AIAssaultHealthyPercent",65));
                int needs[3]={Setting("AIOffensiveSupportMinimumCapturers",2),DesiredSiegeUnits(owner,target->getPlotCity(),(DomainTypes)i->first.domain),Setting("AIOffensiveSupportMinimumRanged",2)};
                for(int role=0;role<3 && selected.size()<maximum;++role)
                {
                    int present=0;
                    for(size_t j=0;j<selected.size();++j)
                    {
                        const CvUnit* u=player.getUnit(selected[j]);
                        if(u && u->GetCurrHitPoints()*100>=u->GetMaxHitPoints()*healthy &&
                            (role==0?CanCapture(u,target):role==1?(i->first.domain==DOMAIN_SEA?u->IsCanAttackRanged():IsSiegeUnit(u)):(u->IsCanAttackRanged()&&!IsSiegeUnit(u))))++present;
                    }
                    for(size_t j=0;j<pool.size() && present<needs[role] && selected.size()<maximum;++j)
                    {
                        const CvUnit* u=player.getUnit(pool[j]);
                        if(!u || u->GetCurrHitPoints()*100<u->GetMaxHitPoints()*healthy ||
                            plotDistance(*u->plot(),*target)>Setting("AIOffensiveSupportLocalRadius",4) ||
                            std::find(selected.begin(),selected.end(),pool[j])!=selected.end())continue;
                        if(role==0?CanCapture(u,target):role==1?(i->first.domain==DOMAIN_SEA?u->IsCanAttackRanged():IsSiegeUnit(u)):(u->IsCanAttackRanged()&&!IsSiegeUnit(u)))
                        {selected.push_back(pool[j]);++present;}
                    }
                }
                for(size_t j=0;j<pool.size() && selected.size()<maximum;++j)
                    if(std::find(selected.begin(),selected.end(),pool[j])==selected.end())selected.push_back(pool[j]);
                force.units.swap(selected);
            }
            catch(const std::bad_alloc&){} // Keep original first-N force; never partial selection.
            if(!force.units.empty()) result.push_back(force);
        }
    }
    bool IsCityAttack(const CvAIOperation* op)
    {
        if(!op) return false;
        const AIOperationTypes type=op->GetOperationType();
        return type==AI_OPERATION_CITY_ATTACK_LAND || type==AI_OPERATION_CITY_ATTACK_NAVAL || type==AI_OPERATION_CITY_ATTACK_COMBINED;
    }
    CvPlot* CityTarget(const CvAIOperation* op)
    {
        CvPlot* waypoint=op?op->GetTargetPlot():NULL;
        if(!waypoint) return NULL;
        if(waypoint->isCity()) return waypoint;
        // VP's naval/combined operation stores a coastal water tile within two
        // rings of the city (GetCoastalWaterNearPlot), not the city itself.
        if(!op->IsNavalOperation()) return NULL;
        for(int i=1;i<RING1_PLOTS;++i)
        {
            CvPlot* p=iterateRingPlots(waypoint,i);
            if(p && p->isCity() && p->getOwner()==op->GetEnemy()) return p;
        }
        // Second ring: only an unambiguous enemy city is the target.
        CvPlot* found=NULL;
        for(int i=RING1_PLOTS;i<RING2_PLOTS;++i)
        {
            CvPlot* p=iterateRingPlots(waypoint,i);
            if(!p || !p->isCity() || p->getOwner()!=op->GetEnemy()) continue;
            if(found) return NULL;
            found=p;
        }
        return found;
    }
    void Handoff(CvAIOperation* op)
    {
        if(!IsCityAttack(op) || !Enabled(op->GetOwner())) return;
        ObserveOperation(op);
        CvPlot* target=CityTarget(op); CvArmyAI* army=op->GetArmy(0);
        if(!target || !army || target->getOwner()!=op->GetEnemy()) return;
        for(CvUnit* u=army->GetFirstUnit();u;u=army->GetNextUnit(u))
        {
            if(!Usable(u)) continue;
            // Keep roles/domains distinct even when a combined fleet releases land troops.
            Objective* o=Touch(op->GetOwner(),target,u->getDomainType());
            if(!o) continue;
            o->operation=op->GetID();
            Commitment& c=commitments[Key(op->GetOwner(),u->GetID())];
            c.goal=ObjectiveKey(op->GetOwner(),target->GetPlotIndex(),u->getDomainType());
            c.turn=c.lastProgress=currentTurn; c.plot=u->plot()->GetPlotIndex();
            c.bestDistance=plotDistance(*u->plot(),*target); c.eta=c.bestDistance/max(1,u->baseMoves(false));
            c.arrived=c.bestDistance<=Setting("AIOffensiveSupportLocalRadius",4);
            CvStackingDiagnostics::Record(1,op->GetOwner(),"OFFENSIVE_SUPPORT","unit=%d target=%d operation=%d action=tactical_handoff",u->GetID(),target->GetPlotIndex(),op->GetID());
        }
        InvalidateProductionOwner(op->GetOwner());
    }
    void Reset()
    {
        ResetOpeningReadiness(); ResetProductionPolicy();
        objectives.clear(); commitments.clear(); failures.clear(); marches.clear(); captureRetries.clear(); production.clear(); stalledProduction.clear(); assemblyHolds.clear(); fireRefusals.clear(); currentTurn=-1; shuttingDown=false;
        if(continuityGeneration==0xffffffffUL) continuityGenerationExhausted=true; else ++continuityGeneration;
    }
    void Shutdown()
    {
        // Operation destructors abort armies after earlier player objects have
        // already been destroyed. They must not refresh production/war state.
        Reset();
        shuttingDown=true;
    }
    bool CanCapture(const CvUnit* u,const CvPlot* city)
    {
        return Usable(u) && city && city->isCity() && u->IsCanAttackWithMove() && !u->isNoCapture() &&
            (u->getDomainType()==DOMAIN_LAND || (u->getDomainType()==DOMAIN_SEA && city->isCoastalLand())) &&
            u->GetCurrHitPoints()>0;
    }
    void ObserveOperation(CvAIOperation* op)
    {
        if(!IsCityAttack(op) || !Enabled(op->GetOwner()) || !Live(op)) return;
        CvArmyAI* army=op->GetArmy(0); CvPlot* target=CityTarget(op);
        if(!army || !target || !target->isCity() || target->getOwner()!=op->GetEnemy()) return;
        // A combined army reports DOMAIN_SEA but carries land troops: its fleet
        // and its troops each belong to their own domain's objective.
        const bool combined=army->GetType()==ARMY_TYPE_COMBINED;
        for(int pass=0;pass<(combined?2:1);++pass)
        {
            const DomainTypes domain=combined&&pass==1?DOMAIN_LAND:army->GetDomainType();
            Objective* o=Touch(op->GetOwner(),target,domain);
            if(!o) continue;
            // Prefer the oldest still-active operation, preventing duplicate force credit.
            CvAIOperation* old=GET_PLAYER(op->GetOwner()).getAIOperation(o->operation);
            if(Live(old) && old->GetID()!=op->GetID() && old->GetTurnStarted()<=op->GetTurnStarted()) continue;
            o->operation=op->GetID();
            CvPlot* stage=army->GetArmyAIState()==ARMYAISTATE_MOVING_TO_DESTINATION?army->GetCenterOfMass(true):op->GetMusterPlot();
            // Land reinforcements gather at the muster city, not the fleet's water tile.
            const bool troops=combined && domain==DOMAIN_LAND;
            if(troops && stage && stage->isWater()) stage=op->GetMusterPlot();
            if(stage && !(troops && stage->isWater())) o->staging=stage->GetPlotIndex();
            int count=0,strength=0;
            for(CvUnit* u=army->GetFirstUnit();u;u=army->GetNextUnit(u))
                if(Usable(u) && u->getDomainType()==domain) { ++count; strength+=CvStackingAI::UnitStrength(u); }
            o->coreUnits=max(o->coreUnits,count); o->coreStrength=max(o->coreStrength,strength);
        }
    }
    void ObserveSiege(PlayerTypes owner,CvCity* city)
    {
        if(!city || !Enabled(owner) || !GET_PLAYER(owner).IsAtWarWith(city->getOwner()) || !city->plot()->isVisible(GET_PLAYER(owner).getTeam())) return;
        Sync(owner);
        // Land demand always remains useful. Add sea support only when a real fleet is present.
        Touch(owner,city->plot(),DOMAIN_LAND);
        if(city->plot()->isCoastalLand())
            for(int i=0;i<RING2_PLOTS;++i)
            {
                CvPlot* p=iterateRingPlots(city->plot(),i); if(!p) continue;
                for(int j=0;j<p->getNumUnits();++j)
                {
                    const CvUnit* u=p->getUnitByIndex(j);
                    if(Usable(u) && u->getOwner()==owner && u->getDomainType()==DOMAIN_SEA)
                    { Touch(owner,city->plot(),DOMAIN_SEA); return; }
                }
            }
    }
    bool HasCommitment(const CvUnit* unit,const CvPlot* target)
    {
        if(!unit || !Enabled(unit->getOwner())) return false;
        Refresh(); std::map<Key,Commitment>::const_iterator i=commitments.find(Key(unit->getOwner(),unit->GetID()));
        if(i==commitments.end()) return false;
        std::map<ObjectiveKey,Objective>::const_iterator o=objectives.find(i->second.goal);
        CvPlot* goal=GC.getMap().plotByIndexUnchecked(i->second.goal.target);
        return o!=objectives.end() && !AssignedElsewhere(unit,i->second.goal) && goal && goal->isCity() && goal->getOwner()==o->second.enemy &&
            goal->getOwner()!=unit->getOwner() &&
            (!target || i->second.goal.target==target->GetPlotIndex() ||
             (GET_PLAYER(unit->getOwner()).getAIOperation(o->second.operation) &&
              GET_PLAYER(unit->getOwner()).getAIOperation(o->second.operation)->GetTargetPlot()==target));
    }
    void AddDemands(CvUnit* unit,std::vector<Demand>& result)
    {
        if(!unit || !Enabled(unit->getOwner())) return;
        const PlayerTypes owner=unit->getOwner(); Sync(owner);
        CvPlayer& player=GET_PLAYER(owner);
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();++i)
        {
            const ObjectiveKey& key=i->first; Objective& o=i->second;
            if(key.owner!=owner || key.domain!=unit->getDomainType()) continue;
            CvPlot* target=GC.getMap().plotByIndexUnchecked(key.target);
            if(!target || !target->isCity() || target->getOwner()!=o.enemy || RouteBlocked(owner,target,key.domain==DOMAIN_SEA)) continue;
            CvAIOperation* op=player.getAIOperation(o.operation);
            const bool active=Live(op) && CvStackingOffensiveAI::CityTarget(op)==target;
            if(op && CvStackingOffensiveAI::CityTarget(op)!=target) continue;
            if(!active && !player.IsAtWarWith((PlayerTypes)o.enemy)) continue;
            if(!active && o.assault.staging<0) o.staging=key.target;
            const std::map<Key,Commitment>::const_iterator own=commitments.find(Key(owner,unit->GetID()));
            if(own!=commitments.end() && !(own->second.goal==key)) continue;
            int count=0,strength=0,capturers=0,ranged=0,siege=0,inbound=0,loop=0;
            for(CvUnit* other=player.firstUnit(&loop);other;other=player.nextUnit(&loop))
            {
                if(other==unit || !Matches(other,key,o) ||
                    other->GetCurrHitPoints()*100<other->GetMaxHitPoints()*Setting("AIOffensiveProductionHealthyPercent",65)) continue;
                ++count; strength+=CvStackingAI::UnitStrength(other);
                capturers+=CanCapture(other,target); siege+=IsSiegeUnit(other);
                ranged+=other->IsCanAttackRanged() && !IsSiegeUnit(other);
                inbound+=plotDistance(*other->plot(),*target)>Setting("AIOffensiveSupportLocalRadius",4);
            }
            const int mean=max(1,o.coreUnits?o.coreStrength/o.coreUnits:CvStackingAI::UnitStrength(unit));
            const int training=active?(int)op->GetNumUnitsCommittedToBeBuilt():0;
            const int maximum=Setting("AIOffensiveSupportMaximumUnits",32);
            const int desiredCount=min(maximum,max(Setting("AIOffensiveSupportMinimumUnits",12),max(DesiredAssaultUnits(owner,target->getPlotCity(),(DomainTypes)key.domain),o.coreUnits)+Setting("AIOffensiveSupportReserveUnits",4)));
            CvPlot* stage=GC.getMap().plotByIndexUnchecked(o.staging);
            if(player.IsAtWarWith((PlayerTypes)o.enemy) && target->isVisible(player.getTeam()))
            {
                const AssaultPlan plan=AssessAssault(owner,target->getPlotCity(),(DomainTypes)key.domain);
                if(!plan.ready && plan.staging>=0) { o.staging=plan.staging; stage=GC.getMap().plotByIndexUnchecked(plan.staging); }
            }
            const int lead=stage?min(Setting("AIReinforcementMaximumTurns",12),plotDistance(*stage,*target)/max(1,unit->baseMoves(false))):0;
            const int reserve=min(Setting("AIOffensiveSupportMaximumReservePercent",60),Setting("AIOffensiveSupportReservePercent",25)+lead*Setting("AIOffensiveSupportTravelReservePercentPerTurn",2));
            const int desiredStrength=max(o.coreStrength,EnemyStrength(owner,target)*Setting("AIOffensiveSupportStrengthPercent",150)/100)*(100+reserve)/100;
            if(player.IsAtWarWith((PlayerTypes)o.enemy) && target->isVisible(player.getTeam())) CapturePlan(owner,target,o,(DomainTypes)key.domain);
            const bool missingCapture=capturers<Setting("AIOffensiveSupportMinimumCapturers",2) ||
                (o.captureKnown && o.captureID<0);
            const bool missingRanged=ranged<Setting("AIOffensiveSupportMinimumRanged",2);
            const int desiredSiege=DesiredSiegeUnits(owner,target->getPlotCity(),(DomainTypes)key.domain);
            const bool missingSiege=key.domain==DOMAIN_LAND?siege<desiredSiege:ranged<desiredSiege;
            const bool usefulRole=(o.captureOwner==owner && o.captureID==unit->GetID()) ||
                (missingCapture && CanCapture(unit,target)) || (missingRanged && unit->IsCanAttackRanged() && !IsSiegeUnit(unit)) ||
                (missingSiege && (key.domain==DOMAIN_LAND?IsSiegeUnit(unit):unit->IsCanAttackRanged()));
            const int repair=usefulRole?Setting("AIOffensiveProductionRoleRepairUnits",2):0;
            if(count+training>=maximum+repair || (!usefulRole && count+training>=desiredCount && strength+training*mean>=desiredStrength)) continue;
            // Do not send a third ranged reserve while a depleted siege specifically needs capture support.
            if(missingCapture && !CanCapture(unit,target) && !missingSiege && count+training>=desiredCount) continue;
            const int need=max(mean,max((desiredCount-count-training)*mean,desiredStrength-strength-training*mean));
            const int priority=Setting("AIReinforcementAttackPriority",200)+(usefulRole?Setting("AIOffensiveSupportRolePriority",80):0);
            result.push_back(Demand(o.staging,key.target,active?o.operation:-1,need,priority));
            CvStackingDiagnostics::Record(2,owner,"OFFENSIVE_DEMAND","target=%d unit=%d domain=%d assigned=%d inbound=%d training=%d strength=%d desired=%d desiredUnits=%d capture=%d ranged=%d siege=%d desiredSiege=%d need=%d",key.target,unit->GetID(),key.domain,count,inbound,training,strength,desiredStrength,desiredCount,capturers,ranged,siege,desiredSiege,need);
        }
    }
    void RecordTransfer(CvUnit* unit,int target,int operation,int eta)
    {
        if(!unit || !Enabled(unit->getOwner())) return;
        Refresh(); const Key key(unit->getOwner(),unit->GetID());
        Commitment& c=commitments[key]; const int plot=unit->plot()->GetPlotIndex();
        CvPlot* goal=GC.getMap().plotByIndexUnchecked(target);
        CvAIOperation* op=GET_PLAYER(unit->getOwner()).getAIOperation(operation);
        if(!goal || !goal->isCity() || goal->getOwner()==unit->getOwner() ||
            (!GET_PLAYER(unit->getOwner()).IsAtWarWith(goal->getOwner()) && (!Live(op) || CityTarget(op)!=goal)))
        { EraseCommitment(key); return; }
        Objective* refreshed=Touch(unit->getOwner(),goal,unit->getDomainType());
        if(!refreshed) { EraseCommitment(key); return; }
        const int distance=plotDistance(*unit->plot(),*goal);
        // An ETA estimate alone, without actual movement, is not progress.
        if(c.goal.target!=target || (c.plot!=plot && distance<c.bestDistance)) c.lastProgress=currentTurn;
        if(c.goal.target!=target) { c.arrived=false; c.capturer=false; c.assembly=false; c.bestDistance=distance;
            c.routeStage=c.routeDestination=c.routeFrom=c.routeTo=c.routeProgress=-1; }
        else c.bestDistance=min(c.bestDistance,distance);
        if(c.goal.target>=0 && !(c.goal==ObjectiveKey(unit->getOwner(),target,unit->getDomainType())))
            InvalidateProductionStaff((PlayerTypes)c.goal.owner,c.goal.target,(DomainTypes)c.goal.domain);
        c.goal=ObjectiveKey(unit->getOwner(),target,unit->getDomainType()); c.turn=currentTurn; c.plot=plot; c.eta=eta;
        refreshed->refreshed=currentTurn;
        InvalidateProductionStaff(unit->getOwner(),target,unit->getDomainType());
        c.arrived=distance<=Setting("AIOffensiveSupportLocalRadius",4);
        CvStackingDiagnostics::Record(1,unit->getOwner(),"OFFENSIVE_SUPPORT","unit=%d target=%d operation=%d eta=%d action=%s",unit->GetID(),target,operation,eta,
            plotDistance(*unit->plot(),*goal)<=Setting("AIOffensiveSupportLocalRadius",4)?"front_arrival":"travelling");
    }
    bool JoinArrived(CvUnit* unit)
    {
        if(!unit || !Enabled(unit->getOwner()) || unit->getArmyID()!=-1) return false;
        Sync(unit->getOwner());
        const Key key(unit->getOwner(),unit->GetID());
        std::map<Key,Commitment>::iterator c=commitments.find(key);
        if(c==commitments.end()) return false;
        std::map<ObjectiveKey,Objective>::iterator o=objectives.find(c->second.goal);
        if(o==objectives.end()) return false;
        CvAIOperation* op=GET_PLAYER(unit->getOwner()).getAIOperation(o->second.operation);
        if(!Live(op)) return false;
        CvArmyAI* army=op->GetArmy(0);
        CvPlot* stage=army?army->GetCenterOfMass(true):NULL;
        if(!stage || plotDistance(*unit->plot(),*stage)>Setting("AIAssaultStageCohesionRadius",2)) return false;
        const int id=unit->GetID(),owner=unit->getOwner();
        // RecruitUnit/AddUnit may upgrade/delete the unit. Never use its pointer afterwards.
        if(op->RecruitUnit(unit))
        {
            EraseCommitment(key);
            CvStackingDiagnostics::Record(1,(PlayerTypes)owner,"OFFENSIVE_SUPPORT","unit=%d operation=%d action=joined_formation",id,op->GetID());
            return true;
        }
        return false;
    }
    void CancelCommitment(const CvUnit* unit)
    {
        if(!unit || !Enabled(unit->getOwner())) return;
        if(EraseCommitment(Key(unit->getOwner(),unit->GetID())))
            CvStackingDiagnostics::Record(1,unit->getOwner(),"OFFENSIVE_SUPPORT","unit=%d action=reassigned_to_other_demand",unit->GetID());
    }
    bool HoldReserve(CvUnit* unit)
    {
        if(!HasCommitment(unit) || unit->GetDanger()>0) return false;
        std::map<Key,Commitment>::iterator c=commitments.find(Key(unit->getOwner(),unit->GetID()));
        std::map<ObjectiveKey,Objective>::iterator o=objectives.find(c->second.goal);
        if(o==objectives.end()) return false;
        CvAIOperation* op=GET_PLAYER(unit->getOwner()).getAIOperation(o->second.operation);
        CvArmyAI* army=Live(op)?op->GetArmy(0):NULL;
        CvPlot* stage=army?army->GetCenterOfMass(true):NULL;
        if(o->second.assault.staging>=0 && o->second.assault.phase!=1)
            stage=GC.getMap().plotByIndexUnchecked(o->second.assault.staging);
        if(!stage || plotDistance(*unit->plot(),*stage)>Setting("AIAssaultStageCohesionRadius",2)) return false;
        // Homeland patrol runs after tactical combat: keep a safe staged reserve available
        // for next turn instead of wandering back home when the formation is still full.
        c->second.lastProgress=currentTurn;
        assemblyHolds[Key(unit->getOwner(),unit->GetID())]=currentTurn;
        unit->SetTurnProcessed(true);
        CvStackingDiagnostics::Record(2,unit->getOwner(),"OFFENSIVE_SUPPORT","unit=%d target=%d operation=%d action=staged_reserve",unit->GetID(),c->second.goal.target,op?op->GetID():-1);
        return true;
    }
    bool RouteBlocked(PlayerTypes owner,CvPlot* target,bool naval)
    {
        if(!target || !Enabled(owner)) return false;
        Refresh(); std::map<ObjectiveKey,Failure>::const_iterator i=failures.find(ObjectiveKey(owner,target->GetPlotIndex(),naval?DOMAIN_SEA:DOMAIN_LAND));
        return i!=failures.end() && i->second.until>=currentTurn && i->second.enemy==target->getOwner();
    }
    void OperationAborted(CvAIOperation* op,int reason)
    {
        if(!IsCityAttack(op) || !Enabled(op->GetOwner()) || !CityTarget(op)) return;
        Refresh();
        if(reason==AI_ABORT_LOST_PATH || reason==AI_ABORT_TIMED_OUT)
        {
            const int turns=Setting("AIOperationRouteRetryTurns",6);
            if(turns>0)
            {
                Failure& f=failures[ObjectiveKey(op->GetOwner(),CityTarget(op)->GetPlotIndex(),op->IsNavalOperation()?DOMAIN_SEA:DOMAIN_LAND)];
                f.until=currentTurn+turns-1; f.enemy=op->GetEnemy();
                CvStackingDiagnostics::Record(1,op->GetOwner(),"OPERATION_ROUTE","operation=%d target=%d reason=%d action=cooldown until=%d",op->GetID(),op->GetTargetPlot()->GetPlotIndex(),reason,f.until);
            }
        }
        // Abort cancels its support objective; successful handoff follows a separate path.
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();)
            if(i->first.owner==op->GetOwner() && i->second.operation==op->GetID()) objectives.erase(i++); else ++i;
    }
    CvPlot* RepairRoute(const CvAIOperation* op,CvArmyAI* army,CvPlot* from,CvPlot* waypoint)
    {
        if(!IsCityAttack(op) || !Enabled(op->GetOwner()) || !army || !waypoint) return NULL;
        int attempts=0; std::set<int> starts;
        if(from) starts.insert(from->GetPlotIndex());
        for(CvUnit* u=army->GetFirstUnit();u && attempts<Setting("AIOperationRouteRepairCandidates",4);u=army->GetNextUnit(u))
        {
            if(!Usable(u) || !starts.insert(u->plot()->GetPlotIndex()).second) continue;
            ++attempts;
            CvPlot* next=op->GetPlotXInStepPath(u->plot(),waypoint,army->GetMovementRate()+1,true);
            CvStackingDiagnostics::Record(1,op->GetOwner(),"OPERATION_ROUTE","operation=%d from=%d waypoint=%d unit=%d candidate=%d repaired=%d",op->GetID(),from?from->GetPlotIndex():-1,waypoint->GetPlotIndex(),u->GetID(),u->plot()->GetPlotIndex(),next!=NULL);
            if(next) return next;
        }
        CvStackingDiagnostics::Record(1,op->GetOwner(),"OPERATION_ROUTE","operation=%d from=%d waypoint=%d target=%d naval=%d attempts=%d action=failed",op->GetID(),from?from->GetPlotIndex():-1,waypoint->GetPlotIndex(),op->GetTargetPlot()?op->GetTargetPlot()->GetPlotIndex():-1,op->IsNavalOperation(),attempts);
        return NULL;
    }
    static bool LegacyOpeningReady(CvAIOperation* op,CvArmyAI* army)
    {
        if(!IsCityAttack(op) || !Enabled(op->GetOwner()) || Setting("AIWarPreparationEnabled",1)==0) return true;
        if(!army || !op->GetTargetPlot()) return false;
        CvPlot* target=CityTarget(op);
        if(!target) return false;
        int total=0,healthy=0,capture=0,ranged=0,strength=0,siege=0,loop=0;
        const int maxTurns=Setting("AIWarOpeningMaximumTurns",3);
        CvPlayer& player=GET_PLAYER(op->GetOwner());
        for(CvUnit* u=player.firstUnit(&loop);u;u=player.nextUnit(&loop))
        {
            if(!Usable(u) || !InArmyDomain(army,u) ||
                (u->getArmyID()!=army->GetID() && !(u->getArmyID()==-1 && HasCommitment(u,target)))) continue;
            ++total;
            if(u->GetCurrHitPoints()*100<u->GetMaxHitPoints()*GD_INT_GET(AI_OPERATIONAL_PERCENT_HEALTH_FOR_OPERATION)) continue;
            // This army path permits the intended enemy only, not third-party closed borders.
            // It is a bounded potential-war distance estimate; actual transfer/capture routes use unit paths.
            const int distance=op->GetStepDistanceBetweenPlots(u->plot(),target);
            if(distance<0 || distance>maxTurns*max(1,u->baseMoves(false))+1) continue;
            ++healthy; strength+=CvStackingAI::UnitStrength(u);
            capture+=CanCapture(u,target); ranged+=u->IsCanAttackRanged();
            siege+=u->getDomainType()==DOMAIN_SEA?u->IsCanAttackRanged():IsSiegeUnit(u);
        }
        const int desiredSiege=KnownFortified(op->GetOwner(),target->getPlotCity())?DesiredSiegeUnits(op->GetOwner(),target->getPlotCity(),AssaultDomain(army)):0;
        const bool ready=siege>=desiredSiege && CvStackingAIPolicy::OpeningReady(healthy,total,capture,ranged,strength,EnemyStrength(op->GetOwner(),target),
            Setting("AIWarOpeningMinimumUnits",4),Setting("AIWarOpeningReadyPercent",75),Setting("AIWarOpeningMinimumRanged",1),Setting("AIWarOpeningStrengthPercent",150));
        CvStackingDiagnostics::Record(1,op->GetOwner(),"WAR_READINESS","operation=%d target=%d total=%d staged=%d capture=%d ranged=%d siege=%d desiredSiege=%d strength=%d ready=%d",op->GetID(),target->GetPlotIndex(),total,healthy,capture,ranged,siege,desiredSiege,strength,ready);
        return ready;
    }
void ResetOpeningReadiness(){openingForecasts.clear();openingForecastTurn=-1;}
    bool TryReadyCoreForArmy(CvAIOperation* op,CvArmyAI* army,bool& ready)
    {
        ready=false;
        if(!IsCityAttack(op)||!Enabled(op->GetOwner())||!army||!CityTarget(op)||
            !GET_PLAYER(op->GetOwner()).IsAtWarWith(op->GetEnemy()))return false;
        CvPlot* target=CityTarget(op);const PlayerTypes owner=op->GetOwner();
        if(target->getOwner()!=op->GetEnemy())return true; // Known ownership change cannot release an attack on the old enemy.
        if(!target->isVisible(GET_PLAYER(owner).getTeam()))return false;
        ObserveOperation(op);const AssaultPlan shared=AssessAssault(owner,target->getPlotCity(),army->GetDomainType());
        std::map<ObjectiveKey,Objective>::iterator found=objectives.find(ObjectiveKey(owner,target->GetPlotIndex(),army->GetDomainType()));
        if(found==objectives.end()||found->second.operation!=op->GetID()||!found->second.waveComplete)return false;
        Objective& o=found->second;
        // A combined army's troops are assessed by its land objective; the
        // wave combines them with the fleet.
        std::map<ObjectiveKey,Objective>::iterator troops=objectives.end();
        if(army->GetType()==ARMY_TYPE_COMBINED)
        {
            AssessAssault(owner,target->getPlotCity(),DOMAIN_LAND);
            troops=objectives.find(ObjectiveKey(owner,target->GetPlotIndex(),DOMAIN_LAND));
            if(troops==objectives.end()||troops->second.operation!=op->GetID()||!troops->second.waveComplete)return false;
        }
        std::vector<AssaultWaveUnit> eligibleRows;int omitted=0;
        try
        {
            for(int pass=0;pass<(troops==objectives.end()?1:2);++pass)
            {
                const std::map<ObjectiveKey,Objective>::iterator source=pass==0?found:troops;
                const std::vector<AssaultWaveUnit>& rows=source->second.waveRows;
                eligibleRows.reserve(eligibleRows.size()+rows.size());
                for(size_t i=0;i<rows.size();++i)
                {
                    const AssaultWaveUnit& row=rows[i];
                    if(row.army!=-1&&row.army!=army->GetID())continue;
                    if(!WaveRecordStillValid(owner,target,row) ||
                        (row.army==-1&&!Matches(GET_PLAYER(owner).getUnit(row.unit),source->first,source->second)))
                    {++omitted;continue;}
                    eligibleRows.push_back(row);
                }
            }
        }
        catch(const std::bad_alloc&){return false;} // Optional metadata uncertainty retains the original policy.
        int eligibleCapture=INT_MAX;
        {
            for(size_t i=0;i<eligibleRows.size();++i)
                if((eligibleRows[i].roles&1)!=0)eligibleCapture=min(eligibleCapture,eligibleRows[i].eta);
        }
        if(eligibleCapture==INT_MAX&&o.captureOwner!=owner&&o.captureOwner!=NO_PLAYER&&o.captureOwner>=0&&o.captureID>=0&&o.captureEta==0)
        {
            // Preserve the existing useful-fire policy for a currently visible
            // adjacent co-belligerent capturer, without crediting its army power.
            const CvUnit* ally=GET_PLAYER((PlayerTypes)o.captureOwner).getUnit(o.captureID);
            if(CanCapture(ally,target)&&InArmyDomain(army,ally)&&
                ally->isNativeDomain(ally->plot())&&plotDistance(*ally->plot(),*target)<=1&&
                ally->plot()->isVisible(GET_PLAYER(owner).getTeam())&&!ally->isInvisible(GET_PLAYER(owner).getTeam(),false)&&
                !GET_PLAYER(owner).IsAtWarWith(ally->getOwner())&&GET_PLAYER(ally->getOwner()).IsAtWarWith(target->getOwner()))eligibleCapture=0;
        }
        // Earlier safe shots, healing or another army can consume optional
        // support. Only unchanged eligible rows contribute to this core; an
        // essential loss still fails the ordinary count/role/power predicates.
        AssaultWave wave=SelectFirstWave(eligibleRows,Setting("AIAssemblyMinimumCombatUnits",4),
            EssentialSiege(owner,target->getPlotCity(),AssaultDomain(army)),Setting("AIAssemblyMinimumRanged",2),
            shared.enemyStrength,Setting("AIAssemblyStrengthPercent",150),max(1,target->getPlotCity()->GetMaxHitPoints()-target->getPlotCity()->getDamage()),
            eligibleCapture,Setting("AIAssaultFirstWaveMaximumTurns",1),
            Setting("AIAssaultWaveArrivalSpreadTurns",1),army->GetID(),Setting("AIAssemblyMinimumCombatUnits",4));
        bool complete=false;const int healing=target->getPlotCity()->GetAssaultHealingForecast(owner,wave.damage,&complete);
        ready=WaveCanSustain(wave,max(1,target->getPlotCity()->GetMaxHitPoints()-target->getPlotCity()->getDamage()),
            healing,Setting("AIAssaultDamageHorizon",4),complete);
        const bool pathUnknown=o.wavePathUnknown||(troops!=objectives.end()&&troops->second.wavePathUnknown);
        const bool captureKnown=o.captureKnown||(troops!=objectives.end()&&troops->second.captureKnown);
        if(!ready&&!omitted&&(pathUnknown||!captureKnown))return false; // Pure path uncertainty stays unknown; changed insufficient cores cannot leak through count fallback.
        CvStackingDiagnostics::Record(1,owner,"OPERATION_READINESS","operation=%d army=%d target=%d core=%d ownCore=%d siege=%d capturers=%d strength=%d damage=%d sustained=%d healing=%d healingComplete=%d firstETA=%d lastETA=%d failedMask=%u ready=%d cohortOmitted=%d policy=capability_first_wave",
            op->GetID(),army->GetID(),target->GetPlotIndex(),wave.units,wave.own,wave.siege,wave.capture,wave.strength,wave.damage,wave.sustain,healing,complete,
            wave.first==INT_MAX?-1:wave.first,wave.last,wave.failed,ready,omitted);
        return true;
    }

    bool OpeningReady(CvAIOperation* op,CvArmyAI* army)
    {
        if(!IsCityAttack(op)||!Enabled(op->GetOwner())||Setting("AIWarPreparationEnabled",1)==0)return true;
        if(!army||!op->GetTargetPlot())return false;
        CvPlot* target=CityTarget(op);if(!target||target->getOwner()!=op->GetEnemy())return false;
        const PlayerTypes owner=op->GetOwner();CvPlayer& player=GET_PLAYER(owner);
        if(player.IsAtWarWith(op->GetEnemy()))
        {bool ready=false;return TryReadyCoreForArmy(op,army,ready)&&ready;}
        const int turn=GC.getGame().getGameTurn();
        if(openingForecastTurn!=turn){openingForecasts.clear();openingForecastTurn=turn;}
        const OpeningKey key(owner,op->GetID(),army->GetID());
        std::map<OpeningKey,OpeningForecast>::const_iterator cached=openingForecasts.find(key);
        const bool visible=target->isVisible(player.getTeam());
        if(cached!=openingForecasts.end())
        {
            const OpeningForecast& f=cached->second;
            if(!f.complete)return LegacyOpeningReady(op,army);
            if(f.target!=target->GetPlotIndex()||f.enemy!=target->getOwner()||f.domain!=army->GetDomainType()||
                f.filled!=(int)army->GetNumSlotsFilled()||f.visible!=visible)return false;
            if(visible&&(f.hp!=target->getPlotCity()->GetMaxHitPoints()-target->getPlotCity()->getDamage()||
                f.strength!=target->getPlotCity()->getStrengthValue()))return false;
            for(size_t i=0;i<f.rows.size();++i)if(!WaveRecordStillValid(owner,target,f.rows[i]))return false;
            return f.ready; // No route retry or hidden reads on a same-turn cache hit.
        }
        int cachedForOwner=0;
        for(std::map<OpeningKey,OpeningForecast>::const_iterator i=openingForecasts.begin();i!=openingForecasts.end();++i)cachedForOwner+=i->first.owner==owner;
        if(cachedForOwner>=Setting("AIOffensiveSupportMaximumObjectives",8))return false;
        OpeningForecast forecast;forecast.turn=turn;forecast.target=target->GetPlotIndex();forecast.enemy=target->getOwner();
        forecast.domain=army->GetDomainType();forecast.filled=(int)army->GetNumSlotsFilled();forecast.visible=visible;
        if(visible){forecast.hp=target->getPlotCity()->GetMaxHitPoints()-target->getPlotCity()->getDamage();forecast.strength=target->getPlotCity()->getStrengthValue();}
        int total=0,healthy=0,capture=0,ranged=0,strength=0,siege=0,loop=0,captureEta=INT_MAX;
        bool complete=true;
        const int maxTurns=Setting("AIWarOpeningMaximumTurns",3);
        for(CvUnit* u=player.firstUnit(&loop);u;u=player.nextUnit(&loop))
        {
            if(!Usable(u)||!InArmyDomain(army,u)||
                (u->getArmyID()!=army->GetID()&&!(u->getArmyID()==-1&&HasCommitment(u,target))))continue;
            ++total;
            const int healthyPercent=visible?max(GD_INT_GET(AI_OPERATIONAL_PERCENT_HEALTH_FOR_OPERATION),Setting("AIAssaultHealthyPercent",65)):
                GD_INT_GET(AI_OPERATIONAL_PERCENT_HEALTH_FOR_OPERATION);
            if((long long)u->GetCurrHitPoints()*100<(long long)u->GetMaxHitPoints()*healthyPercent)continue;
            const int distance=op->GetStepDistanceBetweenPlots(u->plot(),target);
            if(distance<0||distance>maxTurns*max(1,u->baseMoves(false))+1)continue;
            ++healthy;strength+=CvStackingAI::UnitStrength(u);capture+=CanCapture(u,target);ranged+=u->IsCanAttackRanged();
            siege+=u->getDomainType()==DOMAIN_SEA?u->IsCanAttackRanged():IsSiegeUnit(u);
            int hit=0,retaliation=0,garrison=0;
            if(visible)
            {
                if(u->isNativeDomain(u->plot()))
                {
                    // Potential-war operation route is the existing estimate. This
                    // nominal damage forecast does not authorize an actual shot.
                    hit=TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(target->getPlotCity(),u,u->plot(),retaliation,garrison);
                    if(hit<=0||retaliation>=u->GetCurrHitPoints())continue;
                }
                // Embarked troops of a combined invasion land to capture; no
                // damage is forecast for them from the water.
                else if(army->GetType()!=ARMY_TYPE_COMBINED||u->getDomainType()!=DOMAIN_LAND)continue;
            }
            const int reach=u->IsCanAttackRanged()?u->GetRange():1;
            const int travel=max(0,distance-reach),moves=max(1,u->baseMoves(false));
            const int eta=(travel+moves-1)/moves;
            if(CanCapture(u,target))captureEta=min(captureEta,eta);
            if(complete)
            {
                if(forecast.rows.size()>=(size_t)Setting("AIAssaultWaveMaximumRecords",64)){complete=false;forecast.rows.clear();}
                else try{forecast.rows.push_back(AssaultWaveUnit(u,eta,hit,retaliation,target));}
                catch(const std::bad_alloc&){complete=false;forecast.rows.clear();}
            }
        }
        const int enemy=EnemyStrength(owner,target);
        const int desiredSiege=KnownFortified(owner,target->getPlotCity())?DesiredSiegeUnits(owner,target->getPlotCity(),AssaultDomain(army)):0;
        bool ready=siege>=desiredSiege&&CvStackingAIPolicy::OpeningReady(healthy,total,capture,ranged,strength,enemy,
            Setting("AIWarOpeningMinimumUnits",4),Setting("AIWarOpeningReadyPercent",75),Setting("AIWarOpeningMinimumRanged",1),Setting("AIWarOpeningStrengthPercent",150));
        AssaultWave wave;bool healingComplete=false;int healing=0;
        if(visible&&complete)
        {
            wave=SelectFirstWave(forecast.rows,Setting("AIWarOpeningMinimumUnits",4),EssentialSiege(owner,target->getPlotCity(),AssaultDomain(army)),
                Setting("AIWarOpeningMinimumRanged",1),enemy,Setting("AIWarOpeningStrengthPercent",150),max(1,forecast.hp),captureEta,maxTurns,
                Setting("AIAssaultWaveArrivalSpreadTurns",1),army->GetID(),Setting("AIWarOpeningMinimumUnits",4));
            healing=target->getPlotCity()->GetAssaultHealingForecast(owner,wave.damage,&healingComplete);
            ready=WaveCanSustain(wave,max(1,forecast.hp),healing,Setting("AIAssaultDamageHorizon",4),healingComplete);
        }
        if(!complete)wave.failed|=ASSAULT_UNKNOWN;
        forecast.ready=ready;forecast.complete=complete;
        try{openingForecasts.insert(std::make_pair(key,forecast));}catch(const std::bad_alloc&){} // Optional cache only.
        CvStackingDiagnostics::Record(1,owner,"WAR_READINESS","operation=%d target=%d total=%d staged=%d capture=%d ranged=%d siege=%d desiredSiege=%d strength=%d ready=%d visible=%d waveUnits=%d ownCore=%d waveSiege=%d waveDamage=%d waveSustain=%d healing=%d healingComplete=%d captureETA=%d firstETA=%d lastETA=%d failedMask=%u known=%d",
            op->GetID(),target->GetPlotIndex(),total,healthy,capture,ranged,siege,desiredSiege,strength,ready,visible,wave.units,wave.own,wave.siege,wave.damage,wave.sustain,
            healing,healingComplete,captureEta==INT_MAX?-1:captureEta,wave.first==INT_MAX?-1:wave.first,wave.last,wave.failed,complete);
        return ready;
    }
    bool ReadyToDeclare(PlayerTypes owner,PlayerTypes enemy)
    {
        if(!Enabled(owner) || Setting("AIWarPreparationEnabled",1)==0) return true;
        CvPlayer& player=GET_PLAYER(owner);
        if(player.IsAtWarWith(enemy))return true; // Existing forced/defensive war has no voluntary-opening gate.
        bool ready=false;
        for(size_t i=0;i<player.getNumAIOperations();++i)
        {
            CvAIOperation* op=player.getAIOperationByIndex(i);
            if(Live(op) && op->GetEnemy()==enemy && IsCityAttack(op) && OpeningReady(op,op->GetArmy(0))) { ready=true; break; }
        }
        CvStackingDiagnostics::Record(1,owner,"WAR_DECLARATION","enemy=%d reason=voluntary_city_attack ready=%d",enemy,ready);
        return ready;
    }
    bool HoldForContact(CvAIOperation* op,CvArmyAI* army,CvPlot* next)
    {
        if(!IsCityAttack(op) || !Enabled(op->GetOwner()) || !army || !next) return true;
        int exposed=0,total=0;
        for(CvUnit* u=army->GetFirstUnit();u;u=army->GetNextUnit(u))
        {
            if(!Usable(u)) continue;
            ++total;
            exposed+=u->GetDanger()>0 || (u->canUseNow() && u->GetDanger(next)>=u->GetCurrHitPoints());
        }
        const bool hold=total==0 || exposed*100>=total*Setting("AIOperationContactHoldPercent",50);
        CvStackingDiagnostics::Record(1,op->GetOwner(),"OPERATION_CONTACT","operation=%d total=%d exposed=%d hold=%d",op->GetID(),total,exposed,hold);
        return hold;
    }
    bool MovingStalled(CvAIOperation* op,CvArmyAI* army,bool contact)
    {
        if(!IsCityAttack(op) || !Enabled(op->GetOwner()) || army->GetArmyAIState()!=ARMYAISTATE_MOVING_TO_DESTINATION) return false;
        Refresh(); CvPlot* center=army->GetCenterOfMass(true),*target=op->GetTargetPlot();
        if(!center || !target) return false;
        March& m=marches[Key(op->GetOwner(),op->GetID())];
        if(m.turn==currentTurn) return false;
        const int distance=plotDistance(*center,*target);
        if(m.turn<0 || m.target!=target->GetPlotIndex()) { m.distance=distance; m.lastProgress=currentTurn; }
        if(distance<m.distance) m.lastProgress=currentTurn;
        m.turn=currentTurn; m.target=target->GetPlotIndex(); m.distance=min(m.distance,distance);
        // A real siege close to its target should be reassessed by the capture policy, not the march timer.
        if(distance<=op->GetDeployRange()) m.lastProgress=currentTurn;
        const int idle=currentTurn-m.lastProgress;
        const bool stalled=CvStackingAIPolicy::MovingStalled(idle,contact,Setting("AIOperationMovingStallTurns",12),Setting("AIOperationContactStallTurns",20));
        CvStackingDiagnostics::Record(1,op->GetOwner(),"OPERATION_PROGRESS","operation=%d distance=%d bestDistance=%d idle=%d contact=%d action=%s",op->GetID(),distance,m.distance,idle,contact,stalled?"reassess_abort":"continue");
        return stalled;
    }
    bool ContinueSiege(PlayerTypes owner,CvCity* city)
    {
        if(!city || !Enabled(owner) || !city->plot()->isVisible(GET_PLAYER(owner).getTeam())) return true;
        ObserveSiege(owner,city);
        std::map<ObjectiveKey,Objective>::iterator i=objectives.find(ObjectiveKey(owner,city->plot()->GetPlotIndex(),DOMAIN_LAND));
        if(i==objectives.end()) return true;
        Objective& o=i->second; CapturePlan(owner,city->plot(),o);
        const int hp=city->GetMaxHitPoints()-city->getDamage();
        const bool review=o.captureKnown && o.noCaptureSince>=0 && currentTurn-o.noCaptureSince>=Setting("AISiegeNoCaptureReviewTurns",8) &&
            hp*100<=city->GetMaxHitPoints()*Setting("AISiegeNoCaptureLowHPPercent",25);
        if(!review) return true;
        // Collateral/defender pressure remains useful even without a current capture route.
        for(int n=0;n<city->plot()->getNumUnits();++n)
        {
            const CvUnit* u=city->plot()->getUnitByIndex(n);
            if(Usable(u) && u->getOwner()==city->getOwner() && !u->isInvisible(GET_PLAYER(owner).getTeam(),false) &&
                u->GetCurrHitPoints()*100>u->GetMaxHitPoints()*Setting("CollateralHPFloorPercent",50)) return true;
        }
        CvStackingDiagnostics::Record(1,owner,"SIEGE_REASSESS","target=%d hp=%d missingTurns=%d action=skip_futile_city_fire",city->plot()->GetPlotIndex(),hp,currentTurn-o.noCaptureSince);
        return false;
    }
    bool PrioritizeExisting(PlayerTypes owner,CvPlot* target,bool naval)
    {
        if(!Enabled(owner) || !target) return false;
        Sync(owner);
        const ObjectiveKey key(owner,target->GetPlotIndex(),naval?DOMAIN_SEA:DOMAIN_LAND);
        std::map<ObjectiveKey,Objective>::const_iterator i=objectives.find(key);
        if(i==objectives.end()) return false;
        CvAIOperation* op=GET_PLAYER(owner).getAIOperation(i->second.operation);
        // Retained objectives use rear transfers; don't spawn a fresh parallel army every turn.
        return Live(op) || currentTurn-i->second.refreshed<=Setting("AIOffensiveSupportMemoryTurns",12);
    }
}
