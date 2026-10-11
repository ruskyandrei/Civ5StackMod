#pragma once

// Pure policy helpers shared with actual-source native regression tests.
namespace CvStackingAIPolicy
{
    inline int CityProtection(int buildings, int cap, int hp, int maxHP, bool scale)
    {
        const int capped = buildings < 0 ? 0 : (buildings > cap ? cap : buildings);
        if (!scale) return capped;
        if (maxHP <= 0 || hp <= 0) return 0;
        if (hp >= maxHP) return capped;
        return (int)((long long)capped * hp / maxHP);
    }
    inline bool OpeningReady(int healthy, int total, int capturers, int ranged, int strength, int enemy,
        int minimum, int percent, int minimumRanged, int margin)
    {
        return healthy >= minimum && (long long)healthy * 100 >= (long long)total * percent &&
            capturers > 0 && ranged >= minimumRanged && (long long)strength * 100 >= (long long)enemy * margin;
    }
    inline bool MovingStalled(int idle, bool contact, int ordinaryLimit, int contactLimit)
    { return idle >= (contact ? contactLimit : ordinaryLimit); }
} // namespace CvStackingAIPolicy

namespace CvStackingAIPolicy
{
    inline bool BetterGarrison(int current, int candidate, int improvementPercent)
    {
        return candidate > current && (long long)candidate * 100 >= (long long)current * (100 + improvementPercent);
    }
    inline bool CoreReady(int present, int required, int missing, int minimumUnits, int requiredPercent,
        int maximumMissing, bool capture, bool fireSupport, int strength, int enemyStrength, int marginPercent)
    {
        return required > 0 && present >= minimumUnits && missing <= maximumMissing &&
            (long long)(required - missing) * 100 >= (long long)required * requiredPercent && capture && fireSupport &&
            (long long)strength * 100 >= (long long)enemyStrength * marginPercent;
    }
    inline bool ReachedDefense(int count, int strength, int minimum, int maximum, int desiredStrength)
    {
        return count >= maximum || (count >= minimum && strength >= desiredStrength);
    }
    inline bool IsStationary(int oldPlot, int plot, int oldETA, int eta)
    {
        return plot == oldPlot && eta >= oldETA;
    }
    inline int ScoreDemand(int priority, int unmetStrength, int travelTurns, int travelWeight, bool continuing, int continuityBonus)
    {
        return priority + unmetStrength - travelTurns * travelWeight + (continuing ? continuityBonus : 0);
    }
}

namespace CvStackingAIPolicy
{
    // Melee protectors wanted in a mixed stack: one, and a second from six units.
    inline int IdealStackMelee(int total)
    {
        return total < 6 ? 1 : 1 + (total - 2) / 4;
    }
    // Preference of one member for its stack's mix; counts include the member.
    // One melee protector with ranged units is best; all-ranged or melee-heavy
    // stacks are discouraged. A unit alone is neutral.
    inline int CompositionScore(bool ranged, int melee, int rangedCount, int mixBonus, int allRangedPenalty, int extraMeleePenalty)
    {
        const int total = melee + rangedCount;
        if (total < 2) return 0;
        if (ranged) return melee > 0 ? mixBonus : -allRangedPenalty;
        if (rangedCount == 0 || melee > IdealStackMelee(total)) return -extraMeleePenalty;
        return mixBonus;
    }
    // Promotion value scale for a heal-giving promotion (Medic), as a percent.
    // Medic bonuses do not add up, so medics beyond about one per group are wasted.
    inline int MedicPromotionPercent(int medics, int units, int unitsPerMedic, int wantedPercent, int surplusPercent)
    {
        if (unitsPerMedic <= 0) return 100;
        const int wanted = (units + unitsPerMedic - 1) / unitsPerMedic;
        return medics < wanted ? wantedPercent : surplusPercent;
    }
}
