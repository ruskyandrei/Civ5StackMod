"""Work-only allocation-free resident slot-key stage pinned to DLL97."""
from pathlib import Path
import difflib,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];BASE='fbde19541';PATH='CvGameCoreDLL_Expansion2/CvTacticalAI.cpp';OUT=ROOT/'work/resident-slot-key-staged';OUT.mkdir(exist_ok=True)
old=subprocess.check_output(['git','show',BASE+':'+PATH],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n');new=old;changes=[]
def function(s,sig):
 a=s.index(sig);b=s.index('{',a)+1;d=1
 while d:d+=(s[b]=='{')-(s[b]=='}');b+=1
 return s[a:b]
def once(a,b):
 global new
 assert new.count(a)==1,(a[:90],new.count(a));new=new.replace(a,b,1);changes.append((a,b))
api=(ROOT/'work/resident-slot-key-api.cpp').read_text(encoding='utf-8-sig');helpers=(ROOT/'work/resident-slot-key-helpers.cpp').read_text(encoding='utf-8-sig')
once(' // Stable handle. The caller copies scalar/pointer/member data before Context.',api+'\n // Stable handle. The caller copies scalar/pointer/member data before Context.')
once(function(new,'struct ResidentScalarCertificate\n'),'''struct ResidentScalarCertificate
{
 const CvUnit* unit;int extra;bool canonical,valid;
 IndexedStore::ScalarHandle handle;
 ResidentScalarCertificate():unit(NULL),extra(0),canonical(false),valid(false){}
 size_t Bytes()const{return 0;} // The resident table already owns the exact key.
 void Release(){valid=false;}
}''')
once(' int prefix[MAX_PREFIX_WORDS];size_t count;',' int prefix[MAX_PREFIX_WORDS];size_t count;unsigned long revision;long scene;')
once(' ResidentScalarKeyWork():count(0),certificate(NULL),view(NULL),request(NULL){}',' ResidentScalarKeyWork():count(0),revision(0),scene(0),certificate(NULL),view(NULL),request(NULL){}')
a=new.index('static ParentStackPreparationCell* ResidentArrivalCell(');b=new.index('static void MarkParentStackPreparationChild(',a)
once(new[a:b],helpers+'\n')
# No key/projection/scalar/FIFO/miss arithmetic/body changes outside helpers.
for sig in ('static void AppendStackDamageProjected(','static __declspec(noinline) int ResolveStackDangerForecastMiss(','static int GetCachedStackDanger(','static int GetUnitDangerForPlot('):assert function(new,sig)==function(old,sig),sig
restored=new
for a,b in reversed(changes):assert restored.count(b)==1;restored=restored.replace(b,a,1)
assert restored==old
(OUT/'control.cpp').write_text(old,encoding='utf-8');(OUT/'CvTacticalAI.cpp').write_text(new,encoding='utf-8')
(OUT/'slot-key.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+PATH,tofile='b/'+PATH)),encoding='utf-8')
proof=dict(control=BASE,original_sha256=hashlib.sha256(old.encode()).hexdigest(),candidate_sha256=hashlib.sha256(new.encode()).hexdigest(),whole_reverse_exact=True,wrapper_projection_miss_body_unchanged=True,production_untouched=True,scope='No certificate key vector/allocation; one lexical cell acquisition; guarded resident slot prefix copy and post-projection suffix read; no cache/FIFO/search policy change, native ROI unknown.')
(OUT/'manifest.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
