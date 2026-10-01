"""Actual staged offensive registry and post-combat scope, deterministic services."""
from pathlib import Path
import argparse,ast,hashlib,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
P=argparse.ArgumentParser();P.add_argument('--emit-only',action='store_true');args=P.parse_args()
subprocess.run([sys.executable,str(ROOT/'work/stage-ai-continuity-followup.py')],check=True,capture_output=True)
STAGE=ROOT/'work/ai-continuity-followup-staged';OUT=ROOT/'work/ai-continuity-followup-regression';OUT.mkdir(exist_ok=True)
generator=(ROOT/'work/test-offensive-support.py').read_text(encoding='utf-8-sig')
prefix=generator[:generator.index("tests=r'''")]
scope={'__file__':str(ROOT/'work/test-offensive-support.py')}
exec(compile(prefix,'tracked offensive fixture services','exec'),scope)
tree=ast.parse(generator)
oldtests=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='tests' for x in n.targets))
helpers=oldtests[:oldtests.index('void policyTests()')]
source=(STAGE/'CvStackingOffensiveAI.cpp').read_text()
header=(STAGE/'CvStackingOffensiveAI.h').read_text()
combat=(STAGE/'CvUnitCombat.cpp').read_text()
start=combat.index('namespace\n{\n    // Independent of diagnostic level:')
end=combat.index('void CvUnitCombat::ResolveCombat(',start)
actual_scope=combat[start:end]
info=r'''
enum { BATTLE_UNIT_ATTACKER=0,BATTLE_UNIT_DEFENDER=1 };
struct CvCombatInfo{
 CvUnit*attacker,*defender;CvPlot*p;
 CvCombatInfo(CvUnit*a,CvUnit*d,CvPlot*t):attacker(a),defender(d),p(t){}
 CvUnit*getUnit(int slot)const{return slot==BATTLE_UNIT_ATTACKER?attacker:defender;}
 CvPlot*getPlot()const{return p;}
};
'''
tests=r'''
void continuityTests(bool log){
 using namespace CvStackingOffensiveAI;
 init();CvStackingDiagnostics::enabled=log;
 CvPlot t(10,20),s(1,0),from(2,5),detour(3,4),next(4,3),enemyPlot(5,19),elsewhere(6,50);
 CvCity city(10,&t);city.owner=1;
 CvAIOperation op;CvArmyAI a;setup(op,a,t,s);city.owner=1;
 CvUnit u(17);put(u,from);GC.map.plots[detour.id]=&detour;GC.map.plots[next.id]=&next;
 GC.map.plots[enemyPlot.id]=&enemyPlot;GC.map.plots[elsewhere.id]=&elsewhere;
 RecordTransfer(&u,t.id,op.id,5);Key key(0,u.id);
 check(commitments.count(key)==1,"real support commitment created");
 const int initial=commitments[key].lastProgress;
 ++GC.game.turn;RecordTransfer(&u,t.id,op.id,4);
 check(commitments[key].lastProgress==initial,"stationary improved estimate is not actual progress");
 // First route binds; changing a route/stage is not itself progress.
 u.position=&detour;RecordTransfer(&u,t.id,op.id,5);
 RecordStageRouteProgress(&u,t.id,s.id,99,from.id,detour.id);
 check(commitments[key].routeProgress==-1,"first route only establishes identity");
 const int useful=objectives[ObjectiveKey(0,t.id,DOMAIN_LAND)].lastUsefulTurn;
 ++GC.game.turn;u.position=&next;RecordTransfer(&u,t.id,op.id,5);
 RecordStageRouteProgress(&u,t.id,s.id,99,detour.id,next.id);
 check(commitments[key].lastProgress==GC.game.turn && commitments[key].routeProgress==GC.game.turn,"verified route detour retained despite greater city distance");
 check(objectives[ObjectiveKey(0,t.id,DOMAIN_LAND)].lastUsefulTurn==useful,"route progress is not useful assault damage");
 int routeTurn=commitments[key].routeProgress;
 ++GC.game.turn;RecordStageRouteProgress(&u,t.id,s.id,99,next.id,next.id);
 check(commitments[key].routeProgress==routeTurn,"same-hex no-op cannot renew route");
 u.position=&detour;RecordStageRouteProgress(&u,t.id,s.id,99,next.id,detour.id);
 check(commitments[key].routeProgress==routeTurn,"immediate route reversal cannot renew");
 // Real caller order: derived ETA can fall on a reversal without a new best
 // city distance. RecordTransfer must not override the route rejection.
 next.x=8;detour.x=9;from.x=18;u.position=&from;RecordTransfer(&u,t.id,op.id,1);
 u.position=&detour;RecordTransfer(&u,t.id,op.id,5);
 RecordStageRouteProgress(&u,t.id,321,654,from.id,detour.id);
 u.position=&next;RecordTransfer(&u,t.id,op.id,6);
 RecordStageRouteProgress(&u,t.id,321,654,detour.id,next.id);
 const int noProgress=commitments[key].lastProgress;
 ++GC.game.turn;u.position=&detour;RecordTransfer(&u,t.id,op.id,5);
 RecordStageRouteProgress(&u,t.id,321,654,next.id,detour.id);
 check(commitments[key].lastProgress==noProgress,"actual transfer then reverse route does not renew from a lower derived ETA");
 routeTurn=commitments[key].routeProgress;
 u.position=&from;RecordStageRouteProgress(&u,t.id,123,99,detour.id,from.id);
 check(commitments[key].routeProgress==routeTurn,"changed stage cannot renew");
 u.position=&next;RecordStageRouteProgress(&u,t.id,123,100,from.id,next.id);
 check(commitments[key].routeProgress==routeTurn,"changed placement destination cannot renew");
 u.position=&detour;RecordStageRouteProgress(&u,t.id,123,100,next.id,999);
 check(commitments[key].routeProgress==routeTurn,"different actual endpoint cannot certify planned route");
 int target=-1;DomainTypes domain=DOMAIN_SEA;unsigned long generation=0;
 check(GetCombatObjective(&u,target,domain,generation) && target==t.id && domain==DOMAIN_LAND,"committed unit resolves stable combat goal");
 check(IsCombatHistoryCurrent(generation),"current lifetime qualified");
 CvUnit enemy(30);enemy.owner=1;put(enemy,t);
 CvCombatInfo attack(&u,&enemy,&t);
 {OffensiveContributionScope bracket(attack);city.damage+=24;enemy.hp-=7;}
 Objective& objective=objectives[ObjectiveKey(0,t.id,DOMAIN_LAND)];
 check(objective.cityAttempts==1 && objective.fieldContributions==1,"actual city and defender contribution recorded");
 check(objective.lastCityProgress==GC.game.turn && objective.lowestHP==city.maxhp-city.damage,"new city health low refreshes actual siege progress");
 int net=objective.lastCityProgress;
 ++GC.game.turn;{OffensiveContributionScope bracket(attack);}
 check(objective.cityAttempts==2 && objective.lastCityProgress==net,"zero actual damage is an attempt, not net progress");
 // Actual defender health must be resolved by owner/ID; absence is not a kill.
 players[1].units.erase(remove(players[1].units.begin(),players[1].units.end(),&enemy),players[1].units.end());
 int field=objective.fieldContributions;
 ++GC.game.turn;{OffensiveContributionScope bracket(attack);}
 check(objective.fieldContributions==field,"missing defender does not invent damage/death");
 players[1].units.push_back(&enemy);enemy.position=&enemyPlot;CvCombatInfo screen(&u,&enemy,&enemyPlot);
 {OffensiveContributionScope bracket(screen);enemy.hp-=11;}
 check(objective.fieldContributions==field+1,"actual nearby hostile damage contributes to screen clearing");
 check(objective.lastCityProgress==net,"field contribution does not hide stalled city damage");
 // Healing followed by a weaker repeat hit has no new persistent city low.
 city.damage=0;field=objective.lastCityProgress;
 {OffensiveContributionScope bracket(attack);city.damage=5;}
 check(objective.lastCityProgress==field,"healed city repeat chip damage is not net siege progress");
 t.visible=false;int hiddenLow=objective.lowestHP,hiddenProgress=objective.lastCityProgress;
 {OffensiveContributionScope bracket(attack);city.damage+=30;}
 check(objective.lowestHP==hiddenLow && objective.lastCityProgress==hiddenProgress,"hidden post-combat city health cannot reveal net progress");
 t.visible=true;
 CvCombatInfo distant(&u,&enemy,&elsewhere);field=objective.fieldContributions;
 {OffensiveContributionScope bracket(distant);enemy.hp-=3;}
 check(objective.fieldContributions==field,"unrelated distant battle cannot keep objective alive");
 // Check reset before any post-callback identity access.
 unsigned long oldGeneration=generation;
 {OffensiveContributionScope bracket(attack);Reset();}
 check(!IsCombatHistoryCurrent(oldGeneration) && objectives.empty(),"reset cancels active combat bracket without resurrecting histories");
 continuityGeneration=0xffffffffUL;Reset();
 check(!IsCombatHistoryCurrent(0xffffffffUL),"terminal generation wrap rejects old brackets");
 continuityGeneration=1;continuityGenerationExhausted=false;
}
void readyStallTests(bool disabled){
 using namespace CvStackingOffensiveAI;
 init();options["AIAssaultReviewInterval"]=1;if(disabled)options["AIAssaultAttackProgressStallTurns"]=0;
 CvPlot t(10,20),s(1,0),from(2,5);CvCity city(10,&t);city.owner=1;
 CvAIOperation op;CvArmyAI a;setup(op,a,t,s);CvUnit u(17);put(u,from);
 RecordTransfer(&u,t.id,op.id,5);
 Objective& o=objectives[ObjectiveKey(0,t.id,DOMAIN_LAND)];o.assaultTurn=GC.game.turn;o.assault.ready=true;o.assault.phase=1;
 ReviewObjectives(0);check(o.firstReadyTurn==100,"ready assault starts an independent attack-progress clock");
 GC.game.turn=123;o.assaultTurn=123;o.lastUsefulTurn=123;
 ReviewObjectives(0);check(objectives.count(ObjectiveKey(0,t.id,DOMAIN_LAND))==1,"before attack-stall deadline retains objective");
 GC.game.turn=124;o.assaultTurn=124;o.lastUsefulTurn=124;
 ReviewObjectives(0);
 check(disabled?objectives.count(ObjectiveKey(0,t.id,DOMAIN_LAND))==1:objectives.empty(),"queue/arrival progress cannot renew ineffective ready assault; XML disabling retained");
}
void oldShotTests(bool everReady){
 using namespace CvStackingOffensiveAI;
 init();options["AIAssaultReviewInterval"]=1;
 CvPlot t(10,20),s(1,0),from(2,5);CvCity city(10,&t);city.owner=1;
 CvAIOperation op;CvArmyAI a;setup(op,a,t,s);CvUnit u(17);put(u,from);RecordTransfer(&u,t.id,op.id,5);
 Objective& o=objectives[ObjectiveKey(0,t.id,DOMAIN_LAND)];o.lastCityProgress=70;o.lastUsefulTurn=100;
 o.assaultTurn=100;o.assault.ready=everReady;o.assault.phase=everReady?1:0;
 ReviewObjectives(0);
 check(objectives.count(ObjectiveKey(0,t.id,DOMAIN_LAND))==1,"old safe shot cannot expire a newly ready or never-ready force");
 check(everReady?o.firstReadyTurn==100:o.firstReadyTurn==-1,"first-ready origin is required for independent attack timer");
 if(everReady){GC.game.turn=123;o.assaultTurn=123;o.lastCityProgress=122;
  ReviewObjectives(0);check(objectives.count(ObjectiveKey(0,t.id,DOMAIN_LAND))==1,"a new city low postpones actual attack-stall deadline");}
}
void repairRosterTests(){
 using namespace CvStackingOffensiveAI;
 init();options["AIOffensiveSupportMaximumUnits"]=4;
 CvPlot t(10,20),s(1,18);CvCity city(10,&t);city.owner=1;city.strength=3000;CvAIOperation op;CvArmyAI a;setup(op,a,t,s);
 CvUnit units[6];for(int i=0;i<6;++i){units[i].id=100+i;put(units[i],s);}
 units[4].ranged=true;units[4].role=UNITAI_CITY_BOMBARD;units[4].rs=40;
 units[5].ranged=true;units[5].capture=false;units[5].rs=30;
 RecordTransfer(&units[0],t.id,op.id,1);
 std::vector<TacticalForce> forces;TacticalForces(0,forces);
 check(forces.size()==1 && forces[0].units.size()==4,"role repair retains original tactical actor cap");
 check(std::find(forces[0].units.begin(),forces[0].units.end(),units[4].id)!=forces[0].units.end(),"late-created nearby siege is not hidden by first-N melee roster");
 check(std::find(forces[0].units.begin(),forces[0].units.end(),units[5].id)!=forces[0].units.end(),"late-created nearby ranged role can participate");
 check(units[4].pathCalls==0 && units[5].pathCalls==0,"roster role repair adds no path queries");
 // shouldHeal(false) is not a health guarantee when contact/traits override it.
 units[2].ranged=true;units[2].role=UNITAI_CITY_BOMBARD;units[2].hp=50;units[2].heal=false;
 forces.clear();TacticalForces(0,forces);
 check(std::find(forces[0].units.begin(),forces[0].units.end(),units[4].id)!=forces[0].units.end(),"depleted nearby weapon cannot consume healthy replacement priority");
}
int main(){continuityTests(false);continuityTests(true);readyStallTests(false);readyStallTests(true);oldShotTests(false);oldShotTests(true);repairRosterTests();printf("AI continuity: %d checks, %d failures\n",checks,failed);return failed?1:0;}
'''
cpp=OUT/'actual-continuity.cpp'
fixture=scope['stubs']+scope['clean'](header)+scope['policy']+scope['clean'](source)+info+actual_scope+helpers+tests
cpp.write_text(fixture,encoding='utf-8')
proof={'stage':json.loads((STAGE/'manifest.json').read_text()),'fixture_sha256':hashlib.sha256(fixture.encode()).hexdigest(),
       'combat_scope_sha256':hashlib.sha256(actual_scope.encode()).hexdigest(),
       'scope':'Actual complete offensive module and actual post-combat scope; deterministic native services, no real pathfinding/campaign/performance proof'}
(OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
if args.emit_only:print(str(cpp));sys.exit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=OUT/'actual-continuity.exe'
c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(OUT/'actual.obj'),'/Fe'+str(exe)],cwd=OUT,env=env,capture_output=True,text=True,timeout=60)
(OUT/'compile.log').write_text(c.stdout+c.stderr)
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=OUT,capture_output=True,text=True,timeout=30)
proof.update(compile_returncode=c.returncode,test_returncode=r.returncode,output=r.stdout+r.stderr)
(OUT/'result.json').write_text(json.dumps(proof,indent=2)+'\n');print(r.stdout+r.stderr,end='');sys.exit(r.returncode)
