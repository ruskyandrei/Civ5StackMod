"""Actual selector memo and complete field/city/air/collateral forecast oracle.

Actual selection/exchange, scalar/outcome loops and cache storage/keys compile
against deterministic engine damage services. No DLL build/game calls. The
NULL-callback scalar body is reverse-normalized byte-for-byte to DLL60.
"""
from pathlib import Path
import ast,hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2';out=root/'work/danger-defender-cache-regression';out.mkdir(exist_ok=True)
tactical=(core/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig');danger=(core/'CvDangerPlots.cpp').read_text(encoding='utf-8-sig');header=(core/'CvDangerPlots.h').read_text(encoding='utf-8-sig');combat=(core/'CvUnitCombat.cpp').read_text(encoding='utf-8-sig');unit=(core/'CvUnit.h').read_text(encoding='utf-8-sig')
control='688798c3b';old=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/CvDangerPlots.cpp'],cwd=root).decode('utf-8-sig')
def function(text,name):
 a=text.index(name);b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
def literal_scaffold(name):
 values={}
 for n in ast.parse((root/'work'/name).read_text(encoding='utf-8-sig')).body:
  if isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str):
   for target in n.targets:
    if isinstance(target,ast.Name):values[target.id]=n.value.value
 return values
values=literal_scaffold('test-projected-stack-danger.py');prefix=values['prefix'];services=values['services']
alias=header[header.index('typedef const CvUnit* (*StackDangerDefenderSelector)'):];alias=alias[:alias.index(';')+1]
container=unit[unit.index('struct SUnitIDValueContainer\n'):unit.index('\nnamespace std {',unit.index('struct SUnitIDValueContainer\n'))]
contents=header[header.index('struct CvDangerPlotContents\n'):header.index('//++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++',header.index('struct CvDangerPlotContents\n'))]
contents=contents.replace('int GetStackDanger(const CvUnit*', 'int OriginalStackDanger(const CvUnit*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&);\n\tint GetStackDanger(const CvUnit*',1)
scalar=function(danger,'int CvDangerPlotContents::GetStackDanger(');original=function(old,'int CvDangerPlotContents::GetStackDanger(')
normalized=scalar.replace(', StackDangerDefenderSelector selector)',')',1).replace('(selector ? selector : CvUnitCombat::SelectStackDefender)','CvUnitCombat::SelectStackDefender')
assert normalized==original,'Default scalar forecast body/order drifted from DLL60'
original=original.replace('CvDangerPlotContents::GetStackDanger(','CvDangerPlotContents::OriginalStackDanger(',1)
outcome=function(danger,'void CvDangerPlotContents::GetStackDangerOutcome(');extract=function(danger,'int CvDangerPlotContents::GetStackDangerFromOutcome(')
air=function(danger,'static int StackAirStrikeChance(');expected=function(danger,'static int StackExpectedStrikeDamage(');city=function(danger,'static int SimulateStackCityThreats(')
collateral=function(combat,'std::vector<std::pair<const CvUnit*, int> > CvUnitCombat::GetStackCollateralDamage(')
selection=combat[combat.index('static bool IsStackCombatCandidate('):combat.index('// City bombardment uses the identical selector',combat.index('static bool IsStackCombatCandidate('))] if '// City bombardment uses the identical selector' in combat else combat[combat.index('static bool IsStackCombatCandidate('):combat.index('// City bombardment uses the same survival',combat.index('static bool IsStackCombatCandidate('))]
prefix=prefix.replace('#include <vector>','#define NOMINMAX\n#include <windows.h>\n#undef near\n#undef far\n#include <deque>\n#include <unordered_map>\n#include <cstring>\n#include <vector>',1)
prefix=prefix.replace('struct CvSeeder{};', 'struct CvSeeder{};\nstatic unsigned int selectionCalls=0,exchangeCalls=0,finalQuickCalls=0,eventCalls=0,idReads=0;\nstatic bool MOD_EVENTS_CAN_MOVE_INTO=false;static int mutation=0,mutationID=0;\nvoid OnID();void OnExchange();')
prefix=prefix.replace('int GetID()const{return id;}int getOwner()const{return owner;}int getTeam()const{return owner;}int getDomainType()', 'int GetID()const{OnID();return id;}int getOwner()const{return owner;}int getTeam()const{return owner;}int getDomainType()')
prefix=prefix.replace('bool alive,delayed,active,invisible,ranged,noCapture,civilian,trade,terrainIgnore,featureIgnore;', 'bool defend,cargo,flank,flankTarget,anti;int defense;bool alive,delayed,active,invisible,ranged,noCapture,civilian,trade,terrainIgnore,featureIgnore;')
prefix=prefix.replace('alive(true),delayed(false)', 'defend(true),cargo(false),flank(false),flankTarget(false),anti(false),defense(25),alive(true),delayed(false)')
prefix=prefix.replace('bool IsDead()const{return !alive;}', 'bool IsCanDefend()const{return defend;}bool isCargo()const{return cargo;}bool IsDead()const{return !alive;}')
prefix=prefix.replace('bool IsCombatUnit()const{return !civilian;}bool isCargo()const{return false;}', 'bool IsCombatUnit()const{return !civilian;}bool isCargo()const{return cargo;}')
prefix=prefix.replace('int GetMaxRangedCombatStrength(', 'int GetRangeCombatDamage(const CvUnit*d,const CvCity*,int,int&,bool,int extra,int other,const CvPlot*,const CvPlot*,bool,bool)const{OnExchange();return max(0,strength-extra/5-d->defense/2+other/4);}\n int GetAirStrikeDefenseDamage(const CvUnit*,bool,const CvPlot*)const{OnExchange();return defense/3;}\n int GetMaxDefenseStrength(const CvPlot*,const CvUnit*,const CvPlot*,bool,bool,int extra)const{OnExchange();return max(1,defense-extra/5);}\n int getMeleeCombatDamage(int a,int d,int&ret,bool,const CvUnit*,int,int)const{OnExchange();ret=max(0,d-a/2);return max(0,a-d/2);}\n bool isBetterDefenderThan(const CvUnit*u,const CvUnit*)const{return !u||defense>u->defense;}\n int GetMaxRangedCombatStrength(',1)
prefix=prefix.replace('int GetMaxAttackStrength(const CvPlot*,const CvPlot*,const CvUnit*,bool,bool,int extra=0,int=0)const{return', 'int GetMaxAttackStrength(const CvPlot*,const CvPlot*,const CvUnit*,bool,bool,int extra=0,int=0)const{OnExchange();return')
prefix=prefix.replace('CvPlot(int i=0):index', 'CvPlot(int i=0):index')
services=services.replace('static bool cityEnabled=true;', 'static bool enabled=true,selectionEnabled=true,cityEnabled=true;')
services=services.replace('bool IsEnabled(){return true;}', 'bool IsEnabled(){return enabled;}bool CanFlank(const CvUnit*u){return u->flank;}bool IsAntiCavalry(const CvUnit*u){return u->anti;}bool IsFlankTarget(const CvUnit*u){return u->flankTarget;}')
services=services.replace('int GetInt(const char*,int d){return d;}', 'int GetInt(const char*n,int d){return !strcmp(n,"DefenderSelectionEnabled")?(selectionEnabled?1:0):d;}')
stub=function(services,' const CvUnit*SelectStackDefender(');services=services.replace(stub,' const CvUnit*SelectStackDefender(const CvUnit*,const CvPlot*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,bool,int);')
services=services.replace('return SelectStackDefender(NULL,NULL,p,c,d,true,0);','return c.empty()?NULL:c.front();')
services=services.replace('{retaliation=6;return max(', '{++finalQuickCalls;retaliation=6;return max(')
services=services.replace('static bool IsStackCombatCandidate(const CvUnit*u,const SUnitIDValueContainer&d){return u&&u->alive&&!u->delayed&&u->hp>d.GetValue(u->id);}', '')
cache=tactical[tactical.index('struct StackForecastKey\n'):tactical.index('static void AppendStackCandidates(')]+function(tactical,'static void AppendStackCandidates(')+function(tactical,'static const CvUnit* SelectCachedStackDefender(const CvUnit* attacker, const CvPlot* from, const CvPlot* target,\n const vector<const CvUnit*>& candidates, const SUnitIDValueContainer& damage, bool ranged, int attackerDamage)\n{')
cache=cache.replace('CvStacking::GetCityProtection','CvStacking::GetCityProtection')
selection=selection.replace('{','{\n',1);selection=selection.replace('const CvUnit* CvUnitCombat::SelectStackDefender(', 'const CvUnit* CvUnitCombat::SelectStackDefender(',1)
selstart=selection.index('const CvUnit* CvUnitCombat::SelectStackDefender(');brace=selection.index('{',selstart);selection=selection[:brace+1]+'\n ++selectionCalls;'+selection[brace+1:]
fixture_support=r'''
const int NO_PLAYER=-1,TACTSIM_MAX_UNITS=13;
namespace CvStackingStrengthCache{static volatile LONG epoch=0;long SceneEpoch(){return InterlockedCompareExchange(&epoch,0,0);}void Invalidate(){InterlockedIncrement(&epoch);}}
struct StorageStub{size_t limit;StorageStub():limit(512){}size_t getSizeLimit()const{return limit;}}gTactPosStorage;
'''
callbacks=r'''
void OnID(){++idReads;if(mutation==1&&gStackDefenderScratchBusy){mutation=0;CvStackingStrengthCache::Invalidate();}}
void OnExchange(){++exchangeCalls;if(MOD_EVENTS_CAN_MOVE_INTO)++eventCalls;if(mutation==2){mutation=0;CvStackingStrengthCache::Invalidate();}else if(mutation==3){mutation=0;StackForecastScope nested;}}
'''
tests=r'''
static int checks=0,failures=0;void Check(const char*n,bool okay){++checks;if(!okay){++failures;if(failures<10)printf("FAIL %s\n",n);}}
static unsigned seed=72311;unsigned Next(){seed=seed*1664525u+1013904223u;return seed;}
struct ForeignArgs{const CvUnit*a;const CvPlot*p;const vector<const CvUnit*>*r;const SUnitIDValueContainer*d;const CvUnit*expected;};
DWORD WINAPI Foreign(void*v){ForeignArgs*f=(ForeignArgs*)v;const CvUnit*x=SelectCachedStackDefender(f->a,NULL,f->p,*f->r,*f->d,false,7);return x==f->expected?0:1;}
int main(){CvPlot plot(0),near(1),far(17);CvUnit attacker(77,1,&near),units[5];vector<const CvUnit*>roster;SUnitIDValueContainer damage;
 for(int trial=0;trial<12000;++trial){StackForecastScope scope;CvStacking::enabled=true;CvStacking::selectionEnabled=trial%5!=0;roster.clear();damage.clear();attacker=CvUnit(77,1,&near);attacker.strength=20+Next()%180;attacker.flank=Next()%2!=0;attacker.domain=Next()%3;bool ranged=Next()%2!=0;int wounds=(int)(Next()%70)-8;
  for(int i=0;i<5;++i){units[i]=CvUnit(i,0,&plot);units[i].hp=20+Next()%100;units[i].defense=10+Next()%120;units[i].maxHP=75+Next()%100;units[i].ranged=Next()%2!=0;units[i].defend=Next()%9!=0;units[i].cargo=Next()%11==0;units[i].alive=Next()%13!=0;units[i].delayed=Next()%17==0;units[i].domain=Next()%3;units[i].anti=Next()%2!=0;units[i].flankTarget=Next()%2!=0;damage.SetValue(i,(int)(Next()%100)-8);roster.push_back(&units[i]);}
  if(trial%3==0)std::reverse(roster.begin(),roster.end());if(trial%7==0)roster.push_back(&units[1]);if(trial%11==0)roster.push_back(NULL);
  const CvUnit*expected=CvUnitCombat::SelectStackDefender(&attacker,NULL,&plot,roster,damage,ranged,wounds);const CvUnit*actual=SelectCachedStackDefender(&attacker,NULL,&plot,roster,damage,ranged,wounds);Check("random actual selector identity",actual==expected);
  unsigned before=selectionCalls;for(int j=0;j<4;++j){damage.SetValue(900+j,(int)Next());Check("outside roster wounds cannot change selection",SelectCachedStackDefender(&attacker,NULL,&plot,roster,damage,ranged,wounds)==expected);}Check("candidate-only key exact values unchanged",actual==expected);
  if(gStackDefenderHits)Check("repeated memo skips actual selector",selectionCalls==before);
 }
 {StackForecastScope scope;CvStacking::enabled=CvStacking::selectionEnabled=true;roster.clear();damage.clear();attacker=CvUnit(55,1,&near);for(int i=0;i<3;++i){units[i]=CvUnit(i,0,&plot);units[i].defense=20+i*5;roster.push_back(&units[i]);}const CvUnit*expected=CvUnitCombat::SelectStackDefender(&attacker,NULL,&plot,roster,damage,false,0);unsigned before=selectionCalls;for(int j=0;j<20000;++j){damage.SetValue(500,Next()%100);Check("dense repeated full selection exact",SelectCachedStackDefender(&attacker,NULL,&plot,roster,damage,false,0)==expected);}Check("repeated selection one original evaluation",selectionCalls-before==1&&gStackDefenderHits==19999);printf("selector exact work control:20000queries originalEvaluations%u cacheHits%lu; no native speed claim\n",selectionCalls-before,gStackDefenderHits);
  CvUnit aliasAttacker=attacker;aliasAttacker.owner=2;before=selectionCalls;SelectCachedStackDefender(&aliasAttacker,NULL,&plot,roster,damage,false,0);Check("attacker owner is independent key",selectionCalls==before+1);
  for(int i=0;i<3;++i)units[i].owner=2;before=selectionCalls;SelectCachedStackDefender(&attacker,NULL,&plot,roster,damage,false,0);Check("homogeneous defender owner is independent key",selectionCalls==before+1);for(int i=0;i<3;++i)units[i].owner=0;
  CvStacking::selectionEnabled=false;CvStackingStrengthCache::Invalidate();units[0].defense=units[1].defense=units[2].defense=25;vector<const CvUnit*>ordered(roster.begin(),roster.begin()+2),reversed=ordered;reverse(reversed.begin(),reversed.end());Check("disabled selection ordered tie first",SelectCachedStackDefender(&attacker,NULL,&plot,ordered,damage,false,0)==ordered.front());Check("disabled selection reversed tie distinct key",SelectCachedStackDefender(&attacker,NULL,&plot,reversed,damage,false,0)==reversed.front());CvStacking::selectionEnabled=true;CvStackingStrengthCache::Invalidate();for(int i=0;i<3;++i)units[i].defense=20+i*5;
  vector<const CvUnit*>duplicates(2,&units[0]);before=selectionCalls;SelectCachedStackDefender(&attacker,NULL,&plot,duplicates,damage,false,0);SelectCachedStackDefender(&attacker,NULL,&plot,duplicates,damage,false,0);Check("same-pointer duplicate occurrences retained and reusable",selectionCalls==before+1);
  vector<const CvUnit*>mixed=roster;units[2].owner=2;before=selectionCalls;SelectCachedStackDefender(&attacker,NULL,&plot,mixed,damage,false,0);SelectCachedStackDefender(&attacker,NULL,&plot,mixed,damage,false,0);Check("mixed owner roster always original",selectionCalls==before+2);units[2].owner=0;
  CvUnit aliasUnit=units[1];mixed=roster;mixed.push_back(&aliasUnit);before=selectionCalls;SelectCachedStackDefender(&attacker,NULL,&plot,mixed,damage,false,0);SelectCachedStackDefender(&attacker,NULL,&plot,mixed,damage,false,0);Check("distinct sameowner-ID objects bypass",selectionCalls==before+2);
  vector<const CvUnit*>solo(1,&units[0]);before=selectionCalls;unsigned math=exchangeCalls;for(int i=0;i<200;++i)Check("singleton original fast path",SelectCachedStackDefender(&attacker,NULL,&plot,solo,damage,false,0)==&units[0]);Check("singleton no cache entry/exchange work",selectionCalls==before+200&&exchangeCalls==math);
  CvStackingStrengthCache::Invalidate();mutation=1;idReads=0;mutationID=8;before=selectionCalls;Check("key callback returns original once",SelectCachedStackDefender(&attacker,NULL,&plot,roster,damage,false,0)==expected&&selectionCalls==before+1);Check("key invalidation admits no selector",gStackDefenderForecasts.empty());
  for(int mode=2;mode<=3;++mode){CvStackingStrengthCache::Invalidate();mutation=mode;before=selectionCalls;Check("leaf invalidation returns original once",SelectCachedStackDefender(&attacker,NULL,&plot,roster,damage,false,0)==expected&&selectionCalls==before+1);Check("leaf invalidation rejects admission",gStackDefenderForecasts.empty());}
  MOD_EVENTS_CAN_MOVE_INTO=true;before=selectionCalls;unsigned events=eventCalls;SelectCachedStackDefender(&attacker,NULL,&plot,roster,damage,false,0);SelectCachedStackDefender(&attacker,NULL,&plot,roster,damage,false,0);Check("scripted movement bypass preserves evaluations/callbacks",selectionCalls==before+2&&eventCalls>events);MOD_EVENTS_CAN_MOVE_INTO=false;
  {StackForecastScope nested;before=selectionCalls;SelectCachedStackDefender(&attacker,NULL,&plot,roster,damage,false,0);SelectCachedStackDefender(&attacker,NULL,&plot,roster,damage,false,0);Check("nested previews private original fallback",selectionCalls==before+2);}
  ForeignArgs args={&attacker,&plot,&roster,&damage,expected};HANDLE h=CreateThread(NULL,0,Foreign,&args,0,NULL);Check("foreign thread created",h!=NULL);if(h){WaitForSingleObject(h,10000);DWORD result=1;GetExitCodeThread(h,&result);Check("foreign preview original result",result==0);CloseHandle(h);}
  gTactPosStorage.limit=4;
 }
 // Actual scalar/air/city/collateral loops with original60 NULL callback oracle.
 CvCity defended(0,0,&plot);CvUnit enemies[8];CvCity enemyCity(7,1,&near);
 for(int trial=0;trial<3000;++trial){StackForecastScope scope;CvStacking::enabled=CvStacking::selectionEnabled=true;CvDangerPlotContents contents;contents.m_pPlot=&plot;contents.m_iFogCount=trial%4;contents.m_iImprovementDamage=trial%9;contents.m_bFlatPlotDamage=trial%2!=0;plot.city=trial%4==0?&defended:NULL;plot.friendly=trial%4==0;defended.hp=200-trial%190;defended.protection=trial%91;roster.clear();SUnitIDValueContainer friendly,enemy;
  for(int p=0;p<4;++p){players[p]=CvPlayer();players[p].id=p;for(int q=0;q<4;++q)if(q!=p)players[p].enemies.push_back(q);}
  for(int i=0;i<5;++i){units[i]=CvUnit(i,0,&plot);units[i].hp=45+Next()%56;units[i].defense=10+Next()%80;units[i].strength=20+Next()%100;units[i].ranged=Next()%2!=0;units[i].anti=Next()%2!=0;units[i].flankTarget=Next()%2!=0;units[i].collateralLimit=Next()%6;units[i].terrainIgnore=Next()%2!=0;units[i].featureIgnore=Next()%2!=0;roster.push_back(&units[i]);friendly.SetValue(i,Next()%30);players[0].units[i]=&units[i];players[0].possible.push_back(make_pair(i,0));}
  for(int i=0;i<8;++i){int owner=1+i%2,id=i%4;enemies[i]=CvUnit(id,owner,&near);enemies[i].strength=30+Next()%120;enemies[i].flank=Next()%2!=0;enemies[i].ranged=Next()%2!=0;enemies[i].domain=i%4==0?DOMAIN_AIR:DOMAIN_LAND;enemies[i].collateralLimit=Next()%6;enemies[i].aoe=Next()%3;players[owner].units[id]=&enemies[i];contents.m_apUnits.push_back(make_pair(owner,id));enemy.SetValue(id,Next()%30);}
  players[1].cities[7]=&enemyCity;contents.m_apCities.push_back(make_pair(1,7));if(trial%5==0)roster.push_back(&units[1]);if(trial%7==0)reverse(roster.begin(),roster.end());if(trial%13==0)units[4].owner=2;
  for(int i=0;i<5;++i){int a=contents.OriginalStackDanger(&units[i],roster,friendly,enemy);int b=contents.GetStackDanger(&units[i],roster,friendly,enemy,SelectCachedStackDefender);Check("complete original scalar callback forecast",a==b);int c=contents.GetStackDanger(&units[i],roster,friendly,enemy);Check("NULL callback complete original forecast",a==c);SUnitIDValueContainer final;bool fall=false;contents.GetStackDangerOutcome(units[i].getOwner(),units[i].getTeam(),plot.isFriendlyCity(units[i]),roster,friendly,enemy,final,fall,SelectCachedStackDefender);Check("outcome callback result agrees scalar",a==contents.GetStackDangerFromOutcome(&units[i],friendly,final,fall));}
  Check("retained tables stay existing capacity/payload budget",gStackDangerForecasts.size()+gStackDefenderForecasts.size()<=gStackEntryLimit&&gStackKeyPayloadBytes<=gStackKeyPayloadLimit);
 }
 {StackForecastScope scope;StackForecastKey first,second;first.state.push_back(17);second.state.push_back(91);size_t h=0;h^=(size_t)17+0x9e3779b9+(h<<6)+(h>>2);first.state.push_back((int)(h-0x9e3779b9-(h<<6)-(h>>2)));h=0;h^=(size_t)91+0x9e3779b9+(h<<6)+(h>>2);second.state.push_back((int)(h-0x9e3779b9-(h<<6)-(h>>2)));Check("forced full-key hash collision distinct",StackForecastKeyHash()(first)==StackForecastKeyHash()(second)&&!(first==second));StoreStackDefenderForecast(first,&units[0]);StoreStackDefenderForecast(second,&units[1]);Check("collision storage uses complete equality",gStackDefenderForecasts.find(first)->second==&units[0]&&gStackDefenderForecasts.find(second)->second==&units[1]);}
 Check("final quick hit was executed independently",finalQuickCalls>1000);printf("actual selector/danger callback: %d checks,%d failures; finalQuickCalls%u; complete danger and selection/exchange bodies actual, damage services deterministic\n",checks,failures,finalQuickCalls);return failures?1:0;}
'''
danger_types=header[header.index('typedef std::vector<std::pair<PlayerTypes,int>> DangerUnitVector;'):header.index('class CvUnit;',header.index('typedef std::vector<std::pair<PlayerTypes,int>> DangerUnitVector;'))].replace('>>','> >')
fixture=prefix+container+alias+danger_types+contents+services+fixture_support+cache+callbacks+selection+air+expected+city+collateral+original+scalar+outcome+extract+tests
(out/'test.cpp').write_text(fixture,encoding='utf-8')
if '--emit-only' in sys.argv:print('Selector fixture emitted; no compile/run');sys.exit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe';compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);(out/'compile.log').write_text(compiled.stdout+compiled.stderr)
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=60);print(run.stdout+run.stderr,end='');(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,control=control,scalar_default_body_identical=True,fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),scope='Actual selector cache/storage/key and original selector/exchange, complete scalar/outcome/air/city/collateral. Engine strength/damage services deterministic; native comparison required.'),indent=2));sys.exit(run.returncode)
