"""WORK-ONLY immediate key-loan validation reuse, pinned to callback-safe DLL85."""
from pathlib import Path
import difflib,hashlib,json,subprocess
root=Path(__file__).resolve().parents[1];out=root/'work/immediate-forecast-borrow-stage';out.mkdir(exist_ok=True)
control='c92e941cfaf5db4577ac555262a938e52bc3f877';path='CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
old=subprocess.check_output(['git','show',control+':'+path],cwd=root).decode('utf-8-sig').replace('\r\n','\n')
def function(s,name,start=0):
 a=s.index(name,start);b=s.index('{',a)+1;depth=1
 while depth:depth+=(s[b]=='{')-(s[b]=='}');b+=1
 return s[a:b]
new=old;signatures=['static int GetCachedStackDanger(','static const CvUnit* SelectCachedStackDefender(']
for signature in signatures:
 start=old.index('static int GetCachedStackDanger(') if 'SelectCached' in signature else 0
 body=function(old,signature,start);before='bool cacheable = StackForecastContext();';after='bool cacheable = query.scratch != NULL || StackForecastContext();'
 assert body.count(before)==1;changed=body.replace(before,after,1);assert new.count(body)==1;new=new.replace(body,changed,1)
restored=new
for signature in signatures:
 start=restored.index('static int GetCachedStackDanger(') if 'SelectCached' in signature else 0
 body=function(restored,signature,start);restored=restored.replace(body,body.replace('bool cacheable = query.scratch != NULL || StackForecastContext();','bool cacheable = StackForecastContext();',1),1)
assert restored==old,'Whole-file delta extends beyond exactly two cacheable bools'
for signature in ('struct StackForecastQuery\n','struct StackForecastPairQuery\n','static bool StackForecastContext('):assert function(old,signature)==function(new,signature)
bound_names=('CvTacticalAI.cpp','CvUnit.cpp','CvDangerPlots.cpp','CvStackingStrengthCache.h','CvStackingStrengthCache.cpp','CvDangerPlots.h','CvUnit.h','CvUnitCombat.cpp','CvPlot.cpp','CvStackingRules.h','CvStackingRules.cpp')
original={n:subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/'+n],cwd=root).decode('utf-8-sig').replace('\r\n','\n') for n in bound_names}
for n,s in original.items():
 assert (root/'CvGameCoreDLL_Expansion2'/n).read_text(encoding='utf-8-sig')==s,'Stage requires pinned85 baseline: '+n
 (out/('control-'+n)).write_text(s,encoding='utf-8')
(out/'control.cpp').write_text(old,encoding='utf-8');(out/'CvTacticalAI.cpp').write_text(new,encoding='utf-8')
(out/'borrow.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+path,tofile='b/'+path)),encoding='utf-8')
(out/'manifest.json').write_text(json.dumps(dict(control=control,production_untouched=True,
 source_sha256=hashlib.sha256(old.encode()).hexdigest(),candidate_sha256=hashlib.sha256(new.encode()).hexdigest(),
 original_whole_files_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in original.items()},
 candidate_whole_files_sha256={n:hashlib.sha256((new if n=='CvTacticalAI.cpp' else s).encode()).hexdigest() for n,s in original.items()},
 reverse_whole_file_exact=True,constructors_context_final_checks_unchanged=True,
 scope='Only two immediate cacheable bool assignments differ. Shared loan already validated; all private paths keep original second check. Final postkey Context remains mandatory. No native ROI.'),indent=2))
print('Two-line immediate borrow variant staged; production untouched')
