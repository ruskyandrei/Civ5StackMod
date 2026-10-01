"""Emit only an ignored parent preparation prototype, pinned to DLL91."""
from pathlib import Path
import subprocess,hashlib,json,difflib
ROOT=Path(__file__).resolve().parents[1]
BASE='e8b5bd3e6f4177c98a6d63ded0a6fb6f79b0a89e'
OUT=ROOT/'work/parent-stack-preparation-staged'
def original(path):
    return subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
def once(text,a,b):
    assert text.count(a)==1,(a,text.count(a))
    return text.replace(a,b)
def stage():
    cpppath='CvGameCoreDLL_Expansion2/CvTacticalAI.cpp';hpppath='CvGameCoreDLL_Expansion2/CvTacticalAI.h'
    oldcpp=original(cpppath);oldhpp=original(hpppath);cpp=oldcpp;hpp=oldhpp
    template=(ROOT/'work/parent-stack-preparation-template/ParentEvaluation.cpp').read_text().replace('\r\n','\n')
    cpp=once(cpp,'static VirtualFriendlyStackBuffer gStackVirtualScratch;','static void ReleaseParentStackPreparationStorage();\nstatic VirtualFriendlyStackBuffer gStackVirtualScratch;')
    cpp=once(cpp,'   gStackVirtualScratch.release();','   ReleaseParentStackPreparationStorage();\n   gStackVirtualScratch.release();')
    cpp=once(cpp,'// This is the exact size produced by GetVirtualFriendlyStack, including fixed',template+'\n// This is the exact size produced by GetVirtualFriendlyStack, including fixed')
    cpp=once(cpp,'  GetVirtualFriendlyStack(position, plot, unit, selfDamage, buffer->candidates, buffer->damage);','  GetPreparedVirtualFriendlyStack(position, plot, unit, selfDamage, buffer->candidates, buffer->damage, borrowed && context);')
    cpp=once(cpp,'    GetVirtualFriendlyStack(assumedPosition, pPlot, pUnit, iSelfDamage, stack.candidates, stack.damage);','    GetPreparedVirtualFriendlyStack(assumedPosition, pPlot, pUnit, iSelfDamage, stack.candidates, stack.damage, stack.borrowed);')
    cpp=once(cpp,'\t\tnewPosition.ChangeCityDamage(assignment->iDamagedCityId, assignment->iCityDamage);\n}', '\t\tnewPosition.ChangeCityDamage(assignment->iDamagedCityId, assignment->iCityDamage);\n MarkParentStackPreparationChild(previousPosition,newPosition);\n}')
    loop='\tfor (size_t i=0; i< availableUnits_r.size(); i++)\n\t{\n\t\tgetPreferredAssignmentsForUnit(availableUnits_r[i], iMaxChoicesPerUnit);\n\t\tgOverAllChoices.insert( gOverAllChoices.end(), gPossibleMoves.begin(), gPossibleMoves.end() );\n\t}'
    cpp=once(cpp,loop,'\t{\n\t ParentStackPreparationView preparation(*this);\n'+loop+'\n\t}')
    method='\t// Only the const preferred-unit batch and its explicit EFD-only previews use this identity.\n\tbool SharesVirtualStackInputs(const CvTacticalPosition& other) const\n\t{\n\t return ePlayer == other.ePlayer && &tactPlotLookup.read() == &other.tactPlotLookup.read() &&\n\t  &tactPlots.read() == &other.tactPlots.read() && &availableUnits.read() == &other.availableUnits.read() &&\n\t  &notQuiteFinishedUnits.read() == &other.notQuiteFinishedUnits.read() && &finishedUnits.read() == &other.finishedUnits.read();\n\t}\n\n'
    hpp=once(hpp,'\tconst CvTacticalPlot* getTactPlot(int plotindex) const;',method+'\tconst CvTacticalPlot* getTactPlot(int plotindex) const;')
    restored=once(cpp,template+'\n','')
    restored=once(restored,'static void ReleaseParentStackPreparationStorage();\n','')
    restored=once(restored,'   ReleaseParentStackPreparationStorage();\n','')
    restored=once(restored,'  GetPreparedVirtualFriendlyStack(position, plot, unit, selfDamage, buffer->candidates, buffer->damage, borrowed && context);','  GetVirtualFriendlyStack(position, plot, unit, selfDamage, buffer->candidates, buffer->damage);')
    restored=once(restored,'    GetPreparedVirtualFriendlyStack(assumedPosition, pPlot, pUnit, iSelfDamage, stack.candidates, stack.damage, stack.borrowed);','    GetVirtualFriendlyStack(assumedPosition, pPlot, pUnit, iSelfDamage, stack.candidates, stack.damage);')
    restored=once(restored,' MarkParentStackPreparationChild(previousPosition,newPosition);\n','')
    restored=once(restored,'\t{\n\t ParentStackPreparationView preparation(*this);\n'+loop+'\n\t}',loop)
    assert restored==oldcpp,'Reverse whole cpp proof failed'
    assert once(hpp,method,'')==oldhpp,'Reverse whole header proof failed'
    OUT.mkdir(exist_ok=True)
    patch=''
    for path,old,new in [(cpppath,oldcpp,cpp),(hpppath,oldhpp,hpp)]:
        (OUT/Path(path).name).write_text(new,encoding='utf-8',newline='\n')
        patch+=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
    (OUT/'parent-preparation.patch').write_text(patch,encoding='utf-8',newline='\n')
    proof={'baseline':BASE,'reverse_whole_files_exact':True,'files':{p:{'baseline_sha256':hashlib.sha256(o.encode()).hexdigest(),'candidate_sha256':hashlib.sha256(n.encode()).hexdigest()} for p,o,n in [(cpppath,oldcpp,cpp),(hpppath,oldhpp,hpp)]},'scope':'roster/first-match wounds preparation only; full key, kernel, cache admission and outputs unchanged'}
    (OUT/'stage-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return oldcpp,oldhpp,cpp,hpp
if __name__=='__main__':
    stage();print(OUT/'parent-preparation.patch')
