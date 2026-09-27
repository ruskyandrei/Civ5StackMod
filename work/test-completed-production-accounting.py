"""Exercise actual deferral helpers/notification code and existing unit-production accounting.
No VP DLL build or game execution. Engine services are deterministic stubs.
"""
from pathlib import Path
import os,subprocess,hashlib,json,sys,xml.etree.ElementTree as ET
root=Path(r'E:\Projects\Civ5StackMod');work=root/'work/completed-production-regression';work.mkdir(exist_ok=True)
raw=(root/'CvGameCoreDLL_Expansion2/CvCity.cpp').read_bytes();source=raw.decode('utf-8-sig').replace('\r\n','\n')
start=source.index('bool CvCity::IsStackingProductionUnit(');end=source.index('/// Create unit by completing production',start);helpers=source[start:end]
start=source.index('void CvCity::produce(UnitTypes');body=source.index('\n\tif (pUnit)',start);prefix=source[start:body]
acct=source.index('\t\tint iProductionNeeded = getProductionNeeded(eTrainUnit) * 100;',body)
acctend=source.index('\n\t}\n\telse\n\t{\n\t\t// create notification',acct)
accounting=source[acct:acctend]
actual=helpers+'\n'+prefix+'\n\tif(pUnit){ ++successes; investment=false;\n'+accounting+'\n\t}\n}\n'
stubs=r'''
#include <vector>
#include <string>
#include <algorithm>
#include <cstdio>
#include <cassert>
using namespace std;typedef __int64 int64;typedef string CvString;
typedef int UnitTypes;typedef int UnitAITypes;
enum {NO_UNIT=-1,NO_UNITAI=-1,NO_PLAYER=-1,NO_BUILDING=-1,NO_GREATPERSON=-1,DOMAIN_LAND,DOMAIN_SEA,DOMAIN_AIR,DOMAIN_HOVER,REASON_TRAIN,NOTIFICATION_GENERIC,INSTANT_YIELD_TYPE_U_PROD,YIELD_PRODUCTION,MAXED_UNIT_GOLD_PERCENT=100};
#define GD_INT_GET(x) x
#define VALIDATE_OBJECT()
namespace CvStacking {static bool enabled=true;bool IsEnabled(){return enabled;}}
struct CvUnitEntry {int domain,combat,stack;const char*text;CvUnitEntry():domain(DOMAIN_LAND),combat(10),stack(0),text("warrior"){}int GetCombat()const{return combat;}int GetDomainType()const{return domain;}int GetNumberStackingUnits()const{return stack;}const char*GetTextKey()const{return text;}};
struct Game {int turn;Game():turn(5){}int getGameTurn()const{return turn;}};
struct Global {CvUnitEntry info[5];Game game;const CvUnitEntry*getUnitInfo(int i)const{return i>=0&&i<5?&info[i]:NULL;}Game&getGame(){return game;}}GC;
namespace Localization {struct String {string text;String(const char*p):text(p){}String&operator<<(const char*p){text+='|';text+=p;return *this;}const char*toUTF8()const{return text.c_str();}};String Lookup(const char*p){return String(p);}}
struct CvNotifications {struct N{string message;int turn;bool dismissed;N(const char*s):message(s),turn(GC.game.turn),dismissed(false){}};vector<N>items;int GetNumNotifications()const{return items.size();}CvString GetNotificationStr(int i){return items[i].message;}bool IsNotificationDismissed(int i){return items[i].dismissed;}int GetNotificationTurn(int i){return items[i].turn;}int Add(int,const char*m,const char*,int,int,int,int){items.push_back(N(m));return items.size();}};
struct Treasury {int gold100;Treasury():gold100(0){}void ChangeGoldTimes100(int n){gold100+=n;}};
struct CvPlayerAI {CvNotifications notifications;Treasury treasury;int rewards;CvPlayerAI():rewards(0){}CvNotifications*GetNotifications(){return &notifications;}Treasury*GetTreasury(){return &treasury;}void doInstantYield(...){++rewards;}};
static CvPlayerAI owner;
#define GET_PLAYER(x) owner
struct CvUnit {bool civilian;CvUnit():civilian(false){}bool IsCivilianUnit()const{return civilian;}};
struct CvCity {bool space,investment;int cityid,m_iThingsProduced,created,successes,production100,cost,yield100,overflow100;CvUnit result;
 CvCity():space(false),investment(true),cityid(1),m_iThingsProduced(0),created(0),successes(0),production100(10000),cost(100),yield100(1300),overflow100(0){}
 int getOwner()const{return 0;}int GetID()const{return cityid;}int getX()const{return 1;}int getY()const{return 2;}const char*getNameKey()const{return cityid==1?"CityA":"CityB";}
 bool CanPlaceUnitHere(int)const{return space;}bool IsStackingProductionUnit(UnitTypes)const;bool IsUnitProductionBlockedByStacking(UnitTypes)const;void NotifyUnitProductionBlockedByStacking(UnitTypes)const;
 CvUnit*CreateUnit(int type,int,int){++created;result.civilian=GC.info[type].combat==0;return &result;}
 int getProductionNeeded(int)const{return cost;}int getUnitProductionTimes100(int)const{return production100;}int getYieldRateTimes100(int)const{return yield100;}
 void changeOverflowProductionTimes100(int n){overflow100+=n;}void setUnitProduction(int,int n){production100=n*100;}void changeUnitProductionTimes100(int,int n){production100+=n;}
 void produce(UnitTypes e,UnitAITypes ai=NO_UNITAI,bool overflow=true);int getProductionUnit()const{return 0;}
};
'''
tests=r'''
static int checks=0,failed=0;
static void expect(const char*n,int a,int e){++checks;if(a!=e){++failed;printf("FAIL %s actual=%d expected=%d\n",n,a,e);}}
struct Fixture {CvCity city;Fixture(){owner=CvPlayerAI();GC=Global();CvStacking::enabled=true;}};
int main(){
 {Fixture f;expect("ordinary land gated",f.city.IsStackingProductionUnit(0),1);expect("closed city defers",f.city.IsUnitProductionBlockedByStacking(0),1);f.city.space=true;expect("open slot permits completion",f.city.IsUnitProductionBlockedByStacking(0),0);}
 {Fixture f;GC.info[0].domain=DOMAIN_SEA;expect("sea gated",f.city.IsStackingProductionUnit(0),1);GC.info[0].domain=DOMAIN_AIR;expect("air unchanged",f.city.IsStackingProductionUnit(0),0);GC.info[0].domain=DOMAIN_HOVER;expect("other domain unchanged",f.city.IsStackingProductionUnit(0),0);GC.info[0].domain=DOMAIN_LAND;GC.info[0].combat=0;expect("civilian unchanged",f.city.IsStackingProductionUnit(0),0);GC.info[0].combat=10;GC.info[0].stack=1;expect("support unchanged",f.city.IsStackingProductionUnit(0),0);}
 {Fixture f;expect("invalid unit ignored",f.city.IsStackingProductionUnit(-1),0);CvStacking::enabled=false;expect("disabled unchanged",f.city.IsStackingProductionUnit(0),0);}
 {Fixture f;f.city.production100=13457;f.city.produce(0);expect("blocked retains exact fractional progress",f.city.production100,13457);expect("blocked has no unit creation",f.city.created,0);expect("blocked no things-produced increment",f.city.m_iThingsProduced,0);expect("blocked retains investment",f.city.investment,1);expect("blocked no completion rewards",owner.rewards,0);expect("blocked no gold transfer",owner.treasury.gold100,0);expect("blocked no overflow transfer",f.city.overflow100,0);expect("blocked notification",owner.notifications.items.size(),1);f.city.produce(0);expect("same-turn notification deduplicated",owner.notifications.items.size(),1);}
 {Fixture f;f.city.NotifyUnitProductionBlockedByStacking(0);owner.notifications.items[0].dismissed=true;f.city.NotifyUnitProductionBlockedByStacking(0);expect("dismissed notice not repeated same turn",owner.notifications.items.size(),1);++GC.game.turn;f.city.NotifyUnitProductionBlockedByStacking(0);expect("dismissed notice can repeat next turn",owner.notifications.items.size(),2);++GC.game.turn;f.city.NotifyUnitProductionBlockedByStacking(0);expect("active notice deduplicated across turns",owner.notifications.items.size(),2);f.city.cityid=2;f.city.NotifyUnitProductionBlockedByStacking(0);expect("different city gets own notice",owner.notifications.items.size(),3);GC.info[0].text="archer";f.city.NotifyUnitProductionBlockedByStacking(0);expect("different unit gets own notice",owner.notifications.items.size(),4);}
 {Fixture f;f.city.production100=12567;f.city.produce(0);f.city.space=true;f.city.produce(0);expect("one created after release",f.city.created,1);expect("one things-produced after release",f.city.m_iThingsProduced,1);expect("one completion reward after release",owner.rewards,1);expect("investment consumed only at completion",f.city.investment,0);expect("released production consumed",f.city.production100,0);expect("fractional normal overflow retained",f.city.overflow100,2567);expect("no excess gold below overflow limit",owner.treasury.gold100,0);}
 {Fixture f;f.city.production100=35789;f.city.produce(0);expect("excess blocked progress preserved",f.city.production100,35789);f.city.space=true;f.city.produce(0);expect("normal overflow cap",f.city.overflow100,10000);expect("normal excess gold once",owner.treasury.gold100,15789);expect("one excess completion",f.city.created,1);}
 {Fixture f;f.city.production100=24567;f.city.produce(0,NO_UNITAI,false);expect("siphon blocked progress intact",f.city.production100,24567);expect("siphon blocked no rewards",owner.rewards,0);f.city.space=true;f.city.produce(0,NO_UNITAI,false);expect("siphon subtracts one cost only",f.city.production100,14567);expect("siphon does not touch overflow",f.city.overflow100,0);expect("siphon no gold conversion",owner.treasury.gold100,0);expect("siphon one creation",f.city.created,1);}
 {Fixture f;CvStacking::enabled=false;f.city.produce(0);expect("disabled full-city fallback retained",f.city.created,1);}
 {Fixture f;GC.info[0].combat=0;f.city.produce(0);expect("civilian legacy completion",f.city.created,1);expect("civilian no combat production reward",owner.rewards,0);}
 printf("completed production accounting: %d checks, %d failures\n",checks,failed);return failed?1:0;
}
'''
cpp=work/'accounting-source-test.cpp';cpp.write_text(stubs+actual+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=work/'accounting-source-test.exe';compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/Od','/Z7',str(cpp),'/Fo'+str(work/'accounting-source-test.obj'),'/Fe'+str(exe)],cwd=work,env=env,capture_output=True,text=True,timeout=30)
(work/'accounting-compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=work,env=env,capture_output=True,text=True,timeout=10);print(run.stdout+run.stderr,end='')
xml=ET.parse(root/'(1) Community Patch/Database Changes/StackingConfig.xml');rows=xml.findall('./Language_en_US/Row');tags=[r.attrib['Tag'] for r in rows];assert tags.count('TXT_KEY_STACKING_UNIT_READY_NO_SPACE')==1 and tags.count('TXT_KEY_STACKING_UNIT_READY_NO_SPACE_SUMMARY')==1
result={'source_file_sha256':hashlib.sha256(raw).hexdigest().upper(),'extracted_sha256':hashlib.sha256(actual.encode()).hexdigest().upper(),'compile_returncode':compiled.returncode,'test_returncode':run.returncode,'output':run.stdout+run.stderr,'xml_localization_rows_valid':True,'scope':'actual helper/notification/produce preflight and unchanged production accounting with engine stubs; traits/CreateUnit effects stubbed; no VP DLL build or game'}
(work/'accounting-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');sys.exit(run.returncode)
