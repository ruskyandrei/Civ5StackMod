"""Actual-source enemy-roster CoW differential; prepare-only during native timing."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess

ROOT=Path(__file__).resolve().parents[1];STAGE=ROOT/'work/enemy-roster-cow-staged';OUT=ROOT/'work/enemy-roster-cow-regression'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--production',action='store_true',help='Test both exact currently-applied tactical files, refusing any whole-file stage drift.');p.add_argument('--runtime-timeout',type=float,default=15);args=p.parse_args()
def block(text,signature,semi=False):
 start=text.index(signature);end=text.index('{',start)+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 if semi:assert text[end]==';';end+=1
 return text[start:end]
support=json.loads((ROOT/'work/enemy-roster-cow-fixture-data.json').read_text(encoding='utf-8'))
def literal(name):
 value=support['literals'][name]
 assert hashlib.sha256(value.encode()).hexdigest()==support['sha256'][name],('fixture support drift',name)
 return value
old_cpp=(STAGE/'control-CvTacticalAI.cpp').read_text(encoding='utf-8');old_h=(STAGE/'control-CvTacticalAI.h').read_text(encoding='utf-8')
candidate_root=ROOT/'CvGameCoreDLL_Expansion2' if args.production else STAGE
new_cpp=(candidate_root/'CvTacticalAI.cpp').read_text(encoding='utf-8');new_h=(candidate_root/'CvTacticalAI.h').read_text(encoding='utf-8')
proof=json.loads((STAGE/'staging-proof.json').read_text());assert proof['cpp_restoration_byte_exact'] and proof['fixed_roster_unchanged']
for name,text in (('CvTacticalAI.cpp',old_cpp),('CvTacticalAI.h',old_h)):
 pinned=subprocess.check_output(['git','show',proof['control']+':CvGameCoreDLL_Expansion2/'+name],cwd=ROOT).decode('utf-8')
 assert text==pinned and hashlib.sha256(text.encode()).hexdigest()==proof['files'][name]['original_sha256'],('pinned control source drift',name)
for name,text in (('CvTacticalAI.cpp',new_cpp),('CvTacticalAI.h',new_h)):
 assert hashlib.sha256(text.encode()).hexdigest()==proof['files'][name]['candidate_sha256'],('current production source does not exactly match staged candidate' if args.production else 'staged candidate drift',name)
prefix=literal('prefix').replace('struct CvUnit{','static size_t unitIDReads=0,domainReads=0;\nstruct CvUnit{').replace('int GetID()const{return id;}','int GetID()const{++unitIDReads;return id;}').replace('int DomainForUnit(const CvUnit*u){return u->domain;}','int DomainForUnit(const CvUnit*u){++domainReads;return u->domain;}')
prefix=prefix.replace('void*operator new(size_t n)throw(std::bad_alloc){','static int failCountdown=-1;\nvoid*operator new(size_t n)throw(std::bad_alloc){if(failCountdown>=0&&failCountdown--==0){failCountdown=-1;throw std::bad_alloc();}')
unit=block(old_h,'struct STacticalUnit',True);cow='template<typename T>\n'+block(old_h,'struct SCoWField',True)
pieces=[prefix,unit,cow]
for header,cpp,name in ((old_h,old_cpp,'OriginalPlot'),(new_h,new_cpp,'SharedPlot')):
 if name=='SharedPlot':
  pieces.append(block(header,'class STacticalEnemyRoster\n',True))
  pieces.append('static const vector<const CvUnit*> gEmptyTacticalEnemyRoster;\n'+block(cpp,'const vector<const CvUnit*>& STacticalEnemyRoster::Empty()'))
 pieces.append(block(header,'class CvTacticalPlot\n',True).replace('CvTacticalPlot',name).replace('protected:','public:'))
 for signature in ('CvTacticalPlot::CvTacticalPlot(','int CvTacticalPlot::getFixedFriendlyCount(',
                   'void CvTacticalPlot::resetVolatileProperties(','bool CvTacticalPlot::removeEnemyUnitIfPresent(','void CvTacticalPlot::clearCapturedCity('):
  pieces.append(block(cpp,signature).replace('CvTacticalPlot',name))
tests=literal('tests')
tests=tests.replace('for(int k=0;k<80;++k)units[k].id=k;','for(int k=0;k<80;++k){units[k].id=k;units[k].owner=1;}')
tests=tests.replace('&&!current.vFixedFriendlyUnits.get()','&&current.getEnemyUnits().empty()').replace('&&!newer.vFixedFriendlyUnits.get()','&&newer.getEnemyUnits().empty()')
tests=tests.replace('current.getFixedFriendlyUnits().empty()?(!child.vFixedFriendlyUnits.get()):(&current.getFixedFriendlyUnits()==&child.getFixedFriendlyUnits())','current.getEnemyUnits().empty()?child.getEnemyUnits().empty():(&current.getEnemyUnits()==&child.getEnemyUnits())')
tests=tests.replace('nonempty copies share immutable payload','nonempty enemy copies share payload beforemutation')
tests=tests.replace('CvUnit unit(5);CvPlot plot;','CvUnit unit(5);unit.owner=1;CvPlot plot;')
tests=tests.replace('survivor.getFixedFriendlyUnits().size()==1&&survivor.getFixedFriendlyUnits()[0]==&unit','survivor.getEnemyUnits().size()==1&&survivor.getEnemyUnits()[0]==&unit')
tests=tests.replace('int main(){','int main(){\n ExtraEnemyCases();',1)
tests=tests.replace('same actualCoW clone removes nested fixed allocations','same actualCoW clone removes nested enemy allocations')
tests=tests.replace('actual fixed-friendly roster:','actual enemy roster CoW:')
extras=r'''
void ExtraEnemyCases(){
 vector<const CvUnit*>ours;CvUnit units[5];CvPlot plot;
 for(int i=0;i<5;++i){units[i].id=i;units[i].owner=1;plot.units.push_back(&units[i]);}
 units[3].id=1;plot.units.push_back(&units[1]);
 OriginalPlot old(&plot,0,ours);SharedPlot parent(&plot,0,ours),child=parent;
 const vector<const CvUnit*>*borrowed=&child.getEnemyUnits();
 size_t allocations=allocCalls;
 bool absent=child.removeEnemyUnitIfPresent(999);
 Expect("absent removal no detach/alloc",!absent&&allocCalls==allocations&&&child.getEnemyUnits()==borrowed);
 size_t oldIDs=unitIDReads,oldDomains=domainReads;bool a=old.removeEnemyUnitIfPresent(1);oldIDs=unitIDReads-oldIDs;oldDomains=domainReads-oldDomains;
 size_t newIDs=unitIDReads,newDomains=domainReads;bool b=child.removeEnemyUnitIfPresent(1);newIDs=unitIDReads-newIDs;newDomains=domainReads-newDomains;
 Expect("first rawID match and callback order preserved",a==b&&oldIDs==newIDs&&oldDomains==newDomains&&Same(old,child));
 Expect("successful shared removal detaches",&child.getEnemyUnits()!=&parent.getEnemyUnits()&&parent.getEnemyUnits().size()==6&&child.getEnemyUnits().size()==5);
 const vector<const CvUnit*>*unique=&child.getEnemyUnits();allocations=allocCalls;
 a=old.removeEnemyUnitIfPresent(1);b=child.removeEnemyUnitIfPresent(1);
 Expect("subsequent unique removal no allocation",a==b&&Same(old,child)&&allocCalls==allocations&&unique==&child.getEnemyUnits());
 for(int i=0;i<5;++i){a=old.removeEnemyUnitIfPresent(i);b=child.removeEnemyUnitIfPresent(i);Expect("duplicates rawIDs remain exact through repeatedremoval",a==b&&Same(old,child));}
 SharedPlot grandchild=parent;grandchild.clearCapturedCity();OriginalPlot captured(&plot,0,ours);captured.clearCapturedCity();
 Expect("capture clears child only and releases emptyowner",Same(captured,grandchild)&&parent.getEnemyUnits().size()==6&&grandchild.getEnemyUnits().empty());
 SharedPlot anotherEmpty;Expect("all empty accessors use same unowned constant",&anotherEmpty.getEnemyUnits()==&grandchild.getEnemyUnits());
 Expect("last unit removal normalizes to unowned empty",child.getEnemyUnits().empty()&&&child.getEnemyUnits()==&anotherEmpty.getEnemyUnits());
 vector<SharedPlot> emptyCopies;emptyCopies.reserve(256);allocations=allocCalls;for(int i=0;i<256;++i)emptyCopies.push_back(grandchild);Expect("empty copies no allocations/refowners",allocCalls==allocations);
 grandchild=parent;grandchild=grandchild;Expect("copy/selfassignment restores exact roster",grandchild.getEnemyUnits()==parent.getEnemyUnits());
 // Mutated children are separate values; caller views are never retained across
 // clear/detach, matching the complete audited production call sites.
 SCoWField<vector<SharedPlot> >base,branch;base.write().push_back(parent);branch.inheritFrom(base.read());branch.write()[0].removeEnemyUnitIfPresent(0);
 Expect("actual plot-vector CoW plus nestedroster CoW isolates parent",base.read()[0].getEnemyUnits().size()==6&&branch.read()[0].getEnemyUnits().size()==5);
 branch.clear();branch.inheritFrom(base.read());Expect("recycled slot sees inherited current roster",branch.read()[0].getEnemyUnits()==parent.getEnemyUnits());
 vector<SharedPlot> forks(256,parent);vector<const vector<const CvUnit*>*>payloads;
 payloads.push_back(&parent.getEnemyUnits());
 for(size_t i=0;i<forks.size();++i){if(i%4==0)forks[i].removeEnemyUnitIfPresent(0);const vector<const CvUnit*>*view=&forks[i].getEnemyUnits();if(find(payloads.begin(),payloads.end(),view)==payloads.end())payloads.push_back(view);}
 Expect("only mutated branches add payload owners",payloads.size()==65);
 Expect("retained distinct payloads bounded by nonemptyfield references",payloads.size()<=forks.size()+1);
 for(size_t i=0;i<forks.size();++i)Expect("fork casualties isolate every sibling",forks[i].getEnemyUnits().size()==(i%4==0?5:6));
 for(int point=0;point<3;++point){SharedPlot failed=parent;const vector<const CvUnit*>*before=&failed.getEnemyUnits();size_t retained=liveBytes;failCountdown=point;bool caught=false;
  try{failed.removeEnemyUnitIfPresent(0);}catch(const std::bad_alloc&){caught=true;}failCountdown=-1;
  Expect("detach allocationfailure preserves originalowners and flags",caught&&&failed.getEnemyUnits()==before&&failed.getEnemyUnits()==parent.getEnemyUnits()&&failed.aiEnemyDistance[2]==parent.aiEnemyDistance[2]);
  Expect("failed detach releases temporary allocation",liveBytes==retained);
 }
}
'''
# ExtraEnemyCases requires the actual Same/Expect definitions before its body.
insert=tests.index('int main(){');tests=tests[:insert]+extras+tests[insert:]
assert 'vFixedFriendlyUnits.get()' not in tests
fixture='\n'.join(pieces)+tests
OUT.mkdir(exist_ok=True);(OUT/'test.cpp').write_text(fixture,encoding='utf-8')
manifest={'control':proof['control'],'production_applied':args.production,'compiled':False,'fixed_roster_unchanged':True,
 'current_whole_file_binding':args.production,'source_sha256':{name:hashlib.sha256(text.encode()).hexdigest() for name,text in (('CvTacticalAI.cpp',new_cpp),('CvTacticalAI.h',new_h))},
 'fixture_sha256':hashlib.sha256(fixture.encode()).hexdigest(),
 'scope':'Complete actual original/staged tactical plot classes, constructors/count/removal/capture/volatile bodies, enemy CoW wrapper and actual position CoW; native VC9 shared_ptr, deterministic engine service substitutes. No speed/RSS claim.'}
(OUT/'fixture-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if args.prepare_only:print(json.dumps(manifest));raise SystemExit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=OUT/'test.exe';c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(OUT/'test.cpp'),'/Fo'+str(OUT/'test.obj'),'/Fe'+str(exe)],cwd=OUT,env=env,capture_output=True,text=True,timeout=60)
(OUT/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);raise SystemExit(c.returncode)
try:r=subprocess.run([str(exe)],cwd=OUT,capture_output=True,text=True,timeout=args.runtime_timeout)
except subprocess.TimeoutExpired as exc:
 output=(exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout,bytes) else exc.stdout or ''
 (OUT/'result.json').write_text(json.dumps(dict(manifest,compiled=True,timed_out=True,returncode=None,output=output),indent=2)+'\n');print(output);raise
print(r.stdout+r.stderr,end='');(OUT/'result.json').write_text(json.dumps(dict(manifest,compiled=True,returncode=r.returncode,output=r.stdout+r.stderr),indent=2)+'\n')
raise SystemExit(r.returncode)
