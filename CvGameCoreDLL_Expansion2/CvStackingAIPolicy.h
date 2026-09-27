#pragma once

// Pure policy helpers shared with actual-source native regression tests.
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
