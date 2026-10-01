"""Stage one full-movement healing gate change, never apply it."""
from pathlib import Path
import difflib,hashlib,json,subprocess
root=Path(__file__).resolve().parents[1];out=root/'work/healing-resource-gate-staged';out.mkdir(exist_ok=True)
control='9c4b9915e'
path='CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
original=subprocess.check_output(['git','show',control+':'+path],cwd=root).decode('utf-8-sig')
start=original.index('static STacticalAssignment* ScorePlotForCombatUnitMove(')
end=original.index('//stacking with combat units is allowed here!',start)
body=original[start:end]
gate='pUnit->getDamage() + unit.iSelfDamage > 0 && !pUnit->IsCannotHeal(/*bConsiderResourceShortage*/ true) && !pUnit->isEmbarked()'
assert body.count(gate)==2
new_body=body.replace(gate,gate.replace(' true)',' false)'),1)
assert new_body.count(gate)==1
partial=body[body.index('\t\telse\n',body.index('if (unit.iMovesLeft == unit.iMaxMoves)')):]
assert new_body.endswith(partial),'Partial movement and all subsequent scorer statements must remain identical'
candidate=original[:start]+new_body+original[end:]
patch=''.join(difflib.unified_diff(original.splitlines(keepends=True),candidate.splitlines(keepends=True),fromfile='a/'+path,tofile='b/'+path))
(out/'resource-gate.patch').write_text(patch,encoding='utf-8',newline='\n')
(out/'CvTacticalAI.cpp').write_text(candidate,encoding='utf-8',newline='\n')
proof=dict(control=control,production_applied=False,original_sha256=hashlib.sha256(original.encode()).hexdigest(),candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
    changed_predicates=1,partial_and_subsequent_scorer_bytes_identical=True,no_cache_or_api_change=True,
    reasoning='Full-movement path delegates resource eligibility to existing ActualHealRate/canHeal check; partial flat-heal gate still considers resources.')
(out/'staging-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(staged=str(out),production_applied=False)))
