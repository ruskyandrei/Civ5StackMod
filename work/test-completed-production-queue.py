"""Compile actual completed-production control flow against deterministic queue/engine services.
Native VC9 x86 executable only; no full DLL build or game interaction.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(r'E:\Projects\Civ5StackMod');work=root/'work/completed-production-regression';work.mkdir(exist_ok=True)
raw=(root/'CvGameCoreDLL_Expansion2/CvCity.cpp').read_bytes();source=raw.decode('utf-8-sig').replace('\r\n','\n')
def extract(signature):
 start=source.index(signature);cur=source.index('{',start);depth=1;end=cur+1
 while depth:
  if source[end]=='{':depth+=1
  elif source[end]=='}':depth-=1
  end+=1
 return source[start:end]+'\n'
signatures=['bool CvCity::IsStackingProductionUnit(','bool CvCity::IsUnitProductionBlockedByStacking(','void CvCity::NotifyUnitProductionBlockedByStacking(','void CvCity::popOrder(','void CvCity::clearOrderQueue(','void CvCity::swapOrder(','void CvCity::doProduction(','void CvCity::doDecay(']
actual='\n'.join(extract(x) for x in signatures)
stubs=r'''
#include <algorithm>
#include <list>
#include <vector>
#include <string>
#include <cstdio>
#include <cassert>
using namespace std;typedef __int64 int64;typedef string CvString;
enum UnitTypes {NO_UNIT=-1,U0,U1,U2,U3,U4};
enum BuildingTypes {NO_BUILDING=-1,B0,B1};
enum ProjectTypes {NO_PROJECT=-1,P0};
enum ProcessTypes {NO_PROCESS=-1,R0};
enum UnitAITypes {NO_UNITAI=-1,AI0};
enum UnitClassTypes {C0,C1,C2,C3,C4};
enum OrderTypes {ORDER_TRAIN,ORDER_CONSTRUCT,ORDER_CREATE,ORDER_MAINTAIN};
enum {DOMAIN_LAND,DOMAIN_SEA,DOMAIN_AIR,DOMAIN_HOVER,NOTIFICATION_GENERIC,YIELD_PRODUCTION,ISHUMAN_AI_CITY_PRODUCTION,SelectionButtons_DIRTY_BIT,CityScreen_DIRTY_BIT,PlotListButtons_DIRTY_BIT,CityInfo_DIRTY_BIT,WONDER_CREATED,EVENT_MESSAGE_TIME=10,BUILDING_PRODUCTION_DECAY_TIME=50,BUILDING_PRODUCTION_DECAY_PERCENT=99,UNIT_PRODUCTION_DECAY_TIME=10,UNIT_PRODUCTION_DECAY_PERCENT=98};
#define VALIDATE_OBJECT()
#define PRECONDITION(a,b) assert(a)
#define ASSERT(a,b) assert(a)
#define GD_INT_GET(x) x
#define MOD_PROCESS_STOCKPILE false
namespace CvStacking {bool enabled=true;bool IsEnabled(){return enabled;}}
struct CvCity;
struct CvUnitEntry {int domain,combat,stack,unitClass;const char*text;CvUnitEntry():domain(DOMAIN_LAND),combat(10),stack(0),unitClass(0),text("warrior"){}int GetCombat()const{return combat;}int GetDomainType()const{return domain;}int GetNumberStackingUnits()const{return stack;}int GetUnitClassType()const{return unitClass;}const char*GetTextKey()const{return text;}};
struct CvBuildingEntry {int GetBuildingClassType()const{return 0;}int GetBuildingClassInfo()const{return 0;}const char*GetTextKey()const{return "building";}};
struct CvProjectEntry {const char*GetTextKey()const{return "project";}};
struct CvProcessInfo {int getDefenseValue()const{return 1;}};
struct Game {int turn;Game():turn(5){}int getGameTurn()const{return turn;}int getActiveTeam()const{return -1;}int getActivePlayer()const{return -1;}bool isDebugMode()const{return false;}};
struct Global {CvUnitEntry units[5];CvBuildingEntry buildings[2];CvProjectEntry project;CvProcessInfo process;Game game;Global(){for(int i=0;i<5;++i)units[i].unitClass=i;}CvUnitEntry*getUnitInfo(int i){return i>=0&&i<5?&units[i]:NULL;}CvBuildingEntry*getBuildingInfo(int i){return i>=0&&i<2?&buildings[i]:NULL;}CvProjectEntry*getProjectInfo(int){return &project;}CvProcessInfo*getProcessInfo(int){return &process;}int getNumUnitInfos()const{return 5;}int getNumBuildingInfos()const{return 2;}Game&getGame(){return game;}}GC;
namespace Localization {struct String {string text;String(){}String(const char*p):text(p){}String&operator<<(const char*p){text+='|';text+=p;return *this;}const char*toUTF8()const{return text.c_str();}};String Lookup(const char*p){return String(p);}}
struct CvNotifications {struct N{string message;int turn;bool dismissed;N(const char*s):message(s),turn(GC.game.turn),dismissed(false){}};vector<N>items;int GetNumNotifications()const{return items.size();}CvString GetNotificationStr(int i){return items[i].message;}bool IsNotificationDismissed(int i){return items[i].dismissed;}int GetNotificationTurn(int i){return items[i].turn;}int Add(int,const char*m,const char*,int,int,int,int){items.push_back(N(m));return items.size();}};
struct OperationSlot {bool valid;int token;OperationSlot():valid(true),token(42){}bool IsValid()const{return valid;}void Invalidate(){valid=false;}};
struct CvPlayerAI {CvNotifications notifications;int making[5],buildingsMaking,projectsMaking,uncommits;CvPlayerAI():buildingsMaking(0),projectsMaking(0),uncommits(0){fill(making,making+5,0);}void changeUnitClassMaking(int c,int n){making[c]+=n;}void changeBuildingClassMaking(int,int n){buildingsMaking+=n;}void changeProjectMaking(int,int n){projectsMaking+=n;}void CityUncommitToBuildUnitForOperationSlot(const OperationSlot&){++uncommits;}CvNotifications*GetNotifications(){return &notifications;}}owner;
#define GET_PLAYER(x) owner
struct Team {int projects;Team():projects(0){}void changeProjectMaking(int,int n){projects+=n;}}team;
#define GET_TEAM(x) team
struct UI {void setDirty(int,bool){}void AddCityMessage(...){}void AddDeferredWonderCommand(...){} }ui;
#define DLLUI (&ui)
bool isLimitedUnitClass(int){return false;}bool isLimitedWonderClass(int){return false;}bool isLimitedProject(int){return false;}bool isWorldWonderClass(int){return false;}
struct ICvCity1 {virtual~ICvCity1(){}};struct CvDllCity:ICvCity1{CvDllCity(CvCity*){}};template<class T>struct CvInterfacePtr{T*p;CvInterfacePtr(T*q):p(q){}~CvInterfacePtr(){delete p;}T*get(){return p;}};
struct OrderData {OrderTypes eOrderType;int iData1,iData2;bool bSave;OrderData(OrderTypes e=ORDER_TRAIN,int a=0,int b=AI0,bool s=false):eOrderType(e),iData1(a),iData2(b),bSave(s){}};
struct Queue {list<OrderData> data;void deleteNode(OrderData*p){for(list<OrderData>::iterator i=data.begin();i!=data.end();++i)if(&*i==p){data.erase(i);return;}assert(false);}void swapUp(int index){list<OrderData>::iterator a=data.begin();for(int n=0;n<index&&a!=data.end();++n)++a;list<OrderData>::iterator b=a;if(b!=data.end())++b;if(a!=data.end()&&b!=data.end())std::swap(*a,*b);}};
struct CityBuildings {int production[2],time[2];CityBuildings(){fill(production,production+2,0);fill(time,time+2,0);}int GetBuildingProduction(int i)const{return production[i];}void ChangeBuildingProductionTime(int i,int n){time[i]+=n;}int GetBuildingProductionTime(int i)const{return time[i];}void SetBuildingProduction(int i,int n){production[i]=n;}void SetBuildingProductionTime(int i,int n){time[i]=n;}};
struct CvCity {
 Queue m_orderQueue;OperationSlot m_unitBeingBuiltForOperation;CityBuildings buildings;CityBuildings*m_pCityBuildings;
 bool space,human,automated,dirty;int progress[5],cost[5],age[5];int yield100,overflow100,feature100,created,buildingCreates,projectCreates,chooseAI,chooseHuman,pushes,stops,starts,cleanups,strengthUpdates,producedType;
 CvCity():m_pCityBuildings(&buildings),space(false),human(false),automated(false),dirty(false),yield100(100),overflow100(0),feature100(0),created(0),buildingCreates(0),projectCreates(0),chooseAI(0),chooseHuman(0),pushes(0),stops(0),starts(0),cleanups(0),strengthUpdates(0),producedType(NO_UNIT){fill(progress,progress+5,0);fill(cost,cost+5,100);fill(age,age+5,0);}
 int getOwner()const{return 0;}int getTeam()const{return 0;}int GetID()const{return 1;}int GetIDInfo()const{return 1;}int getX()const{return 1;}int getY()const{return 2;}const char*getNameKey()const{return "City";}
 bool CanPlaceUnitHere(int)const{return space;}bool IsStackingProductionUnit(UnitTypes)const;bool IsUnitProductionBlockedByStacking(UnitTypes)const;void NotifyUnitProductionBlockedByStacking(UnitTypes)const;
 OrderData*headOrderQueueNode(){return m_orderQueue.data.empty()?NULL:&m_orderQueue.data.front();}const OrderData*headOrderQueueNode()const{return m_orderQueue.data.empty()?NULL:&m_orderQueue.data.front();}
 OrderData*nextOrderQueueNode(OrderData*p){for(list<OrderData>::iterator i=m_orderQueue.data.begin();i!=m_orderQueue.data.end();++i)if(&*i==p){++i;return i==m_orderQueue.data.end()?NULL:&*i;}return NULL;}
 int getOrderQueueLength()const{return m_orderQueue.data.size();}
 void pushOrder(OrderTypes e,int a,int b,bool repeat,bool pop,bool append){if(pop)clearOrderQueue();OrderData order(e,a,b,repeat);if(append)m_orderQueue.data.push_back(order);else m_orderQueue.data.push_front(order);if(e==ORDER_TRAIN)++owner.making[a];else if(e==ORDER_CONSTRUCT)++owner.buildingsMaking;else if(e==ORDER_CREATE){++owner.projectsMaking;++team.projects;}++pushes;}
 void seed(OrderTypes e,int a,bool repeat=false){pushOrder(e,a,AI0,repeat,false,true);}
 void popOrder(int i,bool finish=false,bool choose=false);void clearOrderQueue();void swapOrder(int);void doProduction(bool);void doDecay();
 void stopHeadOrder(){++stops;}void startHeadOrder(){++starts;}void CleanUpQueue(){++cleanups;}void updateStrengthValue(){++strengthUpdates;}
 bool isCitySelected()const{return false;}bool isHuman(int)const{return human;}bool isProductionAutomated()const{return automated;}bool AI_isChooseProductionDirty()const{return dirty;}
 void AI_chooseProduction(bool,bool){++chooseAI;clearOrderQueue();seed(ORDER_CONSTRUCT,B1);dirty=false;}void chooseProduction(UnitTypes,BuildingTypes,ProjectTypes,bool){++chooseHuman;}
 UnitTypes getProductionUnit()const{const OrderData*p=headOrderQueueNode();return p&&p->eOrderType==ORDER_TRAIN?(UnitTypes)p->iData1:NO_UNIT;}BuildingTypes getProductionBuilding()const{const OrderData*p=headOrderQueueNode();return p&&p->eOrderType==ORDER_CONSTRUCT?(BuildingTypes)p->iData1:NO_BUILDING;}
 bool isProduction()const{return headOrderQueueNode()!=NULL;}bool isProductionProcess()const{return headOrderQueueNode()&&headOrderQueueNode()->eOrderType==ORDER_MAINTAIN;}bool isProductionBuilding()const{return getProductionBuilding()!=NO_BUILDING;}bool isProductionLimited()const{return false;}const char*getProductionNameKey()const{return "next";}
 int getUnitProductionTimes100(UnitTypes e)const{return progress[e];}int getProductionNeeded(UnitTypes e)const{return cost[e];}int getProductionNeeded()const{return getProductionUnit()==NO_UNIT?1000:getProductionNeeded(getProductionUnit());}
 int getUnitProduction(UnitTypes e)const{return progress[e]/100;}void setUnitProduction(UnitTypes e,int n){progress[e]=n*100;}int getUnitProductionTime(UnitTypes e)const{return age[e];}void changeUnitProductionTime(UnitTypes e,int n){age[e]+=n;}void setUnitProductionTime(UnitTypes e,int n){age[e]=n;}
 int getYieldRateTimes100(int)const{return yield100;}int getTotalOverflowProductionTimes100()const{return overflow100+feature100;}void setOverflowProduction(int n){overflow100=n*100;}void setFeatureProduction(int n){feature100=n*100;}void changeOverflowProductionTimes100(int n){overflow100+=n;}
 void changeProductionTimes100(int n){UnitTypes e=getProductionUnit();if(e!=NO_UNIT)progress[e]+=n;else if(isProductionBuilding())buildings.production[getProductionBuilding()]+=n/100;}
 int getProduction()const{UnitTypes e=getProductionUnit();return e==NO_UNIT?(isProductionBuilding()?buildings.production[getProductionBuilding()]:0):progress[e]/100;}
 // Deterministic production service: real produce accounting/traits are separately extracted/tested in accounting-source-test.cpp.
 void produce(UnitTypes e){++created;producedType=e;int excess=progress[e]-cost[e]*100;overflow100+=max(0,excess);progress[e]=0;}
 void produce(BuildingTypes){++buildingCreates;}void produce(ProjectTypes){++projectCreates;}
};
'''
tests=r'''
static int checks=0,failed=0;static void expect(const char*n,int a,int e){++checks;if(a!=e){++failed;printf("FAIL %s actual=%d expected=%d\n",n,a,e);}}
struct Fixture {CvCity city;Fixture(){owner=CvPlayerAI();GC=Global();team=Team();CvStacking::enabled=true;}};
int main(){
 {Fixture f;f.city.seed(ORDER_TRAIN,U0,true);f.city.seed(ORDER_TRAIN,U1);f.city.progress[U0]=12567;OrderData*original=f.city.headOrderQueueNode();int pushes=f.city.pushes;for(int n=0;n<3;++n)f.city.popOrder(0,true,true);expect("blocked queue count unchanged",f.city.getOrderQueueLength(),2);expect("blocked node identity retained",f.city.headOrderQueueNode()==original,1);expect("blocked repeated order not appended",f.city.pushes,pushes);expect("blocked primary making retained",owner.making[U0],1);expect("blocked secondary making retained",owner.making[U1],1);expect("blocked operation retained",f.city.m_unitBeingBuiltForOperation.IsValid(),1);expect("blocked no uncommit",owner.uncommits,0);expect("blocked exact fractional progress",f.city.progress[U0],12567);expect("blocked no create",f.city.created,0);expect("blocked no start/stop",f.city.starts+f.city.stops,0);expect("blocked no cleanup",f.city.cleanups,0);expect("blocked no choose",f.city.chooseAI+f.city.chooseHuman,0);expect("blocked notice dedup",owner.notifications.items.size(),1);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U0,true);f.city.seed(ORDER_TRAIN,U1);f.city.progress[U0]=12567;f.city.popOrder(0,true,true);f.city.space=true;f.city.popOrder(0,true,true);expect("release one creation",f.city.created,1);expect("release exact type",f.city.producedType,U0);expect("release removes head and appends one repeat",f.city.getOrderQueueLength(),2);expect("release next preserved",f.city.headOrderQueueNode()->iData1,U1);expect("release repeat correct",f.city.m_orderQueue.data.back().iData1,U0);expect("release repeat flag retained",f.city.m_orderQueue.data.back().bSave,1);expect("release making repeat net unchanged",owner.making[U0],1);expect("release other making unchanged",owner.making[U1],1);expect("release operation invalidated",f.city.m_unitBeingBuiltForOperation.IsValid(),0);expect("release uncommit once",owner.uncommits,1);expect("release start once",f.city.starts,1);expect("release stop once",f.city.stops,1);expect("release cleanup once",f.city.cleanups,1);expect("release progress consumed",f.city.progress[U0],0);expect("release stub service overflow",f.city.overflow100,2567);expect("release no needless AI choose",f.city.chooseAI,0);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U0,true);f.city.seed(ORDER_TRAIN,U1,true);f.city.progress[0]=11111;f.city.progress[1]=12222;f.city.popOrder(-1,true,false);expect("negative index finishing last deferred",f.city.getOrderQueueLength(),2);f.city.popOrder(9,true,false);expect("invalid index no mutation",f.city.getOrderQueueLength(),2);f.city.clearOrderQueue();expect("blocked clear terminates",f.city.getOrderQueueLength(),0);expect("clear no creates",f.city.created,0);expect("clear no repeat append",f.city.pushes,2);expect("clear making balances",owner.making[0]+owner.making[1],0);expect("clear operation released once",owner.uncommits,1);expect("clear production0 preserved",f.city.progress[0],11111);expect("clear production1 preserved",f.city.progress[1],12222);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U0,true);f.city.seed(ORDER_CONSTRUCT,B0);f.city.progress[0]=10555;f.city.swapOrder(0);expect("explicit swap allowed on completed head",f.city.getProductionBuilding(),B0);expect("swap keeps completed unit queued",f.city.m_orderQueue.data.back().iData1,U0);expect("swap retains progress",f.city.progress[0],10555);expect("swap retains making",owner.making[0],1);expect("swap retains operation",f.city.m_unitBeingBuiltForOperation.IsValid(),1);f.city.AI_chooseProduction(false,false);expect("intentional AI replacement remains available",f.city.chooseAI,1);expect("explicit replacement removes unit order",owner.making[0],0);expect("explicit replacement preserves paid progress",f.city.progress[0],10555);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U0,true);f.city.progress[0]=10000;f.city.dirty=true;f.city.yield100=123;f.city.overflow100=234;f.city.feature100=56;f.city.doProduction(false);expect("routine AI dirty skipped for ready unit",f.city.chooseAI,0);expect("ready head remains",f.city.getProductionUnit(),U0);expect("blocked ready retains daily yield plus old overflow",f.city.progress[0],10413);expect("blocked transfers overflow once",f.city.overflow100,0);expect("blocked feature transfer once",f.city.feature100,0);expect("blocked ready repeat unchanged",f.city.getOrderQueueLength(),1);expect("blocked operation remains",f.city.m_unitBeingBuiltForOperation.IsValid(),1);f.city.doProduction(false);expect("second blocked turn adds only daily yield",f.city.progress[0],10536);expect("second blocked no choose",f.city.chooseAI,0);expect("second blocked no completion",f.city.created,0);f.city.space=true;f.city.doProduction(false);expect("ready open completion once",f.city.created,1);expect("ready open head protected until retry",f.city.chooseAI,0);expect("repeat release exactly one remains",f.city.getOrderQueueLength(),1);expect("ready release pays progress",f.city.progress[0],0);expect("ready release expected overflow",f.city.overflow100,659);expect("ready release making exactly1",owner.making[0],1);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U0);f.city.progress[0]=9999;f.city.dirty=true;f.city.doProduction(false);expect("unfinished AI dirty still reconsiders",f.city.chooseAI,1);expect("unfinished head replaced by intentional AI",f.city.getProductionBuilding(),B1);expect("unfinished production retained",f.city.progress[0],9999);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U0);f.city.progress[0]=10000;f.city.dirty=true;f.city.human=true;f.city.automated=true;f.city.doProduction(false);expect("automated human ready protected",f.city.chooseAI,0);expect("automated human completion deferred",f.city.created,0);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U0);f.city.progress[0]=10000;f.city.dirty=true;CvStacking::enabled=false;f.city.doProduction(false);expect("disabled restores routine AI dirty choice",f.city.chooseAI,1);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U0);f.city.progress[0]=10000;f.city.dirty=true;GC.units[0].combat=0;f.city.doProduction(false);expect("civilian dirty choice unchanged",f.city.chooseAI,1);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U0);f.city.progress[0]=10000;f.city.space=true;f.city.human=true;f.city.doProduction(false);expect("human open createsonce",f.city.created,1);expect("human empty prompts choose",f.city.chooseHuman,1);expect("human completed making decremented",owner.making[0],0);f.city.doProduction(false);expect("no head no duplicate creation",f.city.created,1);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U0);f.city.progress[0]=10000;f.city.space=true;f.city.doProduction(false);expect("AI open createsonce",f.city.created,1);expect("AI empty queue chooses afterward",f.city.chooseAI,1);expect("AI subsequent item selected",f.city.getProductionBuilding(),B1);}
 {Fixture f;f.city.human=true;f.city.doProduction(false);expect("disallowed empty production no overflow",f.city.overflow100,0);f.city.doProduction(true);expect("allowed empty production accrues overflow",f.city.overflow100,100);}
 {Fixture f;f.city.seed(ORDER_CONSTRUCT,B0);f.city.human=true;f.city.progress[0]=10055;f.city.progress[1]=9999;f.city.progress[2]=10000;f.city.progress[3]=10000;f.city.progress[4]=10000;GC.units[2].combat=0;GC.units[3].domain=DOMAIN_AIR;GC.units[4].stack=1;for(int i=0;i<5;++i)f.city.age[i]=10;f.city.buildings.production[1]=100;f.city.buildings.time[1]=50;f.city.doDecay();expect("completed ordinary off-head exact progress preserved",f.city.progress[0],10055);expect("completed ordinary age unchanged",f.city.age[0],10);expect("unfinished ordinary decay retained",f.city.progress[1],9700);expect("unfinished ordinary time advances",f.city.age[1],11);expect("civilian decay retained",f.city.progress[2],9800);expect("air decay retained",f.city.progress[3],9800);expect("support decay retained",f.city.progress[4],9800);expect("building decay retained",f.city.buildings.production[1],99);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U1);f.city.human=true;f.city.progress[0]=10000;f.city.age[0]=10;CvStacking::enabled=false;f.city.doDecay();expect("disabled completed decay retained",f.city.progress[0],9800);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U1);f.city.human=false;f.city.progress[0]=9000;f.city.age[0]=10;f.city.doDecay();expect("AI unfinished no human decay",f.city.progress[0],9000);expect("AI unfinished age tracks normally",f.city.age[0],11);}
 {Fixture f;f.city.seed(ORDER_TRAIN,U0);f.city.progress[0]=10000;f.city.human=true;f.city.age[0]=20;f.city.age[1]=20;f.city.doDecay();expect("current head paid progress unchanged",f.city.progress[0],10000);expect("empty unit resets age",f.city.age[1],0);}
 {Fixture f;f.city.seed(ORDER_CONSTRUCT,B0);f.city.popOrder(0,true,false);expect("building completion unaffected",f.city.buildingCreates,1);expect("building making balanced",owner.buildingsMaking,0);}
 {Fixture f;f.city.seed(ORDER_CREATE,P0);f.city.popOrder(0,true,false);expect("project completion unaffected",f.city.projectCreates,1);expect("project making balanced",owner.projectsMaking+team.projects,0);}
 {Fixture f;f.city.seed(ORDER_MAINTAIN,R0);f.city.popOrder(0,false,false);expect("process removal unaffected",f.city.getOrderQueueLength(),0);expect("defense process strength update",f.city.strengthUpdates,1);}
 printf("completed production queue/control flow: %d checks, %d failures\n",checks,failed);return failed?1:0;
}
'''
cpp=work/'queue-source-test.cpp';cpp.write_text(stubs+'\n'+actual+'\n'+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=work/'queue-source-test.exe';compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/Od','/Z7',str(cpp),'/Fo'+str(work/'queue-source-test.obj'),'/Fe'+str(exe)],cwd=work,env=env,capture_output=True,text=True,timeout=30)
(work/'queue-compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=work,env=env,capture_output=True,text=True,timeout=10);print(run.stdout+run.stderr,end='')
result=dict(source_file_sha256=hashlib.sha256(raw).hexdigest().upper(),extracted_sha256=hashlib.sha256(actual.encode()).hexdigest().upper(),extracted_signatures=signatures,compile_returncode=compiled.returncode,test_returncode=run.returncode,output=run.stdout+run.stderr,scope='Actual complete helper/popOrder/clearOrderQueue/swapOrder/doProduction/doDecay bodies; deterministic queue, engine/UI and production service stubs. Actual produce accounting separately covered in accounting-result.json. No VP DLL build/game.')
if '--mutations' in sys.argv and run.returncode==0:
 mutations=[
 ('remove_pop_deferral', 'if (bFinish && pOrderNode->eOrderType == ORDER_TRAIN &&\n\t\tIsUnitProductionBlockedByStacking', 'if (false && bFinish && pOrderNode->eOrderType == ORDER_TRAIN &&\n\t\tIsUnitProductionBlockedByStacking'),
 ('remove_ready_ai_preservation', '&& !bPreserveCompletedHead)', '&& true)'),
 ('remove_completed_decay_protection', 'if (IsStackingProductionUnit(eUnit) && static_cast<int64>', 'if (false && IsStackingProductionUnit(eUnit) && static_cast<int64>')]
 mutation_results=[]
 for name,before,after in mutations:
  assert actual.count(before)==1,(name,actual.count(before))
  mutated=actual.replace(before,after,1)
  testcpp=work/(name+'.cpp');testcpp.write_text(stubs+'\n'+mutated+'\n'+tests,encoding='utf-8');testexe=work/(name+'.exe')
  c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/Od',str(testcpp),'/Fo'+str(work/(name+'.obj')),'/Fe'+str(testexe)],cwd=work,env=env,capture_output=True,text=True,timeout=30)
  (work/(name+'-compile.log')).write_text(c.stdout+c.stderr,encoding='utf-8')
  if c.returncode:raise RuntimeError('Mutation failed to compile: '+name+'\n'+c.stdout+c.stderr)
  test=subprocess.run([str(testexe)],cwd=work,env=env,capture_output=True,text=True,timeout=10)
  (work/(name+'-output.log')).write_text(test.stdout+test.stderr,encoding='utf-8')
  mutation_results.append(dict(name=name,compile_returncode=c.returncode,test_returncode=test.returncode,detected=test.returncode!=0,explicit_failed_assertions=test.stdout.count('FAIL '),output=test.stdout+test.stderr))
  assert test.returncode!=0,'Tests did not detect mutation '+name
 result['mutation_sensitivity']=mutation_results
 print('Mutations detected: '+str(len(mutation_results)))
(work/'queue-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');sys.exit(run.returncode)
