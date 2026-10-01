"""VC9 actual-source differential of the staged full-move healing resource gate."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];out=root/'work/healing-resource-gate-regression';out.mkdir(exist_ok=True)
stage=root/'work/healing-resource-gate-staged';control='9c4b9915e'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--production',action='store_true')
args=parser.parse_args()
old=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
new=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp' if args.production else stage/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
gate='pUnit->getDamage() + unit.iSelfDamage > 0 && !pUnit->IsCannotHeal(/*bConsiderResourceShortage*/ true) && !pUnit->isEmbarked()'
assert old.count(gate)==2
assert new==old.replace(gate,gate.replace(' true)',' false)'),1),'Only the reviewed full-movement resource gate may change'
unit=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/CvUnit.cpp'],cwd=root).decode('utf-8-sig')
player=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/CvPlayer.cpp'],cwd=root).decode('utf-8-sig')

def function(text,signature):
 start=text.index(signature);end=text.index('{',start)+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]

def scorer_block(source):
 start=source.index('//give a bonus for potential fortifying/healing',source.index('static STacticalAssignment* ScorePlotForCombatUnitMove('))
 end=source.index('\n\t// aoe damage on move',start)
 return source[start:end]

blocks=[scorer_block(old),scorer_block(new)]
assert blocks[0].replace('IsCannotHeal(/*bConsiderResourceShortage*/ true)','IsCannotHeal(/*bConsiderResourceShortage*/ false)',1)==blocks[1]
cannot=function(unit,'bool CvUnit::IsCannotHeal(')
can=function(unit,'bool CvUnit::canHeal(')
actual=function(unit,'int CvUnit::ActualHealRate(')
resources=function(player,'bool CvPlayer::HasResourceForNewUnit(')
# Counters instrument only this fixture's exact existing function/loop entries.
resources=resources.replace('{\n','{\n ++resourceCalls;\n',1).replace('const ResourceTypes eResource = static_cast<ResourceTypes>(iResourceLoop);','++resourceRows;\n\t\tconst ResourceTypes eResource = static_cast<ResourceTypes>(iResourceLoop);',1)
actual=actual.replace('{\n','{\n ++actualCalls;\n',1)
prefix=r'''
#define NOMINMAX
#define VALIDATE_OBJECT() ((void)0)
#define ASSERT(...) ((void)0)
#define PRECONDITION(...) ((void)0)
#include <windows.h>
#include <algorithm>
#include <vector>
#include <string>
#include <cstdio>
#include <cstdarg>
#include <climits>
using namespace std;
typedef int UnitTypes;typedef int ResourceTypes;const int NO_UNIT=-1,DOMAIN_LAND=0,DOMAIN_SEA=1,ISHUMAN_AI_UNITS=1;
bool MOD_BALANCE_RESOURCE_SHORTAGE_UNIT_HEALING=true,MOD_UNITS_RESOURCE_QUANTITY_TOTALS=true,MOD_UNITS_HOVERING_LAND_ONLY_HEAL=true,MOD_CORE_NO_HEALING_ON_MOUNTAINS=true;
int resourceCalls=0,resourceRows=0,actualCalls=0,rateCalls=0;
vector<int>hooks;bool mutateOnEnd=false,mutateOnBlockade=false;
struct CvString:string{void Format(const char*format,...){char buffer[512];va_list args;va_start(args,format);vsprintf_s(buffer,sizeof(buffer),format,args);va_end(args);assign(buffer);}};
struct CvResourceInfo{const char*GetIconString()const{return "R";}const char*GetDescription()const{return "Resource";}const char*GetTextKey()const{return "RESOURCE";}};
struct CvUnitEntry{int totals[8],required[8];CvUnitEntry(){for(int i=0;i<8;++i)totals[i]=required[i]=0;}int GetResourceQuantityTotal(int i)const{return totals[i];}int GetResourceQuantityRequirement(int i)const{return required[i];}};
struct CvPlayer{bool major;int total[8],available[8],traitsHeal;CvPlayer():major(true),traitsHeal(0){for(int i=0;i<8;++i)total[i]=available[i]=5;}bool isMajorCiv()const{return major;}int getNumResourceTotal(int i)const{return total[i];}int getNumResourceAvailable(int i,bool=false)const{return available[i];}int GetNumAluminumStillNeededForSpaceship()const{return 0;}int GetNumAluminumStillNeededForCoreCities()const{return 0;}bool HasResourceForNewUnit(UnitTypes,bool,bool,UnitTypes,bool,CvString* =NULL)const;};
CvPlayer players[2];
#define GET_PLAYER(id) players[id]
struct CvCity{bool blockaded;CvCity():blockaded(false){}bool IsBlockadedWaterAndLand()const;};
struct CvPlot{int index;bool water,mountain,city,embark,friendly;CvCity cityData;CvPlot(int n=1):index(n),water(false),mountain(false),city(false),embark(false),friendly(true){}bool isWater()const{return water;}bool isMountain()const{return mountain;}bool isCity()const{return city;}bool needsEmbarkation(const struct CvUnit*)const{return embark;}bool IsFriendlyTerritory(int)const{return friendly;}CvCity*getPlotCity()const{return city?const_cast<CvCity*>(&cityData):NULL;}};
struct Game{void BuildCannotPerformActionHelpText(CvString*sink,const char*,...){if(!sink)return;*sink+="disabled";}};
struct Globals{CvUnitEntry infos[2];CvResourceInfo resource;Game game;int num;Globals():num(8){}CvUnitEntry*getUnitInfo(int id){return id>=0&&id<2?&infos[id]:NULL;}CvResourceInfo*getResourceInfo(int){return &resource;}int getNumResourceInfos()const{return num;}int getInfoTypeForString(const char*)const{return 0;}Game&getGame(){return game;}}GC;
struct CvUnit{
 int owner,type,damage,cannotCount,domain,flat,rate,aoe,adjCity;bool embarked,cargo,human,fortified,moved,always,barbarian,hovering,outside,dead,fortify,endAllowed;CvPlot live;
 CvUnit():owner(0),type(0),damage(40),cannotCount(0),domain(DOMAIN_LAND),flat(0),rate(20),aoe(0),adjCity(0),embarked(false),cargo(false),human(false),fortified(false),moved(false),always(false),barbarian(false),hovering(false),outside(false),dead(false),fortify(true),endAllowed(true),live(1){}
 int getOwner()const{return owner;}int getUnitType()const{return type;}int getCannotHealCount()const{return cannotCount;}bool IsCannotHeal(bool)const;
 bool isHuman(int)const{return human;}bool IsFortified()const{return fortified;}bool hasMoved()const{return moved;}bool isAlwaysHeal()const{return always;}bool isBarbarian()const{return barbarian;}const CvPlot*plot()const{return &live;}bool IsHurt()const{return damage>0;}bool IsHoveringUnit()const{return hovering;}bool isCargo()const{return cargo;}int getDomainType()const{return domain;}bool isHealOutsideFriendly()const{return outside;}
 bool canEndTurnAtPlot(const CvPlot*)const{hooks.push_back(1);if(mutateOnEnd)players[owner].available[0]=-3;return endAllowed;}bool canHeal(const CvPlot*,bool,CvString* =NULL)const;int ActualHealRate(const CvPlot*,bool)const;
 // The unchanged heavy rate implementation is a deterministic injected engine
 // service. Eligibility/resource/callback paths above remain actual source.
 int healRate(const CvPlot*)const{++rateCalls;hooks.push_back(3);return dead?0:rate+players[owner].traitsHeal;}
 int getDamage()const{return damage;}bool isEmbarked()const{return embarked;}bool IsEverFortifyable()const{return fortify;}int GetDamageAoEFortified()const{return aoe;}int GetFlatHealRate()const{return flat;}int GetAdjacentCityDefenseMod()const{return adjCity;}int getTeam()const{return owner;}
};
bool CvCity::IsBlockadedWaterAndLand()const{hooks.push_back(2);if(mutateOnBlockade)players[0].available[0]=-7;return blockaded;}
enum eAssignmentType{A_MOVE,A_FINISH_TEMP,A_HEAL};const int MS_FIRSTLINE=1;
struct STacticalAssignment{eAssignmentType eAssignmentType;STacticalAssignment():eAssignmentType(A_FINISH_TEMP){}};
struct SUnitStats{int iMovesLeft,iMaxMoves,iSelfDamage,eMoveStrategy;SUnitStats():iMovesLeft(120),iMaxMoves(120),iSelfDamage(0),eMoveStrategy(MS_FIRSTLINE){}};
struct CvTacticalPlot{enum{TD_BOTH=0};int improvementDamage,adjacent;CvTacticalPlot():improvementDamage(0),adjacent(0){}int getNumAdjacentEnemies(int)const{return adjacent;}int GetAdjacentImprovementDamage()const{return improvementDamage;}};
struct Scored{int damage,self,bonus,plot;eAssignmentType type;};
'''
score_functions=[]
for name,body in zip(('OriginalHealScorer','CandidateHealScorer'),blocks):
 score_functions.append('Scored '+name+'(const CvUnit*pUnit,const CvPlot*pTestPlot,const CvTacticalPlot*testPlot,const SUnitStats&unit,bool moving=false)\n{\n STacticalAssignment record;STacticalAssignment*result=&record;if(moving)result->eAssignmentType=A_MOVE;int iDamageDelta=0,iSelfDamage=0,iBonusScore=0,iPlotScore=0,iCurrentHealth=100-pUnit->getDamage()-unit.iSelfDamage;\n'+body+'\n Scored output={iDamageDelta,iSelfDamage,iBonusScore,iPlotScore,result->eAssignmentType};return output;\n}')
# A source helper called only by the unchanged adjacent-city score contribution.
prefix=prefix.replace('bool IsFriendlyTerritory(int)const{return friendly;}','bool IsFriendlyTerritory(int)const{return friendly;}bool IsAdjacentCity(int)const{return false;}')
tests=r'''
int checks=0,failures=0;void Expect(const char*label,bool condition){++checks;if(!condition){++failures;if(failures<12)printf("FAIL %s\n",label);}}
bool Equal(const Scored&a,const Scored&b){return a.damage==b.damage&&a.self==b.self&&a.bonus==b.bonus&&a.plot==b.plot&&a.type==b.type;}
struct Counts{int resource,rows,actual,rate;vector<int>hook;int available[2][8];};
void ResetCounters(){resourceCalls=resourceRows=actualCalls=rateCalls=0;hooks.clear();}
Counts Capture(int){Counts value;value.resource=resourceCalls;value.rows=resourceRows;value.actual=actualCalls;value.rate=rateCalls;value.hook=hooks;for(int player=0;player<2;++player)for(int resource=0;resource<8;++resource)value.available[player][resource]=players[player].available[resource];return value;}
bool EqualWorld(const Counts&left,const Counts&right){for(int player=0;player<2;++player)for(int resource=0;resource<8;++resource)if(left.available[player][resource]!=right.available[player][resource])return false;return true;}
unsigned long seed=963211;unsigned long Next(){seed=seed*1664525UL+1013904223UL;return seed;}
void Compare(CvUnit&unit,CvPlot&proposed,CvTacticalPlot&tactical,SUnitStats&stats,bool moving=false){CvPlayer saved[2]={players[0],players[1]};ResetCounters();Scored before=OriginalHealScorer(&unit,&proposed,&tactical,stats,moving);Counts old=Capture(unit.owner);players[0]=saved[0];players[1]=saved[1];ResetCounters();Scored after=CandidateHealScorer(&unit,&proposed,&tactical,stats,moving);Counts current=Capture(unit.owner);Expect("actual scorer healing/type/citadel/fortification output",Equal(before,after));Expect("movement blockade and heal callbacks exact order/count",old.hook==current.hook&&old.rate==current.rate&&EqualWorld(old,current));Expect("resource scans never increase",current.resource<=old.resource&&current.rows<=old.rows);if(stats.iMovesLeft!=stats.iMaxMoves||moving)Expect("partial/moving actual helper work identical",old.resource==current.resource&&old.rows==current.rows&&old.actual==current.actual);players[0]=saved[0];players[1]=saved[1];}
int main(){
 hooks.reserve(20);
 {CvUnit unit;CvPlot proposed(2);CvTacticalPlot tactical;SUnitStats stats;ResetCounters();OriginalHealScorer(&unit,&proposed,&tactical,stats);Expect("old sufficient fullmove scans resources twice",resourceCalls==2&&resourceRows==16);ResetCounters();CandidateHealScorer(&unit,&proposed,&tactical,stats);Expect("new sufficient fullmove scans once",resourceCalls==1&&resourceRows==8);}
 {CvUnit unit;CvPlot proposed(2);CvTacticalPlot tactical;SUnitStats stats;GC.infos[0].required[0]=1;players[0].available[0]=-1;ResetCounters();Scored old=OriginalHealScorer(&unit,&proposed,&tactical,stats);Expect("old shortage scans once and skips callbacks",resourceCalls==1&&rateCalls==0&&hooks.empty());ResetCounters();Scored current=CandidateHealScorer(&unit,&proposed,&tactical,stats);Expect("new shortage scans once and skips callbacks",resourceCalls==1&&rateCalls==0&&hooks.empty()&&Equal(old,current));players[0]=CvPlayer();GC.infos[0]=CvUnitEntry();}
 for(int iteration=0;iteration<18000;++iteration){CvUnit unit;CvPlot proposed(2);CvTacticalPlot tactical;SUnitStats stats;
  unit.owner=Next()%2;players[unit.owner]=CvPlayer();players[unit.owner].major=Next()%5!=0;players[unit.owner].traitsHeal=(int)(Next()%81)-40;GC.infos[0]=CvUnitEntry();GC.infos[1]=CvUnitEntry();
  for(int i=0;i<8;++i){GC.infos[0].required[i]=Next()%4;GC.infos[0].totals[i]=Next()%3;players[unit.owner].total[i]=(int)(Next()%8)-1;players[unit.owner].available[i]=(int)(Next()%9)-2;}
  MOD_BALANCE_RESOURCE_SHORTAGE_UNIT_HEALING=Next()%5!=0;MOD_UNITS_RESOURCE_QUANTITY_TOTALS=Next()%3!=0;
  unit.type=Next()%31==0?-1:0;unit.damage=Next()%101;unit.cannotCount=Next()%13==0;unit.domain=Next()%3==0?DOMAIN_SEA:DOMAIN_LAND;unit.flat=Next()%31;unit.rate=(int)(Next()%71)-20;
  unit.embarked=Next()%7==0;unit.cargo=Next()%7==0;unit.human=Next()%3==0;unit.fortified=Next()%2!=0;unit.moved=Next()%2!=0;unit.always=Next()%2!=0;unit.barbarian=Next()%7==0;unit.hovering=Next()%7==0;unit.outside=Next()%3==0;unit.dead=Next()%17==0;unit.fortify=Next()%3!=0;unit.endAllowed=Next()%3!=0;unit.aoe=Next()%13;unit.adjCity=Next()%4;
  proposed.water=Next()%3==0;proposed.mountain=Next()%7==0;proposed.city=Next()%3==0;proposed.cityData.blockaded=Next()%3==0;proposed.embark=Next()%4==0;proposed.friendly=Next()%2!=0;
  stats.iMovesLeft=Next()%3==0?60:120;stats.iSelfDamage=(int)(Next()%121)-20;tactical.improvementDamage=Next()%41;tactical.adjacent=Next()%7;
  mutateOnEnd=Next()%5==0;mutateOnBlockade=Next()%5==0;Compare(unit,proposed,tactical,stats,Next()%7==0);
 }
 MOD_BALANCE_RESOURCE_SHORTAGE_UNIT_HEALING=true;MOD_UNITS_RESOURCE_QUANTITY_TOTALS=true;players[0]=CvPlayer();GC.infos[0]=CvUnitEntry();
 {CvUnit unit;CvTacticalPlot tactical;SUnitStats stats;unit.damage=0;stats.iSelfDamage=40;Compare(unit,unit.live,tactical,stats);CvPlot hypothetical(2);Compare(unit,hypothetical,tactical,stats);}
 {CvUnit unit;CvPlot city(2);city.city=true;CvTacticalPlot tactical;SUnitStats stats;unit.human=true;mutateOnEnd=mutateOnBlockade=true;Compare(unit,city,tactical,stats);stats.iMovesLeft=60;unit.always=true;Compare(unit,city,tactical,stats);unit.always=false;unit.flat=7;Compare(unit,city,tactical,stats);}
 printf("actual healing resource gate: %d checks, %d failures; partial branch identical; native gain unmeasured\n",checks,failures);return failures?1:0;
}
'''
fixture=prefix+resources+'\n'+cannot+'\n'+can+'\n'+actual+'\n'+'\n'.join(score_functions)+'\n'+tests
(out/'test.cpp').write_text(fixture,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe';compile=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compile.stdout+compile.stderr,encoding='utf-8')
if compile.returncode:print(compile.stdout+compile.stderr);raise SystemExit(compile.returncode)
run=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(run.stdout+run.stderr,end='')
report=dict(control=control,production_applied=args.production,strict_one_predicate_delta=True,returncode=run.returncode,output=run.stdout+run.stderr,fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),
 scope='Actual old/new scorer healing/fortification/citadel block; actual full IsCannotHeal/canHeal/ActualHealRate/HasResourceForNewUnit. Configurable unchanged healRate service substitutes religion/aura/trait arithmetic, while resource eligibility/movement/blockade hook ordering and mutations are exercised. No whole scorer, full healRate, native timing or game action claim.')
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');raise SystemExit(run.returncode)
