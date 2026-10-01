"""Pinned work-only reinforcement route/contribution stage; no installation."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
BASE='d792b4bcb'
OUT=ROOT/'work/ai-continuity-followup-staged';OUT.mkdir(exist_ok=True)
def read(name):
    return subprocess.check_output(['git','show',BASE+':CvGameCoreDLL_Expansion2/'+name],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
original={n:read(n) for n in ('CvStackingOffensiveAI.cpp','CvStackingOffensiveAI.h','CvUnitCombat.cpp','CvStackingAI.cpp')}
candidate=dict(original)
def change(name,old,new):
    assert candidate[name].count(old)==1,(name,old[:100])
    candidate[name]=candidate[name].replace(old,new,1)
change('CvStackingOffensiveAI.cpp','        int lastUsefulTurn, lowestHP;',
'''        int lastUsefulTurn, lowestHP;
        int firstReadyTurn, lastCityProgress, lastCityAttack, cityAttempts, fieldContributions;''')
change('CvStackingOffensiveAI.cpp','lastUsefulTurn(-1),lowestHP(INT_MAX),captureKnown(false)',
'''lastUsefulTurn(-1),lowestHP(INT_MAX),firstReadyTurn(-1),lastCityProgress(-1),lastCityAttack(-1),cityAttempts(0),fieldContributions(0),captureKnown(false)''')
change('CvStackingOffensiveAI.cpp','        bool arrived, capturer, assembly;',
'''        int routeStage, routeDestination, routeFrom, routeTo, routeProgress;
        bool arrived, capturer, assembly;''')
change('CvStackingOffensiveAI.cpp','bestDistance(INT_MAX),arrived(false)',
'''bestDistance(INT_MAX),routeStage(-1),routeDestination(-1),routeFrom(-1),routeTo(-1),routeProgress(-1),arrived(false)''')
change('CvStackingOffensiveAI.cpp','    bool shuttingDown=false;',
'''    bool shuttingDown=false;
    unsigned long continuityGeneration=1;
    bool continuityGenerationExhausted=false;''')
change('CvStackingOffensiveAI.cpp','{ objectives.clear(); commitments.clear(); failures.clear(); marches.clear(); captureRetries.clear(); production.clear(); stalledProduction.clear(); assemblyHolds.clear(); currentTurn=-1; shuttingDown=false; }',
'''{ objectives.clear(); commitments.clear(); failures.clear(); marches.clear(); captureRetries.clear(); production.clear(); stalledProduction.clear(); assemblyHolds.clear(); currentTurn=-1; shuttingDown=false;
        if(continuityGeneration==0xffffffffUL) continuityGenerationExhausted=true; else ++continuityGeneration; }''')
change('CvStackingOffensiveAI.cpp','        if(c.goal.target!=target || (c.plot!=plot && distance<c.bestDistance) || eta<c.eta) c.lastProgress=currentTurn;',
'''        // An ETA estimate alone, without actual movement, is not progress.
        if(c.goal.target!=target || (c.plot!=plot && distance<c.bestDistance)) c.lastProgress=currentTurn;''')
change('CvStackingOffensiveAI.cpp','        if(c.goal.target!=target) { c.arrived=false; c.capturer=false; c.assembly=false; c.bestDistance=distance; }',
'''        if(c.goal.target!=target) { c.arrived=false; c.capturer=false; c.assembly=false; c.bestDistance=distance;
            c.routeStage=c.routeDestination=c.routeFrom=c.routeTo=c.routeProgress=-1; }''')
helpers='''    // Called only after the existing native path has produced a real move.
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
        o.staffTurn=-1; // Actual wounds/losses can expose a replacement-role deficit.
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
'''
change('CvStackingOffensiveAI.cpp','    bool StageUnit(CvUnit* unit,const CvPlot* cityTarget)\n',helpers+'    bool StageUnit(CvUnit* unit,const CvPlot* cityTarget)\n')
change('CvStackingOffensiveAI.cpp','            const int id=unit->GetID(),from=unit->plot()->GetPlotIndex();',
'''            const int id=unit->GetID(),from=unit->plot()->GetPlotIndex();
            const int targetIndex=cityTarget->GetPlotIndex(),stageIndex=stage->GetPlotIndex(),destination=p->GetPlotIndex(),expectedEnd=end->GetPlotIndex();''')
old='''            RecordTransfer(unit,cityTarget->GetPlotIndex(),-1,plotDistance(*unit->plot(),*cityTarget)/max(1,unit->baseMoves(false)));
            assemblyHolds[Key(owner,id)]=currentTurn;'''
change('CvStackingOffensiveAI.cpp',old,'''            RecordTransfer(unit,targetIndex,-1,plotDistance(*unit->plot(),*cityTarget)/max(1,unit->baseMoves(false)));
            RecordStageRouteProgress(unit,targetIndex,stageIndex,destination,from,expectedEnd);
            assemblyHolds[Key(owner,id)]=currentTurn;''')
change('CvStackingOffensiveAI.cpp','                if(plan.phase==2 && currentTurn-i->second.lastUsefulTurn>=Setting("AIAssaultAbandonTurns",24)) stale.push_back(i->first);',
'''                Objective& o=i->second;
                if(plan.ready && o.firstReadyTurn<0) o.firstReadyTurn=currentTurn;
                const int attackClock=max(o.lastCityProgress,o.firstReadyTurn);
                const int attackStall=Setting("AIAssaultAttackProgressStallTurns",24);
                const bool noAttackProgress=attackStall>0 && o.firstReadyTurn>=0 && currentTurn-attackClock>=attackStall;
                if((plan.phase==2 && currentTurn-o.lastUsefulTurn>=Setting("AIAssaultAbandonTurns",24)) || noAttackProgress) stale.push_back(i->first);''')
change('CvStackingOffensiveAI.h','    bool StageUnit(CvUnit* unit, const CvPlot* cityTarget);',
'''    bool IsCombatHistoryCurrent(unsigned long generation);
    bool GetCombatObjective(const CvUnit* unit,int& target,DomainTypes& domain,unsigned long& generation);
    void RecordCombatContribution(PlayerTypes owner,int unit,int target,DomainTypes domain,
        int combatPlot,int defenderOwner,int fieldDamage,int cityDamage,bool captured);
    void RecordStageRouteProgress(CvUnit* unit,int target,int stage,int destination,int from,int expectedEnd);
    bool StageUnit(CvUnit* unit, const CvPlot* cityTarget);''')
change('CvStackingAI.cpp','        const int unitID=unit->GetID();\n        unit->PushMission',
'''        const int unitID=unit->GetID();
        const int stageIndex=best->GetPlotIndex(),expectedEnd=end->GetPlotIndex();
        unit->PushMission''')
change('CvStackingAI.cpp','        if(bestObjective>=0) CvStackingOffensiveAI::RecordTransfer(unit,bestObjective,bestOperation,bestETA);',
'''        if(bestObjective>=0)
        {
            CvStackingOffensiveAI::RecordTransfer(unit,bestObjective,bestOperation,bestETA);
            CvStackingOffensiveAI::RecordStageRouteProgress(unit,bestObjective,stageIndex,stageIndex,from,expectedEnd);
        }''')
change('CvStackingOffensiveAI.cpp','                if(other==unit || !Matches(other,key,o)) continue;',
'''                if(other==unit || !Matches(other,key,o) ||
                    other->GetCurrHitPoints()*100<other->GetMaxHitPoints()*Setting("AIOffensiveProductionHealthyPercent",65)) continue;''')
change('CvStackingOffensiveAI.cpp','            if(count+training>=maximum || (!usefulRole && count+training>=desiredCount && strength+training*mean>=desiredStrength)) continue;',
'''            const int repair=usefulRole?Setting("AIOffensiveProductionRoleRepairUnits",2):0;
            if(count+training>=maximum+repair || (!usefulRole && count+training>=desiredCount && strength+training*mean>=desiredStrength)) continue;''')
old='''            TacticalForce force(i->first.target,i->first.domain);int loop=0;
            for(CvUnit* u=player.firstUnit(&loop);u && force.units.size()<(size_t)Setting("AIOffensiveSupportMaximumUnits",32);u=player.nextUnit(&loop))
                if(u->getArmyID()==-1 && u->canUseNow() && !u->shouldHeal(false) && !CvStackingAI::RetainCityUnit(u) && Matches(u,i->first,i->second)) force.units.push_back(u->GetID());
            if(!force.units.empty()) result.push_back(force);'''
new='''            TacticalForce force(i->first.target,i->first.domain);int loop=0;
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
            if(!force.units.empty()) result.push_back(force);'''
change('CvStackingOffensiveAI.cpp',old,new)
change('CvUnitCombat.cpp','#include "CvStackingDiagnostics.h"','#include "CvStackingDiagnostics.h"\n#include "CvStackingOffensiveAI.h"')
scope='''namespace
{
    // Independent of diagnostic level: capture identities before combat, then
    // resolve after it. No raw unit/city pointer crosses the combat callbacks.
    struct OffensiveContributionScope
    {
        int owner,unit,target,plot,defenderOwner,defenderID,defenderHP,cityOwner,cityHP;
        DomainTypes domain; unsigned long generation; bool active;
        explicit OffensiveContributionScope(const CvCombatInfo& info):owner(-1),unit(-1),target(-1),plot(-1),
            defenderOwner(-1),defenderID(-1),defenderHP(0),cityOwner(-1),cityHP(0),domain(DOMAIN_LAND),generation(0),active(false)
        {
            const CvUnit* attacker=info.getUnit(BATTLE_UNIT_ATTACKER);
            if(!CvStackingOffensiveAI::GetCombatObjective(attacker,target,domain,generation)) return;
            const CvPlot* p=info.getPlot(); if(!p) return;
            owner=attacker->getOwner();unit=attacker->GetID();plot=p->GetPlotIndex();active=true;
            const CvUnit* defender=info.getUnit(BATTLE_UNIT_DEFENDER);
            if(defender && p->isVisible(GET_PLAYER((PlayerTypes)owner).getTeam()) && !defender->isInvisible(GET_PLAYER((PlayerTypes)owner).getTeam(),false))
            { defenderOwner=defender->getOwner();defenderID=defender->GetID();defenderHP=defender->GetCurrHitPoints(); }
            const CvCity* city=p->getPlotCity();
            if(city && p->isVisible(GET_PLAYER((PlayerTypes)owner).getTeam()))
            { cityOwner=city->getOwner();cityHP=city->GetMaxHitPoints()-city->getDamage(); }
        }
        ~OffensiveContributionScope()
        {
            if(!active || !CvStackingOffensiveAI::IsCombatHistoryCurrent(generation)) return;
            const CvUnit* defender=defenderOwner>=0?GET_PLAYER((PlayerTypes)defenderOwner).getUnit(defenderID):NULL;
            // A missing identity is not treated as proof of damage or death.
            const int fieldDamage=defender?max(0,defenderHP-defender->GetCurrHitPoints()):0;
            const CvPlot* p=GC.getMap().plotByIndexUnchecked(plot);
            const CvCity* city=p?p->getPlotCity():NULL;
            const bool captured=city && cityOwner>=0 && city->getOwner()==owner && cityOwner!=owner;
            const int cityDamage=city && cityOwner>=0 && !captured && p->isVisible(GET_PLAYER((PlayerTypes)owner).getTeam())?
                max(0,cityHP-(city->GetMaxHitPoints()-city->getDamage())):0;
            CvStackingOffensiveAI::RecordCombatContribution((PlayerTypes)owner,unit,target,domain,plot,defenderOwner,fieldDamage,cityDamage,captured);
        }
    private:
        OffensiveContributionScope(const OffensiveContributionScope&);
        OffensiveContributionScope& operator=(const OffensiveContributionScope&);
    };
}
'''
change('CvUnitCombat.cpp','void CvUnitCombat::ResolveCombat(const CvCombatInfo& kInfo, uint uiParentEventID /* = 0 */)\n',scope+'void CvUnitCombat::ResolveCombat(const CvCombatInfo& kInfo, uint uiParentEventID /* = 0 */)\n')
change('CvUnitCombat.cpp','\tCvStackingDiagnostics::CombatScope diagnosticCombat(kInfo, uiParentEventID);','\tOffensiveContributionScope offensiveContribution(kInfo);\n\tCvStackingDiagnostics::CombatScope diagnosticCombat(kInfo, uiParentEventID);')
for name,text in candidate.items():
    (OUT/name).write_text(text,encoding='utf-8')
    (OUT/('control-'+name)).write_text(original[name],encoding='utf-8')
manifest={'control':BASE,'source_hashes':{n:hashlib.sha256(t.encode()).hexdigest() for n,t in original.items()},
          'candidate_hashes':{n:hashlib.sha256(t.encode()).hexdigest() for n,t in candidate.items()},
          'production_untouched':True,'scope':'O(1) post-mission route witness; independent actual combat contribution; bounded ineffective-ready assault review; no new path queries/search budgets/math/save layout'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest))
