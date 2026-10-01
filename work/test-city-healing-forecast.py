"""Bind the staged pure forecast to actual city healing/history/permission source.

No DLL build or game calls. --production is strict standalone four-file adoption
binding; the shared assault rewrite must compose its healing fragment separately.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('city_healing_stage', ROOT / 'work/prepare-city-healing-forecast.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
OUT = ROOT / 'work/city-healing-forecast-regression'

def method(text, name):
    start = text.index(name)
    opening = text.index('{', start)
    i, depth = opening + 1, 1
    while depth:
        depth += (text[i] == '{') - (text[i] == '}')
        i += 1
    return text[start:i]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--compile', action='store_true')
    parser.add_argument('--emit-only', action='store_true')
    parser.add_argument('--production', action='store_true')
    args = parser.parse_args()
    before, after = stage.stage()
    if args.production:
        for path in stage.PATHS:
            actual = (ROOT / path).read_text(encoding='utf-8-sig').replace('\r\n', '\n')
            assert actual == after[path], 'Whole production file differs from frozen candidate: ' + path
        used = {p: (ROOT / p).read_text(encoding='utf-8-sig').replace('\r\n', '\n') for p in stage.PATHS}
    else:
        used = after
    cpp, header, off, tac = (used[p] for p in stage.PATHS)
    baseline_city = before[stage.PATHS[0]]
    native_turn = method(cpp, 'void CvCity::doTurn()')
    assert native_turn == method(baseline_city, 'void CvCity::doTurn()'), 'Actual healing was modified'
    native_start = native_turn.index('\tbool bRunningDefenseProcess = false;')
    native_stop = native_turn.index('\n\tif (MOD_BALANCE_CORE_JFD)', native_start)
    native = 'void CvCity::nativeHeal(){\n' + native_turn[native_start:native_stop] + '\n}\n'
    flip = method(cpp, 'void CvCity::flipDamageReceivedPerTurn()')
    assert flip == method(baseline_city, 'void CvCity::flipDamageReceivedPerTurn()')
    helper = method(cpp, 'int CvCity::GetAssaultHealingForecast(')
    permission = method(stage.original('CvGameCoreDLL_Expansion2/CvGame.cpp'), 'bool CvGame::CanOpenCityScreen(')
    getters = '\n'.join(method(cpp, name) for name in (
        'int CvCity::getDamageTakenThisTurn() const', 'int CvCity::getDamageTakenLastTurn() const'))
    # Read instrumentation only: original getter expressions and branches are unchanged.
    getters = getters.replace('\n{\n', '\n{\n\t++historyReads;\n')
    cached_yield = method(cpp, 'int CvCity::getYieldRateTimes100(YieldTypes eYield, bool bIgnoreTrade, bool bIgnoreProcess, bool bUseCachedValue, CvString* tooltipSink) const')
    off_a = off.index('        bool healingComplete=false;', off.index('AssaultPlan AssessAssault('))
    off_b = off.index('        const bool captureSoon=', off_a)
    off_fn = 'static int offensiveForecast(CvCity*city,PlayerTypes owner,int damage,bool*complete){AssaultPlan result;result.cityDamage=damage;\n' + off[off_a:off_b] + '*complete=healingComplete;return healing;}\n'
    tac_a = tac.index('\t\t\t\t\tint iCityHealRate =', tac.index('void CvTacticalAI::ExecuteCaptureCityMoves('))
    tac_b = tac.index('\n\t\t\t\t\t//assume the city heals each turn', tac_a)
    tac_fn = 'static int tacticalForecast(CvCity*pCity,CvPlayer*m_pPlayer,int iExpectedDamagePerTurn){\n' + tac[tac_a:tac_b] + 'return iCityHealRate;}\n'
    player = stage.original('CvGameCoreDLL_Expansion2/CvPlayer.cpp')
    activate = method(player, 'void CvPlayer::setTurnActive(')
    assert activate.index('SetAllUnitsUnprocessed();') < activate.index('\n\t\t\t\t\t\tdoTurn();')
    reset = method(player, 'void CvPlayer::SetAllUnitsUnprocessed()')
    assert 'pLoopCity->flipDamageReceivedPerTurn();' in reset
    post = method(player, 'void CvPlayer::doTurnPostDiplomacy()')
    assert 'pLoopCity->doTurn();' in post
    native_compute = method(tac, 'int CvTacticalAI::ComputeTotalExpectedDamage(')
    assert 'rtnValue += cityDamage;' in native_compute
    actual = helper + '\n' + permission + '\n' + getters + '\n' + cached_yield + '\n' + flip + '\n' + native + off_fn + tac_fn
    fixture = PREFIX + actual + TESTS
    OUT.mkdir(exist_ok=True)
    source = OUT / 'test.cpp'
    source.write_text(fixture, encoding='utf-8', newline='\n')
    proof = {'baseline': stage.BASE, 'production': args.production,
             'source_sha256': hashlib.sha256(fixture.encode()).hexdigest(),
             'actual_bodies_sha256': hashlib.sha256(actual.encode()).hexdigest(),
             'actual_doTurn_and_history_byte_exact': True,
             'setTurnActive_flips_before_city_turn': True,
             'garrison_split_city_damage_input': True,
             'files': {p: hashlib.sha256(used[p].encode()).hexdigest() for p in stage.PATHS}}
    (OUT / 'source-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    if args.emit_only or not args.compile:
        print('City healing forecast actual-source fixture emitted; no compilation performed.')
        return 0
    vc = ROOT / 'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
    sdk = ROOT / 'work/toolchain/sdk/windows'
    env = os.environ.copy()
    env['PATH'] = str(vc/'Vc7/bin') + ';' + str(vc/'Common7/IDE') + ';' + env.get('PATH', '')
    env['INCLUDE'] = str(ROOT/'work/toolchain/sdk/vc9/include') + ';' + str(sdk/'Include')
    env['LIB'] = str(ROOT/'work/toolchain/sdk/vc9/lib') + ';' + str(sdk/'Lib')
    for key in ('CL', '_CL_', 'LINK'):
        env.pop(key, None)
    exe = OUT/'test.exe'
    compiled = subprocess.run([str(vc/'Vc7/bin/cl.exe'), '/nologo', '/O2', '/EHsc', '/MT', '/Z7', str(source), '/Fo'+str(OUT/'test.obj'), '/Fe'+str(exe)], cwd=OUT, env=env, capture_output=True, text=True, timeout=60)
    (OUT/'compile.log').write_text(compiled.stdout+compiled.stderr)
    if compiled.returncode:
        print(compiled.stdout+compiled.stderr)
        return compiled.returncode
    result = subprocess.run([str(exe)], cwd=OUT, capture_output=True, text=True, timeout=30)
    (OUT/'output.log').write_text(result.stdout+result.stderr)
    proof.update({'returncode': result.returncode, 'output': result.stdout+result.stderr,
                  'scope': 'Actual native heal, actual damage-history smoothing, actual city-screen permission and cached production accessor; actual staged shared helper and both healing caller fragments. Deterministic city/map/espionage services; no game/build.'})
    (OUT/'result.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(result.stdout+result.stderr, end='')
    return result.returncode

PREFIX = r'''
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <cstdio>
#include <algorithm>
#include <new>
#include <cstdlib>
using namespace std;
static long allocationCalls=0;
void* operator new(size_t size){++allocationCalls;void*p=malloc(size?size:1);if(!p)throw bad_alloc();return p;}
void operator delete(void*p){free(p);}
typedef int PlayerTypes;typedef int TeamTypes;typedef int YieldTypes;typedef int CvString;
const int MAX_PLAYERS=8,NO_PROCESS=-1,YIELD_PRODUCTION=0;
static bool vp=true,offensiveEnabled=true;
static int baseHeal=8,buildingReads=0,processReads=0,populationReads=0,historyReads=0,citizenReads=0,productionReads=0,yieldReads=0,uncachedYieldReads=0,debugVisibilityReads=0;
#define MOD_BALANCE_VP vp
#define GD_INT_GET(x) baseHeal
#define VALIDATE_OBJECT() ((void)0)
struct CvCity;
struct PlayerEspionage{bool surveillance,schmoozing;PlayerEspionage():surveillance(false),schmoozing(false){}bool HasEstablishedSurveillanceInCity(CvCity*)const{return surveillance;}bool IsAnySchmoozing(CvCity*)const{return schmoozing;}};
struct CvPlayer{int id,team;bool observer,minor;PlayerEspionage spies;CvPlayer():id(0),team(0),observer(false),minor(false){}int GetID()const{return id;}int getTeam()const{return team;}bool isObserver()const{return observer;}bool isMinorCiv()const{return minor;}PlayerEspionage*GetEspionage(){return &spies;}};
static CvPlayer players[MAX_PLAYERS];
#define GET_PLAYER(x) players[x]
struct CityEspionage{bool revealed;CityEspionage():revealed(false){}bool GetRevealCityScreen(PlayerTypes)const{return revealed;}};
struct CvCityBuildings{int defense,modifier;CvCityBuildings():defense(0),modifier(0){}int GetBuildingDefense()const{++buildingReads;return defense;}int GetBuildingDefenseMod()const{return modifier;}};
struct Citizens{bool blockaded;Citizens():blockaded(false){}bool AnyPlotBlockaded()const{++citizenReads;return blockaded;}};
struct CvProcessInfo{int value,perTurn,cap;CvProcessInfo():value(100),perTurn(20),cap(150){}int getDefenseValue()const{return value;}int getDefenseValuePerTurn()const{return perTurn;}int getDefenseValueCap()const{return cap;}};
struct CvGame{bool CanOpenCityScreen(PlayerTypes,CvCity*);};
struct Globals{CvProcessInfo process;bool processValid;CvGame game;Globals():processValid(true){}CvProcessInfo*getProcessInfo(int){++processReads;return processValid?&process:NULL;}CvGame&getGame(){return game;}}GC;
namespace CvStackingOffensiveAI{static bool Enabled(PlayerTypes){return offensiveEnabled;}}
struct AssaultPlan{int cityDamage;AssaultPlan():cityDamage(0){}};
struct CvCity{
 int owner,team,population,m_iDamage,m_iDamageTakenThisTurn,m_iDamageTakenLastTurn,process,processTurns,production,maxHP,lastHealing;
 bool visible,blockaded;CvCityBuildings buildings;CvCityBuildings*m_pCityBuildings;Citizens citizens;CityEspionage espionage;
 CvCity():owner(1),team(1),population(20),m_iDamage(400),m_iDamageTakenThisTurn(0),m_iDamageTakenLastTurn(0),process(NO_PROCESS),processTurns(0),production(1000),maxHP(1000),lastHealing(0),visible(true),blockaded(false),m_pCityBuildings(&buildings){}
 CvCity(const CvCity&x){*this=x;m_pCityBuildings=&buildings;}
 int getOwner()const{return owner;}int getTeam()const{return team;}bool isVisible(TeamTypes,bool debug)const{debugVisibilityReads+=debug?1:0;return visible;}
 bool IsBlockadedWaterAndLand()const{return blockaded;}int getDamage()const{return m_iDamage;}int getPopulation()const{++populationReads;return population;}
 int getDamageTakenThisTurn()const;int getDamageTakenLastTurn()const;void flipDamageReceivedPerTurn();
 Citizens*GetCityCitizens()const{return const_cast<Citizens*>(&citizens);}CityEspionage*GetCityEspionage()const{return const_cast<CityEspionage*>(&espionage);}
 int getProductionProcess()const{++productionReads;return process;}int GetDefenseProcessTurns()const{return processTurns;}
 int getYieldRateTimes100(YieldTypes,bool=false,bool=false,bool=true,CvString*=NULL)const;
 int getYieldRateTimes100(YieldTypes,bool,bool,int,bool,bool,bool,CvString*)const{++uncachedYieldReads;return production;}
 int GetStaticYield(YieldTypes)const{++yieldReads;return production;}bool isFoodProduction()const{return false;}
 void changeDamage(int amount){lastHealing=-amount;m_iDamage=max(0,min(maxHP,m_iDamage+amount));}void setDamage(int d){m_iDamage=max(0,min(maxHP,d));}
 void ResetGreatWorkYieldCache(){}void ChangeDefenseProcessTurns(int x){processTurns+=x;}void SetDefenseProcessTurns(int x){processTurns=x;}
 int GetAssaultHealingForecast(PlayerTypes,int,bool*=NULL)const;void nativeHeal();
};
static void resetReads(){buildingReads=processReads=populationReads=historyReads=citizenReads=productionReads=yieldReads=uncachedYieldReads=debugVisibilityReads=0;}
static int checks=0,failures=0;
static void expect(const char*name,bool ok){++checks;if(!ok){++failures;if(failures<20)printf("FAIL %s\n",name);}}
static void setup(){for(int i=0;i<MAX_PLAYERS;++i){players[i]=CvPlayer();players[i].id=i;players[i].team=i;}GC.processValid=true;GC.process=CvProcessInfo();vp=true;baseHeal=8;offensiveEnabled=true;resetReads();}
static int nativeNextRate(const CvCity&city,int expected){CvCity next(city);next.changeDamage(max(0,expected));next.m_iDamageTakenThisTurn+=max(0,expected);next.flipDamageReceivedPerTurn();next.lastHealing=0;next.nativeHeal();return next.lastHealing;}
'''.replace('CvString*=NULL', 'CvString* = NULL').replace('bool*=NULL','bool* = NULL')

TESTS = r'''
int main(){
 setup();
 const int defenses[4]={0,999,1000,3501},modifiers[3]={-25,0,50},incoming[5]={0,1,2,7,31};
 const int history[4]={0,1,4,9},pops[3]={0,1,20};
 for(int v=0;v<2;++v)for(int b=0;b<4;++b)for(int m=0;m<3;++m)for(int d=0;d<5;++d)for(int h=0;h<4;++h)for(int p=0;p<3;++p)for(int blocked=0;blocked<2;++blocked){
  vp=v!=0;baseHeal=vp?8:20;CvCity city;city.population=pops[p];city.buildings.defense=defenses[b];city.buildings.modifier=modifiers[m];city.blockaded=blocked!=0;
  city.m_iDamageTakenThisTurn=history[h];city.m_iDamageTakenLastTurn=history[(h+1)%4];city.citizens.blockaded=(h%2)!=0;
  bool complete=false;int oldDamage=city.m_iDamage,oldThis=city.m_iDamageTakenThisTurn,oldLast=city.m_iDamageTakenLastTurn,oldTurns=city.processTurns;
  long allocations=allocationCalls;int predicted=city.GetAssaultHealingForecast(1,incoming[d],&complete);
  expect("known-team forecast has no allocations or mutations",allocationCalls==allocations&&city.m_iDamage==oldDamage&&city.m_iDamageTakenThisTurn==oldThis&&city.m_iDamageTakenLastTurn==oldLast&&city.processTurns==oldTurns);
  expect("same-team exact native rate after damage-history flip",predicted==nativeNextRate(city,incoming[d])&&complete);
  expect("offensive caller uses same shared rate and completeness",offensiveForecast(&city,1,incoming[d],&complete)==predicted&&complete);
  expect("tactical caller uses same shared rate",tacticalForecast(&city,&players[1],incoming[d])==predicted);
 }
 for(int v=0;v<2;++v)for(int value=-1;value<3;++value)for(int per=0;per<3;++per)for(int cap=0;cap<3;++cap)for(int turns=0;turns<5;++turns)for(int q=0;q<2;++q){
  setup();vp=v!=0;baseHeal=vp?8:20;CvCity city;city.process=0;city.processTurns=turns;city.production=12345;city.buildings.defense=3001;city.buildings.modifier=33;
  GC.process.value=value*37;GC.process.perTurn=per*23;GC.process.cap=cap==0?0:cap*50;
  city.m_iDamageTakenThisTurn=q?8:0;city.citizens.blockaded=false;bool complete=false;
  int forecast=city.GetAssaultHealingForecast(1,0,&complete);expect("process base/perturn/cap/truncation native parity",forecast==nativeNextRate(city,0)&&complete);
  CvCity next(city);next.flipDamageReceivedPerTurn();next.nativeHeal();expect("helper uses process turns before native increments them",city.processTurns==turns&&next.processTurns==(GC.process.perTurn!=0?turns+1:0));
  resetReads();city.GetAssaultHealingForecast(1,0);expect("process reads cached production with no uncached yield rebuild",uncachedYieldReads==0);
 }
 {
  setup();CvCity c;c.m_iDamageTakenThisTurn=0;c.m_iDamageTakenLastTurn=0;c.citizens.blockaded=false;
  expect("one new HP damage rounds to quiet zero",c.GetAssaultHealingForecast(1,1)==84&&nativeNextRate(c,1)==84);
  expect("two new HP damage cancels quiet triple",c.GetAssaultHealingForecast(1,2)==28&&nativeNextRate(c,2)==28);
  c.m_iDamageTakenLastTurn=4;expect("smoothed last damage four decays to quiet zero",c.GetAssaultHealingForecast(1,0)==84);
  c.m_iDamageTakenLastTurn=5;expect("smoothed last damage five remains nonzero",c.GetAssaultHealingForecast(1,0)==28);
  c.m_iDamageTakenLastTurn=0;c.citizens.blockaded=true;expect("citizen plot blockade suppresses quiet but not all healing",c.GetAssaultHealingForecast(1,0)==28);
 }
 for(int v=0;v<2;++v)for(int intel=0;intel<2;++intel)for(int expected=0;expected<4;++expected){
  setup();vp=v!=0;baseHeal=vp?8:20;CvCity city;city.buildings.defense=90000;city.process=0;city.processTurns=7;city.production=40000;
  city.espionage.revealed=intel!=0;players[0].spies.surveillance=intel!=0;
  resetReads();bool complete=true;long allocations=allocationCalls;int forecast=city.GetAssaultHealingForecast(0,expected,&complete);
  expect("foreign helper no allocation",allocationCalls==allocations);
  expect("foreign history and citizen cache never read",historyReads==0&&citizenReads==0);
  expect("foreign no debug visibility privilege",debugVisibilityReads==0);
  if(!intel){expect("ordinary foreign no hidden building or production reads",buildingReads==0&&productionReads==0&&processReads==0&&yieldReads==0);expect("ordinary visible fallback base/pop incomplete",forecast==baseHeal+(vp?20:0)&&!complete);}
  else{expect("normal cityscreen permits building/process",buildingReads>0&&processReads>0&&productionReads>0&&yieldReads>0);expect("foreign completeness needs quiet ruled out in VP",complete==(!vp||expected>=2));if(!vp||expected>=2)expect("legal foreign exact native rate",forecast==nativeNextRate(city,expected));}
 }
 {
  setup();CvCity city;city.buildings.defense=90000;city.process=0;city.production=100000;city.espionage.revealed=true;players[0].observer=true;
  resetReads();bool complete=true;expect("observer excluded even though engine cityscreen grants access",city.GetAssaultHealingForecast(0,5,&complete)==0&&!complete);expect("observer has no hidden reads",buildingReads+processReads+productionReads+historyReads+citizenReads+populationReads==0);
  players[0].observer=false;city.visible=false;resetReads();complete=true;expect("invisible foreign rejected even with espionage screen permission",city.GetAssaultHealingForecast(0,5,&complete)==0&&!complete);expect("invisible foreign reads no city economic information",buildingReads+processReads+productionReads+historyReads+citizenReads+populationReads==0);
  city.visible=true;players[1].minor=true;resetReads();expect("foreign minor cityscreen denied by actual permission body",city.GetAssaultHealingForecast(0,5,&complete)==28&&!complete&&buildingReads==0&&processReads==0);
  resetReads();complete=true;expect("invalid observer rejected",city.GetAssaultHealingForecast(-1,5,&complete)==0&&!complete&&city.GetAssaultHealingForecast(MAX_PLAYERS,5,&complete)==0&&!complete);
 }
 {
  setup();CvCity city;city.blockaded=true;city.process=0;city.buildings.defense=90000;bool complete=false;resetReads();
  expect("fully blockaded zero and no optional healing reads",city.GetAssaultHealingForecast(0,50,&complete)==0&&complete&&buildingReads+populationReads+productionReads+processReads+historyReads+citizenReads==0);
  city.blockaded=false;city.m_iDamage=0;resetReads();expect("full health and no incoming damage no healing reads",city.GetAssaultHealingForecast(0,0,&complete)==0&&complete&&buildingReads+populationReads+productionReads+processReads+historyReads+citizenReads==0);
  expect("full health future wounds still have healing forecast",city.GetAssaultHealingForecast(0,7)==28);
  city.m_iDamage=city.maxHP;expect("zero health damaged city still has nonblockaded heal rate",city.GetAssaultHealingForecast(1,7)>0);
  GC.processValid=false;expect("null process info safe and native parity",city.GetAssaultHealingForecast(1,7)==nativeNextRate(city,7));
 }
 {
  setup();CvCity city;city.process=0;city.buildings.defense=8000;city.citizens.blockaded=false;city.m_iDamageTakenLastTurn=0;offensiveEnabled=false;
  resetReads();expect("disabled mod tactical retains old VP approximate rate",tacticalForecast(&city,&players[1],0)==28&&buildingReads+processReads+historyReads+citizenReads==0);
  vp=false;baseHeal=20;expect("disabled mod tactical retains CP base rate",tacticalForecast(&city,&players[1],0)==20);
  city.blockaded=true;expect("disabled mod blockade remains zero",tacticalForecast(&city,&players[1],10)==0);
 }
 printf("City healing forecast actual-source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''

if __name__ == '__main__':
    sys.exit(main())
