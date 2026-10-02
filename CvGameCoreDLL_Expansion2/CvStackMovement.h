#pragma once
#ifndef CV_STACK_MOVEMENT_H
#define CV_STACK_MOVEMENT_H
#include <vector>
class CvUnit;
class CvPlot;
namespace CvStackMovement
{
    struct Member
    {
        int id;
        const char* reason;
        bool canMove, sent, protector, vulnerable, uncertain;
        int movesLeft;
        int turns; // path turns to the destination; 0 arrives this turn, -1 when no path was computed
        Member(int unitID) : id(unitID), reason("Unavailable"), canMove(false), sent(false),
            protector(false), vulnerable(false), uncertain(false), movesLeft(0), turns(-1) {}
    };
    struct Plan
    {
        std::vector<Member> members;
        int moving, staying;
        bool protectorStays;
        Plan() : moving(0), staying(0), protectorStays(false) {}
    };
    struct ReachPlot
    {
        int plotIndex;
        int arriving;
        ReachPlot(int index, int count) : plotIndex(index), arriving(count) {}
    };
    // Plots that at least one member can enter this turn, with how many arrive after capacity.
    struct Reach
    {
        std::vector<ReachPlot> plots;
        int members, eligible;
        Reach() : members(0), eligible(0) {}
    };
    // bQueueLater also orders members that cannot arrive this turn, as ordinary multi-turn moves.
    Plan Preview(CvUnit* pSelected, CvPlot* pSource, CvPlot* pDestination, const std::vector<int>& ids, bool bQueueLater = false);
    Plan Execute(CvUnit* pSelected, CvPlot* pSource, CvPlot* pDestination, const std::vector<int>& ids, bool bQueueLater = false);
    Reach GetReach(CvUnit* pSelected, CvPlot* pSource, const std::vector<int>& ids);
}
#endif
