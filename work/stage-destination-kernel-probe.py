"""Stage an observational destination-kernel prototype against a pinned source.

No production edit/build/game call. The marker-stripped entire candidate must
equal the selected control; original arithmetic, policy, enumeration and forecast calls remain.
Defaults reproduce the original frozen86 stage; use separate --output-directory
for later controls so the earlier reviewed experiment stays intact.
"""
from pathlib import Path
import argparse,difflib,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--control',default='ef274591d')
parser.add_argument('--diagnostics-control',default='2bdba7c0584fab417e929ce0735dc4371a59313d')
parser.add_argument('--output-directory',type=Path,default=Path('work/destination-kernel-probe-staged'))
parser.add_argument('--bind-current',action='store_true',help='Require whole current control source before emitting a parallel stage')
args=parser.parse_args()
OUT=args.output_directory if args.output_directory.is_absolute() else ROOT/args.output_directory
OUT.mkdir(exist_ok=True)
BASE=args.control;PATH='CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
DIAGNOSTICS_BASE=args.diagnostics_control
old=subprocess.check_output(['git','show',BASE+':'+PATH],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
fragment=(ROOT/'work/destination-kernel-probe-fragment.cpp').read_text(encoding='utf-8-sig')
new=old
def once(before,after):
 global new
 assert new.count(before)==1,'Ambiguous/missing insertion: '+before[:90]
 new=new.replace(before,after,1)
once('static int GetCachedStackDanger(',fragment+'\nstatic int GetCachedStackDanger(')
indexed_backend='class IndexedStore\n' in old
line='  int cachedResult=0;\n  if (cacheable && FindStackDangerForecastScalar(key,cachedResult))' if indexed_backend else '  StackDangerForecasts::const_iterator cached = cacheable ? gStackDangerForecasts.find(key) : gStackDangerForecasts.end();'
once(line,'  ObserveDestinationDangerKey(unit,plot,candidates,friendlyDamage,key,cacheable); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY\n'+line)
line=' CvStackingDiagnostics::PlanSampleScope sample(CvStackingDiagnostics::PLAN_UNIT_DANGER); // PLAN_SAMPLE_DIAGNOSTIC_ONLY'
once(line,line+'\n DestinationKernelProbeFrame kernelProbe(0,pUnit,pPlot,assumedPosition,iSelfDamage); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY')
line=' return iDanger == INT_MAX ? 10 * pUnit->GetMaxHitPoints() : iDanger;'
once(line,' return kernelProbe.Finish(iDanger == INT_MAX ? 10 * pUnit->GetMaxHitPoints() : iDanger); // DESTINATION_KERNEL_SHADOW_WRAP_ORIGINAL_RETURN')
line=' if (candidates.size() < 2)\n  return 0;\n // City bombardment alone'
once(line,' DestinationKernelProbeFrame kernelProbe(1,unit,plot,position,0,&candidates,&damage); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY\n if (candidates.size() < 2)\n  return kernelProbe.Finish(0); // DESTINATION_KERNEL_SHADOW_WRAP_ORIGINAL_RETURN\n // City bombardment alone')
line=' return score;\n}\n\nstatic int ScoreStackPosition('
once(line,' return kernelProbe.Finish(score); // DESTINATION_KERNEL_SHADOW_WRAP_ORIGINAL_RETURN\n}\n\nstatic int ScoreStackPosition(')
line='\tPacketProbeScope packetProbeScope(ePlayer,pTarget->GetPlotIndex()); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY'
once(line,'\tDestinationKernelProbeSession kernelProbeSession(ePlayer,pTarget->GetPlotIndex()); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY\n'+line)
def function(text,signature):
 a=text.index(signature);b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
for signature,parent in [('void CvTacticalPosition::initFromScratch(','NULL'),('void CvTacticalPosition::initFromParent(','&parent'),('void CvTacticalPosition::ChangeUnitDamage(','parentPosition'),('void CvTacticalPosition::ChangeCityDamage(','parentPosition'),('void CvTacticalPosition::HealFriendlyUnit(','parentPosition')]:
 body=function(new,signature)
 # Mutations may throw; a fresh diagnostic token does not affect the object.
 changed=body.replace('{','{\n ObserveKernelStateMutation(this,'+parent+'); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY',1)
 once(body,changed)
body=function(new,'CvTacticalPosition::AddAssignmentResult CvTacticalPosition::addAssignment(')
needle='\titUnit->eLastAssignment = newAssignment.eAssignmentType;'
assert body.count(needle)==1
once(body,body.replace(needle,'\tObserveKernelStateMutation(this,parentPosition); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY\n'+needle,1))
def without_probe(text):
 text=re.sub(r'// BEGIN DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY\n.*?// END DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY\n\n','',text,flags=re.S)
 text=re.sub(r'^.* // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY\n','',text,flags=re.M)
 text=text.replace('return kernelProbe.Finish(iDanger == INT_MAX ? 10 * pUnit->GetMaxHitPoints() : iDanger); // DESTINATION_KERNEL_SHADOW_WRAP_ORIGINAL_RETURN','return iDanger == INT_MAX ? 10 * pUnit->GetMaxHitPoints() : iDanger;')
 text=text.replace('return kernelProbe.Finish(0); // DESTINATION_KERNEL_SHADOW_WRAP_ORIGINAL_RETURN','return 0;')
 text=text.replace('return kernelProbe.Finish(score); // DESTINATION_KERNEL_SHADOW_WRAP_ORIGINAL_RETURN','return score;')
 return text
assert without_probe(new)==old,'Observer changed original gameplay source'
diag_path='CvGameCoreDLL_Expansion2/CvStackingDiagnostics.cpp'
old_diag=subprocess.check_output(['git','show',DIAGNOSTICS_BASE+':'+diag_path],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
needle=' || !strcmp(category,"PLAN_PACKET_PROBE")) return 16;'
assert old_diag.count(needle)==1
new_diag=old_diag.replace(needle,' || !strcmp(category,"PLAN_PACKET_PROBE") || !strcmp(category,"PLAN_KERNEL_PROBE")) return 16;',1)
assert new_diag.replace(' || !strcmp(category,"PLAN_KERNEL_PROBE")','',1)==old_diag
binding_names=('CvTacticalAI.cpp','CvUnit.cpp','CvDangerPlots.cpp','CvStackingStrengthCache.h','CvStackingStrengthCache.cpp','CvDangerPlots.h','CvUnit.h','CvUnitCombat.cpp','CvPlot.cpp','CvStackingRules.h','CvStackingRules.cpp','CvStackingDiagnostics.h','CvStackingDiagnostics.cpp')
binding={}
for name in binding_names:
 commit=DIAGNOSTICS_BASE if name in ('CvStackingDiagnostics.h','CvStackingDiagnostics.cpp') else BASE
 pinned=subprocess.check_output(['git','show',commit+':CvGameCoreDLL_Expansion2/'+name],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
 if args.bind_current:assert (ROOT/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8-sig')==pinned,'Current whole control mismatch: '+name
 binding[name]=hashlib.sha256(pinned.encode()).hexdigest()
(OUT/'control.cpp').write_text(old,encoding='utf-8');(OUT/'CvTacticalAI.cpp').write_text(new,encoding='utf-8')
(OUT/'control-CvStackingDiagnostics.cpp').write_text(old_diag,encoding='utf-8');(OUT/'CvStackingDiagnostics.cpp').write_text(new_diag,encoding='utf-8')
patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+PATH,tofile='b/'+PATH))+''.join(difflib.unified_diff(old_diag.splitlines(True),new_diag.splitlines(True),fromfile='a/'+diag_path,tofile='b/'+diag_path))
(OUT/'kernel-probe.patch').write_text(patch,encoding='utf-8')
(OUT/'manifest.json').write_text(json.dumps(dict(control=BASE,diagnostics_control=DIAGNOSTICS_BASE,original_sha256=hashlib.sha256(old.encode()).hexdigest(),candidate_sha256=hashlib.sha256(new.encode()).hexdigest(),diagnostics_original_sha256=hashlib.sha256(old_diag.encode()).hexdigest(),diagnostics_candidate_sha256=hashlib.sha256(new_diag.encode()).hexdigest(),fragment_sha256=hashlib.sha256(fragment.encode()).hexdigest(),whole_gameplay_reverse_exact=True,production_untouched=True,bound_current_control=args.bind_current,original_whole_files_sha256=binding,indexed_backend=indexed_backend,scope='Default-off observer only plus one performance-category mapping: original destination kernels and scalar key sequences still execute; equal footprint/results measure opportunity, not certified dependency/reuse or native speedup.'),indent=2))
print(json.dumps(dict(control=BASE,stage=str(OUT),indexed_backend=indexed_backend,bound_current_control=args.bind_current,whole_gameplay_reverse_exact=True,production_untouched=True)))
