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
        Member(int unitID) : id(unitID), reason("Unavailable"), canMove(false), sent(false),
            protector(false), vulnerable(false), uncertain(false), movesLeft(0) {}
    };
    struct Plan
    {
        std::vector<Member> members;
        int moving, staying;
        bool protectorStays;
        Plan() : moving(0), staying(0), protectorStays(false) {}
    };
    Plan Preview(CvUnit* pSelected, CvPlot* pSource, CvPlot* pDestination, const std::vector<int>& ids);
    Plan Execute(CvUnit* pSelected, CvPlot* pSource, CvPlot* pDestination, const std::vector<int>& ids);
}
#endif
