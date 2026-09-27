#include "CvGameCoreDLLPCH.h"
#include "CvStackingAI.h"
#include "CvStackingAIPolicy.h"
#include "CvStackingRules.h"
#include "CvStackingDiagnostics.h"
#include "CvPlayerAI.h"
#include "CvUnit.h"
#include "CvCity.h"
#include "CvPlot.h"
#include "CvMap.h"
#include "CvTeam.h"
#include "CvArmyAI.h"
#include "CvAIOperation.h"
#include "CvMilitaryAI.h"
#include "CvDangerPlots.h"
#include "CvTacticalAI.h"
#include "CvTypes.h"
#include <map>
#include <set>
#include <algorithm>
#include "LintFree.h"

namespace
{
    typedef std::pair<int,int> Key;
    struct Progress
    {
        int turn, plot, eta, army, checkpoint, stationary;
        Progress() : turn(-1), plot(-1), eta(INT_MAX), army(-1), checkpoint(-1), stationary(0) {}
    };
    struct Cooldown { int until, target; Cooldown() : until(-1), target(-1) {} };
    struct Transfer { int turn, target; Transfer() : turn(-1), target(-1) {} };
    struct Assembly
    {
        int turn, state, stageStart, lastProgress, units, distance;
        Assembly() : turn(-1), state(-1), stageStart(-1), lastProgress(-1), units(0), distance(INT_MAX) {}
    };
    std::map<Key, CvStackingAI::CityDefense> cities;
    std::map<Key, Progress> progress;
    std::map<Key, Cooldown> cooldowns;
    std::map<Key, Transfer> transfers;
    std::map<Key, Assembly> assemblies;
    int cacheTurn = -1;
    int pathQueries[MAX_PLAYERS] = {0}, transfersThisTurn[MAX_PLAYERS] = {0};

    int Setting(const char* name, int fallback) { return CvStacking::GetInt(name, fallback); }
    void Refresh()
    {
        const int turn = GC.getGame().getGameTurn();
        if (cacheTurn == turn) return;
        cacheTurn = turn;
        cities.clear();
        memset(pathQueries, 0, sizeof(pathQueries));
        memset(transfersThisTurn, 0, sizeof(transfersThisTurn));
        // No per-unit history grows with campaign duration; no pointers survive turns.
        for (std::map<Key, Progress>::iterator i=progress.begin(); i!=progress.end(); )
            if (turn-i->second.turn > 8) progress.erase(i++); else ++i;
        for (std::map<Key, Cooldown>::iterator i=cooldowns.begin(); i!=cooldowns.end(); )
            if (i->second.until < turn) cooldowns.erase(i++); else ++i;
        for (std::map<Key, Transfer>::iterator i=transfers.begin(); i!=transfers.end(); )
            if (turn-i->second.turn > Setting("AIReassignmentCooldown",3)+1) transfers.erase(i++); else ++i;
        for (std::map<Key, Assembly>::iterator i=assemblies.begin(); i!=assemblies.end(); )
            if (turn-i->second.turn > 2) assemblies.erase(i++); else ++i;
    }
    bool Eligible(const CvUnit* unit, PlayerTypes owner, DomainTypes domain)
    {
        return unit && unit->getOwner()==owner && unit->getDomainType()==domain && unit->IsCombatUnit() &&
            !unit->isCargo() && !unit->isDelayedDeath() && !unit->IsStackingUnit() && !unit->isEmbarked();
    }
    int GarrisonScore(const CvUnit* unit, const CvCity* city)
    {
        int score = CvStackingAI::UnitStrength(unit) * 100;
        if (unit->IsCanAttackRanged() && unit->GetRange()>1 && unit->AI_getUnitAIType()!=UNITAI_CITY_BOMBARD)
            score += Setting("AIGarrisonRangedBonus",20)*100;
        if (unit->AI_getUnitAIType()==UNITAI_CITY_BOMBARD) score /= 2;
        if (unit->getUnitInfo().GetDefaultUnitAIType()==UNITAI_EXPLORE) score /= 2;
        if (unit->getDomainType()==DOMAIN_SEA) score /= 2;
        if (city && city->GetGarrisonedUnit()==unit) ++score; // stable ties, no endless swaps
        return score;
    }
    void Defenders(const CvCity* city, DomainTypes domain, std::vector<const CvUnit*>& result)
    {
        for (int i=0; i<city->plot()->getNumUnits(); ++i)
        {
            const CvUnit* unit=city->plot()->getUnitByIndex(i);
            if (Eligible(unit,city->getOwner(),domain)) result.push_back(unit);
        }
    }
    struct RetentionOrder
    {
        const CvCity* city; bool cavalry;
        RetentionOrder(const CvCity* c, bool f) : city(c), cavalry(f) {}
        int Score(const CvUnit* u) const
        {
            int result=GarrisonScore(u,city);
            // Keep available city defenders before tying down an already assembled army.
            if (u->getArmyID()==-1) result+=100000;
            if (cavalry && CvStacking::IsAntiCavalry(u)) result+=Setting("AIStackAntiFlankBonus",12)*100;
            return result;
        }
        bool operator()(const CvUnit* a,const CvUnit* b) const
        { const int sa=Score(a),sb=Score(b); return sa!=sb ? sa>sb : a->GetID()<b->GetID(); }
    };
    struct Demand
    {
        int plot, priority, strength, operation; DomainTypes domain;
        Demand(int p,int pr,int s,int o,DomainTypes d):plot(p),priority(pr),strength(s),operation(o),domain(d){}
        bool operator<(const Demand& other) const
        { return priority!=other.priority?priority>other.priority:plot!=other.plot?plot<other.plot:operation<other.operation; }
    };
}

namespace CvStackingAI
{
    bool Enabled(PlayerTypes owner)
    {
        return owner!=NO_PLAYER && CvStacking::IsEnabled() && Setting("AIEnabled",1)!=0 &&
            Setting("AIMilitaryAllocationEnabled",1)!=0 && !GET_PLAYER(owner).isBarbarian() &&
            !GET_PLAYER(owner).isHuman(ISHUMAN_AI_UNITS);
    }
    void Reset()
    {
        cities.clear(); progress.clear(); cooldowns.clear(); transfers.clear(); assemblies.clear(); cacheTurn=-1;
    }
    int UnitStrength(const CvUnit* unit)
    {
        if (!unit) return 0;
        const int base=max(unit->GetBaseCombatStrength(),unit->GetBaseRangedCombatStrength());
        return max(1,base*unit->GetCurrHitPoints()/max(1,unit->GetMaxHitPoints()));
    }
    CityDefense AssessCity(const CvCity* city)
    {
        CityDefense result;
        if (!city || !Enabled(city->getOwner())) return result;
        Refresh();
        const Key key(city->getOwner(),city->GetID());
        std::map<Key,CityDefense>::const_iterator found=cities.find(key);
        if (found!=cities.end()) return found->second;
        CvPlayer& player=GET_PLAYER(city->getOwner());
        const TeamTypes team=player.getTeam();
        std::set<Key> immediate, counted;
        // This is VP's actual attack-reach map, not an omniscient unit search.
        const std::vector<CvUnit*> attackers=player.GetPossibleAttackers(*city->plot(),team);
        for (size_t i=0;i<attackers.size();++i)
            if (attackers[i] && !attackers[i]->isInvisible(team,false))
                immediate.insert(Key(attackers[i]->getOwner(),attackers[i]->GetID()));
        const int radius=Setting("AICityApproachRadius",6);
        for (int i=0;i<1+3*radius*(radius+1);++i)
        {
            const CvPlot* plot=iterateRingPlots(city->plot(),i);
            if (!plot || !plot->isVisible(team)) continue;
            for (int j=0;j<plot->getNumUnits();++j)
            {
                const CvUnit* enemy=plot->getUnitByIndex(j);
                if (!enemy || enemy->isDelayedDeath() || enemy->isCargo() ||
                    !enemy->IsCanAttack() || !player.IsAtWarWith(enemy->getOwner()) || enemy->isInvisible(team,false)) continue;
                const Key enemyKey(enemy->getOwner(),enemy->GetID());
                if (!counted.insert(enemyKey).second) continue;
                const bool canReach=immediate.count(enemyKey)!=0;
                const int strength=UnitStrength(enemy)*(canReach?100:Setting("AICityApproachWeight",35))/100;
                result.enemyStrength+=strength;
                if (enemy->getDomainType()==DOMAIN_SEA) result.seaStrength+=strength;
                if (canReach) ++result.immediate; else ++result.nearby;
                result.collateral+=CvStacking::GetCollateralTargetLimit(enemy)>0;
                result.cavalry+=CvStacking::CanFlank(enemy);
            }
        }
        // Long-range air/ranged attackers may lie outside the approach scan.
        for (size_t i=0;i<attackers.size();++i)
        {
            const CvUnit* enemy=attackers[i];
            if (!enemy || enemy->isInvisible(team,false) || !player.IsAtWarWith(enemy->getOwner()) ||
                !counted.insert(Key(enemy->getOwner(),enemy->GetID())).second) continue;
            ++result.immediate; result.enemyStrength+=UnitStrength(enemy);
            if (enemy->getDomainType()==DOMAIN_SEA) result.seaStrength+=UnitStrength(enemy);
            result.collateral+=CvStacking::GetCollateralTargetLimit(enemy)>0;
            result.cavalry+=CvStacking::CanFlank(enemy);
        }
        const int cap=CvStacking::GetCapacity(player.GetID(),DOMAIN_LAND,true);
        result.landMaximum=min(cap,Setting("AICityMaximumDefenders",3));
        result.landMinimum=player.IsEarlyExpansionPhase()?0:min(result.landMaximum,Setting("AICitySafeDefenders",1));
        if (city->isUnderSiege() || city->isInDangerOfFalling())
            result.landMinimum=min(result.landMaximum,max(result.landMinimum,Setting("AICityEmergencyDefenders",2)));
        const int cityCredit=(city->getStrengthValue()/100)*max(0,city->GetMaxHitPoints()-city->getDamage())/
            max(1,city->GetMaxHitPoints())*Setting("AICityStrengthCreditPercent",50)/100;
        result.landStrength=max(0,result.enemyStrength*Setting("AICityDefenseStrengthPercent",120)/100-cityCredit);
        if (city->isCapital() && result.enemyStrength>0)
            result.landStrength=result.landStrength*Setting("AICapitalDefensePercent",125)/100;
        result.seaMaximum=result.seaStrength>0?min(CvStacking::GetCapacity(player.GetID(),DOMAIN_SEA,true),Setting("AICityMaximumNavalDefenders",2)):0;
        cities.insert(std::make_pair(key,result));
        CvStackingDiagnostics::Record(1,player.GetID(),"CITY_DEFENSE","city=%d plot=%d immediate=%d nearby=%d enemyStrength=%d needStrength=%d minimum=%d maximum=%d navalMaximum=%d collateral=%d cavalry=%d; nearby is visibility-limited proximity, not confirmed reach",
            city->GetID(),city->plot()->GetPlotIndex(),result.immediate,result.nearby,result.enemyStrength,result.landStrength,
            result.landMinimum,result.landMaximum,result.seaMaximum,result.collateral,result.cavalry);
        return result;
    }
    bool RetainCityUnit(const CvUnit* unit)
    {
        if (!unit || !unit->plot() || !unit->plot()->isCity()) return false;
        const CvCity* city=unit->plot()->getPlotCity();
        if (city->getOwner()!=unit->getOwner()) return false;
        if (!Enabled(unit->getOwner())) return unit->IsGarrisoned() && city->NeedsGarrison();
        const DomainTypes domain=unit->getDomainType();
        if (!Eligible(unit,city->getOwner(),domain) || domain==DOMAIN_AIR) return false;
        const CityDefense assessment=AssessCity(city);
        const int minimum=domain==DOMAIN_LAND?assessment.landMinimum:0;
        const int maximum=domain==DOMAIN_LAND?assessment.landMaximum:assessment.seaMaximum;
        const int desired=domain==DOMAIN_LAND?assessment.landStrength:assessment.seaStrength;
        std::vector<const CvUnit*> units; Defenders(city,domain,units);
        std::stable_sort(units.begin(),units.end(),RetentionOrder(city,assessment.cavalry>0));
        int count=0,strength=0;
        for (size_t i=0;i<units.size();++i)
        {
            if (CvStackingAIPolicy::ReachedDefense(count,strength,minimum,maximum,desired)) break;
            if (units[i]==unit) return true;
            ++count; strength+=UnitStrength(units[i]);
        }
        return false;
    }
    bool NeedsCityDefender(const CvCity* city)
    {
        if (!city) return false;
        const CityDefense a=AssessCity(city);
        std::vector<const CvUnit*> units; Defenders(city,DOMAIN_LAND,units);
        int strength=0; for(size_t i=0;i<units.size();++i) strength+=UnitStrength(units[i]);
        return !CvStackingAIPolicy::ReachedDefense((int)units.size(),strength,a.landMinimum,a.landMaximum,a.landStrength);
    }
    bool UsefulGarrison(const CvUnit* candidate,const CvCity* city)
    {
        if (!candidate || !city || candidate->getDomainType()!=DOMAIN_LAND || candidate->isCargo()) return false;
        if (candidate->plot()==city->plot()) return false; // already counted, adds no defensive capacity
        if (NeedsCityDefender(city)) return true;
        const CvUnit* current=city->GetGarrisonedUnit();
        if (!current || current==candidate) return false;
        const CityDefense a=AssessCity(city);
        // Rear cities need an adequate garrison, not a perpetual search for a ranged one.
        if (!a.immediate && !a.nearby) return false;
        return CvStackingAIPolicy::BetterGarrison(GarrisonScore(current,city),GarrisonScore(candidate,city),Setting("AIGarrisonReplacementPercent",20));
    }
    bool RecruitmentBlocked(const CvUnit* unit,const CvPlot* target)
    {
        if (!unit || !Enabled(unit->getOwner())) return false;
        Refresh();
        const std::map<Key,Cooldown>::const_iterator i=cooldowns.find(Key(unit->getOwner(),unit->GetID()));
        return i!=cooldowns.end() && i->second.until>=cacheTurn && (!target || i->second.target==target->GetPlotIndex());
    }
    void DelayRecruitment(const CvUnit* unit,const CvPlot* target)
    {
        if (!unit || !Enabled(unit->getOwner())) return;
        Refresh(); Cooldown& c=cooldowns[Key(unit->getOwner(),unit->GetID())];
        c.until=cacheTurn+Setting("AIFailedAssignmentCooldown",3); c.target=target?target->GetPlotIndex():-1;
    }
    bool ArmyUnitStalled(CvUnit* unit,CvArmyAI* army,CvPlot* checkpoint,int eta)
    {
        if (!unit || !army || !checkpoint || !Enabled(unit->getOwner())) return false;
        Refresh(); Progress& p=progress[Key(unit->getOwner(),unit->GetID())];
        if (p.turn==cacheTurn) return false;
        const int position=unit->plot()->GetPlotIndex();
        const bool same=p.turn==cacheTurn-1 && p.army==army->GetID() && p.checkpoint==checkpoint->GetPlotIndex();
        p.stationary=same && CvStackingAIPolicy::IsStationary(p.plot,position,p.eta,eta)?p.stationary+1:0;
        p.turn=cacheTurn; p.plot=position; p.eta=eta; p.army=army->GetID(); p.checkpoint=checkpoint->GetPlotIndex();
        const int grace=Setting("AIAssemblyNoProgressTurns",3);
        CvAIOperation* operation=GET_PLAYER(unit->getOwner()).getAIOperation(army->GetOperationID());
        if(!operation) return false;
        const bool atCheckpoint=plotDistance(*unit->plot(),*checkpoint)<=operation->GetGatherTolerance(army,checkpoint);
        if (atCheckpoint || unit->shouldHeal(false) || unit->GetDanger()>0) { p.stationary=0; return false; }
        if (p.stationary==grace)
        {
            unit->ClearPathCache();
            CvStackingDiagnostics::Record(1,unit->getOwner(),"ASSEMBLY_STALL","army=%d unit=%d checkpoint=%d eta=%d stationary=%d action=repath",army->GetID(),unit->GetID(),p.checkpoint,eta,p.stationary);
        }
        const bool release=p.stationary>=grace*2;
        if(release) CvStackingDiagnostics::Record(1,unit->getOwner(),"ASSEMBLY_STALL","army=%d unit=%d checkpoint=%d eta=%d stationary=%d action=release",army->GetID(),unit->GetID(),p.checkpoint,eta,p.stationary);
        CvStackingDiagnostics::Record(2,unit->getOwner(),"ASSEMBLY_PROGRESS","army=%d unit=%d plot=%d checkpoint=%d eta=%d stationary=%d release=%d",army->GetID(),unit->GetID(),position,p.checkpoint,eta,p.stationary,release);
        return release;
    }
    bool ReadyWithAvailableUnits(CvAIOperation* operation,CvArmyAI* army)
    {
        if (!operation || !army || !Enabled(operation->GetOwner()) || !operation->IsOffensive() ||
            GC.getGame().getGameTurn()-operation->GetTurnStarted()<Setting("AIRecruitmentReviewTurns",5) ||
            operation->GetEnemy()==NO_PLAYER || !GET_PLAYER(operation->GetOwner()).IsAtWarWith(operation->GetEnemy())) return false;
        CvPlot* target=operation->GetTargetPlot();
        if (!target || !target->isCity() || !target->isVisible(GET_PLAYER(operation->GetOwner()).getTeam())) return false;
        int present=0,required=0,missing=0,strength=0,support=0; bool capture=false;
        const std::vector<CvArmyFormationSlot>& slots=army->GetSlotStatus();
        for (size_t i=0;i<slots.size();++i)
        {
            if (slots[i].IsRequired()) { ++required; if(!slots[i].IsUsed()) ++missing; }
            const CvUnit* u=slots[i].IsUsed()?GET_PLAYER(operation->GetOwner()).getUnit(slots[i].GetUnitID()):NULL;
            if (!u || !u->IsCombatUnit() || u->isDelayedDeath()) continue;
            ++present; strength+=UnitStrength(u); support+=u->IsCanAttackRanged();
            capture|=u->IsCanAttackWithMove() && !u->isNoCapture() && (u->getDomainType()==DOMAIN_LAND || target->isCoastalLand());
        }
        int enemyStrength=max(1,target->getPlotCity()->getStrengthValue()/100);
        const TeamTypes team=GET_PLAYER(operation->GetOwner()).getTeam();
        for(int i=0;i<RING2_PLOTS;++i)
        {
            const CvPlot* p=iterateRingPlots(target,i);
            if(!p || !p->isVisible(team)) continue;
            for(int j=0;j<p->getNumUnits();++j)
            {
                const CvUnit* e=p->getUnitByIndex(j);
                if(e && !e->isDelayedDeath() && e->IsCombatUnit() && !e->isInvisible(team,false) && GET_PLAYER(operation->GetOwner()).IsAtWarWith(e->getOwner())) enemyStrength+=UnitStrength(e);
            }
        }
        const bool ready=CvStackingAIPolicy::CoreReady(present,required,missing,Setting("AIAssemblyMinimumCombatUnits",4),
            Setting("AIAssemblyRequiredPercent",75),Setting("AIAssemblyMaximumMissing",1),capture,support>=Setting("AIAssemblyMinimumRanged",2),strength,enemyStrength,Setting("AIAssemblyStrengthPercent",150));
        CvStackingDiagnostics::Record(1,operation->GetOwner(),"OPERATION_READINESS","operation=%d age=%d present=%d required=%d missing=%d capture=%d support=%d strength=%d enemy=%d ready=%d",operation->GetID(),GC.getGame().getGameTurn()-operation->GetTurnStarted(),present,required,missing,capture,support,strength,enemyStrength,ready);
        return ready;
    }
    bool AssemblyStalled(CvAIOperation* operation,CvArmyAI* army)
    {
        if(!operation || !army || !Enabled(operation->GetOwner()) || !operation->IsOffensive()) return false;
        const int state=army->GetArmyAIState();
        if(state!=ARMYAISTATE_WAITING_FOR_UNITS_TO_REINFORCE && state!=ARMYAISTATE_WAITING_FOR_UNITS_TO_CATCH_UP) return false;
        Refresh(); Assembly& a=assemblies[Key(operation->GetOwner(),operation->GetID())];
        if(a.turn==cacheTurn) return false;
        const int count=(int)army->GetNumSlotsFilled(),distance=army->GetFurthestUnitDistance(operation->GetMusterPlot());
        if(a.state!=state || a.turn<0) { a.stageStart=cacheTurn; a.lastProgress=cacheTurn; a.state=state; }
        if(count>a.units || distance<a.distance) a.lastProgress=cacheTurn;
        a.turn=cacheTurn; a.units=count; a.distance=distance;
        const bool stalled=cacheTurn-a.lastProgress>=Setting("AIAssemblyStallReviewTurns",12);
        CvStackingDiagnostics::Record(1,operation->GetOwner(),"OPERATION_ASSEMBLY","operation=%d state=%d stageAge=%d idle=%d units=%d farthest=%d recover=%d",operation->GetID(),state,cacheTurn-a.stageStart,cacheTurn-a.lastProgress,count,distance,stalled);
        if(stalled) for(CvUnit* u=army->GetFirstUnit();u;u=army->GetNextUnit(u)) DelayRecruitment(u,operation->GetTargetPlot());
        return stalled;
    }
    bool CanStartAnotherOperation(PlayerTypes owner,DomainTypes domain)
    {
        if (!Enabled(owner)) return true;
        CvPlayer& player=GET_PLAYER(owner);
        if (player.GetNumOffensiveOperations(domain)>=Setting("AIOffensiveOperationsPerDomain",2)) return false;
        int available=0,loop=0;
        for(CvUnit* u=player.firstUnit(&loop);u;u=player.nextUnit(&loop))
        {
            if(!Eligible(u,owner,domain) || u->shouldHeal(false) || u->IsCoveringFriendlyCivilian() || u->getArmyID()!=-1 ||
                u->GetCurrHitPoints()*100<u->GetMaxHitPoints()*GD_INT_GET(AI_OPERATIONAL_PERCENT_HEALTH_FOR_OPERATION) ||
                !u->canUseForAIOperation()) continue;
            if(++available>=Setting("AIOffensiveReserveMinimumUnits",4)) return true;
        }
        return false;
    }
    bool TryReinforceRearUnit(CvUnit* unit)
    {
        if(!unit || !Enabled(unit->getOwner()) || !unit->canUseNow() || unit->getArmyID()!=-1 ||
            unit->getDomainType()==DOMAIN_AIR || !unit->IsCombatUnit() || unit->isCargo() || unit->isEmbarked() ||
            unit->shouldHeal(false) || unit->IsCoveringFriendlyCivilian() || RetainCityUnit(unit)) return false;
        CvPlayer& player=GET_PLAYER(unit->getOwner());
        if(!player.IsAtWarAnyMajor() && !player.IsAtWarAnyMinor()) return false;
        if(!unit->canUseForAIOperation()) return false; // includes contested citadels and nearby enemy contact
        Refresh();
        if(transfersThisTurn[player.GetID()]>=Setting("AIReinforcementUnitsPerTurn",8) || unit->GetDanger()>0) return false;
        std::vector<Demand> demands;
        int loop=0;
        for(CvCity* city=player.firstCity(&loop);city;city=player.nextCity(&loop))
        {
            const CityDefense a=AssessCity(city);
            const int threat=unit->getDomainType()==DOMAIN_SEA?a.seaStrength:a.landStrength;
            int localStrength=0;
            for(int i=0;i<RING2_PLOTS;++i)
            {
                const CvPlot* p=iterateRingPlots(city->plot(),i);
                if(!p) continue;
                for(int j=0;j<p->getNumUnits();++j)
                { const CvUnit* defender=p->getUnitByIndex(j); if(Eligible(defender,player.GetID(),unit->getDomainType())) localStrength+=UnitStrength(defender); }
            }
            // A field unit next to a threatened city is part of its defense too.
            if(plotDistance(*unit->plot(),*city->plot())<=2 && threat>localStrength-UnitStrength(unit)) return false;
            if(threat>localStrength) demands.push_back(Demand(city->plot()->GetPlotIndex(),Setting("AIReinforcementDefensePriority",300),threat-localStrength,-1,unit->getDomainType()));
        }
        for(CvArmyAI* army=player.firstArmyAI(&loop);army;army=player.nextArmyAI(&loop))
        {
            CvAIOperation* op=player.getAIOperation(army->GetOperationID());
            if(!op || !op->IsOffensive() || op->GetEnemy()==NO_PLAYER || !player.IsAtWarWith(op->GetEnemy()) ||
                op->GetOperationState()==AI_OPERATION_STATE_ABORTED || op->GetOperationState()==AI_OPERATION_STATE_SUCCESSFUL_FINISH ||
                army->GetDomainType()!=unit->getDomainType()) continue;
            CvPlot* staging=army->GetArmyAIState()==ARMYAISTATE_MOVING_TO_DESTINATION?army->GetCenterOfMass(true):op->GetMusterPlot();
            if(staging) demands.push_back(Demand(staging->GetPlotIndex(),Setting("AIReinforcementAttackPriority",200),
                max(1,(int)army->GetNumFormationEntries()-(int)army->GetNumSlotsFilled())*UnitStrength(unit),op->GetID(),unit->getDomainType()));
        }
        std::stable_sort(demands.begin(),demands.end());
        int bestScore=INT_MIN; CvPlot* best=NULL; int bestOperation=-1,bestETA=INT_MAX;
        const Key key(player.GetID(),unit->GetID());
        const std::map<Key,Transfer>::const_iterator commitment=transfers.find(key);
        const int horizon=Setting("AIReinforcementMaximumTurns",12);
        for(size_t i=0;i<demands.size() && i<(size_t)Setting("AIReinforcementMaximumTargets",8);++i)
        {
            const Demand& d=demands[i]; CvPlot* target=GC.getMap().plotByIndexUnchecked(d.plot);
            if(!target || plotDistance(*unit->plot(),*target)<=2 || RecruitmentBlocked(unit,target)) continue;
            if(pathQueries[player.GetID()]>=Setting("AIReinforcementPathQueriesPerTurn",32)) break;
            ++pathQueries[player.GetID()];
            const int flags=CvUnit::MOVEFLAG_APPROX_TARGET_RING2|CvUnit::MOVEFLAG_APPROX_TARGET_NATIVE_DOMAIN|CvUnit::MOVEFLAG_NO_EMBARK|CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER;
            const int eta=unit->TurnsToReachTarget(target,flags,horizon);
            if(eta==INT_MAX || eta>horizon)
            {
                CvStackingDiagnostics::Record(2,player.GetID(),"REINFORCEMENT","unit=%d goal=%d reason=no_path_within_horizon",unit->GetID(),d.plot);
                continue;
            }
            int inbound=0;
            for(std::map<Key,Transfer>::const_iterator t=transfers.begin();t!=transfers.end();++t)
                if(t->first.first==player.GetID() && t->first!=key && t->second.target==d.plot)
                { const CvUnit* other=player.getUnit(t->first.second); if(other && !other->isDelayedDeath() && other->getArmyID()==-1 && other->getDomainType()==d.domain && plotDistance(*other->plot(),*target)>2) inbound+=UnitStrength(other); }
            if(inbound>=d.strength) continue;
            const int score=CvStackingAIPolicy::ScoreDemand(d.priority,max(0,d.strength-inbound),eta,Setting("AIReinforcementTravelWeight",15),
                commitment!=transfers.end() && commitment->second.target==d.plot,Setting("AIReassignmentContinuityBonus",40));
            if(score>bestScore) { bestScore=score; best=target; bestOperation=d.operation; bestETA=eta; }
        }
        if(!best) return false;
        const int flags=CvUnit::MOVEFLAG_APPROX_TARGET_RING2|CvUnit::MOVEFLAG_APPROX_TARGET_NATIVE_DOMAIN|CvUnit::MOVEFLAG_NO_EMBARK|CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER;
        if(!unit->GeneratePath(best,flags,horizon))
        {
            CvStackingDiagnostics::Record(2,player.GetID(),"REINFORCEMENT","unit=%d goal=%d reason=path_changed",unit->GetID(),best->GetPlotIndex());
            return false;
        }
        CvPlot* end=unit->GetPathEndFirstTurnPlot();
        if(!end || end==unit->plot())
        {
            CvStackingDiagnostics::Record(2,player.GetID(),"REINFORCEMENT","unit=%d goal=%d reason=no_legal_endpoint",unit->GetID(),best->GetPlotIndex());
            return false;
        }
        const int danger=unit->GetDanger(end);
        if(danger>0) // strategic transfer is not permission to start an unsupported tactical attack
        {
            CvStackingDiagnostics::Record(2,player.GetID(),"REINFORCEMENT","unit=%d goal=%d endpoint=%d reason=unsafe_endpoint danger=%d",unit->GetID(),best->GetPlotIndex(),end->GetPlotIndex(),danger);
            return false;
        }
        const int from=unit->plot()->GetPlotIndex();
        const int unitID=unit->GetID();
        unit->PushMission(CvTypes::getMISSION_MOVE_TO(),best->getX(),best->getY(),flags,false,false,MISSIONAI_TACTMOVE);
        unit=player.getUnit(unitID);
        if(!unit || unit->isDelayedDeath())
        {
            CvStackingDiagnostics::Record(1,player.GetID(),"REINFORCEMENT","unit=%d from=%d goal=%d status=removed_during_move",unitID,from,best->GetPlotIndex());
            return true;
        }
        const int after=unit->plot()->GetPlotIndex();
        if(after==from)
        {
            CvStackingDiagnostics::Record(2,player.GetID(),"REINFORCEMENT","unit=%d from=%d goal=%d status=no_progress",unitID,from,best->GetPlotIndex());
            return false;
        }
        Transfer& transfer=transfers[key]; transfer.turn=cacheTurn; transfer.target=best->GetPlotIndex();
        ++transfersThisTurn[player.GetID()];
        CvStackingDiagnostics::Record(1,player.GetID(),"REINFORCEMENT","unit=%d from=%d after=%d goal=%d operation=%d eta=%d score=%d status=%s",unit->GetID(),from,after,best->GetPlotIndex(),bestOperation,bestETA,bestScore,plotDistance(*unit->plot(),*best)<=2?"arrived":"moving");
        unit->SetTurnProcessed(true);
        return true;
    }
}
