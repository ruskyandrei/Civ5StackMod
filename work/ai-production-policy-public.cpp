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
