"""VC9 actual scorers/assignment acceptance/caller admission/projection regression.

Native damage and policy services are deterministic, while both scorer methods,
STacticalAssignment, admission guards and GetNextPosition/GetNextUnit are read
from production source. Old zero-score gate controls must admit phantom damage.
"""
from pathlib import Path
import hashlib, json, os, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root/'work/city-attack-score-gate-regression'
out.mkdir(exist_ok=True)
source = (root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
header = (root/'CvGameCoreDLL_Expansion2/CvTacticalAI.h').read_text(encoding='utf-8-sig')


def method(signature):
    start = source.index(signature)
    end = source.index('{', start)+1
    depth = 1
    while depth:
        depth += (source[end] == '{')-(source[end] == '}')
        end += 1
    return source[start:end]


assignment = header[header.index('struct STacticalAssignment\n'):header.index('struct SComboMove\n')]
ranged = method('static STacticalAssignment* ScorePlotForRangedAttack(')
melee = method('static STacticalAssignment* ScorePlotForMeleeAttack(')
old_gate = '{ result->SetScore(0,0,0);return result; }'
new_gate = '{ result->SetImpossible();return result; }'
assert ranged.count(new_gate) == melee.count(new_gate) == 1
ranged_control = ranged.replace('ScorePlotForRangedAttack(', 'ScorePlotForRangedAttackControl(', 1).replace(new_gate, old_gate)
melee_control = melee.replace('ScorePlotForMeleeAttack(', 'ScorePlotForMeleeAttackControl(', 1).replace(new_gate, old_gate)
projection = method('static void GetNextPosition(') + '\n' + method('static SUnitStats GetNextUnit(')
ranged_begin = source.index('STacticalAssignment* rangedAttack = ScorePlotForRangedAttack(unit, assumedUnitPlot, enemyPlot, *this);')
ranged_end = source.index('SUnitStats tempUnit = GetNextUnit(unit, rangedAttack);', ranged_begin)+len('SUnitStats tempUnit = GetNextUnit(unit, rangedAttack);')
melee_begin = source.index('STacticalAssignment* attack = ScorePlotForMeleeAttack(unit,assumedUnitPlot,testPlot,it->iMovesLeft,*this);')
melee_end = source.index('SUnitStats tempUnit = GetNextUnit(unit, attack);', melee_begin)+len('SUnitStats tempUnit = GetNextUnit(unit, attack);')
ranged_admission = source[ranged_begin:ranged_end].replace('*this','position')
melee_admission = source[melee_begin:melee_end].replace('*this','position').replace('it->iMovesLeft','assumedMoves')

head = r'''
#include <vector>
#include <map>
#include <string>
#include <sstream>
#include <algorithm>
#include <climits>
#include <cstdio>
#include <cassert>
using namespace std;
#define VALIDATE_OBJECT()
#define ASSERT(x) assert(x)
const short TACTICAL_COMBAT_IMPOSSIBLE_SCORE=-1000;
typedef vector<pair<int,int> > SUnitIDValueContainer;
enum eUnitMovementStrategy{MS_NONE,MS_FIRSTLINE,MS_SECONDLINE,MS_THIRDLINE,MS_SUPPORT,MS_EMBARKED};
enum eUnitAssignmentType{A_INITIAL,A_MOVE,A_MELEEATTACK,A_MELEEKILL,A_RANGEATTACK,A_RANGEKILL,A_FINISH,A_BLOCKED,A_PILLAGE,A_CAPTURE,A_MOVE_FORCED,A_RESTART,A_MELEEKILL_NO_ADVANCE,A_MOVE_SWAP,A_MOVE_SWAP_REVERSE,A_MOVE_DOUBLE,A_USE_POWER,A_FINISH_TEMP,A_HEAL,A_WAIT};
'''
services = r'''
struct CvCity{}city;
struct CvUnit{bool ranged,freeAttack;int owner;CvUnit():ranged(true),freeAttack(false),owner(0){}bool IsCanAttackRanged()const{return ranged;}bool IsFreeAttackMoves()const{return freeAttack;}bool IsCivilianUnit()const{return false;}int getOwner()const{return owner;}int getTeam()const{return 0;}int AI_getUnitAIType()const{return 0;}} actor;
struct CvPlot{int id;CvCity*city;CvPlot(int n=0):id(n),city(NULL){}int GetPlotIndex()const{return id;}CvCity*getPlotCity()const{return city;}int getNumUnits()const{return 0;}CvUnit*getUnitByIndex(int)const{return NULL;}int getRevealedImprovementType(int)const{return 0;}} firing(0),target(1);
struct CvTacticalPlot{CvPlot*p;bool enemy,enemyCity,civilian;int adjacent;CvTacticalPlot(CvPlot*x):p(x),enemy(true),enemyCity(true),civilian(false),adjacent(0){}int getPlotIndex()const{return p->id;}const CvPlot*getPlot()const{return p;}bool isEnemyCity()const{return enemyCity;}bool isEnemy()const{return enemy;}bool isEnemyCivilian()const{return civilian;}int getNumAdjacentEnemies(int)const{return adjacent;}} own(&firing),enemy(&target);
struct SUnitStats{const CvUnit*pUnit;int iPlotIndex,iUnitID,iMovesLeft,iAttacksLeft,iSelfDamage;eUnitMovementStrategy eMoveStrategy;SUnitStats():pUnit(&actor),iPlotIndex(0),iUnitID(11),iMovesLeft(180),iAttacksLeft(2),iSelfDamage(0),eMoveStrategy(MS_SECONDLINE){}};
int projectedCalls=0,policyCalls=0,previousScore=-30;bool allowed=false,capture=false,damagePossible=true,endTurn=false,zoc=false;bool seenCapture=false;
struct CvTacticalPosition{int cityDamage,unitDamage;CvTacticalPosition():cityDamage(0),unitDamage(0){}const CvPlot*getTarget()const{return &target;}int getPlayer()const{return 0;}const vector<int>&getFreedPlots()const{static vector<int>empty;return empty;}void initFromParent(const CvTacticalPosition&parent){*this=parent;++projectedCalls;}void ChangeUnitDamage(int,int amount){unitDamage+=amount;}void ChangeCityDamage(int,int amount){cityDamage+=amount;}};
struct Storage{STacticalAssignment a;STacticalAssignment*peekNext(){return &a;}}gAssignmentStorage;
struct TactStorage{int getAttackCache(){return 0;}}gTactPosStorage;
int GetPrevPlotScore(int,const CvTacticalPosition&){return previousScore;}bool AttackEndsTurn(const CvUnit*,int){return endTurn;}
int NumAttacksForUnit(int moves,int attacks,bool free){return free?attacks:min((moves+59)/60,attacks);}int DomainForUnit(const CvUnit*){return 0;}
const int MOVE_DENOMINATOR=60,BARBARIAN_CAMP_IMPROVEMENT=999,UNITAI_WORKER=3;
#define GD_INT_GET(name) name
namespace CvUnitMovement{bool IsSlowedByZOC(const CvUnit*,const CvPlot*,const CvPlot*,const vector<int>&){return zoc;}}
namespace CvStackingOffensiveAI{bool AllowCityAttack(const CvUnit*,CvCity*,const CvPlot*,bool capture){++policyCalls;seenCapture=capture;return allowed||capture;}}
namespace TacticalAIHelpers{int GetOtherPlayerImprovementDamage(const CvPlot*,int,bool){return 0;}}
struct Player{bool IsAtWarWith(int)const{return true;}}player;
#define GET_PLAYER(x) player
void ScoreAttackDamage(const CvTacticalPlot*,const CvUnit*,const CvTacticalPlot*,const CvTacticalPosition&,int,STacticalAssignment*result,int){if(!damagePossible){result->SetImpossible();return;}result->unitDamage.push_back(make_pair(99,17));result->iDamagedCityId=1;result->iCityDamage=50;result->iSelfDamage=5;if(capture)result->eAssignmentType=A_MELEEKILL;result->SetScore(10,2,40);}
void reset(){actor=CvUnit();own=CvTacticalPlot(&firing);enemy=CvTacticalPlot(&target);target.city=&city;projectedCalls=policyCalls=0;previousScore=-30;allowed=capture=endTurn=zoc=seenCapture=false;damagePossible=true;}
int checks=0,failures=0;void check(bool ok,const char*name){++checks;if(!ok){++failures;printf("FAIL: %s\n",name);}}
string assignmentState(const STacticalAssignment&a){ostringstream s;s<<(int)a.eAssignmentType<<","<<a.Score()<<","<<a.GetPlotScore()<<","<<a.GetBonusScore()<<","<<a.GetDamageDelta()<<","<<a.iRemainingMoves<<","<<a.iCityDamage<<","<<a.iSelfDamage<<","<<a.iDamagedCityId;for(size_t i=0;i<a.unitDamage.size();++i)s<<";"<<a.unitDamage[i].first<<":"<<a.unitDamage[i].second;return s.str();}
'''

def caller(name, body):
    return 'bool '+name+'(const SUnitStats&unit,const CvTacticalPlot*assumedUnitPlot,const CvTacticalPlot*enemyPlot,const CvTacticalPosition&position,CvTacticalPosition&projected){CvTacticalPosition tempPosition;const CvTacticalPlot*testPlot=enemyPlot;int assumedMoves=120;for(int once=0;once<1;++once){\n'+body+'\nprojected=tempPosition;return true;}return false;}\n'

callers = caller('AdmitRanged',ranged_admission) + caller('AdmitMelee',melee_admission)
callers += caller('AdmitRangedControl',ranged_admission.replace('ScorePlotForRangedAttack(','ScorePlotForRangedAttackControl('))
callers += caller('AdmitMeleeControl',melee_admission.replace('ScorePlotForMeleeAttack(','ScorePlotForMeleeAttackControl('))
tests = r'''
int main(){
 for(int old=-90;old<=90;old+=30){reset();previousScore=old;SUnitStats unit;CvTacticalPosition position,projected;
  STacticalAssignment denied=*ScorePlotForRangedAttack(unit,&own,&enemy,position);check(!denied.IsAcceptable(),"ranged city gate is impossible for every previous plot score");
  check(!AdmitRanged(unit,&own,&enemy,position,projected)&&projectedCalls==0&&projected.cityDamage==0&&projected.unitDamage==0,"actual ranged admission rejects payload before projection");
  actor.ranged=false;denied=*ScorePlotForMeleeAttack(unit,&own,&enemy,120,position);check(!denied.IsAcceptable(),"melee city gate is impossible for every previous plot score");
  check(!AdmitMelee(unit,&own,&enemy,position,projected)&&projectedCalls==0&&projected.cityDamage==0,"actual melee admission rejects payload before projection");
 }
 reset();SUnitStats unit;CvTacticalPosition position,projected;check(AdmitRangedControl(unit,&own,&enemy,position,projected)&&projected.cityDamage==50&&projected.unitDamage==17,"old ranged zero-score control admits phantom city/unit damage with negative old plot score");
 reset();actor.ranged=false;check(AdmitMeleeControl(unit,&own,&enemy,position,projected)&&projected.cityDamage==50,"old melee zero-score control admits phantom city damage");
 for(int rangedUnit=0;rangedUnit<=1;++rangedUnit){reset();actor.ranged=rangedUnit!=0;allowed=true;STacticalAssignment now=rangedUnit?*ScorePlotForRangedAttack(unit,&own,&enemy,position):*ScorePlotForMeleeAttack(unit,&own,&enemy,120,position);STacticalAssignment old=rangedUnit?*ScorePlotForRangedAttackControl(unit,&own,&enemy,position):*ScorePlotForMeleeAttackControl(unit,&own,&enemy,120,position);check(now.IsAcceptable()&&assignmentState(now)==assignmentState(old),"allowed attacks preserve complete tested assignment output");projected=CvTacticalPosition();check((rangedUnit?AdmitRanged(unit,&own,&enemy,position,projected):AdmitMelee(unit,&own,&enemy,position,projected))&&projected.cityDamage==50,"allowed attacks still project actual damage");}
 reset();actor.ranged=false;capture=true;STacticalAssignment a=*ScorePlotForMeleeAttack(unit,&own,&enemy,120,position);check(a.IsAcceptable()&&seenCapture&&a.eAssignmentType==A_MELEEKILL&&a.iRemainingMoves==0,"city capture bypass and move-ending rule preserved");
 reset();enemy.enemyCity=false;target.city=NULL;actor.ranged=false;check(ScorePlotForMeleeAttack(unit,&own,&enemy,120,position)->IsAcceptable()&&policyCalls==0,"ordinary melee unit combat does not acquire city gate");
 reset();enemy.enemyCity=false;target.city=NULL;check(ScorePlotForRangedAttack(unit,&own,&enemy,position)->IsAcceptable()&&policyCalls==0,"ordinary ranged unit combat does not acquire city gate");
 reset();damagePossible=false;check(!ScorePlotForRangedAttack(unit,&own,&enemy,position)->IsAcceptable()&&policyCalls==0,"existing impossible damage rejected before city policy");
 reset();actor.ranged=false;unit.iMovesLeft=0;check(!ScorePlotForMeleeAttack(unit,&own,&enemy,0,position)->IsAcceptable()&&policyCalls==0,"existing no-attack-moves rule preserved");
 printf("city attack score gate: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
cpp = out/'test.cpp'
actual = assignment+ranged+melee+projection+ranged_admission+melee_admission
cpp.write_text(head+assignment+services+ranged_control+melee_control+ranged+melee+projection+callers+tests,encoding='utf-8')
vc = root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk = root/'work/toolchain/sdk/windows'
env = os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','')
env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=out/'test.exe';compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],env=env,cwd=out,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr)
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20);print(run.stdout+run.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,actual_source_sha256=hashlib.sha256(actual.encode()).hexdigest(),scope='Actual scorers, assignment acceptance, caller admission, and projection with deterministic policy/damage services; old denied-action controls reproduce phantom damage; not native campaign equivalence.'),indent=2)+'\n')
sys.exit(run.returncode)
