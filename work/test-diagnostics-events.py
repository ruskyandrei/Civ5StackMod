"""Actual complete diagnostic module under deterministic game services; real VC9 file I/O."""
from pathlib import Path
import os,re,subprocess,sys,json,hashlib
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2';out=root/'work/diagnostics-events-regression';out.mkdir(exist_ok=True);(out/'logs').mkdir(exist_ok=True)
source=(core/'CvStackingDiagnostics.cpp').read_text(encoding='utf-8-sig');actual=source[source.index('namespace\n'):]
header=(core/'CvStackingDiagnostics.h').read_text(encoding='utf-8-sig');header=re.sub(r'^#.*\n','',header,flags=re.M)
head=r'''
#define NOMINMAX
#include <windows.h>
#include <share.h>
#include <cstdio>
#include <cstdarg>
#include <string>
#include <vector>
#include <map>
#include <algorithm>
using namespace std;
typedef int PlayerTypes;typedef int BattleUnitTypes;
const int MAX_PLAYERS=4,NO_PLAYER=-1,DOMAIN_LAND=2,DOMAIN_SEA=0,DOMAIN_AIR=1;
const int AI_TACTICAL_MOVE_NONE=0,AI_HOMELAND_MOVE_NONE=0,AI_HOMELAND_MOVE_UNASSIGNED=1;
const int BATTLE_UNIT_ATTACKER=0,BATTLE_UNIT_DEFENDER=1,BATTLE_UNIT_COUNT=3;
#define CURRENT_GAMECORE_VERSION "diagnostic-events-fixture"
map<string,int> cfg;int capCalls=0,roleCalls=0,lookups=0,unitLoops=0,protectionCalls=0;
class CvCity;class CvUnit;
class CvPlot{
public:int id;CvCity*city;vector<CvUnit*> units;CvPlot(int n=0):id(n),city(NULL){}
 int GetPlotIndex()const{return id;}bool isCity()const{return city!=NULL;}CvCity*getPlotCity()const{return city;}
 int getX()const{return id;}int getY()const{return 0;}int getNumUnits()const{return(int)units.size();}CvUnit*getUnitByIndex(int i)const{return units[i];}
};
class CvUnit{
public:int id,owner,domain,hp,cap,army;bool combat,cargo,dead,embarked,ranged,support,legal;CvPlot*p;
 CvUnit(int n=0):id(n),owner(0),domain(DOMAIN_LAND),hp(100),cap(10),army(-1),combat(true),cargo(false),dead(false),embarked(false),ranged(false),support(false),legal(true),p(NULL){}
 int GetID()const{return id;}int getOwner()const{return owner;}int getDomainType()const{return domain;}bool isDelayedDeath()const{return dead;}
 bool IsCombatUnit()const{return combat;}bool IsStackingUnit()const{return support;}bool isCargo()const{return cargo;}bool isEmbarked()const{return embarked;}bool IsCanAttackRanged()const{return ranged;}
 int GetStackingLimit(const CvPlot*)const{++capCalls;return cap;}bool CanStackUnitAtPlot(const CvPlot*)const{return legal;}
 int GetCurrHitPoints()const{return hp;}int GetMaxHitPoints()const{return 100;}int getDamage()const{return 100-hp;}CvPlot*plot()const{return p;}
 int getUnitType()const{return id;}int getX()const{return p?p->getX():0;}int getY()const{return 0;}int getMoves()const{return 120;}int getArmyID()const{return army;}
 bool IsHurt()const{return hp<100;}int getTacticalMove()const{return 0;}int getHomelandMove()const{return 1;}bool TurnProcessed()const{return false;}bool IsGarrisoned()const{return p&&p->isCity();}
};
class CvCity{public:int id,owner,damage,maxHP;CvUnit*garrison;CvPlot*p;
 CvCity(CvPlot*plot):id(7),owner(1),damage(0),maxHP(300),garrison(NULL),p(plot){plot->city=this;}
 int GetID()const{return id;}int getOwner()const{return owner;}int getDamage()const{return damage;}int GetMaxHitPoints()const{return maxHP;}
 int getX()const{return p->id;}int getY()const{return 0;}int getPopulation()const{return 10;}CvUnit*GetGarrisonedUnit()const{return garrison;}
};
class CvArmyAI{public:int GetID()const{return 4;}int GetNumSlotsFilled()const{return 6;}int GetNumFormationEntries()const{return 10;}};
class CvAIOperation{public:CvPlot*target;CvPlot*muster;CvArmyAI*army;CvAIOperation():target(NULL),muster(NULL),army(NULL){}
 int GetID()const{return 3;}int GetOperationType()const{return 2;}int GetOperationState()const{return 3;}int GetEnemy()const{return 1;}
 CvPlot*GetTargetPlot()const{return target;}CvPlot*GetMusterPlot()const{return muster;}CvArmyAI*GetArmy(int)const{return army;}
 int GetNumUnitsNeededToBeBuilt()const{return 2;}int GetNumUnitsCommittedToBeBuilt()const{return 1;}int GetTurnStarted()const{return 0;}
};
class CvPlayer{public:int id;vector<CvUnit*>units;vector<CvCity*>cities;vector<CvAIOperation*>ops;CvPlayer():id(0){}
 int GetID()const{return id;}CvUnit*firstUnit(int*i){++unitLoops;*i=0;return units.empty()?NULL:units[0];}CvUnit*nextUnit(int*i){++*i;return *i<(int)units.size()?units[*i]:NULL;}
 CvCity*firstCity(int*i){*i=0;return cities.empty()?NULL:cities[0];}CvCity*nextCity(int*i){++*i;return *i<(int)cities.size()?cities[*i]:NULL;}
 CvUnit*getUnit(int id){++lookups;for(size_t i=0;i<units.size();++i)if(units[i]->id==id)return units[i];return NULL;}
 size_t getNumAIOperations()const{return ops.size();}CvAIOperation*getAIOperationByIndex(size_t i){return ops[i];}
} players[MAX_PLAYERS];
#define GET_PLAYER(n) players[n]
namespace CvStacking{int GetInt(const char*n,int f){return cfg.count(n)?cfg[n]:f;}bool IsAntiCavalry(const CvUnit*){++roleCalls;return false;}bool CanFlank(const CvUnit*){++roleCalls;return false;}int GetCollateralTargetLimit(const CvUnit*){++roleCalls;return 0;}int GetCityProtection(const CvCity*c){++protectionCalls;return 90*(c->maxHP-c->damage)/c->maxHP;}}
namespace Database{struct Results{bool Step(){return false;}const char*GetText(const char*){return "";}};struct Connection{bool Execute(Results&,const char*){return true;}};}
struct Game{int turn;Game():turn(1){}int getGameTurn(){return turn;}};
struct Map{map<int,CvPlot*>plots;int getGridWidth(){return 80;}int getGridHeight(){return 52;}CvPlot*plotByIndexUnchecked(int i){return plots.count(i)?plots[i]:NULL;}};
struct Global{Game game;Map map;Database::Connection db;Game&getGame(){return game;}Map&getMap(){return map;}Database::Connection*GetGameDatabase(){return &db;}}GC;
struct FILogFile{enum{kDontTimeStamp=0};const wchar_t*GetFileName(){return L"logs\\StackingDiagnostics-path.log";}} locator;
struct LogMgr{FILogFile*GetLog(const char*,int){return &locator;}}LOGFILEMGR;
struct CvCombatMemberEntry{int owner,id,damage;CvCombatMemberEntry(int o=1,int i=2,int d=5):owner(o),id(i),damage(d){}bool IsUnit()const{return true;}int GetPlayer()const{return owner;}int GetID()const{return id;}int GetDamage()const{return damage;}};
class CvCombatInfo{public:CvUnit*units[3];CvCity*cities[3];CvPlot*p;vector<CvCombatMemberEntry>members;bool ranged,bombing;
 CvCombatInfo():p(NULL),ranged(true),bombing(false){for(int i=0;i<3;++i){units[i]=NULL;cities[i]=NULL;}}
 CvUnit*getUnit(int i)const{return units[i];}CvCity*getCity(int i)const{return cities[i];}CvPlot*getPlot()const{return p;}
 bool getAttackIsRanged()const{return ranged;}bool getAttackIsBombingMission()const{return bombing;}int getDamageInflicted(int i)const{return i==0?40:0;}
 int getDamageMemberCount()const{return (int)members.size();}const CvCombatMemberEntry*getDamageMembers()const{return members.empty()?NULL:&members[0];}bool getAttackerAdvances()const{return !ranged;}
};
'''
tests=r'''
int checks=0,failedChecks=0;void check(bool ok,const char*n){++checks;if(!ok){++failedChecks;printf("FAIL %s\n",n);}}
string logs(){CvStackingDiagnostics::Flush();char p[MAX_PATH];WideCharToMultiByte(CP_UTF8,0,directory,-1,p,sizeof(p),NULL,NULL);string path=string(p)+prefix+"-00.log";FILE*f=fopen(path.c_str(),"rb");string result;if(f){char b[4096];size_t n;while((n=fread(b,1,sizeof b,f))!=0)result.append(b,n);fclose(f);}return result;}
int countText(const string&s,const char*k){int n=0;size_t p=0;while((p=s.find(k,p))!=string::npos){++n;p+=strlen(k);}return n;}
void reset(){CvStackingDiagnostics::Reset();cfg.clear();cfg["DiagnosticsMemoryInterval"]=0;GC.game.turn=1;GC.map.plots.clear();for(int i=0;i<4;++i){players[i]=CvPlayer();players[i].id=i;}capCalls=roleCalls=lookups=unitLoops=protectionCalls=0;}
void put(CvUnit&u,CvPlot&p){u.p=&p;p.units.push_back(&u);players[u.owner].units.push_back(&u);GC.map.plots[p.id]=&p;}
void snapshots(){reset();CvPlot plots[10];CvUnit units[100];for(int i=0;i<100;++i){units[i].id=i;units[i].ranged=i%2!=0;plots[i/10].id=i/10;put(units[i],plots[i/10]);}
 CvStackingDiagnostics::SetLevel(1);CvStackingDiagnostics::OnPlayerTurn(players[0]);string s=logs();
 check(s.find("units=100 countedCombat=100 ranged=50")!=string::npos,"summary composition preserved");
 check(s.find("stackTiles=10 maxStack=10 illegal=0 overCap=0 rangedWithoutMelee=0")!=string::npos,"each tile/domain counted once");
 check(capCalls==200,"capacity lookup once per unit plus once per representative group, not per unit-pair");
 check(roleCalls==0,"summary does not collect verbose role detail");CvStackingDiagnostics::AfterPlayerUnitAI(players[0]);s=logs();
 check(countText(s,"|DIAGNOSTIC_COST|")==1,"actual first-pass cost scope recorded");check(s.find("phase=first_unit_AI_pass")!=string::npos,"timing scope explicit");
 int loops=unitLoops;CvStackingDiagnostics::AfterPlayerUnitAI(players[0]);check(unitLoops==loops,"repeated passes do not rescan units");
 reset();cfg["DiagnosticsSummaryInterval"]=5;put(units[0],plots[0]);CvStackingDiagnostics::SetLevel(1);CvStackingDiagnostics::OnPlayerTurn(players[0]);CvStackingDiagnostics::AfterPlayerUnitAI(players[0]);check(unitLoops==0,"both unsampled snapshots skip unit scans");
 reset();cfg["DiagnosticsCategoryMask"]=16;put(units[0],plots[0]);CvStackingDiagnostics::SetLevel(1);CvStackingDiagnostics::OnPlayerTurn(players[0]);CvStackingDiagnostics::AfterPlayerUnitAI(players[0]);s=logs();check(unitLoops==0&&countText(s,"|DIAGNOSTIC_COST|")==1,"performance-only filter avoids structural collection");
 reset();cfg["DiagnosticsCategoryMask"]=2;CvAIOperation op;CvArmyAI army;op.army=&army;op.target=&plots[0];op.muster=&plots[1];players[0].ops.push_back(&op);CvStackingDiagnostics::SetLevel(1);CvStackingDiagnostics::OnPlayerTurn(players[0]);CvStackingDiagnostics::AfterPlayerUnitAI(players[0]);s=logs();check(unitLoops==0&&s.find("filled=6 slots=10 neededBuild=2 training=1")!=string::npos,"operation/production evidence requires no unit snapshot");
}
void combats(){reset();CvPlot plot(1);CvCity city(&plot);CvUnit attacker(1),garrison(2);garrison.owner=1;put(attacker,plot);put(garrison,plot);city.garrison=&garrison;
 CvCombatInfo info;info.p=&plot;info.units[0]=&attacker;info.cities[1]=&city;info.members.push_back(CvCombatMemberEntry());
 CvStackingDiagnostics::SetLevel(1);{CvStackingDiagnostics::CombatScope event(info,9);city.damage=40;garrison.hp=95;}
 string s=logs();check(countText(s,"|COMBAT_SUMMARY|")==1,"summary gets one compact combat result");check(countText(s,"|COMBAT_BEGIN|")==0&&countText(s,"|COMBAT_AFTER|")==0,"summary skips participant detail lines");
 check(s.find("bystanders=1 bystanderRolledDamage=5 hpLostPresent=5 missingUnits=0")!=string::npos,"bystander damage labels include ordinary absorption");
 check(s.find("cityHPBefore=300 cityHPAfter=260 protectionBefore=90")!=string::npos,"city HP and mitigation observed around real scope");
 city.damage=0;city.owner=1;info.ranged=false;{CvStackingDiagnostics::CombatScope event(info,10);city.owner=0;city.id=8;}
 s=logs();check(countText(s,"|CITY_CAPTURE|")==1&&s.find("oldOwner=1 newOwner=0 oldCity=7 newCity=8")!=string::npos,"city capture outcome includes changing owner-specific identity");
 {CvStackingDiagnostics::CombatScope event(info,11);players[1].units.clear();}s=logs();check(s.find("missingUnits=1")!=string::npos,"deleted identity is reported missing without claiming death");
 reset();city.owner=1;city.id=7;city.damage=0;garrison.hp=100;put(attacker,plot);put(garrison,plot);cfg["DiagnosticsPlayer"]=1;CvStackingDiagnostics::SetLevel(1);{CvStackingDiagnostics::CombatScope event(info,12);}
 s=logs();check(s.find("|player=1|COMBAT_SUMMARY|")!=string::npos&&s.find("attackerOwner=0")!=string::npos,"civilization filter includes incoming attacks and preserves actual aggressor");
 reset();put(attacker,plot);put(garrison,plot);cfg["DiagnosticsPlayer"]=3;CvStackingDiagnostics::SetLevel(1);{CvStackingDiagnostics::CombatScope event(info,13);}check(countText(logs(),"|COMBAT_SUMMARY|")==0&&lookups==0,"uninvolved filtered combat skips participant collection");
 reset();put(attacker,plot);put(garrison,plot);cfg["DiagnosticsCategoryMask"]=2;CvStackingDiagnostics::SetLevel(2);{CvStackingDiagnostics::CombatScope event(info,14);}check(countText(logs(),"|COMBAT_")==0&&lookups==0&&protectionCalls==0,"disabled combat category skips combat collection");
 reset();put(attacker,plot);put(garrison,plot);cfg["DiagnosticsCombatSummary"]=0;CvStackingDiagnostics::SetLevel(1);{CvStackingDiagnostics::CombatScope event(info,15);}check(countText(logs(),"|COMBAT_SUMMARY|")==0&&lookups==0,"compact combat can be disabled independently");
 reset();put(attacker,plot);put(garrison,plot);cfg["DiagnosticsVerboseStartTurn"]=5;CvStackingDiagnostics::SetLevel(2);{CvStackingDiagnostics::CombatScope event(info,16);}s=logs();check(countText(s,"|COMBAT_BEGIN|")==0&&countText(s,"|COMBAT_SUMMARY|")==1,"outside verbose window compact evidence remains");
 GC.game.turn=5;{CvStackingDiagnostics::CombatScope event(info,17);}s=logs();check(countText(s,"|COMBAT_BEGIN|")==1&&countText(s,"|COMBAT_END|")==1,"verbose window retains full matched combat bracket");
}
int main(){snapshots();combats();CvStackingDiagnostics::Reset();printf("diagnostic events/sampling: %d checks, %d failures\n",checks,failedChecks);return failedChecks?1:0;}
'''
cpp=out/'diagnostic-events-source-test.cpp';cpp.write_text(head+header+actual+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for k in ('CL','_CL_','LINK'):env.pop(k,None)
exe=out/'diagnostic-events-source-test.exe';compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'events.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);(out/'compile.log').write_text(compiled.stdout+compiled.stderr)
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
result=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(result.stdout+result.stderr,end='');(out/'result.json').write_text(json.dumps({'returncode':result.returncode,'output':result.stdout+result.stderr,'source_sha256':hashlib.sha256((core/'CvStackingDiagnostics.cpp').read_bytes()).hexdigest(),'scope':'Entire actual diagnostic module, deterministic game services, real VC9 CRT file IO; no game performance or live combat/UI validation.'},indent=2));sys.exit(result.returncode)
