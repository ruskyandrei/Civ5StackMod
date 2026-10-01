// Bounded cached first-wave records; no serialized game-object fields.
struct AssaultWaveUnit
{
    int unit, army, eta, damage, sustain, strength, roles, hp, type, range, moves,plot,domain,remaining,available,spent,setup;
    AssaultWaveUnit(CvUnit* u,int turns,int hit,int retaliation,const CvPlot* target):
        unit(u->GetID()),army(u->getArmyID()),eta(turns),damage(hit),sustain(0),strength(CvStackingAI::UnitStrength(u)),
        roles((CvStackingOffensiveAI::CanCapture(u,target)?1:0)|(u->IsCanAttackRanged()?2:0)|
            ((u->getDomainType()==DOMAIN_SEA?u->IsCanAttackRanged():CvStackingOffensiveAI::IsSiegeUnit(u))?4:0)),
        hp(u->GetCurrHitPoints()),type(u->getUnitType()),range(u->GetRange()),moves(u->baseMoves(false)),plot(u->plot()->GetPlotIndex()),domain(u->getDomainType()),remaining(u->getMoves()),available(u->canUseNow()),spent(u->isOutOfAttacks()),setup(u->isSetUpForRangedAttack())
    {
        // A second-turn damage forecast must not reuse an attacker which its
        // first attack would leave below the same healthy-force threshold.
        if((long long)(hp-retaliation)*100>=
            (long long)u->GetMaxHitPoints()*CvStacking::GetInt("AIAssaultHealthyPercent",65)) sustain=hit;
    }
};
struct AssaultWave
{
    int units, siege, ranged, capture, strength, damage, sustain, first, last, own;
    unsigned failed;
    AssaultWave():units(0),siege(0),ranged(0),capture(0),strength(0),damage(0),sustain(0),first(INT_MAX),last(0),own(0),failed(0){}
};
enum AssaultFailure
{
    ASSAULT_CAPTURE=1,ASSAULT_SIEGE=2,ASSAULT_COUNT=4,ASSAULT_STRENGTH=8,
    ASSAULT_DAMAGE=16,ASSAULT_COHESION=32,ASSAULT_OWN_ARMY=64,ASSAULT_UNKNOWN=128
};
