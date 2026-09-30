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
    struct Objective
    {
        int enemy, operation, staging, refreshed, created, coreUnits, coreStrength, captureTurn, captureID, noCaptureSince;
        int captureOwner, captureEta, captureProgress, capturePlot, captureDistance;
        CvStackingOffensiveAI::AssaultPlan assault;
        int assaultTurn, phaseSince, phaseLogged;
        int staffTurn, staffUnits, staffSiege, staffRanged, staffCapture;
        int lastUsefulTurn, lowestHP;
        bool captureKnown;
        Objective():enemy(-1),operation(-1),staging(-1),refreshed(-1),created(-1),coreUnits(0),coreStrength(0),
            captureTurn(-1),captureID(-1),noCaptureSince(-1),captureOwner(-1),captureEta(INT_MAX),captureProgress(-1),capturePlot(-1),captureDistance(INT_MAX),
            assaultTurn(-1),phaseSince(-1),phaseLogged(-1),staffTurn(-1),staffUnits(0),staffSiege(0),staffRanged(0),staffCapture(0),lastUsefulTurn(-1),lowestHP(INT_MAX),captureKnown(false){}
    };
    struct Commitment
    {
        ObjectiveKey goal; int turn, lastProgress, plot, eta, bestDistance;
        bool arrived, capturer, assembly;
        Commitment():turn(-1),lastProgress(-1),plot(-1),eta(INT_MAX),bestDistance(INT_MAX),arrived(false),capturer(false),assembly(false){}
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
    std::map<ObjectiveKey,Objective> objectives;
    std::map<Key,Commitment> commitments;
    std::map<ObjectiveKey,Failure> failures;
    std::map<Key,March> marches;
    std::map<Key,std::pair<int,int> > captureRetries; // unit -> target, expiry
    std::map<Key,ProductionClaim> production;
    std::map<Key,int> assemblyHolds;
    int currentTurn=-1, synced[MAX_PLAYERS], captureQueries[MAX_PLAYERS], extraBatches[MAX_PLAYERS], assaultQueries[MAX_PLAYERS];
    bool shuttingDown=false;
    int Setting(const char* name,int value) { return CvStacking::GetInt(name,value); }
    bool Live(CvAIOperation* op)
    { return op && op->GetOperationState()!=AI_OPERATION_STATE_ABORTED && op->GetOperationState()!=AI_OPERATION_STATE_SUCCESSFUL_FINISH; }
    bool Usable(const CvUnit* u)
    { return u && u->plot() && u->GetCurrHitPoints()>0 && u->IsCombatUnit() && !u->IsStackingUnit() && !u->isCargo() && !u->isDelayedDeath() && u->getDomainType()!=DOMAIN_AIR; }
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
    void Refresh()
    {
        if(shuttingDown) return;
        const int turn=GC.getGame().getGameTurn();
        if(currentTurn==turn) return;
        currentTurn=turn;
        assemblyHolds.clear();
        for(int i=0;i<MAX_PLAYERS;++i) { synced[i]=-1; captureQueries[i]=0; extraBatches[i]=0; assaultQueries[i]=0; }
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
                CvStackingDiagnostics::Record(1,(PlayerTypes)i->first.first,"OFFENSIVE_PRODUCTION","city=%d target=%d unitType=%d action=cancel reason=%s",i->first.second,i->second.goal.target,i->second.unit,valid?"stalled":"queue_or_objective_changed");
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
                commitments.erase(i++);
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
    int ProductionChoice(const CvCity* city,UnitTypes unit,ObjectiveKey& chosen)
    {
        const PlayerTypes owner=city->getOwner(); CvPlayer& player=GET_PLAYER(owner);
        const CvUnitEntry* entry=GC.getUnitInfo(unit);
        if(!entry || (entry->GetCombat()<=0 && entry->GetRangedCombat()<=0) || entry->GetDomainType()==DOMAIN_AIR ||
            city->getProductionTurnsLeft(unit,0)>Setting("AIOffensiveProductionMaximumTurns",12)) return 0;
        const Key ownCity(owner,city->GetID());
        int best=0;
        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();i!=objectives.end();++i)
        {
            const ObjectiveKey& key=i->first; Objective& o=i->second;
            if(key.owner!=owner || key.domain!=entry->GetDomainType()) continue;
            CvPlot* target=GC.getMap().plotByIndexUnchecked(key.target);
            if(!target || !target->isCity() || target->getOwner()!=o.enemy ||
                CvStackingOffensiveAI::RouteBlocked(owner,target,key.domain==DOMAIN_SEA) ||
                plotDistance(*city->plot(),*target)>Setting("AIReinforcementMaximumTurns",12)*max(1,entry->GetMoves())) continue;
            if(o.staffTurn!=currentTurn)
            {
                o.staffTurn=currentTurn;o.staffUnits=o.staffSiege=o.staffRanged=o.staffCapture=0;
                int loop=0;
                for(CvUnit* u=player.firstUnit(&loop);u;u=player.nextUnit(&loop))
                {
                    if(!Matches(u,key,o) || u->GetCurrHitPoints()*100<u->GetMaxHitPoints()*Setting("AIAssaultHealthyPercent",65)) continue;
                    ++o.staffUnits;o.staffSiege+=key.domain==DOMAIN_SEA?u->IsCanAttackRanged():CvStackingOffensiveAI::IsSiegeUnit(u);
                    o.staffRanged+=u->IsCanAttackRanged() && !CvStackingOffensiveAI::IsSiegeUnit(u);
                    o.staffCapture+=CvStackingOffensiveAI::CanCapture(u,target);
                }
            }
            int count=o.staffUnits,siege=o.staffSiege,ranged=o.staffRanged,capture=o.staffCapture,queued=0;
            for(std::map<Key,ProductionClaim>::const_iterator p=production.begin();p!=production.end();++p)
            {
                if(p->first==ownCity || !(p->second.goal==key)) continue;
                const CvUnitEntry* pending=GC.getUnitInfo((UnitTypes)p->second.unit);
                if(!pending) continue;
                ++queued;++count; siege+=key.domain==DOMAIN_SEA?EntryRanged(pending):EntrySiege(pending);
                ranged+=EntryRanged(pending) && !EntrySiege(pending);capture+=EntryCapture(pending);
            }
            int cityLoop=0;
            for(CvCity* factory=player.firstCity(&cityLoop);factory;factory=player.nextCity(&cityLoop))
            {
                // Existing formation promises remain owned by VP. Credit their
                // actual queued role without creating another support claim.
                if(factory==city || !factory->IsBuildingUnitForOperation() || factory->GetUnitProductionOperation()!=o.operation) continue;
                const CvUnitEntry* pending=GC.getUnitInfo(factory->getProductionUnit());
                if(!pending || pending->GetDomainType()!=key.domain) continue;
                ++queued;++count;siege+=key.domain==DOMAIN_SEA?EntryRanged(pending):EntrySiege(pending);
                ranged+=EntryRanged(pending) && !EntrySiege(pending);capture+=EntryCapture(pending);
            }
            if(queued>=Setting("AIOffensiveProductionMaximumUnits",4) || count>=Setting("AIOffensiveSupportMaximumUnits",32)) continue;
            const int desired=CvStackingOffensiveAI::DesiredAssaultUnits(owner,target->getPlotCity(),(DomainTypes)key.domain)+Setting("AIOffensiveSupportReserveUnits",4);
            const int desiredSiege=CvStackingOffensiveAI::DesiredSiegeUnits(owner,target->getPlotCity(),(DomainTypes)key.domain);
            const bool neededSiege=desiredSiege>0 && siege<desiredSiege+Setting("AIOffensiveProductionSiegeReserves",2);
            const bool neededCapture=capture<Setting("AIOffensiveSupportMinimumCapturers",2);
            const bool neededRanged=ranged<Setting("AIOffensiveSupportMinimumRanged",2);
            const bool siegeRole=key.domain==DOMAIN_SEA?EntryRanged(entry):EntrySiege(entry);
            const bool role=(neededSiege && siegeRole) || (neededCapture && EntryCapture(entry)) ||
                (neededRanged && EntryRanged(entry) && !EntrySiege(entry));
            if(!role && (count>=desired || neededSiege || neededCapture)) continue;
            const int score=Setting("AIOffensiveProductionPriority",400)+(role?Setting("AIOffensiveProductionRolePriority",400):0)-
                plotDistance(*city->plot(),*target)*Setting("AIReinforcementTravelWeight",15);
            if(score>best) { best=score;chosen=key; }
        }
        return max(0,best);
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
                commitments.erase(unitKey);
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
            if(!firing) { ++result.inbound;continue; }
            int retaliation=0,garrison=0;
            const int damage=TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(city,u,firing,retaliation,garrison);
            if(damage<=0 || retaliation>=u->GetCurrHitPoints()) continue;
            ++result.readyUnits; strength+=CvStackingAI::UnitStrength(u);
            firstArrival=min(firstArrival,eta);lastArrival=max(lastArrival,eta);
            result.siege+=domain==DOMAIN_SEA?u->IsCanAttackRanged():IsSiegeUnit(u);
            result.ranged+=u->IsCanAttackRanged();
            result.capturers+=CanCapture(u,target);
            result.cityDamage+=damage;
        }
        const int hp=max(1,city->GetMaxHitPoints()-city->getDamage());
        if(hp<o.lowestHP || result.readyUnits>o.assault.readyUnits) o.lastUsefulTurn=currentTurn;
        o.lowestHP=min(o.lowestHP,hp);
        int healing=city->IsBlockadedWaterAndLand()?0:GD_INT_GET(CITY_HIT_POINTS_HEALED_PER_TURN);
        if(MOD_BALANCE_VP) healing+=city->getPopulation();
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
        result.reason=immediateCapture?0:!captureSoon?1:!roles?2:!damageEnough?3:!cohesive?6:!result.ready?4:0;
        // Committed waves remain committed while their core and essential roles
        // are still useful. Do not demand that replacements already be present.
        if(previousPhase==1 && !result.ready && roles && damageEnough &&
            result.readyUnits>=Setting("AIAssaultMinimumReadyUnits",4)) result.ready=true;
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
            CvStackingDiagnostics::Record(1,owner,"ASSAULT_PLAN","target=%d domain=%d phase=%d reason=%d stage=%d ready=%d desired=%d siege=%d desiredSiege=%d ranged=%d capturers=%d inbound=%d damage=%d heal=%d hp=%d enemyStrength=%d captureUnit=%d captureOwner=%d captureEta=%d gatherAge=%d pathQueries=%d firstArrival=%d lastArrival=%d; ready is a route-and-damage forecast, not an executed attack",
                key.target,domain,result.phase,result.reason,result.staging,result.readyUnits,result.desiredUnits,result.siege,result.desiredSiege,
                result.ranged,result.capturers,result.inbound,result.cityDamage,healing,hp,result.enemyStrength,o.captureID,o.captureOwner,o.captureEta,currentTurn-o.phaseSince,assaultQueries[owner],firstArrival==INT_MAX?-1:firstArrival,lastArrival);
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
    bool StageUnit(CvUnit* unit,const CvPlot* cityTarget)
    {
        if(!Usable(unit) || !unit->canUseNow() || !cityTarget || !cityTarget->isCity()) return false;
        const PlayerTypes owner=unit->getOwner();CvPlayer& player=GET_PLAYER(owner);
        const AssaultPlan plan=AssessAssault(owner,cityTarget->getPlotCity(),unit->getDomainType());
        if(plan.ready || plan.staging<0) return false;
        CvPlot* stage=GC.getMap().plotByIndexUnchecked(plan.staging);
        const std::vector<const CvUnit*> alone(1,unit);const SUnitIDValueContainer noDamage;
        const int currentDanger=player.GetDangerPlots()->GetStackDanger(*unit->plot(),unit,alone,noDamage,noDamage);
        const int dangerLimit=unit->GetCurrHitPoints()*Setting("AIAssaultStageDangerPercent",0)/100;
        if(currentDanger==0 && unit->IsCanAttackRanged() && unit->canRangeStrikeAt(cityTarget->getX(),cityTarget->getY()) &&
            ContinueSiege(owner,cityTarget->getPlotCity()))
        {
            const int id=unit->GetID();
            unit->PushMission(CvTypes::getMISSION_RANGE_ATTACK(),cityTarget->getX(),cityTarget->getY(),0,false,false,MISSIONAI_TACTMOVE);
            unit=player.getUnit(id);
            if(unit && !unit->isDelayedDeath() && !unit->canUseNow()) unit->SetTurnProcessed(true);
            return true;
        }
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
            unit->PushMission(CvTypes::getMISSION_MOVE_TO(),p->getX(),p->getY(),flags,false,false,MISSIONAI_TACTMOVE);
            unit=player.getUnit(id);
            if(!unit || unit->isDelayedDeath()) return true;
            if(unit->plot()->GetPlotIndex()==from) continue;
            RecordTransfer(unit,cityTarget->GetPlotIndex(),-1,plotDistance(*unit->plot(),*cityTarget)/max(1,unit->baseMoves(false)));
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
            return !plan.ready;
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
    bool AllowCityAttack(const CvUnit* unit,CvCity* city,const CvPlot* firing,bool capture)
    {
        if(!unit || !city || !firing) return false;
        if(!Enabled(unit->getOwner()) || Setting("AIAssaultCoordinationEnabled",1)==0 || capture) return true;
        const AssaultPlan plan=AssessAssault(unit->getOwner(),city,unit->getDomainType());
        if(plan.ready) return true;
        if(!unit->IsCanAttackRanged()) return false;
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
                if(plan.phase==2 && currentTurn-i->second.lastUsefulTurn>=Setting("AIAssaultAbandonTurns",24)) stale.push_back(i->first);
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
    int ProductionBonus(const CvCity* city,UnitTypes unit)
    {
        if(!city || !Enabled(city->getOwner()) || Setting("AIOffensiveProductionMaximumUnits",4)==0) return 0;
        Sync(city->getOwner()); ObjectiveKey chosen;
        return ProductionChoice(city,unit,chosen);
    }
    void RecordProduction(CvCity* city,UnitTypes unit)
    {
        if(!city || !Enabled(city->getOwner()) || city->IsBuildingUnitForOperation() || city->getProductionUnit()!=unit ||
            Setting("AIOffensiveProductionMaximumUnits",4)==0) return;
        Sync(city->getOwner()); ObjectiveKey chosen;
        if(!ProductionChoice(city,unit,chosen)) return;
        ProductionClaim& claim=production[Key(city->getOwner(),city->GetID())];
        if(claim.started>=0 && claim.unit==unit && claim.goal==chosen) return;
        claim.goal=chosen; claim.unit=unit; claim.started=claim.progress=currentTurn; claim.turns=city->getProductionTurnsLeft();
        objectives[chosen].lastUsefulTurn=currentTurn;
        CvStackingDiagnostics::Record(1,city->getOwner(),"OFFENSIVE_PRODUCTION","city=%d target=%d domain=%d unitType=%d remaining=%d action=queued",city->GetID(),chosen.target,chosen.domain,unit,claim.turns);
    }
    void UnitProduced(CvCity* city,CvUnit* unit)
    {
        if(!city || !Usable(unit) || !Enabled(city->getOwner())) return;
        const Key key(city->getOwner(),city->GetID());
        std::map<Key,ProductionClaim>::iterator claim=production.find(key);
        if(claim==production.end() || claim->second.unit!=unit->getUnitType()) return;
        const ObjectiveKey goal=claim->second.goal;
        production.erase(claim); // completion must replace its pending credit exactly once
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
            for(CvUnit* u=player.firstUnit(&loop);u && force.units.size()<(size_t)Setting("AIOffensiveSupportMaximumUnits",32);u=player.nextUnit(&loop))
                if(u->getArmyID()==-1 && u->canUseNow() && !u->shouldHeal(false) && !CvStackingAI::RetainCityUnit(u) && Matches(u,i->first,i->second)) force.units.push_back(u->GetID());
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
    }
    void Reset()
    { objectives.clear(); commitments.clear(); failures.clear(); marches.clear(); captureRetries.clear(); production.clear(); assemblyHolds.clear(); currentTurn=-1; shuttingDown=false; }
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
                if(other==unit || !Matches(other,key,o)) continue;
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
            if(count+training>=maximum || (!usefulRole && count+training>=desiredCount && strength+training*mean>=desiredStrength)) continue;
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
        { commitments.erase(key); return; }
        Objective* refreshed=Touch(unit->getOwner(),goal,unit->getDomainType());
        if(!refreshed) { commitments.erase(key); return; }
        const int distance=plotDistance(*unit->plot(),*goal);
        if(c.goal.target!=target || (c.plot!=plot && distance<c.bestDistance) || eta<c.eta) c.lastProgress=currentTurn;
        if(c.goal.target!=target) { c.arrived=false; c.capturer=false; c.assembly=false; c.bestDistance=distance; }
        else c.bestDistance=min(c.bestDistance,distance);
        c.goal=ObjectiveKey(unit->getOwner(),target,unit->getDomainType()); c.turn=currentTurn; c.plot=plot; c.eta=eta;
        refreshed->refreshed=currentTurn;
        refreshed->staffTurn=-1;
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
    bool OpeningReady(CvAIOperation* op,CvArmyAI* army)
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
            if(!Usable(u) || u->getDomainType()!=army->GetDomainType() ||
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
        const int desiredSiege=KnownFortified(op->GetOwner(),target->getPlotCity())?DesiredSiegeUnits(op->GetOwner(),target->getPlotCity(),army->GetDomainType()):0;
        const bool ready=siege>=desiredSiege && CvStackingAIPolicy::OpeningReady(healthy,total,capture,ranged,strength,EnemyStrength(op->GetOwner(),target),
            Setting("AIWarOpeningMinimumUnits",4),Setting("AIWarOpeningReadyPercent",75),Setting("AIWarOpeningMinimumRanged",1),Setting("AIWarOpeningStrengthPercent",150));
        CvStackingDiagnostics::Record(1,op->GetOwner(),"WAR_READINESS","operation=%d target=%d total=%d staged=%d capture=%d ranged=%d siege=%d desiredSiege=%d strength=%d ready=%d",op->GetID(),target->GetPlotIndex(),total,healthy,capture,ranged,siege,desiredSiege,strength,ready);
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
