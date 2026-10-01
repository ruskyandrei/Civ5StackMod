"""VC9 differential test of current sorted scores and actual score/finish methods."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys

root=Path(__file__).resolve().parents[1];out=root/'work/plot-score-container-regression';out.mkdir(exist_ok=True)
staged=root/'work/plot-score-container-staged';control='490ee12c4';production_base='fb45e447e'
old_cpp=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
old_header=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/CvTacticalAI.h'],cwd=root).decode('utf-8-sig')
unit_header=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/CvUnit.h'],cwd=root).decode('utf-8-sig')
new_cpp=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_text(encoding='utf-8-sig');new_header=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.h').read_text(encoding='utf-8-sig')
staged_cpp=(staged/'CvTacticalAI.cpp').read_text(encoding='utf-8');staged_header=(staged/'CvTacticalAI.h').read_text(encoding='utf-8')
assert new_header==staged_header,'Production header differs from the reviewed staged proposal'
before_cpp=subprocess.check_output(['git','show',production_base+':CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
before_header=subprocess.check_output(['git','show',production_base+':CvGameCoreDLL_Expansion2/CvTacticalAI.h'],cwd=root).decode('utf-8-sig')
assert new_cpp.count('STacticalPlotScores')==4,'Unexpected current production type occurrences'
assert new_cpp.replace('STacticalPlotScores','map<int, short>')==before_cpp,'Production cpp changes extend beyond the four approved type substitutions'

def block(text,signature,semicolon=False):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
    if semicolon:
        assert text[end]==';';end+=1
    return text[start:end]

wrapper=block(new_header,'class STacticalPlotScores',True)
assert wrapper==block(staged_header,'class STacticalPlotScores',True),'Production wrapper differs from staged proposal'
wrapper_start=new_header.index('// Plot scores are small, frequently copied')
wrapper_end=new_header.index('//copy-on-write for often reused seldom updated fields in tactical positions')
assert (new_header[:wrapper_start]+new_header[wrapper_end:]).replace('SCoWField<STacticalPlotScores> plotScores;','SCoWField<map<int, short>> plotScores;')==before_header,'Production header changes extend beyond wrapper and field type'
cow='template<typename T>\n'+block(old_header,'struct SCoWField',True)
assert cow in new_header
values=block(unit_header,'struct SUnitIDValueContainer',True)
assignments=block(old_header,'struct STacticalAssignment',True)
enums=old_header[old_header.index('enum CLOSED_ENUM eUnitMoveEvalMode'):old_header.index('struct STacticalAssignment')]
equal=block(old_cpp,'static bool EqualAssignedUnitValues(')+ '\n'+block(old_cpp,'bool STacticalAssignment::operator==(')
methods=[]
for cpp,name in ((old_cpp,'MapPosition'),(new_cpp,'VectorPosition')):
    for signature in ('void CvBasePosition::UpdateScore(int ', 'bool CvTacticalPosition::addFinishMovesIfAcceptable(', 'const STacticalAssignment* CvBasePosition::getInitialAssignment('):
        if name=='VectorPosition':
            assert block(cpp,signature)==block(staged_cpp,signature),'Current actual method differs from reviewed staging: '+signature
            assert block(cpp,signature).replace('STacticalPlotScores','map<int, short>')==block(old_cpp,signature),'Current actual method differs from original oracle beyond the container type: '+signature
        methods.append(block(cpp,signature).replace('CvBasePosition::',name+'::').replace('CvTacticalPosition::',name+'::'))
prefix=r'''
#define NOMINMAX
#define CLOSED_ENUM
#define VALIDATE_OBJECT() ((void)0)
#define ASSERT(x) ((void)0)
#include <windows.h>
#include <algorithm>
#include <vector>
#include <map>
#include <utility>
#include <cstdio>
#include <cstdlib>
#include <new>
#include <climits>
#include <ctime>
using namespace std;
typedef int PlayerTypes;const PlayerTypes NO_PLAYER=-1;
const short TACTICAL_COMBAT_IMPOSSIBLE_SCORE=-1000;
static unsigned long allocationCalls=0;
static unsigned __int64 allocatedRequestedBytes=0,liveRequestedBytes=0,peakRequestedBytes=0;
union AllocationHeader{size_t bytes;double alignment;};
void* operator new(size_t n){AllocationHeader*p=(AllocationHeader*)malloc(sizeof(AllocationHeader)+(n?n:1));if(!p)throw bad_alloc();p->bytes=n;++allocationCalls;allocatedRequestedBytes+=n;liveRequestedBytes+=n;if(liveRequestedBytes>peakRequestedBytes)peakRequestedBytes=liveRequestedBytes;return p+1;}
void operator delete(void*p){if(p){AllocationHeader*h=(AllocationHeader*)p-1;liveRequestedBytes-=h->bytes;free(h);}}
void* operator new[](size_t n){return ::operator new(n);}void operator delete[](void*p){::operator delete(p);}
namespace CvStacking{bool enabled=true;bool IsEnabled(){return enabled;}}
struct CvPlot{int index;CvPlot(int value=0):index(value){}int GetPlotIndex()const{return index;}};
struct CvUnit{CvPlot location;int experience;CvUnit():location(1),experience(100){}const CvPlot*plot()const{return &location;}int getExperienceTimes100()const{return experience;}};
struct CvTacticalPlot{int index;CvTacticalPlot(int value=0):index(value){}int getPlotIndex()const{return index;}};
'''
harness=r'''
struct SUnitStats{
 int iUnitID,iPlotIndex,iMovesLeft;eUnitAssignmentType eLastAssignment;const CvUnit*pUnit;
 SUnitStats(int id=0,const CvUnit*unit=NULL,int moves=0,eUnitAssignmentType type=A_INITIAL):iUnitID(id),iPlotIndex(1),iMovesLeft(moves),eLastAssignment(type),pUnit(unit){}
};
int gDefaultUnitLossThreshold=1,gMedianUnitXP=50;
template<class Scores>struct PositionFields{
 SCoWField<Scores>plotScores;
 SCoWField<vector<SUnitStats> >availableUnits,notQuiteFinishedUnits,finishedUnits;
 SCoWField<vector<STacticalAssignment> >assignedMoves;
 int iScoreOverParent,iDamageDelta,iBonusScore,iTotalScore,nKilledEnemies,nSaveMovement;
 bool bReturnToStartPositions,early,improved;int scoringCalls;
 map<int,STacticalAssignment> forecasts;map<int,CvTacticalPlot>plots;
 PositionFields():iScoreOverParent(0),iDamageDelta(0),iBonusScore(0),iTotalScore(0),nKilledEnemies(0),nSaveMovement(0),bReturnToStartPositions(false),early(false),improved(true),scoringCalls(0){plots[1]=CvTacticalPlot(1);plots[2]=CvTacticalPlot(2);}
 const CvTacticalPlot*getTactPlot(int id)const{typename map<int,CvTacticalPlot>::const_iterator i=plots.find(id);return i==plots.end()?NULL:&i->second;}
 bool isEarlyFinish()const{return early;}bool isKillOrImprovedPosition()const{return improved;}
 void inherit(const PositionFields&parent){plotScores.inheritFrom(parent.plotScores.read());availableUnits.inheritFrom(parent.availableUnits.read());notQuiteFinishedUnits.inheritFrom(parent.notQuiteFinishedUnits.read());finishedUnits.inheritFrom(parent.finishedUnits.read());assignedMoves.inheritFrom(parent.assignedMoves.read());iDamageDelta=parent.iDamageDelta;iBonusScore=parent.iBonusScore;iTotalScore=parent.iTotalScore;iScoreOverParent=0;nKilledEnemies=parent.nKilledEnemies;nSaveMovement=parent.nSaveMovement;bReturnToStartPositions=parent.bReturnToStartPositions;early=parent.early;improved=parent.improved;forecasts=parent.forecasts;plots=parent.plots;scoringCalls=0;}
};
struct MapPosition:PositionFields<map<int,short> >{void UpdateScore(int,int,int,int,int);bool addFinishMovesIfAcceptable(bool,int&);const STacticalAssignment*getInitialAssignment(int)const;};
struct VectorPosition:PositionFields<STacticalPlotScores>{void UpdateScore(int,int,int,int,int);bool addFinishMovesIfAcceptable(bool,int&);const STacticalAssignment*getInitialAssignment(int)const;};
template<class Position>STacticalAssignment*ScorePlotForMove(const SUnitStats&unit,const CvTacticalPlot*,Position&position,eUnitMoveEvalMode){++position.scoringCalls;return &position.forecasts[unit.iUnitID];}
'''
tests=r'''
int checks=0,failures=0;void Expect(const char*label,bool result){++checks;if(!result){++failures;if(failures<12)printf("FAIL %s\n",label);}}
template<class Left,class Right>bool EqualScores(const Left&left,const Right&right){if(left.size()!=right.size())return false;typename Left::const_iterator a=left.begin();typename Right::const_iterator b=right.begin();for(;a!=left.end();++a,++b)if(a->first!=b->first||a->second!=b->second)return false;return true;}
bool EqualUnits(const vector<SUnitStats>&left,const vector<SUnitStats>&right){if(left.size()!=right.size())return false;for(size_t i=0;i<left.size();++i)if(left[i].iUnitID!=right[i].iUnitID||left[i].iPlotIndex!=right[i].iPlotIndex||left[i].iMovesLeft!=right[i].iMovesLeft||left[i].eLastAssignment!=right[i].eLastAssignment||left[i].pUnit!=right[i].pUnit)return false;return true;}
bool EqualAssignments(const vector<STacticalAssignment>&left,const vector<STacticalAssignment>&right){if(left.size()!=right.size())return false;for(size_t i=0;i<left.size();++i)if(!(left[i]==right[i])||left[i].GetPlotScore()!=right[i].GetPlotScore()||left[i].GetOldPlotScore()!=right[i].GetOldPlotScore()||left[i].GetBonusScore()!=right[i].GetBonusScore()||left[i].GetDamageDelta()!=right[i].GetDamageDelta())return false;return true;}
bool EqualPositions(const MapPosition&left,const VectorPosition&right){return EqualScores(left.plotScores.read(),right.plotScores.read())&&left.iScoreOverParent==right.iScoreOverParent&&left.iDamageDelta==right.iDamageDelta&&left.iBonusScore==right.iBonusScore&&left.iTotalScore==right.iTotalScore&&left.scoringCalls==right.scoringCalls&&EqualAssignments(left.assignedMoves.read(),right.assignedMoves.read())&&EqualUnits(left.availableUnits.read(),right.availableUnits.read())&&EqualUnits(left.notQuiteFinishedUnits.read(),right.notQuiteFinishedUnits.read())&&EqualUnits(left.finishedUnits.read(),right.finishedUnits.read());}
unsigned long rng=1234567;unsigned long Next(){rng=rng*1664525UL+1013904223UL;return rng;}
template<class Position>void SetupFinish(Position&position,CvUnit*units,int scenario){
 position.UpdateScore(1,7,0,3,4);position.UpdateScore(2,11,0,0,0);position.UpdateScore(3,4,0,0,0);position.UpdateScore(4,9,0,0,0);
 position.availableUnits.write().push_back(SUnitStats(1,&units[1],2,A_INITIAL));position.availableUnits.write().push_back(SUnitStats(4,&units[4],2,A_MOVE));position.availableUnits.write().push_back(SUnitStats(7,&units[7],1,A_INITIAL));
 position.notQuiteFinishedUnits.write().push_back(SUnitStats(2,&units[2],0));position.notQuiteFinishedUnits.write().push_back(SUnitStats(3,&units[3],1,A_BLOCKED));
 for(int id=1;id<=7;++id){STacticalAssignment initial(1,1,id,2,MS_FIRSTLINE,A_INITIAL,0);initial.SetScore(3,0,0);position.assignedMoves.write().push_back(initial);STacticalAssignment forecast(1,1,id,0,MS_FIRSTLINE,A_FINISH_TEMP,3);forecast.SetScore(31+id,17,19);forecast.iPrimaryUnitID=100+id;forecast.ePrimaryUnitOwner=2;forecast.iSelfDamage=4;forecast.iDamagedCityId=8;forecast.iCityDamage=12;forecast.unitDamage.SetValue(100,20);forecast.unitDamage.SetValue(200,30);forecast.unitHealing.SetValue(9,6);position.forecasts[id]=forecast;}
 position.early=(scenario&1)!=0;position.improved=scenario!=2;
 if(scenario==3){position.bReturnToStartPositions=true;position.notQuiteFinishedUnits.write()[0].iPlotIndex=2;}
 if(scenario==4)position.nSaveMovement=1;
 if(scenario==5||scenario==6||scenario==8){position.forecasts[2].SetImpossible();units[2].experience=scenario==5?100:0;}
 if(scenario==7)position.assignedMoves.write().clear();
 if(scenario==8){position.notQuiteFinishedUnits.write()[1].iMovesLeft=0;position.notQuiteFinishedUnits.write()[1].eLastAssignment=A_MOVE;position.forecasts[3].SetImpossible();units[3].experience=0;}
 if(scenario==9){position.notQuiteFinishedUnits.write()[0].eLastAssignment=A_BLOCKED;position.notQuiteFinishedUnits.write()[0].iMovesLeft=0;}
 if(scenario==10){position.nKilledEnemies=3;position.forecasts[2].SetImpossible();units[2].experience=0;}
}
template<class Container>void AllocationCase(const char*name,int keys,int cycles){
 unsigned __int64 startLive=liveRequestedBytes;unsigned long count;unsigned __int64 bytes,retained,peak;
 {SCoWField<Container>parent,child;for(int i=0;i<keys;++i)parent.write()[i*7919-2000]=(short)(i-30);unsigned long start=allocationCalls;unsigned __int64 before=allocatedRequestedBytes;peakRequestedBytes=liveRequestedBytes;
  for(int round=0;round<cycles;++round){child.inheritFrom(parent.read());if(keys)child.write()[(round%keys)*7919-2000]=(short)(round&32767);else child.write();}
  count=allocationCalls-start;bytes=allocatedRequestedBytes-before;retained=liveRequestedBytes-startLive;peak=peakRequestedBytes-startLive;printf("ALLOC %s keys%d cycles%d calls%lu bytes%I64u retained%I64u peak%I64u\n",name,keys,cycles,count,bytes,retained,peak);
 }
 Expect("allocation case releases requested bytes at destruction",liveRequestedBytes==startLive);
 Expect("fixed-size vector clone requires at most firstgrowth",strcmp(name,"vector")!=0||count<=(keys?1u:0u));
 Expect("VC9 map nodes reallocated percopy",strcmp(name,"map")!=0||count==(unsigned long)(keys*cycles));
}
int main(){
 {map<int,short>old;STacticalPlotScores current;const int ids[]={INT_MAX,INT_MIN,-1,0,1000000,1,13,14,500};for(size_t i=0;i<sizeof(ids)/sizeof(ids[0]);++i){Expect("default zero insertion",old[ids[i]]==current[ids[i]]);old[ids[i]]=current[ids[i]]=(short)(i*8193);Expect("ascending extreme-key sequence",EqualScores(old,current));}
  for(int i=0;i<1000;++i){old[i*47-30000]=(short)(i*973);current[i*47-30000]=(short)(i*973);}Expect("no13 actor cap",current.size()>1000&&EqualScores(old,current));
  map<int,short>copyOld(old);STacticalPlotScores copyCurrent(current);copyOld[77]=copyCurrent[77]=32767;Expect("copy construction independent",EqualScores(copyOld,copyCurrent)&&EqualScores(old,current));
  STacticalPlotScores assigned;map<int,short>assignedOld;assigned=current;assignedOld=old;assigned=assigned;assignedOld=assignedOld;Expect("copy assignment and self assignment",EqualScores(assignedOld,assigned));
  short*same=&assigned[1000000];short*sameOld=&assignedOld[1000000];assigned[1000000]+=123;assignedOld[1000000]+=123;Expect("existing-key mutation keeps its reference",same==&assigned[1000000]&&sameOld==&assignedOld[1000000]&&EqualScores(assignedOld,assigned));
  assigned.clear();assignedOld.clear();Expect("clear removes all keys",assigned.empty()&&EqualScores(assignedOld,assigned));assigned.swap(copyCurrent);assignedOld.swap(copyOld);Expect("swap exact payloads",EqualScores(assignedOld,assigned)&&EqualScores(copyOld,copyCurrent));}
 {SCoWField<map<int,short> >oldParent,oldChild,oldGrand;SCoWField<STacticalPlotScores>parent,child,grand;
  for(int i=0;i<40;++i){oldParent.write()[i]=parent.write()[i]=(short)(i*1001);}
  child.inheritFrom(parent.read());oldChild.inheritFrom(oldParent.read());Expect("inherited read borrows exact container object",&child.read()==&parent.read()&&&oldChild.read()==&oldParent.read());
  child.write()[13]=oldChild.write()[13]=-32768;Expect("child firstwrite isolated",EqualScores(oldChild.read(),child.read())&&EqualScores(oldParent.read(),parent.read())&&parent.read().begin()->second==0);
  grand.inheritFrom(child.read());oldGrand.inheritFrom(oldChild.read());grand.write()[400]=oldGrand.write()[400]=17;Expect("grandchild owns insertion without changing ancestors",EqualScores(oldGrand.read(),grand.read())&&EqualScores(oldChild.read(),child.read()));
  child.inheritFrom(parent.read());oldChild.inheritFrom(oldParent.read());Expect("recycled dirty child returns borrowed parent",EqualScores(oldChild.read(),child.read())&&&child.read()==&parent.read());
  child.clear();oldChild.clear();Expect("clear afterinherit never exposes stale scores",child.read().empty()&&oldChild.read().empty());child.write()[99]=oldChild.write()[99]=21;Expect("cleared child reusable",EqualScores(oldChild.read(),child.read()));
  child.inheritFrom(child.read());oldChild.inheritFrom(oldChild.read());Expect("selfinherit old empty behavior preserved",child.read().empty()&&oldChild.read().empty());
  child.write()[9]=oldChild.write()[9]=37;child.wipe();oldChild.wipe();Expect("wipe releases data and parent",child.parentData==NULL&&oldChild.parentData==NULL&&EqualScores(oldChild.read(),child.read()));
  child.inheritFrom(parent.read());oldChild.inheritFrom(oldParent.read());SCoWField<STacticalPlotScores>borrowedCopy(child);SCoWField<map<int,short> >oldBorrowedCopy(oldChild);Expect("CoW copied borrowed field keeps parent contract",&borrowedCopy.read()==&parent.read()&&EqualScores(oldBorrowedCopy.read(),borrowedCopy.read()));}
 for(int enabled=0;enabled<2;++enabled){CvStacking::enabled=enabled!=0;MapPosition old;VectorPosition current;
  int special[]={INT_MIN,INT_MAX,0,-1,1,1000000};for(int round=0;round<24000;++round){int id=round<6?special[round]:(int)(Next()%137)-37;int value=(int)(Next()%131071)-65535;int prev=(int)(Next()%201)-100;int damage=(int)(Next()%31)-15;int bonus=(int)(Next()%31)-15;old.UpdateScore(id,value,prev,damage,bonus);current.UpdateScore(id,value,prev,damage,bonus);Expect("actual UpdateScore allkeys totals shorts stackonoff",EqualPositions(old,current));
   if(round%97==0){MapPosition oldChild;VectorPosition child;oldChild.inherit(old);child.inherit(current);int childID=1000000+round;oldChild.UpdateScore(childID,32000,3,7,9);child.UpdateScore(childID,32000,3,7,9);Expect("actual UpdateScore borrowed child inserted afteriteration",EqualPositions(oldChild,child));oldChild.UpdateScore(id,-40000,300,4,5);child.UpdateScore(id,-40000,300,4,5);Expect("actual UpdateScore existing borrowed-key iteration safe",EqualPositions(oldChild,child));Expect("parent unchanged afterchild updates",EqualPositions(old,current));}}
 }
 for(int enabled=0;enabled<2;++enabled)for(int scenario=0;scenario<11;++scenario)for(int argument=0;argument<2;++argument){CvStacking::enabled=enabled!=0;CvUnit units[12];MapPosition oldParent;VectorPosition parent;SetupFinish(oldParent,units,scenario);SetupFinish(parent,units,scenario);MapPosition old;VectorPosition current;old.inherit(oldParent);current.inherit(parent);int oldBad=123,newBad=123;bool oldResult=old.addFinishMovesIfAcceptable(argument!=0,oldBad);bool result=current.addFinishMovesIfAcceptable(argument!=0,newBad);Expect("actual fullfinish return badID and completepayload",result==oldResult&&oldBad==newBad&&EqualPositions(old,current));Expect("actual fullfinish parent containers unchanged",EqualPositions(oldParent,parent));
  if(scenario==0){Expect("healthy ordinaryfinish succeeds",result);Expect("unchanged forecast damage/bonus not reapplied to total",current.iDamageDelta==3&&current.iBonusScore==4);Expect("nontrivial emitted finish payload retained",current.assignedMoves.read().back().unitDamage.GetValue(200)==30&&current.assignedMoves.read().back().iPrimaryUnitID==102);}
  if(scenario==3||scenario==4||scenario==5||scenario==7||scenario==8)Expect("negative finish safeguards stillreject",!result);
  if(scenario==6||scenario==10)Expect("allowed loss budget stillaccepts",result);
 }
 for(int enabled=0;enabled<2;++enabled)for(int early=0;early<2;++early){CvStacking::enabled=enabled!=0;CvUnit units[12];MapPosition old;VectorPosition current;SetupFinish(old,units,0);SetupFinish(current,units,0);old.plotScores.write()[1]=current.plotScores.write()[1]=32760;old.early=current.early=early!=0;int oldBad=17,newBad=17;bool a=old.addFinishMovesIfAcceptable(false,oldBad),b=current.addFinishMovesIfAcceptable(false,newBad);Expect("actualfinish short += conversion preserved",a==b&&oldBad==newBad&&EqualPositions(old,current));short expected=(short)(32760+(early?123:45));Expect("actualfinish wrap visible for inherited score key",current.plotScores.read().begin()->second==expected);}
 const int sizes[]={0,1,13,40,127};for(size_t i=0;i<sizeof(sizes)/sizeof(sizes[0]);++i){AllocationCase<map<int,short> >("map",sizes[i],3000);AllocationCase<STacticalPlotScores>("vector",sizes[i],3000);}
 printf("actual plot-score differential: %d checks, %d failures; sorted pair size%u; native turn speed unmeasured\n",checks,failures,(unsigned)sizeof(STacticalPlotScores::value_type));return failures?1:0;
}
'''
fixture=prefix+values+'\n'+enums+assignments+'\n'+equal+'\n'+wrapper+'\n'+cow+'\n'+harness+'\n'+'\n'.join(methods)+'\n'+tests
(out/'test.cpp').write_text(fixture,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe'
compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);raise SystemExit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=60)
print(run.stdout+run.stderr,end='')
rows=[]
for line in run.stdout.splitlines():
    match=re.fullmatch(r'ALLOC (map|vector) keys(\d+) cycles(\d+) calls(\d+) bytes(\d+) retained(\d+) peak(\d+)',line)
    if match:rows.append(dict(container=match[1],**dict(zip(('keys','cycles','allocations','requested_bytes','retained_requested_bytes','peak_requested_bytes'),map(int,match.group(2,3,4,5,6,7))))))
report=dict(returncode=run.returncode,output=run.stdout+run.stderr,control=control,production_base=production_base,production_applied=True,
    production_cpp_sha256=hashlib.sha256(new_cpp.encode()).hexdigest(),production_header_sha256=hashlib.sha256(new_header.encode()).hexdigest(),
    current_header_identical_to_reviewed_staging=True,current_methods_identical_to_reviewed_staging=True,whole_production_container_only_delta_verified=True,
    fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),allocation_cases=rows,
    scope='Actual original/current production UpdateScore and complete addFinishMovesIfAcceptable, actual SCoWField/assignment/value payloads; strict whole-source container-only delta against pre-container DLL64. Deterministic unit/plot/forecast services. VC9 x86. Allocation requests are helper experiments, not native turn speed or RSS.')
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
raise SystemExit(run.returncode)
