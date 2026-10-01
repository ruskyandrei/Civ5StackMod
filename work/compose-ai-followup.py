"""Compose frozen work-only AI stages; never silently resolve source conflicts."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];BASE='d792b4bcb'
OUT=ROOT/'work/ai-followup-composed';OUT.mkdir(exist_ok=True)
components=(('continuity','ai-continuity-followup-staged',('CvStackingOffensiveAI.cpp','CvStackingOffensiveAI.h','CvUnitCombat.cpp','CvStackingAI.cpp')),
            ('healing','city-healing-forecast-staged',('CvCity.cpp','CvCity.h','CvTacticalAI.cpp')),
            ('wave','first-wave-staged',('CvStackingOffensiveAI.cpp','CvStackingOffensiveAI.h','CvStackingAI.cpp')),
            ('production','ai-production-policy-staged',('CvStackingOffensiveAI.cpp','CvStackingOffensiveAI.h','CvCity.cpp','CvUnitProductionAI.cpp')))
original={};current={};component_hashes={};conflicts=[]
for label,directory,names in components:
    component_hashes[label]={}
    for name in names:
        file=ROOT/'work'/directory/name
        if not file.exists():raise RuntimeError('Missing frozen component '+str(file))
        if name not in original:
            original[name]=subprocess.check_output(['git','show',BASE+':CvGameCoreDLL_Expansion2/'+name],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
            current[name]=original[name]
        theirs=file.read_text(encoding='utf-8-sig')
        component_hashes[label][name]=hashlib.sha256(theirs.encode()).hexdigest()
        if current[name]==original[name]:current[name]=theirs
        else:
            ours=OUT/(label+'-ours-'+name);base=OUT/(label+'-base-'+name);other=OUT/(label+'-theirs-'+name)
            ours.write_text(current[name],encoding='utf-8');base.write_text(original[name],encoding='utf-8');other.write_text(theirs,encoding='utf-8')
            r=subprocess.run(['git','merge-file','--diff3','-L','composed','-L',BASE,'-L',label,str(ours),str(base),str(other)],cwd=ROOT,capture_output=True,text=True)
            if r.returncode<0 or r.returncode>127:raise RuntimeError(r.stdout+r.stderr or 'merge-file failed '+str(r.returncode))
            current[name]=ours.read_text(encoding='utf-8')
            if r.returncode:conflicts.append(name+':'+label)
for name,text in current.items():
    (OUT/name).write_text(text,encoding='utf-8')
    (OUT/('control-'+name)).write_text(original[name],encoding='utf-8')
proof={'control':BASE,'component_hashes':component_hashes,'conflicts':conflicts,
       'candidate_hashes':{n:hashlib.sha256(t.encode()).hexdigest() for n,t in current.items()},
       'production_untouched':True,'pending':'Resolve explicit conflicts, compose lifecycle/progress/XML/reader seams, bind integrated tests before adoption'}
(OUT/'composition-inputs.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'files':len(current),'conflicts':conflicts,'production_untouched':True}))
sys.exit(1 if conflicts else 0)
