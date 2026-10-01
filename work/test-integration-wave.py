"""Bind the final first-wave oracle to complete composed offensive/core sources.

Only engine service models are supplied here. All candidate OffensiveAI methods,
public declarations and ReadyWithAvailableUnits come from --source-dir verbatim
after include/forward declaration removal. Healing's independent native formula
oracle remains a separate prerequisite; this fixture models that service boundary.
"""
from pathlib import Path
import argparse,ast,hashlib,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
P=argparse.ArgumentParser(description=__doc__)
P.add_argument('--source-dir',type=Path,required=True)
P.add_argument('--emit-only',action='store_true')
args=P.parse_args();SOURCE=args.source_dir.resolve();OUT=ROOT/'work/integration-wave-regression';OUT.mkdir(exist_ok=True)
harness=(ROOT/'work/test-first-wave.py').read_text(encoding='utf-8-sig')
prefix=harness[:harness.index("\ntests=r'''")]
ns={'__file__':str(ROOT/'work/test-first-wave.py')}
exec(compile(prefix,'frozen first-wave services and original controls','exec'),ns)
stubs=ns['stubs'];clean=ns['clean'];fun=ns['fun'];policy=ns['policy']
tests=next(ast.literal_eval(n.value) for n in ast.parse(harness).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='tests' for t in n.targets))
files={n:p.read_text(encoding='utf-8-sig') for p in SOURCE.glob('*.cpp') if not p.name.startswith(('control-','wave-','production-')) for n in [p.name]}
files.update({n:(SOURCE/n).read_text(encoding='utf-8-sig') for n in ('CvStackingOffensiveAI.h','CvCity.h')})
manifest=json.loads((SOURCE/'finished-proof.json').read_text())
hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in files.items()}
for n,h in manifest['candidate_hashes'].items():assert hashes[n]==h,(n,'Composed whole-file binding mismatch')
assert fun(files['CvStackingOffensiveAI.cpp'],'    bool TryReadyCoreForArmy(')==fun(ns['trial']['CvStackingOffensiveAI.cpp'],'    bool TryReadyCoreForArmy('),'Core filter must exactly match frozen 49-check component'

def replace_once(old,new):
 global stubs
 assert stubs.count(old)==1,(old[:80],stubs.count(old))
 stubs=stubs.replace(old,new,1)

# Production and continuity engine services; the actual policy implementation
# remains in the composed complete OffensiveAI module below.
replace_once('typedef int PlayerTypes;', 'typedef int PromotionTypes;typedef int TechTypes;typedef int UnitCombatTypes;typedef int UnitClassTypes;\ntypedef int PlayerTypes;')
replace_once('const int NO_UNIT=-1,', 'const int NO_DOMAIN=-1,NO_UNITCOMBAT=-1,NO_UNITCLASS=-1,NO_TECH=-1;\nconst int NO_UNIT=-1,')
replace_once('struct CvPlayer{', '''struct IntegrationTraits{bool HasFreePromotionUnitCombat(int,int)const{return false;}bool HasFreePromotionUnitClass(int,int)const{return false;}};
struct IntegrationEconomy{int GetSoftSupplyCap()const{return 100;}};
struct IntegrationMilitary{int GetRecommendedMilitarySize()const{return 100;}int GetRecommendLandArmySize()const{return 50;}int GetRecommendNavySize()const{return 50;}int GetRecommendedExplorers()const{return 0;}};
struct CvPlayer{''')
replace_once('CvDangerPlots*GetDangerPlots()const{return &dangerMap;}', '''IntegrationTraits traits;IntegrationEconomy economy;IntegrationMilitary military;
 IntegrationTraits*GetPlayerTraits(){return &traits;}IntegrationEconomy*GetEconomicAI(){return &economy;}IntegrationMilitary*GetMilitaryAI(){return &military;}
 int GetNumUnitsSupplied()const{return 100;}int GetNumUnitsToSupply()const{return (int)units.size();}int getNumMilitaryLandUnits()const{int n=0;for(size_t i=0;i<units.size();++i)n+=units[i]->domain==DOMAIN_LAND;return n;}int getNumMilitarySeaUnits()const{int n=0;for(size_t i=0;i<units.size();++i)n+=units[i]->domain==DOMAIN_SEA;return n;}
 int getNumCities()const{return (int)cities.size();}bool HasTech(int)const{return true;}bool IsFreePromotion(int)const{return false;}
 CvDangerPlots*GetDangerPlots()const{return &dangerMap;}''')
replace_once('struct CvUnitEntry{', '''struct CvPromotionEntry{bool IsNoCapture()const{return false;}bool IsOnlyDefensive()const{return false;}int GetTechPrereq()const{return NO_TECH;}};
struct CvUnitEntry{''')
replace_once('int GetRange()const{return range;}int GetDefaultUnitAIType()const{return role;}', '''int GetRange()const{return range;}bool IsMilitarySupport()const{return false;}bool IsNoSupply()const{return false;}bool GetFreePromotions(int)const{return false;}int GetUnitCombatType()const{return 0;}int GetUnitClassType()const{return 0;}bool IsUnitEraUpgrade()const{return false;}int GetUnitNewEraPromotions(int,int)const{return 0;}int GetDefaultUnitAIType()const{return role;}''')
replace_once('bool IsBuildingUnitForOperation()const', 'vector<PromotionTypes>getFreePromotions()const{return vector<PromotionTypes>();}bool IsBuildingUnitForOperation()const')
replace_once('CvUnitEntry entries[8];Game&', 'CvPromotionEntry promotion;int getNumPromotionInfos()const{return 1;}CvPromotionEntry*getPromotionInfo(int p){return p==0?&promotion:NULL;}int getNumEraInfos()const{return 4;}CvUnitEntry entries[8];Game&')
stubs+='''
struct IntegrationTeam{int GetCurrentEra()const{return 1;}}integrationTeam;
#define GET_TEAM(teamID) integrationTeam
bool IsPromotionValidForUnitCombatType(int,UnitTypes){return true;}bool IsPromotionValidForCivilianUnitType(int,UnitTypes){return false;}
'''
if 'bool Enabled(int,int)' not in stubs and 'bool Enabled(int,PlayerTypes)' not in stubs:
 diagnostic_flag=re.search(r'namespace CvStackingDiagnostics\{bool enabled=(?:true|false);',stubs)
 if diagnostic_flag:replace_once(diagnostic_flag.group(),diagnostic_flag.group()+'bool Enabled(int,PlayerTypes){return enabled;}')
 else:replace_once('namespace CvStackingDiagnostics{', 'namespace CvStackingDiagnostics{bool enabled=false;bool Enabled(int,PlayerTypes){return enabled;}')

continuity_text=(ROOT/'work/test-ai-continuity-followup.py').read_text(encoding='utf-8-sig')
continuity_ast=ast.parse(continuity_text)
literal=lambda tree,name:next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
continuity_info=literal(continuity_ast,'info');continuity_tests=literal(continuity_ast,'tests')
offensive_ast=ast.parse((ROOT/'work/test-offensive-support.py').read_text(encoding='utf-8-sig'))
old_tests=literal(offensive_ast,'tests');continuity_helpers=old_tests[:old_tests.index('void policyTests()')]
combat=files['CvUnitCombat.cpp'];begin=combat.index('namespace\n{\n    // Independent of diagnostic level:');end=combat.index('void CvUnitCombat::ResolveCombat(',begin)
actual_combat_scope=combat[begin:end]
interop_tests=r'''
void integrationStaffTests(){
 using namespace CvStackingOffensiveAI;
 init();CvPlot target(10,20),stage(1,18);CvCity city(10,&target);city.owner=1;
 CvAIOperation op;CvArmyAI army;setup(op,army,target,stage);CvUnit unit(17);put(unit,stage);
 RecordTransfer(&unit,target.id,op.id,1);Objective& objective=objectives[ObjectiveKey(0,target.id,DOMAIN_LAND)];
 objective.staffTurn=objective.productionTurn=objective.assaultTurn=GC.game.turn;
 RecordTransfer(&unit,target.id,op.id,1);
 check(objective.staffTurn==-1&&objective.productionTurn==-1,"transfer invalidates integrated staffing and production-role cache together");
 check(objective.assaultTurn==GC.game.turn,"transfer preserves once-turn assault forecast rather than reopening paths");
 objective.staffTurn=objective.productionTurn=GC.game.turn;
 RecordCombatContribution(0,unit.id,target.id,DOMAIN_LAND,target.id,1,0,7,false);
 check(objective.staffTurn==-1&&objective.productionTurn==-1,"actual contribution invalidates integrated staffing and production-role cache together");
 check(objective.assaultTurn==GC.game.turn,"combat contribution preserves strategic once-turn assault work bound");
}
void integrationGoalStaffTests(){
 using namespace CvStackingOffensiveAI;
 init();CvPlot oldPlot(10,20),newPlot(20,21),stage(1,18),remote(40,100),factoryPlot(30,18);
 CvCity oldCity(10,&oldPlot),newCity(20,&newPlot),factory(30,&factoryPlot);oldCity.owner=newCity.owner=oldPlot.owner=newPlot.owner=1;
 CvAIOperation op;CvArmyAI army;setup(op,army,oldPlot,stage);CvUnit unit(17);put(unit,stage);
 GC.map.plots[newPlot.id]=&newPlot;GC.map.plots[remote.id]=&remote;GC.map.plots[factoryPlot.id]=&factoryPlot;players[0].cities.push_back(&factory);
 RecordTransfer(&unit,oldPlot.id,op.id,1);ProductionIntent intent;GetProductionIntent(&factory,0,intent,false);
 Objective& oldObjective=objectives[ObjectiveKey(0,oldPlot.id,DOMAIN_LAND)];
 check(oldObjective.staffCapture==1&&oldObjective.staffTurn==GC.game.turn,"old-goal cached capture staffing is initially live");
 const int paths=unit.pathCalls;RecordTransfer(&unit,newPlot.id,-1,1);
 Objective& nextObjective=objectives[ObjectiveKey(0,newPlot.id,DOMAIN_LAND)];
 check(oldObjective.staffTurn==-1&&oldObjective.productionTurn==-1&&nextObjective.staffTurn==-1&&nextObjective.productionTurn==-1,"goal transfer invalidates both old and new staffing and production-role caches");
 GetProductionIntent(&factory,0,intent,false);
 check(oldObjective.staffCapture==0&&nextObjective.staffCapture==1,"production refresh cannot keep transferred capturer credited to old goal");
 unit.position=&remote;CancelCommitment(&unit);
 check(commitments.count(Key(0,unit.id))==0&&nextObjective.staffTurn==-1&&nextObjective.productionTurn==-1,"canceling support invalidates old goal before removing commitment");
 GetProductionIntent(&factory,0,intent,false);
 check(nextObjective.staffCapture==0&&unit.pathCalls==paths,"canceled distant support cannot leave ghost role credit or add paths");
}
'''
continuity_tests=continuity_tests.replace('int main(){','int ContinuityMain(){integrationStaffTests();integrationGoalStaffTests();',1)
continuity='namespace IntegratedContinuity{using namespace Trial;\n'+continuity_info+actual_combat_scope+continuity_helpers+interop_tests+continuity_tests+'\n}\n'
assert tests.count(' printf("FIRST WAVE:')==1
clock_test=r'''
 {Scenario s(4);for(int i=1;i<4;++i)s.Ranged(i);for(int i=0;i<4;++i)s.units[i].cityShot=50;Trial::CvStackingOffensiveAI::ObserveOperation(&s.op);Trial::Objective&objective=Trial::objectives.begin()->second;objective.assault.phase=1;failWaveRecord=true;Trial::CvStackingOffensiveAI::AssaultPlan plan=Trial::CvStackingOffensiveAI::AssessAssault(0,&s.city,DOMAIN_LAND);Check("first-ready clock stamps readiness finalized by metadata continuation fallback",plan.ready&&!objective.waveComplete&&objective.firstReadyTurn==GC.game.turn);}
'''
tests=tests.replace(' printf("FIRST WAVE:',clock_test+' int continuityResult=IntegratedContinuity::ContinuityMain();\n printf("FIRST WAVE:',1).replace('return failed?1:0;\n}', 'return (failed||continuityResult)?1:0;\n}',1)

module=''
for name,text in [('Baseline',ns['original']),('PreviousWave',ns['previous']),('Trial',files)]:
 alias='namespace CvStackingAI{using ::CvStackingAI::Enabled;using ::CvStackingAI::UnitStrength;using ::CvStackingAI::RetainCityUnit;static int Setting(const char*n,int f){return CvStacking::GetInt(n,f);}}\n'
 body=clean(text['CvStackingOffensiveAI.cpp']).replace('try{o.waveRows.push_back(', 'try{if(failWaveRecord){failWaveRecord=false;throw std::bad_alloc();}o.waveRows.push_back(').replace('eligibleRows.reserve(o.waveRows.size());','if(failCoreRows){failCoreRows=false;throw std::bad_alloc();}eligibleRows.reserve(o.waveRows.size());')
 module+='namespace '+name+'{\n'+alias+re.sub(r'^class Cv\w+;\n','',clean(text['CvStackingOffensiveAI.h']),flags=re.M)+body+'\nnamespace CvStackingAI{'+fun(text['CvStackingAI.cpp'],'    bool ReadyWithAvailableUnits(')+'\n}\n}\n'
code=stubs+policy+module+continuity+tests;(OUT/'test.cpp').write_text(code,encoding='utf-8')
binding=dict(source_dir=str(SOURCE),source_hashes=hashes,finished_proof_sha256=hashlib.sha256((SOURCE/'finished-proof.json').read_bytes()).hexdigest(),fixture_sha256=hashlib.sha256(code.encode()).hexdigest(),combat_scope_sha256=hashlib.sha256(actual_combat_scope.encode()).hexdigest(),frozen_component_fixture_sha256='cf7941e17944aec3677e6ba3b8f52c7fc6e0652efed899c47b357a39b633ef37',scope='Complete composed OffensiveAI/header plus actual ReadyWithAvailableUnits and post-combat scope, preserving all 49 frozen wave and 64 continuity checks, previous-wave veto negative control, optional metadata fault seams, nine staffing/production-cache interop checks including transfer/cancel ghost-role invalidation and a finalized-readiness clock check. Other composed files bound whole but not executed; city healing and native production sanity are independently verified by their respective integration fixtures. No native game/timing claim.')
(OUT/'proof.json').write_text(json.dumps(binding,indent=2)+'\n')
if args.emit_only:print(OUT/'test.cpp');sys.exit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for n in ('CL','_CL_','LINK'):env.pop(n,None)
build=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(OUT/'test.cpp'),'/Fo'+str(OUT/'test.obj'),'/Fe'+str(OUT/'test.exe')],cwd=OUT,env=env,capture_output=True,text=True,timeout=60);(OUT/'compile.log').write_text(build.stdout+build.stderr)
if build.returncode:print(build.stdout+build.stderr);sys.exit(build.returncode)
run=subprocess.run([str(OUT/'test.exe')],cwd=OUT,capture_output=True,text=True,timeout=45);print(run.stdout+run.stderr);binding.update(compile_returncode=build.returncode,test_returncode=run.returncode,output=run.stdout+run.stderr);(OUT/'result.json').write_text(json.dumps(binding,indent=2)+'\n');sys.exit(run.returncode)
