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
        std::vector<AssaultWaveUnit> eligibleRows;int omitted=0;
        try
        {
            eligibleRows.reserve(o.waveRows.size());
            for(size_t i=0;i<o.waveRows.size();++i)
            {
                const AssaultWaveUnit& row=o.waveRows[i];
                if(row.army!=-1&&row.army!=army->GetID())continue;
                if(!WaveRecordStillValid(owner,target,row) ||
                    (row.army==-1&&!Matches(GET_PLAYER(owner).getUnit(row.unit),found->first,o)))
                {++omitted;continue;}
                eligibleRows.push_back(row);
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
            if(CanCapture(ally,target)&&ally->getDomainType()==army->GetDomainType()&&
                ally->isNativeDomain(ally->plot())&&plotDistance(*ally->plot(),*target)<=1&&
                ally->plot()->isVisible(GET_PLAYER(owner).getTeam())&&!ally->isInvisible(GET_PLAYER(owner).getTeam(),false)&&
                !GET_PLAYER(owner).IsAtWarWith(ally->getOwner())&&GET_PLAYER(ally->getOwner()).IsAtWarWith(target->getOwner()))eligibleCapture=0;
        }
        // Earlier safe shots, healing or another army can consume optional
        // support. Only unchanged eligible rows contribute to this core; an
        // essential loss still fails the ordinary count/role/power predicates.
        AssaultWave wave=SelectFirstWave(eligibleRows,Setting("AIAssemblyMinimumCombatUnits",4),
            EssentialSiege(owner,target->getPlotCity(),army->GetDomainType()),Setting("AIAssemblyMinimumRanged",2),
            shared.enemyStrength,Setting("AIAssemblyStrengthPercent",150),max(1,target->getPlotCity()->GetMaxHitPoints()-target->getPlotCity()->getDamage()),
            eligibleCapture,Setting("AIAssaultFirstWaveMaximumTurns",1),
            Setting("AIAssaultWaveArrivalSpreadTurns",1),army->GetID(),Setting("AIAssemblyMinimumCombatUnits",4));
        bool complete=false;const int healing=target->getPlotCity()->GetAssaultHealingForecast(owner,wave.damage,&complete);
        ready=WaveCanSustain(wave,max(1,target->getPlotCity()->GetMaxHitPoints()-target->getPlotCity()->getDamage()),
            healing,Setting("AIAssaultDamageHorizon",4),complete);
        if(!ready&&!omitted&&(o.wavePathUnknown||!o.captureKnown))return false; // Pure path uncertainty stays unknown; changed insufficient cores cannot leak through count fallback.
        CvStackingDiagnostics::Record(1,owner,"OPERATION_READINESS","operation=%d army=%d target=%d core=%d ownCore=%d siege=%d capturers=%d strength=%d damage=%d sustained=%d healing=%d healingComplete=%d firstETA=%d lastETA=%d failedMask=%u ready=%d cohortOmitted=%d policy=capability_first_wave",
            op->GetID(),army->GetID(),target->GetPlotIndex(),wave.units,wave.own,wave.siege,wave.capture,wave.strength,wave.damage,wave.sustain,healing,complete,
            wave.first==INT_MAX?-1:wave.first,wave.last,wave.failed,ready,omitted);
        return true;
    }
