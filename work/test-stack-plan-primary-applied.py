"""Actual applied-source regression against pinned DLL54 executor.

Default reads production directly and requires the approved primary-identity
patch to be present. --prepared explicitly tests the complete prepared source
copies while production remains committed54; it never silently substitutes a
generated executor. Engine missions are deterministic substitutes, not a game.
"""
from pathlib import Path
import ast, hashlib, json, os, subprocess, sys
root=Path(__file__).resolve().parents[1]
revision='0273c8e3e5104493af3be6ae62aec50bb576f7ae'
prepared='--prepared' in sys.argv
scope=root/'work/primary-identity-prepared' if prepared else root/'CvGameCoreDLL_Expansion2'
source=(scope/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
header=(scope/'CvTacticalAI.h').read_text(encoding='utf-8-sig')
control_source=subprocess.check_output(['git','show',revision+':CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
control_header=subprocess.check_output(['git','show',revision+':CvGameCoreDLL_Expansion2/CvTacticalAI.h'],cwd=root).decode('utf-8-sig')
unit_header=(root/'CvGameCoreDLL_Expansion2/CvUnit.h').read_text(encoding='utf-8-sig')
def block(text,name):
 start=text.index(name);opening=text.index('{',start);end=opening+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
damage_type=block(unit_header,'struct SUnitIDValueContainer')+';'
actual_assignment=block(header,'struct STacticalAssignment')+';'
assert 'iPrimaryUnitID' in actual_assignment and 'ePrimaryUnitOwner' in actual_assignment,'Apply approved source patch first, or explicitly use --prepared'
original_assignment=block(control_header,'struct STacticalAssignment')+';'
actual=block(source,'bool TacticalAIHelpers::ExecuteUnitAssignments(')
control=block(control_source,'bool TacticalAIHelpers::ExecuteUnitAssignments(')
actual_helpers=source[source.index('// Execution identities are ephemeral tactical evidence, never save data.'):source.index('bool TacticalAIHelpers::ExecuteUnitAssignments(')]
assert 'actor_removed' in actual and 'pUnit->IsDead()' in actual and 'StackPlanPrimaryMatches' in actual
values=block(source,'static bool EqualAssignedUnitValues(')
original_equality=block(control_source,'bool STacticalAssignment::operator==(').replace('STacticalAssignment','STacticalAssignmentOriginal')
actual_equality=block(source,'bool STacticalAssignment::operator==(')
assert 'iPrimaryUnitID == rhs.iPrimaryUnitID' in actual_equality
scorer=block(source,'bool ScoreAttackDamage(')
old_scorer=block(control_source,'bool ScoreAttackDamage(')
marker='''
    // Primary identity belongs to this projected attack, not to the savegame.
    // City garrison selection and stack defense can choose different units.
    result->iPrimaryUnitID = pEnemyUnit ? pEnemyUnit->GetID() : -1;
    result->ePrimaryUnitOwner = pEnemyUnit ? pEnemyUnit->getOwner() : (pEnemyCity ? pEnemyCity->getOwner() : NO_PLAYER);'''
assert scorer.count(marker)==1 and scorer.replace(marker,'')==old_scorer,'Scorer math/search behavior must remain exact DLL54 except primary recording'
classification_start=scorer.index('\tif (bCityKill)\n\t\tresult->eAssignmentType = A_MELEEKILL;')
classification_end=scorer.index('\n\tresult->iSelfDamage',classification_start)
classification=scorer[classification_start:classification_end]+marker
# Reuse only deterministic engine substitute and test literals; never import or
# execute the proposal generator, and never take its candidate method.
tree=ast.parse((root/'work/test-stack-plan-primary-identity.py').read_text())
strings={}
for node in tree.body:
 if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
  for target in node.targets:
   if isinstance(target,ast.Name) and target.id in ('fixture','tests'):strings[target.id]=node.value.value
fixture=strings['fixture'];tests=strings['tests']
fixture=fixture.replace('__ACTUAL_DAMAGE_CONTAINER__',damage_type).replace('__ASSIGNMENT_TYPES__',original_assignment.replace('STacticalAssignment','STacticalAssignmentOriginal')+'\n'+actual_assignment)
helpers_start=fixture.index('// Candidate helpers preserve one victim identity;')
helpers_end=fixture.index('int checks=0,failures=0;',helpers_start)
fixture=fixture[:helpers_start]+actual_helpers+fixture[helpers_end:]
fixture=fixture.replace('bool diagnostics=false', 'bool diagnostics=false')
fixture=fixture.replace('int staleReads=0,orders=0,processed=0,forecastDamage=100', 'bool diagnostics=false,dieActor=false;int diagnosticRows=0;string diagnosticReason;\nint staleReads=0,orders=0,processed=0,forecastDamage=100')
fixture=fixture.replace('bool EnabledCategory(int,int,const char*){return false;}', 'bool EnabledCategory(int,int,const char*){return diagnostics;}')
fixture=fixture.replace('void RecordStackPlanExecutionFailure(int,const STacticalAssignment&,size_t,const char*,bool,bool,unsigned int,unsigned int,const StackPlanDiagnosticUnitState&){}', 'void RecordStackPlanExecutionFailure(int owner,const STacticalAssignment&a,size_t,const char*reason,bool,bool,unsigned int,unsigned int,const StackPlanDiagnosticUnitState&,PlayerTypes nativeOwner=NO_PLAYER,int nativeID=-1){++diagnosticRows;diagnosticReason=reason;CvUnit*actor=GET_PLAYER(owner).getUnit(a.iUnitID);if(actor&&actor->poison)++staleReads;}')
fixture=fixture.replace('if(deleteActor)retire(this);', 'if(dieActor)hp=0;if(deleteActor)retire(this);')
fixture=fixture.replace('staleReads=orders=processed=0;', 'staleReads=orders=processed=0;diagnostics=dieActor=false;diagnosticRows=0;diagnosticReason.clear();')
fixture+='\nstruct CvTacticalPlot{vector<const CvUnit*>enemies;const vector<const CvUnit*>&getEnemyUnits()const{return enemies;}};\nvoid ClassifyProjectedAttack(bool bCityKill,bool bUnitKill,bool bRanged,const CvUnit*pEnemyUnit,const CvCity*pEnemyCity,const CvPlot*pTestPlot,int iPrevCityHitPoints,const CvTacticalPlot*tactPlot,STacticalAssignment*result){\n'+classification+'\n}\n'
tests=tests.replace('printf("SIZE original=', '''reset();a=prepare(A_RANGEKILL,false,false);deleteActor=true;diagnostics=true;
 check(!execute(a,true)&&staleReads==0&&diagnosticRows==1&&diagnosticReason=="actor_removed","removed actor failure diagnostic uses saved owner/ID safely");
 reset();a=prepare(A_RANGEKILL,false,false);dieActor=true;diagnostics=true;
 check(!execute(a,true)&&staleReads==0&&diagnosticRows==1&&diagnosticReason=="actor_unavailable","HP-dead actor returns safe diagnostic even without delayed death");
 printf("SIZE original=''')
tests=tests.replace('executor explicit-primary prototype:', 'executor '+('prepared-source' if prepared else 'applied-source')+' primary identity:')
actual=actual.replace('ExecuteUnitAssignments(','ExecuteUnitAssignmentsCandidate(',1)
out=root/('work/stack-plan-primary-prepared-regression' if prepared else 'work/stack-plan-primary-applied-regression');out.mkdir(exist_ok=True)
cpp=out/'test.cpp';cpp.write_text(fixture+values+original_equality+actual_equality+control+actual+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=out/'test.exe'
compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
ran=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
print(ran.stdout+ran.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(returncode=ran.returncode,output=ran.stdout+ran.stderr,controlRevision=revision,sourceMode='explicit prepared source copies' if prepared else 'actual production source',sourceDirectory=str(scope),sourceSha256=hashlib.sha256(source.encode()).hexdigest(),headerSha256=hashlib.sha256(header.encode()).hexdigest(),scope='Complete source executor/assignment/damage container/equality plus actual classifier vs pinned54; deterministic mission substitutes. No native timing/equivalence claim.'),indent=2)+'\n')
sys.exit(ran.returncode)
