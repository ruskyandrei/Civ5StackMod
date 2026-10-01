    void ResetOpeningReadiness(){openingForecasts.clear();openingForecastTurn=-1;}
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
            if(!Usable(u)||u->getDomainType()!=army->GetDomainType()||
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
                if(!u->isNativeDomain(u->plot()))continue;
                // Potential-war operation route is the existing estimate. This
                // nominal damage forecast does not authorize an actual shot.
                hit=TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(target->getPlotCity(),u,u->plot(),retaliation,garrison);
                if(hit<=0||retaliation>=u->GetCurrHitPoints())continue;
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
        const int desiredSiege=KnownFortified(owner,target->getPlotCity())?DesiredSiegeUnits(owner,target->getPlotCity(),army->GetDomainType()):0;
        bool ready=siege>=desiredSiege&&CvStackingAIPolicy::OpeningReady(healthy,total,capture,ranged,strength,enemy,
            Setting("AIWarOpeningMinimumUnits",4),Setting("AIWarOpeningReadyPercent",75),Setting("AIWarOpeningMinimumRanged",1),Setting("AIWarOpeningStrengthPercent",150));
        AssaultWave wave;bool healingComplete=false;int healing=0;
        if(visible&&complete)
        {
            wave=SelectFirstWave(forecast.rows,Setting("AIWarOpeningMinimumUnits",4),EssentialSiege(owner,target->getPlotCity(),army->GetDomainType()),
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
