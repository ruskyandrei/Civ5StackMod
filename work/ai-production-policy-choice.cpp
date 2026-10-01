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
