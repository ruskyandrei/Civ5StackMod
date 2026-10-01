"""Stage a main-only shared-ancestor history comparison; never apply it."""
from pathlib import Path
import difflib,hashlib,json,subprocess

root=Path(__file__).resolve().parents[1];out=root/'work/uniqueness-history-staged';out.mkdir(exist_ok=True)
control='1715cd68f'
files=['CvTacticalAI.cpp','CvTacticalAI.h']
original={name:subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/'+name],cwd=root).decode('utf-8-sig') for name in files}

def function(text,signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

cpp=original[files[0]];header=original[files[1]]
legacy=function(cpp,'static bool positionIsEquivalent(')
old_traversal=function(cpp,'static bool tacticalPositionIsEquivalentToAnyChild(')
old_unique=function(cpp,'bool CvTacticalPosition::isUnique(')
context='''// Normal tactical expansion preserves the ancestor's assigned-history prefix.
// Keep this context local to one check: no persistent cache or mutable-history API.
struct TacticalHistoryEquivalenceContext
{
    size_t first;
    int referenceScore;
    bool referenceScoreReady;
    TacticalHistoryEquivalenceContext(const CvBasePosition* reference, size_t sharedPrefix)
        : first(std::max(reference->getFirstInterestingAssignment(), sharedPrefix)),
          referenceScore(0), referenceScoreReady(false) {}
};

'''
specialized=legacy.replace('static bool positionIsEquivalent(const CvBasePosition* ref, const CvBasePosition* other)',
    'static bool tacticalPositionIsEquivalentWithSharedHistory(const CvBasePosition* ref, const CvBasePosition* other, TacticalHistoryEquivalenceContext& context)',1)
before='''	int iRefScore = 0;
	int iOtherScore = 0;
	for (size_t i = ref->getFirstInterestingAssignment(); i < ref->GetNumAssignments(); i++)
	{
		iRefScore += ref->GetAssignment(i).Score();
		iOtherScore += other->GetAssignment(i).Score();
	}'''
after='''	// The identical shared prefix cancels in the score comparison. Initialize
	// only after the original self/length guards; many pairs need no history work.
	if (!context.referenceScoreReady)
	{
		for (size_t i = context.first; i < ref->GetNumAssignments(); ++i)
			context.referenceScore += ref->GetAssignment(i).Score();
		context.referenceScoreReady = true;
	}
	const int iRefScore = context.referenceScore;
	int iOtherScore = 0;
	for (size_t i = context.first; i < ref->GetNumAssignments(); ++i)
		iOtherScore += other->GetAssignment(i).Score();'''
assert specialized.count(before)==1
specialized=specialized.replace(before,after,1)
specialized=specialized.replace('cursor > ref->getFirstInterestingAssignment()','cursor > context.first',1)
new_traversal=old_traversal.replace('tacticalPositionIsEquivalentToAnyChild','tacticalPositionIsEquivalentToAnyChildWithSharedHistory')
new_traversal=new_traversal.replace('const CvTacticalPosition* current)','const CvTacticalPosition* current, TacticalHistoryEquivalenceContext& context)',1)
new_traversal=new_traversal.replace('(ref, children[i])','(ref, children[i], context)',1)
new_traversal=new_traversal.replace('return positionIsEquivalent(ref, current);','return tacticalPositionIsEquivalentWithSharedHistory(ref, current, context);',1)
new_unique=old_unique.replace('CvTacticalPosition::isUnique(','CvTacticalPosition::isUniqueWithSharedHistory(',1)
new_unique=new_unique.replace('return !tacticalPositionIsEquivalentToAnyChild(this, start);',
    'TacticalHistoryEquivalenceContext context(this, start->GetNumAssignments());\n\treturn !tacticalPositionIsEquivalentToAnyChildWithSharedHistory(this, start, context);',1)
cpp=cpp.replace(old_traversal,context+specialized+'\n\n'+new_traversal+'\n\n'+old_traversal,1)
cpp=cpp.replace(old_unique,old_unique+'\n\n'+new_unique,1)
call='pNewChild->isUnique(TACTSIM_UNIQUENESS_CHECK_GENERATIONS)'
assert cpp.count(call)==2
cpp=cpp.replace(call,'pNewChild->isUniqueWithSharedHistory(TACTSIM_UNIQUENESS_CHECK_GENERATIONS)',1)
declaration='\tconst vector<int>& getRangeAttackPlotsForUnit(const SUnitStats& unit) const;'
assert header.count(declaration)==1
header=header.replace(declaration,'\t// Only normal append-only tactical expansion may skip its inherited prefix.\n\tbool isUniqueWithSharedHistory(int levelsToCheck) const;\n'+declaration,1)
staged=dict(zip(files,(cpp,header)))
assert function(cpp,'static bool positionIsEquivalent(')==legacy
assert function(cpp,'static bool tacticalPositionIsEquivalentToAnyChild(')==old_traversal
assert function(cpp,'bool CvTacticalPosition::isUnique(')==old_unique
assert function(cpp,'static bool supportPositionIsEquivalentToAnyChild(')==function(original[files[0]],'static bool supportPositionIsEquivalentToAnyChild(')
assert function(cpp,'bool CvSupportPosition::isUnique(')==function(original[files[0]],'bool CvSupportPosition::isUnique(')
for name,text in staged.items():(out/name).write_text(text,encoding='utf-8',newline='\n')
patch=''.join(''.join(difflib.unified_diff(original[name].splitlines(keepends=True),staged[name].splitlines(keepends=True),fromfile='a/CvGameCoreDLL_Expansion2/'+name,tofile='b/CvGameCoreDLL_Expansion2/'+name)) for name in files)
(out/'history.patch').write_text(patch,encoding='utf-8',newline='\n')
proof=dict(control=control,production_applied=False,default_comparator_identical=True,default_tactical_traversal_identical=True,
    default_public_tactical_isUnique_identical=True,support_traversal_and_isUnique_identical=True,main_callsite_changes=1,no_persistent_cache=True,
    begin='max(reference.firstInteresting, chosenAncestor.GetNumAssignments())',same_reference_length_end=True,lazy_reference_sum_after_existing_guards=True,
    files={name:dict(original_sha256=hashlib.sha256(original[name].encode()).hexdigest(),staged_sha256=hashlib.sha256(staged[name].encode()).hexdigest()) for name in files})
(out/'staging-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(staged=str(out),production_applied=False)))
