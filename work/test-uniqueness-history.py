"""Emit a current-production actual-source uniqueness differential fixture.

Default is emit-only: compilation/run requires explicit --compile after the
parent controller says the quiet replay has closed. No production edits.
"""
from pathlib import Path
import ast,hashlib,json,os,re,subprocess,sys

root=Path(__file__).resolve().parents[1];stage=root/'work/uniqueness-history-staged';out=root/'work/uniqueness-history-regression';out.mkdir(exist_ok=True)
control='1715cd68f'
original=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
header=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/CvTacticalAI.h'],cwd=root).decode('utf-8-sig')
unit=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/CvUnit.h'],cwd=root).decode('utf-8-sig')
candidate=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
candidate_header=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.h').read_text(encoding='utf-8-sig')
assert candidate==(stage/'CvTacticalAI.cpp').read_text(encoding='utf-8'),'Current production cpp differs from the reviewed staged proposal'
assert candidate_header==(stage/'CvTacticalAI.h').read_text(encoding='utf-8'),'Current production header differs from the reviewed staged proposal'

def block(text,signature,semicolon=False):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
    if semicolon:assert text[end]==';';end+=1
    return text[start:end]

legacy=block(original,'static bool positionIsEquivalent(')
assert legacy==block(candidate,'static bool positionIsEquivalent(')
default_unique=block(original,'bool CvTacticalPosition::isUnique(')
assert default_unique==block(candidate,'bool CvTacticalPosition::isUnique(')
default_traversal=block(original,'static bool tacticalPositionIsEquivalentToAnyChild(')
assert default_traversal==block(candidate,'static bool tacticalPositionIsEquivalentToAnyChild(')
equal=block(original,'static bool EqualAssignedUnitValues(')+'\n'+block(original,'bool STacticalAssignment::operator==(')
context=block(candidate,'struct TacticalHistoryEquivalenceContext',True)
specialized=block(candidate,'static bool tacticalPositionIsEquivalentWithSharedHistory(')
special_traversal=block(candidate,'static bool tacticalPositionIsEquivalentToAnyChildWithSharedHistory(')
special_unique=block(candidate,'bool CvTacticalPosition::isUniqueWithSharedHistory(')
assert block(candidate,'static bool supportPositionIsEquivalentToAnyChild(')==block(original,'static bool supportPositionIsEquivalentToAnyChild(')
assert block(candidate,'bool CvSupportPosition::isUnique(')==block(original,'bool CvSupportPosition::isUnique(')
reversed_cpp=candidate
added_start=reversed_cpp.index('// Normal tactical expansion preserves the ancestor')
added_end=reversed_cpp.index('static bool tacticalPositionIsEquivalentToAnyChild(',added_start)
reversed_cpp=reversed_cpp[:added_start]+reversed_cpp[added_end:]
assert reversed_cpp.count('\n\n'+special_unique)==1
reversed_cpp=reversed_cpp.replace('\n\n'+special_unique,'',1)
assert reversed_cpp.count('pNewChild->isUniqueWithSharedHistory(TACTSIM_UNIQUENESS_CHECK_GENERATIONS)')==1
reversed_cpp=reversed_cpp.replace('pNewChild->isUniqueWithSharedHistory(TACTSIM_UNIQUENESS_CHECK_GENERATIONS)','pNewChild->isUnique(TACTSIM_UNIQUENESS_CHECK_GENERATIONS)',1)
assert reversed_cpp==original,'Current production cpp delta extends beyond reviewed main-only helper additions and one callsite'
added_header='\t// Only normal append-only tactical expansion may skip its inherited prefix.\n\tbool isUniqueWithSharedHistory(int levelsToCheck) const;\n'
assert candidate_header.count(added_header)==1 and candidate_header.replace(added_header,'',1)==header,'Current production header delta extends beyond the protected opt-in declaration'
values=block(unit,'struct SUnitIDValueContainer',True)
assignments=block(header,'struct STacticalAssignment',True)
enums=header[header.index('enum CLOSED_ENUM eUnitMoveEvalMode'):header.index('struct STacticalAssignment')]
cow='template<typename T>\n'+block(header,'struct SCoWField',True)
prefix=r'''
#define NOMINMAX
#define CLOSED_ENUM
#define VALIDATE_OBJECT() ((void)0)
#define ASSERT(x) ((void)0)
#include <windows.h>
#include <algorithm>
#include <vector>
#include <map>
#include <utility>
#include <cstdio>
#include <cstdlib>
#include <climits>
using namespace std;typedef int PlayerTypes;const PlayerTypes NO_PLAYER=-1;
const short TACTICAL_COMBAT_IMPOSSIBLE_SCORE=-1000;
unsigned long giDifferentPos=0,giEquivalentPos=0;
unsigned __int64 fixtureReads=0,fixtureVisits=0;
'''
harness=r'''
class CvBasePosition{
public:
 SCoWField<vector<STacticalAssignment> >assignedMoves;size_t nFirstInterestingAssignment;
 CvBasePosition():nFirstInterestingAssignment(0){}
 size_t GetNumAssignments()const{return assignedMoves.read().size();}
 const STacticalAssignment&GetAssignment(size_t index)const{++fixtureReads;return assignedMoves.read()[index];}
 size_t getFirstInterestingAssignment()const{return nFirstInterestingAssignment;}
};
class CvTacticalPosition:public CvBasePosition{
public:
 const CvTacticalPosition*parentPosition;vector<CvTacticalPosition*>childPositions;
 CvTacticalPosition():parentPosition(NULL){}
 const vector<CvTacticalPosition*>&getChildren()const{return childPositions;}
 void initFromParent(const CvTacticalPosition&parent){parentPosition=&parent;childPositions.clear();assignedMoves.inheritFrom(parent.assignedMoves.read());nFirstInterestingAssignment=parent.nFirstInterestingAssignment;}
 bool isUnique(int levels)const;bool isUniqueWithSharedHistory(int levels)const;
};
vector<const CvTacticalPosition*>visited,compared;const CvTacticalPosition*firstMatch=NULL;
'''

def measured_traversal(source,special):
    source=source.replace('{\n','{\n ++fixtureVisits;visited.push_back(current);\n',1)
    before='return tacticalPositionIsEquivalentWithSharedHistory(ref, current, context);' if special else 'return positionIsEquivalent(ref, current);'
    after='compared.push_back(current);bool matches='+before[len('return '):-1]+';if(matches)firstMatch=current;return matches;'
    assert source.count(before)==1
    return source.replace(before,after)

tests=r'''
int checks=0,failures=0;void Expect(const char*label,bool result){++checks;if(!result){++failures;if(failures<12)printf("FAIL %s\n",label);}}
struct Tree{vector<CvTacticalPosition*>owned;~Tree(){for(size_t i=0;i<owned.size();++i)delete owned[i];}
 CvTacticalPosition*root(){CvTacticalPosition*node=new CvTacticalPosition();owned.push_back(node);return node;}
 CvTacticalPosition*child(CvTacticalPosition*parent){CvTacticalPosition*node=root();node->initFromParent(*parent);parent->childPositions.push_back(node);return node;}
};
unsigned long randomState=19810429;unsigned long Next(){randomState=randomState*1664525UL+1013904223UL;return randomState;}
STacticalAssignment Assignment(int actor,int score,eUnitAssignmentType type=A_MOVE){STacticalAssignment result(1,2,actor,60,MS_FIRSTLINE,type,0);result.SetScore(score,0,0);result.iPrimaryUnitID=actor^57913;result.ePrimaryUnitOwner=actor&3;result.iSelfDamage=actor&7;result.iCityDamage=actor&5;result.iDamagedCityId=actor&15;result.unitDamage.SetValue(actor,actor&31);result.unitDamage.SetValue(actor^1597,actor&15);result.unitHealing.SetValue(actor^777,actor&7);return result;}
void ResetCounters(){fixtureReads=fixtureVisits=0;giDifferentPos=giEquivalentPos=0;visited.clear();compared.clear();firstMatch=NULL;}
void Compare(CvTacticalPosition*ref,int levels){
 ResetCounters();bool old=ref->isUnique(levels);unsigned long oldDifferent=giDifferentPos,oldEquivalent=giEquivalentPos;unsigned __int64 oldReads=fixtureReads,oldVisits=fixtureVisits;const CvTacticalPosition*oldMatch=firstMatch;vector<const CvTacticalPosition*>oldOrder(visited),oldComparisons(compared);
 ResetCounters();bool result=ref->isUniqueWithSharedHistory(levels);
 Expect("actual unique result unchanged",old==result);Expect("actual counter deltas unchanged",oldDifferent==giDifferentPos&&oldEquivalent==giEquivalentPos);Expect("actual descendant visit cardinality unchanged",oldVisits==fixtureVisits);Expect("actual recursive node-entry order unchanged",oldOrder==visited);Expect("actual comparison postorder first match unchanged",oldComparisons==compared&&oldMatch==firstMatch);Expect("specialized history reads never increase",fixtureReads<=oldReads);
}
void Prefix(CvTacticalPosition*node,int count,int first){for(int i=0;i<count;++i)node->assignedMoves.write().push_back(Assignment(i,(i&1)?-32768:32767,A_INITIAL));node->nFirstInterestingAssignment=first;}
int main(){
 visited.reserve(20000);compared.reserve(20000);
 {Tree tree;CvTacticalPosition*root=tree.root();Prefix(root,80,7);Compare(root,0);CvTacticalPosition*ref=tree.child(root);ref->assignedMoves.write().push_back(Assignment(100,321));Compare(ref,3);ResetCounters();TacticalHistoryEquivalenceContext context(ref,root->GetNumAssignments());Expect("self guard before lazy sum",!tacticalPositionIsEquivalentWithSharedHistory(ref,ref,context)&&!context.referenceScoreReady&&fixtureReads==0);Expect("length guard before lazy sum",!tacticalPositionIsEquivalentWithSharedHistory(ref,root,context)&&!context.referenceScoreReady&&fixtureReads==0);}
 for(int cycle=2;cycle<=4;++cycle)for(int offset=0;offset<cycle;++offset){Tree tree;CvTacticalPosition*root=tree.root();Prefix(root,89,9);CvTacticalPosition*other=tree.child(root);CvTacticalPosition*ref=tree.child(root);for(int i=0;i<cycle;++i){other->assignedMoves.write().push_back(Assignment(300+i,57-i));ref->assignedMoves.write().push_back(Assignment(300+(i+offset)%cycle,57-(i+offset)%cycle));}other->assignedMoves.write().push_back(Assignment(999,32767,A_FINISH));Compare(ref,3);for(int levels=0;levels<=4;++levels)Compare(ref,levels);}
 for(int first=0;first<=20;++first){Tree tree;CvTacticalPosition*root=tree.root();Prefix(root,20,first);CvTacticalPosition*other=tree.child(root);CvTacticalPosition*ref=tree.child(root);other->assignedMoves.write().push_back(Assignment(500,0));ref->assignedMoves.write().push_back(Assignment(501,0));Compare(ref,3);}
 for(int iteration=0;iteration<500;++iteration){Tree tree;CvTacticalPosition*root=tree.root();int prefixCount=40+(int)(Next()%61);Prefix(root,prefixCount,(int)(Next()%(prefixCount+1)));vector<CvTacticalPosition*>nodes;nodes.push_back(root);
  for(int n=0;n<35;++n){CvTacticalPosition*parent=nodes[Next()%nodes.size()];CvTacticalPosition*child=tree.child(parent);int additions=1+(int)(Next()%3);for(int j=0;j<additions;++j){int actor=(int)(Next()%11);int score=(int)(Next()%65536)-32768;child->assignedMoves.write().push_back(Assignment(actor,score,(Next()&7)==0?A_RESTART:A_MOVE));}nodes.push_back(child);Compare(child,(int)(Next()%6));}
  CvTacticalPosition*parent=nodes[Next()%nodes.size()];CvTacticalPosition*existing=tree.child(parent);existing->assignedMoves.write().push_back(Assignment(70,0));CvTacticalPosition*reused=tree.child(parent);reused->assignedMoves.write().push_back(Assignment(70,0));Compare(reused,3);parent->childPositions.pop_back();reused->initFromParent(*parent);parent->childPositions.push_back(reused);reused->assignedMoves.write().push_back(Assignment(71,0));Compare(reused,3);
 }
 {Tree tree;CvTacticalPosition*root=tree.root();Prefix(root,1500,0);CvTacticalPosition*other=tree.child(root);CvTacticalPosition*ref=tree.child(root);other->assignedMoves.write().push_back(Assignment(INT_MIN,32767));other->assignedMoves.write().push_back(Assignment(INT_MAX,-32768));ref->assignedMoves.write().push_back(Assignment(INT_MAX,-32768));ref->assignedMoves.write().push_back(Assignment(INT_MIN,32767));Compare(ref,99);}
 // Deliberately inconsistent manual prefixes use only the unchanged public path.
 {Tree tree;CvTacticalPosition*root=tree.root();Prefix(root,3,0);CvTacticalPosition*other=tree.child(root);CvTacticalPosition*ref=tree.child(root);other->assignedMoves.write().push_back(Assignment(88,0));ref->assignedMoves.write().push_back(Assignment(88,0));ref->assignedMoves.write()[0]=Assignment(99999,32767);ResetCounters();bool result=ref->isUnique(3);Expect("public default still distinguishes different manual prefix",result);Expect("public default inspected prefix",fixtureReads>2&&giDifferentPos>0);}
 printf("actual tactical shared-history: %d checks, %d failures; default/support source unchanged; native speed unmeasured\n",checks,failures);return failures?1:0;
}
'''
fixture=prefix+values+'\n'+enums+assignments+'\n'+equal+'\n'+cow+'\n'+harness+'\n'+legacy+'\n'+context+'\n'+specialized+'\n'+measured_traversal(default_traversal,False)+'\n'+measured_traversal(special_traversal,True)+'\n'+default_unique+'\n'+special_unique+'\n'+tests
(out/'test.cpp').write_text(fixture,encoding='utf-8')
manifest=dict(control=control,production_applied=True,compiled=False,fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),
    production_cpp_sha256=hashlib.sha256(candidate.encode()).hexdigest(),production_header_sha256=hashlib.sha256(candidate_header.encode()).hexdigest(),
    current_source_identical_to_reviewed_staging=True,whole_source_main_only_delta_verified=True,default_and_support_methods_byte_identical=True,
    scope='Actual production legacy/specialized comparator and recursive unique methods; actual assignment/value/COW definitions. Strict full-source equality to reviewed staging and reversed main-only delta to DLL65. Fixture-only tree wiring/GetAssignment read counters and deterministic inherited histories. Defaults to emit-only while game is active.')
(out/'fixture-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
if '--compile' not in sys.argv:
    print(json.dumps(dict(emitted=str(out/'test.cpp'),compiled=False,production_applied=True)));raise SystemExit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe'
compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);raise SystemExit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=60);print(run.stdout+run.stderr,end='')
manifest.update(compiled=True,returncode=run.returncode,output=run.stdout+run.stderr)
(out/'result.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
raise SystemExit(run.returncode)
