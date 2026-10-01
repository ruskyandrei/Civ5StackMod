    enum ProductionRole { PRODUCTION_CAPTURE=1, PRODUCTION_SIEGE=2, PRODUCTION_RANGED=4 };
    enum ProductionReason { PRODUCTION_NONE=0, PRODUCTION_ROLE=1, PRODUCTION_QUEUE_LIMIT=2,
        PRODUCTION_FORCE_LIMIT=3, PRODUCTION_SUPPLY=4, PRODUCTION_AFFORDABILITY=5,
        PRODUCTION_DOMAIN_QUOTA=6, PRODUCTION_HOME_DEFENSE=7, PRODUCTION_NO_OBJECTIVE=8 };
    struct ProductionBudget
    {
        int turn, supplyAvailable, affordableAvailable, queuedSupply, queuedLand, queuedSea;
        unsigned long generation;
        bool ready;
        ProductionBudget():turn(-1),supplyAvailable(0),affordableAvailable(0),queuedSupply(0),queuedLand(0),queuedSea(0),generation(0),ready(false){}
    };
    struct ProductionIntent
    {
        int target, domain, roles, bonus, reason, units, queued, missingSiege, missingRanged, missingCapture, quotaUnits;
        bool missingRole, quotaEligible;
        ProductionIntent():target(-1),domain(NO_DOMAIN),roles(0),bonus(0),reason(PRODUCTION_NO_OBJECTIVE),
            units(0),queued(0),missingSiege(0),missingRanged(0),missingCapture(0),quotaUnits(0),missingRole(false),quotaEligible(false){}
    };
    // Demand/budget evidence does not replace native canTrain/purchase/resource checks.
    bool GetProductionBudget(PlayerTypes owner,ProductionBudget& result);
    bool GetProductionIntent(const CvCity* city,UnitTypes unit,ProductionIntent& result,bool replaceQueue=true);
    void ProductionQueueChanged(const CvCity* city);
    void ResetProductionPolicy();
    void ProductionCitiesChanged(PlayerTypes owner);
    void InvalidateProductionStaff(PlayerTypes owner,int target,DomainTypes domain);
    void InvalidateProductionOwner(PlayerTypes owner);
    void ProductionEconomyChanged(PlayerTypes owner);
    void RecordProductionRejection(const CvCity* city,UnitTypes unit,const ProductionIntent& intent,int reason);
