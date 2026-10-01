"""Source-bound production policy acceptance for a composed AI candidate.

Compiles actual composed production helpers/claims and native production sanity
boundaries. Player/city/type/route/Matches services are explicit deterministic
substitutes. Unexecuted sanity code is protected by exact reviewed reversal.
This is not a whole-DLL/native performance test.
"""
from pathlib import Path
import argparse, ast, hashlib, importlib.util, json, os, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-dir',type=Path,required=True)
parser.add_argument('--emit-only',action='store_true')
parser.add_argument('--out-dir',type=Path,default=ROOT/'work/integration-production-regression')
args=parser.parse_args(); source_dir=args.source_dir.resolve(); out=args.out_dir.resolve()
spec=importlib.util.spec_from_file_location('production_stage',ROOT/'work/stage-ai-production-policy.py')
stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage);fn=stage.function

fixture_path=ROOT/'work/test-ai-production-policy.py'
fixture_text=fixture_path.read_text(encoding='utf-8-sig');tree=ast.parse(fixture_text)
def literal(name):
    node=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
    while isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):node=node.func.value
    return ast.literal_eval(node)

finished_path=source_dir/'finished-proof.json'
finished=json.loads(finished_path.read_text(encoding='utf-8-sig'))
sources={name:(source_dir/name).read_text(encoding='utf-8-sig').replace('\r\n','\n') for name in finished['candidate_hashes']}
source_hashes={name:hashlib.sha256(text.encode()).hexdigest() for name,text in sources.items()}
assert source_hashes==finished['candidate_hashes'],'composed source differs from finished-proof.json'
assert all(not any(marker in text for marker in ('<<<<<<<','>>>>>>>','|||||||')) for text in sources.values()),'unresolved source conflicts'
source=sources['CvStackingOffensiveAI.cpp'];header=sources['CvStackingOffensiveAI.h'];unit=sources['CvUnitProductionAI.cpp']

# Only the reviewed recommendation gate/bonus seam may change this entire
# native sanity body. Other composed files may differ; no standalone file SHA
# is required for the candidate.
old,reviewed,unused=stage.generate()
sanity=fn(unit,'int CvUnitProductionAI::CheckUnitBuildSanity(')
expected=fn(reviewed['CvUnitProductionAI.cpp'],'int CvUnitProductionAI::CheckUnitBuildSanity(')
assert sanity==expected,'unreviewed native sanity-body change'
control_sanity=fn(old['CvUnitProductionAI.cpp'],'int CvUnitProductionAI::CheckUnitBuildSanity(')
for name in ('EntryRanged','EntrySiege','EntryCapture'):
    assert fn(source,'    bool '+name+'(')==fn(old['CvStackingOffensiveAI.cpp'],'    bool '+name+'('),'unexpected entry-role change'
assert fn(source,'    void ResetProductionPolicy(')==fn(reviewed['CvStackingOffensiveAI.cpp'],'    void ResetProductionPolicy('),'cleanup proof drift'

api=header[header.index('    enum ProductionRole '):header.index('    int ProductionBonus(')]
models=literal('models').replace(' API ',api)
models=models.replace('#include <cstdio>','#include <cstdio>\n#include <string>\n#include <cstdlib>\n#include <cstring>')
# Execute the native Refresh claim loop with the same modeled registry fields.
models=models.replace('lastUsefulTurn,productionTurn','lastUsefulTurn,refreshed,productionTurn')
models=models.replace('lastUsefulTurn(-1),productionTurn','lastUsefulTurn(-1),refreshed(-1),productionTurn')
commitment_struct=fn(source,'    struct Commitment')+';'
models=models.replace('static int currentTurn=12;',commitment_struct+'\nmap<Key,Commitment>commitments;\nstatic int currentTurn=12;')
stalled_struct=fn(source,'    struct StalledProductionQueue')+';'
models=models.replace('static bool ProductionQueueStalled(const CvCity*,const Key&){return false;}',stalled_struct+'\nmap<Key,StalledProductionQueue>stalledProduction;\nstatic bool ProductionQueueStalled(const CvCity*,const Key&);')

roles='\n'.join(fn(source,'    bool '+name+'(') for name in ('EntryRanged','EntrySiege','EntryCapture'))
budget=source[source.index('    struct ProductionQueueState'):source.index('    bool ProductionQueueCredits(')]
choice=fn(source,'    bool ProductionQueueCredits(')+'\n'+fn(source,'    int ProductionChoice(')
public_names=('ResetProductionPolicy','ProductionCitiesChanged','InvalidateProductionStaff','InvalidateProductionOwner','ProductionEconomyChanged','ProductionQueueChanged','GetProductionBudget','GetProductionIntent','RecordProductionRejection','ProductionBonus')
public='\n'.join(fn(source,'    '+('bool ' if n in ('GetProductionBudget','GetProductionIntent') else 'int ' if n=='ProductionBonus' else 'void ')+n+'(') for n in public_names)
lifecycle='\n'.join(fn(source,'    void '+n+'(') for n in ('RecordProduction','UnitProduced'))
stalled=fn(source,'    bool ProductionQueueStalled(').replace('    bool ','    static bool ',1)
refresh=fn(source,'    void Refresh()')
a=refresh.index('        for(std::map<Key,ProductionClaim>::iterator i=production.begin();')
b=refresh.index('        for(std::map<ObjectiveKey,Objective>::iterator i=objectives.begin();',a)
claim_refresh='static void RefreshProductionClaimsOnly(){const int turn=GC.getGame().getGameTurn();\n'+refresh[a:b]+'\n}'
assert 'AdvanceProductionGeneration((PlayerTypes)i->first.first);\n                production.erase(i++);' in claim_refresh,'Refresh omitted claim-generation invalidation'
assert 'ResetProductionPolicy();' in fn(source,'    void Reset()')
assert 'InvalidateProductionStaff(unit->getOwner(),target,unit->getDomainType());' in fn(source,'    void RecordTransfer(')
transfer=fn(source,'    void RecordTransfer(')
old_goal='InvalidateProductionStaff((PlayerTypes)c.goal.owner,c.goal.target,(DomainTypes)c.goal.domain);'
assert old_goal in transfer and transfer.index(old_goal)<transfer.index('c.goal=ObjectiveKey(unit->getOwner(),target,unit->getDomainType());'),'retarget must invalidate old goal before overwrite'
erase_commitment=fn(source,'    bool EraseCommitment(std::map<Key,Commitment>::iterator')+'\n'+fn(source,'    bool EraseCommitment(const Key&')
assert 'InvalidateProductionStaff((PlayerTypes)goal.owner,goal.target,(DomainTypes)goal.domain);' in erase_commitment,'cancellation must invalidate old staffing'
assert 'InvalidateProductionOwner(op->GetOwner());' in fn(source,'    void Handoff(')
assert 'InvalidateProductionStaff(owner,target,domain);' in fn(source,'    void RecordCombatContribution(')
assert sources['CvPlayer.cpp'].count('CvStackingOffensiveAI::InvalidateProductionOwner(GetID());')>=4,'native birth/loss hooks absent'
assert sources['CvPlayer.cpp'].count('CvStackingOffensiveAI::ProductionCitiesChanged(')>=5,'city ownership/topology hooks absent'
assert 'if(changed && m_eOwner != NO_PLAYER) CvStackingOffensiveAI::InvalidateProductionOwner(m_eOwner);' in sources['CvUnit.cpp'],'army membership hook absent'

a=sanity.index('\tif (!bDesperate && !bFree)');b=sanity.index('\n\t//don\'t build land/sea',a);maintenance=sanity[a:b]
a=sanity.index('\tCvStackingOffensiveAI::ProductionIntent stackingIntent;');b=sanity.index('\n\t//only war with majors count',a);quota=sanity[a:b]
a=sanity.index('\t\t//Check for special unlimited');b=sanity.index('\n\t\t///////////////\n\t\t//UNIT TYPE CHECKS',a);resources=sanity[a:b]
shell=literal('shell').replace('MAINTENANCE',maintenance).replace('QUOTA',quota).replace('RESOURCE',resources)
tests=literal('tests')
tests=tests.replace('settings.clear();objectives.clear();production.clear();','settings.clear();objectives.clear();production.clear();commitments.clear();',1)
extra=r'''
 Setup(0);factory.unit=0;CvStackingOffensiveAI::GetProductionBudget(0,budget);CvStackingOffensiveAI::RecordProduction(&factory,0);
 CvStackingOffensiveAI::GetProductionIntent(&second,0,intent);Check("integrated queued capture credited before cancellation",intent.missingCapture==1);
 const unsigned long claimGeneration=productionPolicy[0].generation;factory.unit=NO_UNIT;
 RefreshProductionClaimsOnly();Check("actual Refresh erases claim and advances queue generation",production.empty()&&productionPolicy[0].generation>claimGeneration);
 CvStackingOffensiveAI::ProductionQueueChanged(&factory);CvStackingOffensiveAI::GetProductionIntent(&second,0,intent);
 Check("integrated canceled queue no longer promises capturer",intent.missingCapture==2);
 Setup(0);factory.unit=0;CvStackingOffensiveAI::GetProductionBudget(0,budget);CvStackingOffensiveAI::RecordProduction(&factory,0);
 turn+=7;currentTurn=turn;RefreshProductionClaimsOnly();Check("actual stalled-claim invalidation retained",production.empty()&&!stalledProduction.empty());
 Check("actual stale queue is not immediately reclaimed",ProductionQueueStalled(&factory,Key(0,factory.id)));
 factory.turns-=1;Check("actual queue progress releases stalled exclusion",!ProductionQueueStalled(&factory,Key(0,factory.id)));
 CvStackingOffensiveAI::RecordProduction(&factory,0);Check("integrated progressing queue may reacquire one claim",production.size()==1);
 Setup(2);CvStackingOffensiveAI::GetProductionIntent(&factory,1,intent);const ObjectiveKey oldGoal(0,20,DOMAIN_LAND);
 Check("old objective has cached two-capturer staff before cancel",objectives[oldGoal].staffTurn==turn&&objectives[oldGoal].productionTurn==turn&&objectives[oldGoal].staffCapture==2);
 Commitment canceled;canceled.goal=oldGoal;commitments[Key(0,troops[0].id)]=canceled;troops[0].goal=-1;
 Check("actual commitment cancellation invalidates old cached staffing",EraseCommitment(Key(0,troops[0].id))&&objectives[oldGoal].staffTurn==-1&&objectives[oldGoal].productionTurn==-1);
 CvStackingOffensiveAI::GetProductionIntent(&factory,1,intent);Check("canceled staff is not retained as capturer credit",intent.target==20&&intent.missingCapture==1&&objectives[oldGoal].staffCapture==1);
 Check("missing commitment cancellation is idempotent",!EraseCommitment(Key(0,troops[0].id))&&objectives[oldGoal].staffTurn==turn);
'''
tests=tests.replace(' printf("ACTUAL PRODUCTION POLICY:',extra+'\n printf("INTEGRATED PRODUCTION POLICY:',1)
cpp=models+roles+'\n'+budget+'\n'+choice+'\n'+stalled+'\n'+erase_commitment+'\nnamespace CvStackingOffensiveAI{\n'+public+'\n'+lifecycle+'\n}\n'+claim_refresh+'\n'+shell+'\n'+tests
out.mkdir(parents=True,exist_ok=True);(out/'test.cpp').write_text(cpp,encoding='utf-8')
report=dict(control=stage.BASE,source_dir=str(source_dir),source_sha256=source_hashes,
            source_finished_proof_sha256=hashlib.sha256(finished_path.read_bytes()).hexdigest(),fixture_prerequisite_sha256=hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
            fixture_sha256=hashlib.sha256(cpp.encode()).hexdigest(),native_sanity_reviewed_reverse_exact=True,
            original_sanity_sha256=hashlib.sha256(control_sanity.encode()).hexdigest(),actual_sanity_sha256=hashlib.sha256(sanity.encode()).hexdigest(),
            tested_scope='Actual composed production API, complete budget/roles/choice/public/claims, actual Refresh claim loop, stalled queue logic and commitment cancellation helper; actual native maintenance/resources/recommendation boundary. Explicit deterministic player/city/type/Matches/route/Sync substitutions. Full unexecuted native sanity body exactly matches reviewed changes. Retarget pre-overwrite invalidation and other native lifecycle hooks source-bound, not whole-engine executed. No native performance claim.',game_calls=0)
(out/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
if args.emit_only:print(json.dumps(dict(emitted=True,fixture_sha256=report['fixture_sha256'],source_sha256=source_hashes)));sys.exit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
built=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/GS','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fo'+str(out/'test.obj'),'/Fe'+str(out/'test.exe')],cwd=out,env=env,capture_output=True,text=True,timeout=45)
(out/'compile.log').write_text(built.stdout+built.stderr)
if built.returncode:print(built.stdout+built.stderr);sys.exit(built.returncode)
run=subprocess.run([str(out/'test.exe')],cwd=out,capture_output=True,text=True,timeout=20)
assert source_hashes=={name:hashlib.sha256((source_dir/name).read_text(encoding='utf-8-sig').replace('\r\n','\n').encode()).hexdigest() for name in sources},'source changed during fixture'
report.update(compile_returncode=built.returncode,test_returncode=run.returncode,output=run.stdout+run.stderr)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(run.stdout+run.stderr,end='');sys.exit(run.returncode)
