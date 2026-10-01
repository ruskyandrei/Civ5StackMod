    int EssentialSiege(PlayerTypes owner,const CvCity* city,DomainTypes domain)
    {
        const int desired=CvStackingOffensiveAI::DesiredSiegeUnits(owner,city,domain);
        return domain==DOMAIN_SEA?desired:min(desired,Setting("AIAssaultEssentialSiegeUnits",2));
    }
    bool WaveRecordStillValid(PlayerTypes owner,const CvPlot* target,const AssaultWaveUnit& row)
    {
        const CvUnit* u=GET_PLAYER(owner).getUnit(row.unit);
        if(!Usable(u)||u->getArmyID()!=row.army||u->GetCurrHitPoints()!=row.hp||u->getUnitType()!=row.type||
            u->GetRange()!=row.range||u->baseMoves(false)!=row.moves||u->plot()->GetPlotIndex()!=row.plot||u->getDomainType()!=row.domain||u->getMoves()!=row.remaining||
            u->canUseNow()!=!!row.available||u->isOutOfAttacks()!=!!row.spent||u->isSetUpForRangedAttack()!=!!row.setup) return false;
        const int roles=(CvStackingOffensiveAI::CanCapture(u,target)?1:0)|(u->IsCanAttackRanged()?2:0)|
            ((u->getDomainType()==DOMAIN_SEA?u->IsCanAttackRanged():CvStackingOffensiveAI::IsSiegeUnit(u))?4:0);
        return roles==row.roles;
    }
    AssaultWave SelectFirstWave(const std::vector<AssaultWaveUnit>& rows,int minimum,int siege,int ranged,
        int enemy,int margin,int hp,int captureEta,int maxArrival,int spread,int army=-1,int ownMinimum=0)
    {
        AssaultWave best;bool found=false;
        // The existing XML maximum is bounded to ten; no new paths or search
        // branches are created. All work uses the already-simulated records.
        for(int start=0;start<=maxArrival;++start)
        {
            const int end=min(maxArrival,start+spread);AssaultWave wave;
            for(size_t i=0;i<rows.size();++i)
            {
                const AssaultWaveUnit& r=rows[i];
                if(r.eta<start||r.eta>end||(army>=0&&r.army!=-1&&r.army!=army))continue;
                ++wave.units;wave.siege+=(r.roles&4)!=0;wave.ranged+=(r.roles&2)!=0;wave.capture+=(r.roles&1)!=0;
                wave.strength+=r.strength;wave.damage+=r.damage;wave.sustain+=r.sustain;
                wave.first=min(wave.first,r.eta);wave.last=max(wave.last,r.eta);wave.own+=r.army==army;
            }
            // An already-arrived reserved capturer may wait for the wave.
            if(captureEta<0||captureEta==INT_MAX||captureEta>end||(captureEta!=0&&captureEta<start))wave.failed|=ASSAULT_CAPTURE;
            if(wave.siege<siege||wave.ranged<ranged)wave.failed|=ASSAULT_SIEGE;
            if(wave.units<minimum)wave.failed|=ASSAULT_COUNT;
            if(enemy<=0)wave.failed|=ASSAULT_UNKNOWN;
            else if((long long)wave.strength*100<(long long)enemy*margin)wave.failed|=ASSAULT_STRENGTH;
            if(wave.own<ownMinimum)wave.failed|=ASSAULT_OWN_ARMY;
            if(wave.first==INT_MAX||wave.last-wave.first>spread)wave.failed|=ASSAULT_COHESION;
            const unsigned relevant=ASSAULT_CAPTURE|ASSAULT_SIEGE|ASSAULT_COUNT|ASSAULT_STRENGTH|ASSAULT_OWN_ARMY|ASSAULT_UNKNOWN|ASSAULT_COHESION;
            const bool valid=(wave.failed&relevant)==0,bestValid=(best.failed&relevant)==0;
            const bool finish=wave.damage>=hp,bestFinish=best.damage>=hp;
            const bool betterRank=finish!=bestFinish?finish:wave.sustain!=best.sustain?wave.sustain>best.sustain:
                wave.damage!=best.damage?wave.damage>best.damage:wave.strength!=best.strength?wave.strength>best.strength:wave.first<best.first;
            if(!found||(valid&&!bestValid)||(valid==bestValid&&betterRank))
            {best=wave;found=true;}
        }
        return best;
    }
    bool WaveCanSustain(AssaultWave& wave,int hp,int healing,int horizon,bool complete)
    {
        const int confidence=complete?100:Setting("AIAssaultIncompleteDamagePercent",125);
        if(wave.damage<hp&&(long long)(wave.sustain-healing)*horizon*100<(long long)hp*confidence)wave.failed|=ASSAULT_DAMAGE;
        return wave.failed==0;
    }
    void CopyWave(CvStackingOffensiveAI::AssaultPlan& plan,const AssaultWave& wave)
    {
        plan.waveUnits=wave.units;plan.waveSiege=wave.siege;plan.waveCapturers=wave.capture;
        plan.waveStrength=wave.strength;plan.waveDamage=wave.damage;plan.waveSustain=wave.sustain;
        plan.waveFirstETA=wave.first==INT_MAX?-1:wave.first;plan.waveLastETA=wave.last;plan.failedMask=wave.failed;
    }
