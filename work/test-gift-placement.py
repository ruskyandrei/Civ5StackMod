"""Exercise the actual gift preflight, canGift and gift bodies using engine stubs.
No VP DLL build, game launch, or installation changes.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];work=root/'work/gift-regression';work.mkdir(exist_ok=True)
source=(root/'CvGameCoreDLL_Expansion2/CvUnit.cpp').read_text(encoding='utf-8-sig')
start=source.index('static bool CanGiftStackInPlace(')
end=source.index('// Long-distance gift to a city state',start)
actual=source[start:end]
prefix=r'''
#include <vector>
#include <string>
#include <cstdio>
#include <cassert>
using namespace std;
typedef int PlayerTypes;typedef int UnitClassTypes;typedef string CvString;
enum DomainTypes {DOMAIN_LAND,DOMAIN_SEA,DOMAIN_AIR,DOMAIN_HOVER};
enum {NO_PLAYER=-1,NO_UNITCLASS=-1,UNITAI_EXPLORE=10,REASON_GIFT=1,GAMEEVENTRETURN_FALSE=0};
#define VALIDATE_OBJECT()
#define PRECONDITION(x,y) assert(x)
#define ASSERT(x,y) assert(x)
#define GD_INT_GET(x) 10
static bool MOD_CORE_NO_INTERMAJOR_UNIT_GIFTING=false,MOD_EVENTS_MINORS_INTERACTION=false;
struct CvUnit;struct CvPlot;
static int TestGiftHook();
#define GAMEEVENTINVOKE_TESTALL(...) TestGiftHook()
struct IDInfo {CvUnit* unit;IDInfo(CvUnit*p):unit(p){}};
CvUnit* GetPlayerUnit(const IDInfo&i){return i.unit;}
struct Religion {int value,strength,spreads;Religion():value(0),strength(0),spreads(0){}void SetReligion(int v){value=v;}void SetReligiousStrength(int v){strength=v;}void SetSpreadsUsed(int v){spreads=v;}int GetReligion()const{return value;}int GetReligiousStrength()const{return strength;}int GetSpreadsUsed()const{return spreads;}};
struct UnitInfo {int ai;bool spread,remove;UnitInfo():ai(0),spread(false),remove(false){}int GetDefaultUnitAIType()const{return ai;}bool IsSpreadReligion()const{return spread;}bool IsRemoveHeresy()const{return remove;}};
struct Traits {int greatPerson;Traits():greatPerson(0){}int GetGreatPersonGiftInfluence()const{return greatPerson;}};
struct MinorAI {int benefits;MinorAI():benefits(0){}void DoUnitGiftFromMajor(int,CvUnit*,bool){++benefits;}};
struct CvTeam {bool war[4],maxed;CvTeam():maxed(false){for(int i=0;i<4;++i)war[i]=false;}bool isUnitClassMaxedOut(int,int)const{return maxed;}int getUnitClassMaking(int)const{return 0;}};
struct CvPlayer {int id,team,created;bool minor,major,maxed;Traits traits;MinorAI ai;CvPlayer():id(0),team(0),created(0),minor(false),major(true),maxed(false){}int getTeam()const{return team;}bool isMinorCiv()const{return minor;}bool isMajorCiv()const{return major;}bool isUnitClassMaxedOut(int,int)const{return maxed;}int getUnitClassMaking(int)const{return 0;}Traits*GetPlayerTraits(){return &traits;}CvUnit*initUnit(int,int,int,int,int,bool,bool);MinorAI*GetMinorCivAI(){return &ai;}const char*getNameKey()const{return "player";}};
static CvPlayer players[4];static CvTeam teams[4];
#define GET_PLAYER(x) players[x]
#define GET_TEAM(x) teams[x]
static bool atWar(int a,int b){return teams[a].war[b];}
struct CvPlot {int owner,x,y;bool city,hostile;vector<IDInfo> units;CvPlot():owner(1),x(4),y(6),city(false),hostile(false){}bool isOwned()const{return owner>=0;}int getOwner()const{return owner;}int getTeam()const{return players[owner].team;}bool isCity()const{return city;}bool isVisibleEnemyUnit(int)const{return hostile;}bool isVisibleEnemyUnit(const CvUnit*)const{return hostile;}IDInfo*headUnitNode()const{return units.empty()?NULL:const_cast<IDInfo*>(&units[0]);}IDInfo*nextUnitNode(const IDInfo*p)const{size_t i=p-&units[0]+1;return i<units.size()?const_cast<IDInfo*>(&units[i]):NULL;}void add(CvUnit&u){units.push_back(IDInfo(&u));}};
struct CvUnit {int m_eOwner,id,damage,danger,unitClass,giftedBy;DomainTypes domain;bool combat,support,cargo,dead,delayed,native,found,abroad,great;CvPlot*location;CvUnit*transport;UnitInfo info;Religion religion;
 CvUnit(int owner=0,DomainTypes d=DOMAIN_LAND):m_eOwner(owner),id(owner+10),damage(0),danger(0),unitClass(0),giftedBy(-1),domain(d),combat(true),support(false),cargo(false),dead(false),delayed(false),native(true),found(false),abroad(false),great(false),location(NULL),transport(NULL){}
 int getOwner()const{return m_eOwner;}int getTeam()const{return players[m_eOwner].team;}int getDamage()const{return damage;}int GetDanger()const{return danger;}int GetID()const{return id;}int GetIDInfo()const{return id;}int getUnitType()const{return 0;}int getUnitClassType()const{return unitClass;}int AI_getUnitAIType()const{return 0;}int getX()const{return location->x;}int getY()const{return location->y;}
 bool IsCombatUnit()const{return combat;}bool IsStackingUnit()const{return support;}bool isCargo()const{return cargo;}bool IsDead()const{return dead;}bool isDelayedDeath()const{return delayed;}DomainTypes getDomainType()const{return domain;}CvPlot*plot()const{return location;}bool isNativeDomain(const CvPlot*)const{return native;}const CvUnit*getTransportUnit()const{return transport;}bool isFound()const{return found;}bool IsFoundAbroad()const{return abroad;}bool IsGreatPerson()const{return great;}const UnitInfo&getUnitInfo()const{return info;}const char*getNameKey()const{return "unit";}
 void kill(bool delay){delayed=true;dead=!delay;}void convert(CvUnit*old,bool,bool){domain=old->domain;old->kill(true);}void setupGraphical(){}Religion*GetReligionDataMutable(){return &religion;}const Religion*GetReligionData()const{return &religion;}void SetGiftedByPlayer(int p){giftedBy=p;}
 bool canGift(bool=false,bool=true)const;void gift(bool=true);
};
static CvPlot*spawnPlot=NULL;static vector<CvUnit*>allocated;
CvUnit*CvPlayer::initUnit(int,int x,int y,int,int,bool,bool){assert(spawnPlot&&spawnPlot->x==x&&spawnPlot->y==y);++created;CvUnit*u=new CvUnit(id);u->location=spawnPlot;spawnPlot->add(*u);allocated.push_back(u);return u;}
namespace CvStacking {static bool enabled=true;static int cap[4][4],cityBonus=0;bool IsEnabled(){return enabled;}int GetCapacity(int owner,DomainTypes domain,bool city){return cap[owner][domain]+(city?cityBonus:0);}}
struct Game {int getActivePlayer()const{return -1;}};struct Global {Game game;int scoutClass;Global():scoutClass(-1){}int getInfoTypeForString(const char*,bool)const{return scoutClass;}Game&getGame(){return game;}};static Global GC;
struct UI {void AddUnitMessage(int,int,int,bool,int,const CvString&) {}};static UI ui;static UI*DLLUI=&ui;
static string GetLocalizedText(const char*,const char*,const char*){return "gift";}
static CvUnit*hookArrival=NULL;static bool hookAllowed=true;static int hookCalls=0;
static int TestGiftHook(){++hookCalls;if(hookArrival){spawnPlot->add(*hookArrival);hookArrival=NULL;}return hookAllowed?1:GAMEEVENTRETURN_FALSE;}
'''
tests=r'''
static int checks=0,failures=0;
static void expect(const char*name,int actual,int wanted){++checks;if(actual!=wanted){++failures;printf("FAIL %s actual=%d expected=%d\n",name,actual,wanted);}}
struct Fixture {CvPlot p;CvUnit donor,other,recipient,third,cargo;
 Fixture():donor(0),other(0),recipient(1),third(2),cargo(0){for(size_t i=0;i<allocated.size();++i)delete allocated[i];allocated.clear();for(int i=0;i<4;++i){players[i]=CvPlayer();players[i].id=players[i].team=i;teams[i]=CvTeam();for(int j=0;j<4;++j)CvStacking::cap[i][j]=2;}players[1].minor=true;players[1].major=false;CvStacking::enabled=true;CvStacking::cityBonus=0;MOD_CORE_NO_INTERMAJOR_UNIT_GIFTING=false;MOD_EVENTS_MINORS_INTERACTION=false;GC.scoutClass=-1;hookArrival=NULL;hookAllowed=true;hookCalls=0;spawnPlot=&p;donor.location=other.location=recipient.location=third.location=cargo.location=&p;p.add(donor);cargo.cargo=true;cargo.transport=&donor;}
 bool allowed(){return donor.canGift();}bool stack(){return CanGiftStackInPlace(&donor,&p,1);}void act(){donor.gift();}
};
int main(){
 {Fixture f;expect("single donor allowed",f.allowed(),1);f.act();expect("single donor recipient created",players[1].created,1);expect("single donor converted",f.donor.delayed,1);expect("single gift benefits",players[1].ai.benefits,1);expect("recipient stays same plot",allocated[0]->plot()==&f.p,1);expect("gifted-by recorded",allocated[0]->giftedBy,0);}
 {Fixture f;f.p.add(f.other);expect("stacked donor rejected",f.allowed(),0);f.act();expect("rejected gift creates nothing",players[1].created,0);expect("rejected donor survives",f.donor.delayed,0);expect("rejected companion survives",f.other.delayed,0);expect("rejected gift grants no benefit",players[1].ai.benefits,0);expect("rejected no movement",f.donor.plot()==&f.p&&f.other.plot()==&f.p,1);}
 {Fixture f;f.p.add(f.recipient);CvStacking::cap[0][DOMAIN_LAND]=1;CvStacking::cap[1][DOMAIN_LAND]=2;expect("recipient free slot used despite donor lower cap",f.allowed(),1);f.act();expect("shared recipient gift succeeds",players[1].created,1);}
 {Fixture f;f.p.add(f.recipient);CvStacking::cap[0][DOMAIN_LAND]=10;CvStacking::cap[1][DOMAIN_LAND]=1;expect("recipient cap enforced despite donor higher cap",f.allowed(),0);f.act();expect("capacity refusal retains donor",f.donor.delayed,0);}
 for(int cap=2;cap<=10;++cap){Fixture f;CvStacking::cap[1][DOMAIN_LAND]=cap;vector<CvUnit> rec(cap,CvUnit(1));for(int i=0;i<cap-1;++i)f.p.add(rec[i]);expect("recipient cap2..10 final free slot",f.stack(),1);f.p.add(rec[cap-1]);expect("recipient cap2..10 full refusal",f.stack(),0);}
 {Fixture f;f.p.add(f.recipient);CvStacking::cap[1][DOMAIN_LAND]=1;CvStacking::cityBonus=1;expect("field no city bonus",f.stack(),0);f.p.city=true;expect("recipient city bonus respected",f.stack(),1);}
 {Fixture f;f.p.add(f.third);expect("third-owner occupant blocks",f.stack(),0);players[2].team=players[1].team;expect("recipient teammate other owner still blocks",f.stack(),0);}
 {Fixture f;f.other.domain=DOMAIN_SEA;f.p.add(f.other);expect("other-domain donor stays separate",f.stack(),1);f.donor.domain=DOMAIN_SEA;expect("naval donor same-domain companion blocks",f.stack(),0);}
 {Fixture f;f.p.add(f.other);f.other.delayed=true;expect("delayed donor companion ignored",f.stack(),1);f.other.delayed=false;f.other.dead=true;expect("dead companion ignored",f.stack(),1);f.other.dead=false;f.other.cargo=true;expect("cargo companion ignored",f.stack(),1);f.other.cargo=false;f.other.support=true;expect("support companion ignored",f.stack(),1);f.other.support=false;f.other.combat=false;expect("civilian companion ignored",f.stack(),1);}
 {Fixture f;f.p.add(f.other);CvStacking::enabled=false;expect("disabled stack preflight inactive",f.allowed(),1);f.act();expect("disabled legacy gift still creates",players[1].created,1);}
 {Fixture f;f.p.add(f.other);f.donor.support=true;expect("special stack donor unchanged",f.stack(),1);f.donor.support=false;f.donor.cargo=true;expect("cargo donor unchanged",f.stack(),1);f.donor.cargo=false;f.donor.combat=false;expect("civilian donor unchanged",f.stack(),1);f.donor.combat=true;f.donor.domain=DOMAIN_AIR;expect("air donor unchanged",f.stack(),1);}
 {Fixture f;f.p.add(f.other);f.p.add(f.cargo);f.act();expect("blocked gift leaves cargo alive",f.cargo.dead,0);expect("blocked gift leaves cargo attached",f.cargo.transport==&f.donor,1);}
 {Fixture f;MOD_EVENTS_MINORS_INTERACTION=true;hookArrival=&f.other;f.p.add(f.cargo);f.act();expect("permission hook called once",hookCalls,1);expect("post-hook arrival blocks creation",players[1].created,0);expect("post-hook refusal precedes cargo deletion",f.cargo.dead,0);expect("post-hook refusal retains donor",f.donor.delayed,0);}
 {Fixture f;MOD_EVENTS_MINORS_INTERACTION=true;hookAllowed=false;expect("existing hook veto retained",f.allowed(),0);}
 {Fixture f;f.donor.damage=1;expect("damaged donor rejected",f.allowed(),0);f.donor.damage=0;f.donor.delayed=true;expect("delayed donor rejected",f.allowed(),0);}
 {Fixture f;f.p.owner=-1;expect("unowned plot rejected",f.allowed(),0);f.p.owner=0;expect("own plot rejected",f.allowed(),0);}
 {Fixture f;f.donor.native=false;expect("non-native donor rejection retained",f.allowed(),0);f.donor.transport=&f.recipient;expect("recipient-team transport exception retained",f.allowed(),1);f.donor.transport=&f.third;expect("foreign-team transport rejected",f.allowed(),0);}
 {Fixture f;f.donor.info.ai=UNITAI_EXPLORE;expect("minor scout AI rejected",f.allowed(),0);f.donor.info.ai=0;GC.scoutClass=f.donor.unitClass;expect("minor scout class rejected",f.allowed(),0);}
 {Fixture f;f.donor.found=true;expect("minor settler rejected",f.allowed(),0);f.donor.found=false;f.donor.combat=false;expect("minor ordinary civilian rejected",f.allowed(),0);f.donor.great=true;players[0].traits.greatPerson=1;expect("minor great-person trait exception retained",f.allowed(),1);}
 {Fixture f;teams[1].war[0]=true;expect("war blocks gift",f.allowed(),0);teams[1].war[0]=false;f.p.hostile=true;expect("visible danger blocks gift",f.allowed(),0);f.p.hostile=false;f.donor.danger=1;expect("forecast danger blocks gift",f.allowed(),0);}
 {Fixture f;f.donor.info.spread=true;expect("religious spread donor rejected",f.allowed(),0);f.donor.info.spread=false;f.donor.info.remove=true;expect("heresy donor rejected",f.allowed(),0);}
 {Fixture f;teams[1].maxed=true;expect("recipient team class cap retained",f.allowed(),0);expect("visible query ignores class cap as before",f.donor.canGift(true),1);teams[1].maxed=false;players[1].maxed=true;expect("recipient player class cap retained",f.allowed(),0);}
 {Fixture f;players[1].minor=false;players[1].major=true;MOD_CORE_NO_INTERMAJOR_UNIT_GIFTING=true;expect("intermajor gift switch retained",f.allowed(),0);MOD_CORE_NO_INTERMAJOR_UNIT_GIFTING=false;expect("enabled intermajor gift retained",f.allowed(),1);}
 printf("gift regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
cpp=work/'gift-source-test.cpp';cpp.write_text(prefix+actual+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
inc=root/'work/toolchain/sdk/vc9/include';lib=root/'work/toolchain/sdk/vc9/lib';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(inc)+';'+str(sdk/'Include');env['LIB']=str(lib)+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=work/'gift-source-test.exe';cmd=[str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/Od','/Z7',str(cpp),'/Fo'+str(work/'gift-source-test.obj'),'/Fe'+str(exe)]
compiled=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True);(work/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=work,env=env,capture_output=True,text=True);print(run.stdout+run.stderr,end='')
result={'source_sha256':hashlib.sha256(source.encode()).hexdigest().upper(),'extracted_sha256':hashlib.sha256(actual.encode()).hexdigest().upper(),'compile_returncode':compiled.returncode,'test_returncode':run.returncode,'output':run.stdout+run.stderr,'scope':'actual extracted preflight, canGift and complete gift bodies with deterministic engine stubs; no VP DLL build or live gift proof'}
(work/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');sys.exit(run.returncode)
