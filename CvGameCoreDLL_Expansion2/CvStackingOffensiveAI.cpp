#include "CvGameCoreDLLPCH.h"
#include "CvStackingOffensiveAI.h"
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
#include "CvTacticalAI.h"
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
    struct Objective
    {
        int enemy, operation, staging, refreshed, created, coreUnits, coreStrength, captureTurn, captureID, noCaptureSince;
        bool captureKnown;
        Objective():enemy(-1),operation(-1),staging(-1),refreshed(-1),created(-1),coreUnits(0),coreStrength(0),
            captureTurn(-1),captureID(-1),noCaptureSince(-1),captureKnown(false){}
    };
    struct Commitment
    {
        ObjectiveKey goal; int turn, lastProgress, plot, eta;
        Commitment():turn(-1),lastProgress(-1),plot(-1),eta(INT_MAX){}
    };
    struct March
    {
        int turn, lastProgress, distance, target;
        March():turn(-1),lastProgress(-1),distance(INT_MAX),target(-1){}
    };
    struct Failure { int until, enemy; Failure():until(-1),enemy(-1){} };
    std::map<ObjectiveKey,Objective> objectives;
    std::map<Key,Commitment> commitments;
    std::map<ObjectiveKey,Failure> failures;
    std::map<Key,March> marches;
    int currentTurn=-1, synced[MAX_PLAYERS], captureQueries[MAX_PLAYERS];
    int Setting(const char* name,int value) { return CvStacking::GetInt(name,value); }
    bool Live(CvAIOperation* op)
    { return op && op->GetOperationState()!=AI_OPERATION_STATE_ABORTED && op->GetOperationState()!=AI_OPERATION_STATE_SUCCESSFUL_FINISH; }
    bool Usable(const CvUnit* u)
    { return u && u->IsCombatUnit() && !u->IsStackingUnit() && !u->isCargo() && !u->isDelayedDeath() && u->getDomainType()!=DOMAIN_AIR; }
    void Refresh()
    {
        const int turn=GC.getGame().getGameTurn();
        if(currentTurn==turn) return;
        currentTurn=turn;
        for(int i=0;i<MAX_PLAYERS;++i) { synced[i]=-1; captureQueries[i]=0; }
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();)
        {
            CvPlot* p=GC.getMap().plotByIndexUnchecked(i->first.target);
            CvAIOperation* op=GET_PLAYER((PlayerTypes)i->first.owner).getAIOperation(i->second.operation);
            const bool active=Live(op) && CvStackingOffensiveAI::CityTarget(op)==p;
            // City ownership is already public game information. Never read hidden occupants.
            const bool invalid=!p || !p->isCity() || p->getOwner()!=i->second.enemy || (op && CvStackingOffensiveAI::CityTarget(op)!=p) ||
                (!GET_PLAYER((PlayerTypes)i->first.owner).IsAtWarWith((PlayerTypes)i->second.enemy) && !active);
            if(invalid || (!active && turn-i->second.refreshed>Setting("AIOffensiveSupportMemoryTurns",12)))
            {
                CvStackingDiagnostics::Record(1,(PlayerTypes)i->first.owner,"OFFENSIVE_OBJECTIVE","target=%d domain=%d action=expire",i->first.target,i->first.domain);
                objectives.erase(i++);
            }
            else ++i;
        }
        for(std::map<Key,Commitment>::iterator i=commitments.begin();i!=commitments.end();)
        {
            const CvUnit* u=GET_PLAYER((PlayerTypes)i->first.first).getUnit(i->first.second);
            if(!Usable(u) || objectives.find(i->second.goal)==objectives.end() ||
                turn-i->second.lastProgress>Setting("AIOffensiveSupportStallTurns",5))
            {
                CvStackingDiagnostics::Record(1,(PlayerTypes)i->first.first,"OFFENSIVE_SUPPORT","unit=%d target=%d action=release_stale",i->first.second,i->second.goal.target);
                commitments.erase(i++);
            }
            else ++i;
        }
        for(std::map<ObjectiveKey,Failure>::iterator i=failures.begin();i!=failures.end();)
            if(i->second.until<turn) failures.erase(i++); else ++i;
        for(std::map<Key,March>::iterator i=marches.begin();i!=marches.end();)
            if(turn-i->second.turn>2) marches.erase(i++); else ++i;
    }
    Objective* Touch(PlayerTypes owner,CvPlot* target,DomainTypes domain)
    {
        if(!target || !target->isCity()) return NULL;
        Refresh(); const ObjectiveKey key(owner,target->GetPlotIndex(),domain);
        std::map<ObjectiveKey,Objective>::iterator found=objectives.find(key);
        if(found==objectives.end())
        {
            int count=0;
            for(std::map<ObjectiveKey,Objective>::const_iterator i=objectives.begin();i!=objectives.end();++i) count+=i->first.owner==owner;
            if(count>=Setting("AIOffensiveSupportMaximumObjectives",8)) return NULL;
        }
        Objective& o=objectives[key];
        if(o.created<0 || o.enemy!=target->getOwner()) { o=Objective(); o.created=currentTurn; }
        o.enemy=target->getOwner(); o.refreshed=currentTurn;
        if(o.staging<0) o.staging=target->GetPlotIndex();
        return &o;
    }
    void Sync(PlayerTypes owner)
    {
        Refresh(); if(synced[owner]==currentTurn) return;
        synced[owner]=currentTurn;
        CvPlayer& player=GET_PLAYER(owner);
        for(size_t i=0;i<player.getNumAIOperations();++i)
            CvStackingOffensiveAI::ObserveOperation(player.getAIOperationByIndex(i));
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
    void CapturePlan(PlayerTypes owner,CvPlot* target,Objective& o)
    {
        if(o.captureTurn==currentTurn) return;
        o.captureTurn=currentTurn; o.captureID=-1; o.captureKnown=true;
        const int horizon=Setting("AICapturePlanMaximumTurns",6);
        CvPlayer& player=GET_PLAYER(owner);
        int loop=0;
        for(CvUnit* u=player.firstUnit(&loop);u;u=player.nextUnit(&loop))
        {
            if(!CvStackingOffensiveAI::CanCapture(u,target) || CvStackingAI::RetainCityUnit(u) || u->IsCoveringFriendlyCivilian()) continue;
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
            if(!approach || plotDistance(*approach,*target)>1 || !u->isNativeDomain(approach)) continue;
            int retaliation=0,garrison=0;
            TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(target->getPlotCity(),u,approach,retaliation,garrison,false,0,
                max(0,target->getPlotCity()->GetMaxHitPoints()-target->getPlotCity()->getDamage()-1));
            const bool survives=retaliation<u->GetCurrHitPoints();
            CvStackingDiagnostics::Record(1,owner,"CAPTURE_CANDIDATE","target=%d unit=%d domain=%d eta=%d approach=%d retaliation=%d hp=%d viable=%d",target->GetPlotIndex(),u->GetID(),u->getDomainType(),eta,approach->GetPlotIndex(),retaliation,u->GetCurrHitPoints(),survives);
            if(survives) { o.captureID=u->GetID(); break; }
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
                    CvStackingDiagnostics::Record(1,owner,"CAPTURE_CANDIDATE","target=%d unit=%d unitOwner=%d reason=visible_adjacent_ally viable=1",target->GetPlotIndex(),ally->GetID(),ally->getOwner());
                    break;
                }
            }
        if(o.captureID>=0) o.noCaptureSince=-1;
        else if(o.captureKnown && o.noCaptureSince<0) o.noCaptureSince=currentTurn;
        CvStackingDiagnostics::Record(1,owner,"CAPTURE_PLAN","target=%d unit=%d known=%d missingTurns=%d queries=%d",target->GetPlotIndex(),o.captureID,o.captureKnown,o.noCaptureSince<0?0:currentTurn-o.noCaptureSince,captureQueries[owner]);
    }
}

namespace CvStackingOffensiveAI
{
    bool Enabled(PlayerTypes owner)
    { return CvStackingAI::Enabled(owner) && Setting("AIOffensiveSupportEnabled",1)!=0; }
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
        // VP's naval/combined operation stores the adjacent water tile, not the city.
        if(!op->IsNavalOperation()) return NULL;
        for(int i=1;i<RING1_PLOTS;++i)
        {
            CvPlot* p=iterateRingPlots(waypoint,i);
            if(p && p->isCity() && p->getOwner()==op->GetEnemy()) return p;
        }
        return NULL;
    }
    void Handoff(CvAIOperation* op)
    {
        if(!IsCityAttack(op) || !Enabled(op->GetOwner())) return;
        ObserveOperation(op);
        CvPlot* target=CityTarget(op); CvArmyAI* army=op->GetArmy(0);
        if(!target || !army) return;
        for(CvUnit* u=army->GetFirstUnit();u;u=army->GetNextUnit(u))
        {
            if(!Usable(u)) continue;
            // Keep roles/domains distinct even when a combined fleet releases land troops.
            Objective* o=Touch(op->GetOwner(),target,u->getDomainType());
            if(!o) continue;
            o->operation=op->GetID();
            Commitment& c=commitments[Key(op->GetOwner(),u->GetID())];
            c.goal=ObjectiveKey(op->GetOwner(),target->GetPlotIndex(),u->getDomainType());
            c.turn=c.lastProgress=currentTurn; c.plot=u->plot()->GetPlotIndex(); c.eta=0;
            CvStackingDiagnostics::Record(1,op->GetOwner(),"OFFENSIVE_SUPPORT","unit=%d target=%d operation=%d action=tactical_handoff",u->GetID(),target->GetPlotIndex(),op->GetID());
        }
    }
    void Reset()
    { objectives.clear(); commitments.clear(); failures.clear(); marches.clear(); currentTurn=-1; }
    bool CanCapture(const CvUnit* u,const CvPlot* city)
    {
        return Usable(u) && city && city->isCity() && u->IsCanAttackWithMove() && !u->isNoCapture() &&
            (u->getDomainType()==DOMAIN_LAND || (u->getDomainType()==DOMAIN_SEA && city->isCoastalLand())) &&
            u->GetCurrHitPoints()*100>=u->GetMaxHitPoints()*Setting("AICapturePlanMinimumHPPercent",60);
    }
    void ObserveOperation(CvAIOperation* op)
    {
        if(!IsCityAttack(op) || !Enabled(op->GetOwner()) || !Live(op)) return;
        CvArmyAI* army=op->GetArmy(0); CvPlot* target=CityTarget(op);
        if(!army || !target || !target->isCity()) return;
        Objective* o=Touch(op->GetOwner(),target,army->GetDomainType());
        if(!o) return;
        // Prefer the oldest still-active operation, preventing duplicate force credit.
        CvAIOperation* old=GET_PLAYER(op->GetOwner()).getAIOperation(o->operation);
        if(Live(old) && old->GetID()!=op->GetID() && old->GetTurnStarted()<=op->GetTurnStarted()) return;
        o->operation=op->GetID();
        CvPlot* stage=army->GetArmyAIState()==ARMYAISTATE_MOVING_TO_DESTINATION?army->GetCenterOfMass(true):op->GetMusterPlot();
        if(stage) o->staging=stage->GetPlotIndex();
        int count=0,strength=0;
        for(CvUnit* u=army->GetFirstUnit();u;u=army->GetNextUnit(u))
            if(Usable(u) && u->getDomainType()==army->GetDomainType()) { ++count; strength+=CvStackingAI::UnitStrength(u); }
        o->coreUnits=max(o->coreUnits,count); o->coreStrength=max(o->coreStrength,strength);
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
        return o!=objectives.end() && goal && goal->isCity() && goal->getOwner()==o->second.enemy &&
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
            if(!active) o.staging=key.target;
            const std::map<Key,Commitment>::const_iterator own=commitments.find(Key(owner,unit->GetID()));
            if(own!=commitments.end() && !(own->second.goal==key)) continue;
            int count=0,strength=0,capturers=0,ranged=0,inbound=0,loop=0;
            for(CvUnit* other=player.firstUnit(&loop);other;other=player.nextUnit(&loop))
            {
                if(other==unit || !Matches(other,key,o)) continue;
                ++count; strength+=CvStackingAI::UnitStrength(other);
                capturers+=CanCapture(other,target); ranged+=other->IsCanAttackRanged();
                inbound+=plotDistance(*other->plot(),*target)>Setting("AIOffensiveSupportLocalRadius",4);
            }
            const int mean=max(1,o.coreUnits?o.coreStrength/o.coreUnits:CvStackingAI::UnitStrength(unit));
            const int training=active?(int)op->GetNumUnitsCommittedToBeBuilt():0;
            const int maximum=Setting("AIOffensiveSupportMaximumUnits",18);
            const int desiredCount=min(maximum,max(Setting("AIOffensiveSupportMinimumUnits",6),o.coreUnits+Setting("AIOffensiveSupportReserveUnits",2)));
            CvPlot* stage=GC.getMap().plotByIndexUnchecked(o.staging);
            const int lead=stage?min(Setting("AIReinforcementMaximumTurns",12),plotDistance(*stage,*target)/max(1,unit->baseMoves(false))):0;
            const int reserve=min(Setting("AIOffensiveSupportMaximumReservePercent",60),Setting("AIOffensiveSupportReservePercent",25)+lead*Setting("AIOffensiveSupportTravelReservePercentPerTurn",2));
            const int desiredStrength=max(o.coreStrength,EnemyStrength(owner,target)*Setting("AIOffensiveSupportStrengthPercent",150)/100)*(100+reserve)/100;
            if(player.IsAtWarWith((PlayerTypes)o.enemy) && target->isVisible(player.getTeam())) CapturePlan(owner,target,o);
            const bool missingCapture=capturers<Setting("AIOffensiveSupportMinimumCapturers",2) ||
                (o.captureKnown && o.captureID<0);
            const bool missingRanged=ranged<Setting("AIOffensiveSupportMinimumRanged",2);
            const bool usefulRole=(missingCapture && CanCapture(unit,target)) || (missingRanged && unit->IsCanAttackRanged());
            if(count+training>=maximum || (!usefulRole && count+training>=desiredCount && strength+training*mean>=desiredStrength)) continue;
            // Do not send a third ranged reserve while a depleted siege specifically needs capture support.
            if(missingCapture && !CanCapture(unit,target) && count+training>=desiredCount) continue;
            const int need=max(mean,max((desiredCount-count-training)*mean,desiredStrength-strength-training*mean));
            const int priority=Setting("AIReinforcementAttackPriority",200)+(usefulRole?Setting("AIOffensiveSupportRolePriority",80):0);
            result.push_back(Demand(o.staging,key.target,active?o.operation:-1,need,priority));
            CvStackingDiagnostics::Record(2,owner,"OFFENSIVE_DEMAND","target=%d unit=%d domain=%d assigned=%d inbound=%d training=%d strength=%d desired=%d desiredUnits=%d capture=%d ranged=%d need=%d",key.target,unit->GetID(),key.domain,count,inbound,training,strength,desiredStrength,desiredCount,capturers,ranged,need);
        }
    }
    void RecordTransfer(CvUnit* unit,int target,int operation,int eta)
    {
        if(!unit || !Enabled(unit->getOwner())) return;
        Refresh(); const Key key(unit->getOwner(),unit->GetID());
        Commitment& c=commitments[key]; const int plot=unit->plot()->GetPlotIndex();
        if(c.goal.target!=target || c.plot!=plot || eta<c.eta) c.lastProgress=currentTurn;
        c.goal=ObjectiveKey(unit->getOwner(),target,unit->getDomainType()); c.turn=currentTurn; c.plot=plot; c.eta=eta;
        CvPlot* goal=GC.getMap().plotByIndexUnchecked(target);
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
        CvArmyAI* army=Live(op)?op->GetArmy(0):NULL;
        CvPlot* stage=army?army->GetCenterOfMass(true):NULL;
        if(!stage || plotDistance(*unit->plot(),*stage)>2) return false;
        const int id=unit->GetID(),owner=unit->getOwner();
        // RecruitUnit/AddUnit may upgrade/delete the unit. Never use its pointer afterwards.
        if(op->RecruitUnit(unit))
        {
            commitments.erase(key);
            CvStackingDiagnostics::Record(1,(PlayerTypes)owner,"OFFENSIVE_SUPPORT","unit=%d operation=%d action=joined_formation",id,op->GetID());
            return true;
        }
        return false;
    }
    void CancelCommitment(const CvUnit* unit)
    {
        if(!unit || !Enabled(unit->getOwner())) return;
        if(commitments.erase(Key(unit->getOwner(),unit->GetID())))
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
        if(!stage || plotDistance(*unit->plot(),*stage)>2) return false;
        // Homeland patrol runs after tactical combat: keep a safe staged reserve available
        // for next turn instead of wandering back home when the formation is still full.
        c->second.lastProgress=currentTurn;
        unit->SetTurnProcessed(true);
        CvStackingDiagnostics::Record(1,unit->getOwner(),"OFFENSIVE_SUPPORT","unit=%d target=%d operation=%d action=staged_reserve",unit->GetID(),c->second.goal.target,op->GetID());
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
    bool OpeningReady(CvAIOperation* op,CvArmyAI* army)
    {
        if(!IsCityAttack(op) || !Enabled(op->GetOwner()) || Setting("AIWarPreparationEnabled",1)==0) return true;
        if(!army || !op->GetTargetPlot()) return false;
        CvPlot* target=CityTarget(op);
        if(!target) return false;
        int total=0,healthy=0,capture=0,ranged=0,strength=0;
        const int maxTurns=Setting("AIWarOpeningMaximumTurns",3);
        for(CvUnit* u=army->GetFirstUnit();u;u=army->GetNextUnit(u))
        {
            if(!Usable(u)) continue;
            ++total;
            if(u->GetCurrHitPoints()*100<u->GetMaxHitPoints()*GD_INT_GET(AI_OPERATIONAL_PERCENT_HEALTH_FOR_OPERATION)) continue;
            // This army path permits the intended enemy only, not third-party closed borders.
            // It is a bounded potential-war distance estimate; actual transfer/capture routes use unit paths.
            const int distance=op->GetStepDistanceBetweenPlots(u->plot(),target);
            if(distance<0 || distance>maxTurns*max(1,u->baseMoves(false))+1) continue;
            ++healthy; strength+=CvStackingAI::UnitStrength(u);
            capture+=CanCapture(u,target); ranged+=u->IsCanAttackRanged();
        }
        const bool ready=CvStackingAIPolicy::OpeningReady(healthy,total,capture,ranged,strength,EnemyStrength(op->GetOwner(),target),
            Setting("AIWarOpeningMinimumUnits",4),Setting("AIWarOpeningReadyPercent",75),Setting("AIWarOpeningMinimumRanged",1),Setting("AIWarOpeningStrengthPercent",150));
        CvStackingDiagnostics::Record(1,op->GetOwner(),"WAR_READINESS","operation=%d target=%d total=%d staged=%d capture=%d ranged=%d strength=%d ready=%d",op->GetID(),target->GetPlotIndex(),total,healthy,capture,ranged,strength,ready);
        return ready;
    }
    bool ReadyToDeclare(PlayerTypes owner,PlayerTypes enemy)
    {
        if(!Enabled(owner) || Setting("AIWarPreparationEnabled",1)==0) return true;
        CvPlayer& player=GET_PLAYER(owner);
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
        const bool review=o.captureKnown && o.captureID<0 && o.noCaptureSince>=0 && currentTurn-o.noCaptureSince>=Setting("AISiegeNoCaptureReviewTurns",8) &&
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
