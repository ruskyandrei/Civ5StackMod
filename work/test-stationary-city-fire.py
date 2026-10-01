"""Actual StageUnit permits existing protected fire without weakening staging safety."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];source=(root/'CvGameCoreDLL_Expansion2/CvStackingOffensiveAI.cpp').read_text(encoding='utf-8-sig')
out=root/'work/stationary-city-fire-regression';out.mkdir(exist_ok=True)
def function(text,signature):
 a=text.index(signature);b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
usable=function(source,'bool Usable(');stage=function(source,'bool StageUnit(');fire=function(source,'bool TryStationaryCityFire(')
prefix=r'''
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <vector>
#include <map>
#include <algorithm>
#include <utility>
#include <cstring>
#include <cstdio>
#include <cstdlib>
using namespace std;
typedef int PlayerTypes;
const int DOMAIN_LAND=2,DOMAIN_AIR=1,MISSIONAI_TACTMOVE=0;
static int turn=1,dangerPercent=0,soloDanger=49,soloQueries=0,pathQueries=0,shots=0,moveOrders=0,staleReads=0;
static bool allowSiege=true,deleteOnShot=false;
typedef pair<int,int>Key;static map<Key,int>assemblyHolds;static int assaultQueries[4]={0};static int currentTurn=1;
static int Setting(const char*name,int value){return !strcmp(name,"AIAssaultStageDangerPercent")?dangerPercent:value;}
struct CvCity{};struct CvUnit;
struct CvPlot{int id;CvCity*city;CvPlot(int i=0):id(i),city(NULL){}bool isCity()const{return city!=NULL;}int getOwner()const{return 1;}CvCity*getPlotCity()const{return city;}int GetPlotIndex()const{return id;}bool isVisible(int)const{return true;}int getX()const{return id;}int getY()const{return 0;}};
static int plotDistance(const CvPlot&a,const CvPlot&b){return abs(a.id-b.id);}
static CvPlot*iterateRingPlots(CvPlot*p,int i){return i==0?p:NULL;}
typedef vector<pair<int,int> >SUnitIDValueContainer;
namespace CvTypes{int getMISSION_RANGE_ATTACK(){return 2;}int getMISSION_MOVE_TO(){return 1;}}
struct CvUnit{
 enum{MOVEFLAG_DESTINATION=1,MOVEFLAG_SAFE_EMBARK_ONLY=2,MOVEFLAG_AI_ABORT_IN_DANGER=4};
 int id,hp,danger,moves;bool ranged,processed,dead,canFire,setup,outOfAttacks,stale;CvPlot*position;
 CvUnit():id(7),hp(100),danger(0),moves(120),ranged(true),processed(false),dead(false),canFire(true),setup(true),outOfAttacks(false),stale(false),position(NULL){}
 void read()const{if(stale)++staleReads;}int GetID()const{read();return id;}int getOwner()const{read();return 0;}int getDomainType()const{read();return DOMAIN_LAND;}
 CvPlot*plot()const{read();return position;}int GetCurrHitPoints()const{read();return hp;}bool IsCombatUnit()const{read();return true;}bool IsStackingUnit()const{read();return false;}bool isCargo()const{read();return false;}
 bool isDelayedDeath()const{read();return dead;}bool canUseNow()const{read();return !processed&&!dead&&moves>0;}bool TurnProcessed()const{return processed;}bool isOutOfAttacks()const{return outOfAttacks;}
 bool IsCanAttackRanged()const{read();return ranged;}bool canRangeStrikeAt(int,int)const{read();return ranged&&canFire&&setup&&!outOfAttacks&&moves>0&&!processed;}
 int GetDanger()const{read();return danger;}void SetTurnProcessed(bool b){read();processed=b;}int baseMoves(bool)const{read();return 2;}
 bool isNativeDomain(const CvPlot*)const{read();return true;}bool canMoveInto(const CvPlot&,int)const{read();return true;}
 bool GeneratePath(CvPlot*,int,int){read();++pathQueries;return false;}CvPlot*GetPathEndFirstTurnPlot()const{read();return position;}
 void PushMission(int,int,int,int,bool,bool,int);
};
struct Danger{int GetStackDanger(const CvPlot&,const CvUnit*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&){++soloQueries;return soloDanger;}}danger;
struct CvPlayer{map<int,CvUnit*>units;int getTeam()const{return 0;}bool IsAtWarWith(int p)const{return p==1;}CvUnit*getUnit(int id){map<int,CvUnit*>::iterator it=units.find(id);return it==units.end()?NULL:it->second;}Danger*GetDangerPlots(){return &danger;}}players[4];
#define GET_PLAYER(owner) players[owner]
void CvUnit::PushMission(int mission,int,int,int,bool,bool,int){read();if(mission==2){++shots;moves=0;outOfAttacks=true;if(deleteOnShot){players[0].units.erase(id);stale=true;}}else ++moveOrders;}
struct Map{CvPlot stage;CvPlot*plotByIndexUnchecked(int){return &stage;}};
struct Globals{Map map;Map&getMap(){return map;}}GC;
namespace CvStackingDiagnostics{void Record(int,int,const char*,const char*,...) {}}
struct AssaultPlan{bool ready;int staging;AssaultPlan():ready(false),staging(-1){}}plan;
static AssaultPlan AssessAssault(int,CvCity*,int){return plan;}
static bool ContinueSiege(int,CvCity*){return allowSiege;}
static bool Enabled(int){return true;}namespace CvStackingAI{bool RetainCityUnit(const CvUnit*){return false;}}
static bool HasCommitment(CvUnit*,const CvPlot* = NULL){return true;}
static void RecordTransfer(CvUnit*,int,int,int){}
// Route bookkeeping is independently source-tested; this fixture tests fire/staging legality.
static void RecordStageRouteProgress(CvUnit*,int,int,int,int,int){}
'''
tests=r'''
static int checks=0,failures=0;static void expect(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<12)printf("FAIL %s\n",n);}}
struct Fixture{
 CvCity city;CvPlot at,target;CvUnit unit;
 Fixture():at(1),target(2){target.city=&city;unit.position=&at;players[0].units.clear();players[0].units[unit.id]=&unit;plan=AssaultPlan();GC.map.stage.id=1;dangerPercent=0;soloDanger=49;soloQueries=pathQueries=shots=moveOrders=staleReads=0;allowSiege=true;deleteOnShot=false;assemblyHolds.clear();assaultQueries[0]=0;}
};
int main(){
 {Fixture f;expect("protected existing shot available without any stage",StageUnit(&f.unit,&f.target)&&shots==1&&moveOrders==0);expect("no singleton scans or path work for stationaryfire",soloQueries==0&&pathQueries==0&&assaultQueries[0]==0);expect("shot unit processed after attacks consumed",f.unit.processed);}
 {Fixture f;plan.staging=1;expect("protected realstack shot allowed despite singleton49danger",StageUnit(&f.unit,&f.target)&&shots==1&&moveOrders==0&&soloQueries==0);}
 {Fixture f;f.unit.danger=49;expect("exposed49danger cannot fire withzero dangerdefault",!StageUnit(&f.unit,&f.target)&&shots==0&&moveOrders==0);}
 {Fixture f;f.unit.danger=71;expect("exposed71danger cannot fire",!StageUnit(&f.unit,&f.target)&&shots==0);}
 {Fixture f;allowSiege=false;expect("futile siege policy remains enforced",!StageUnit(&f.unit,&f.target)&&shots==0);}
 {Fixture f;plan.ready=true;expect("committed wave retains generic execution",!StageUnit(&f.unit,&f.target)&&shots==0);}
 {Fixture f;f.unit.canFire=false;expect("illegal range orLOS cannot fire",!StageUnit(&f.unit,&f.target)&&shots==0);}
 {Fixture f;f.unit.setup=false;expect("missing required setup cannot fire",!StageUnit(&f.unit,&f.target)&&shots==0);}
 {Fixture f;f.unit.outOfAttacks=true;expect("used attack allowance cannot fire",!StageUnit(&f.unit,&f.target)&&shots==0);}
 {Fixture f;f.unit.moves=0;expect("no remaining movement cannot fire",!StageUnit(&f.unit,&f.target)&&shots==0);}
 {Fixture f;f.unit.processed=true;expect("processed unit cannot fire twice",!StageUnit(&f.unit,&f.target)&&shots==0);}
 {Fixture f;plan.staging=1;f.unit.canFire=false;expect("futureposition singleton danger remains conservative",!StageUnit(&f.unit,&f.target)&&shots==0&&moveOrders==0&&soloQueries>0&&pathQueries==0);}
 {Fixture f;dangerPercent=25;f.unit.hp=77;f.unit.danger=19;expect("existingXML dangerlimit with integerHPthreshold respected",StageUnit(&f.unit,&f.target)&&shots==1);}
 {Fixture f;dangerPercent=25;f.unit.hp=77;f.unit.danger=20;expect("one point beyondXML threshold cannot fire",!StageUnit(&f.unit,&f.target)&&shots==0);}
 {Fixture f;deleteOnShot=true;expect("mission callback deletion safelyre-resolved",StageUnit(&f.unit,&f.target)&&shots==1&&players[0].getUnit(7)==NULL&&staleReads==0);}
 printf("stationary city fire actual-source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
def run(label,body):
 fixture=prefix+usable+fire+body+tests;cpp=out/(label+'.cpp');cpp.write_text(fixture,encoding='utf-8');exe=out/(label+'.exe')
 c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/(label+'.obj')),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);(out/(label+'-compile.log')).write_text(c.stdout+c.stderr,encoding='utf-8')
 if c.returncode:print(c.stdout+c.stderr);raise SystemExit(c.returncode)
 r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);(out/(label+'-output.log')).write_text(r.stdout+r.stderr,encoding='utf-8');return r,fixture
r,fixture=run('current',stage);print(r.stdout+r.stderr,end='')
before=subprocess.check_output(['git','show','effbe594a:CvGameCoreDLL_Expansion2/CvStackingOffensiveAI.cpp'],cwd=root).decode('utf-8-sig')
control,_=run('control',function(before,'bool StageUnit('));print('Previous singleton/no-stage fire control rejected as expected' if control.returncode==1 else 'FAIL previous source did not fail assertions')
result=r.returncode or (0 if control.returncode==1 else 1)
(out/'result.json').write_text(json.dumps(dict(fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),returncode=result,output=r.stdout+r.stderr,control_commit='effbe594a',control_returncode=control.returncode,control_output=control.stdout+control.stderr,scope='Actual full StageUnit plus Usable; deterministic stack-danger/range/setup/attack/path/mission services. Stationaryfire uses existingprotectedplot danger; moving endpoints retain singleton danger. No DLLbuild/game launch.'),indent=2),encoding='utf-8');sys.exit(result)
