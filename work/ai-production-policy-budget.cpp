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
