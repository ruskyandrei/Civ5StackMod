"""Actual indexed-module hash-only differential and bounded VC9 x86 microbench.

Source fixtures are synthetic profiles, not native captured keys or end-turn ROI.
The existing 433k indexed regression's literal services/tests are reused intact.
"""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,os,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--variant',choices=('multiply2','multiply1'),default='multiply2');p.add_argument('--emit-only',action='store_true');p.add_argument('--no-benchmark',action='store_true');p.add_argument('--production',action='store_true');args=p.parse_args()
spec=importlib.util.spec_from_file_location('hash_stager',ROOT/'work/prepare-strength-hash-experiment.py');stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
out=stage.OUT/args.variant;proof=json.loads((out/'staging-proof.json').read_text())
source=subprocess.check_output(['git','show',stage.CONTROL+':'+stage.PATH],cwd=ROOT).decode('utf-8-sig')
header=subprocess.check_output(['git','show',stage.CONTROL+':'+stage.HEADER],cwd=ROOT).decode('utf-8-sig')
candidate=(ROOT/stage.PATH).read_text(encoding='utf-8-sig') if args.production else (out/'CvStackingStrengthCache.cpp').read_text(encoding='utf-8-sig')
assert source==(out/'control.cpp').read_text(encoding='utf-8-sig') and candidate==stage.transform(source,args.variant)
assert hashlib.sha256(candidate.encode()).hexdigest()==proof['candidate_sha256']
assert hashlib.sha256(header.encode()).hexdigest()==proof['header_sha256'] and (ROOT/stage.HEADER).read_text(encoding='utf-8-sig')==header
for signature in ('bool Context(','void Invalidate(','long SceneEpoch(','bool IsOwner(','LONG Read(','bool Key::operator==(',
                  'size_t Find(','void Link(','void Unlink(','void Clear(','bool Lookup(','void Store(','Scope::Scope(', 'Scope::~Scope('):
 assert stage.function(candidate,signature)==stage.function(source,signature),signature
def literal(name):
 tree=ast.parse((ROOT/'work/test-strength-index-container-prototype.py').read_text(encoding='utf-8'))
 for n in tree.body:
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets):return ast.literal_eval(n.value)
 raise ValueError(name)
prefix=literal('prefix');tests=literal('tests')
omit=('#include "CvGameCoreDLLPCH.h"','#include "CvStackingStrengthCache.h"','#include "LintFree.h"')
module='\n'.join(line for line in source.splitlines() if line not in omit)
trial='\n'.join(line for line in candidate.splitlines() if line not in omit)
constant=trial.replace(stage.function(trial,'size_t operator()(const Key& key) const'),'size_t operator()(const Key&) const { return 0; }',1)
extras=r'''
using std::vector;using std::pair;using std::make_pair;using std::sort;
void HashSpecificCases(){
 Expect("native unsigned full-word width",sizeof(unsigned int)==4&&sizeof(Index::Key)==88);
 Baseline::Key zero;for(int i=0;i<22;++i)zero.values[i]=0;
 const size_t original=Index::Hash()(Indexed(zero));unsigned totalFlips=0,changes=0;
 {Baseline::Scope bs(1024);Index::Scope cs(1024);long b,c;Baseline::Context(b);Index::Context(c);
  for(int w=0;w<22;++w)for(int bit=0;bit<32;++bit){Baseline::Key key=zero;key.values[w]=(int)(1u<<bit);const size_t hash=Index::Hash()(Indexed(key));Expect("every single word bit reaches full hash",hash!=original);unsigned delta=(unsigned)hash^(unsigned)original;for(;delta;delta&=delta-1)++totalFlips;++changes;Baseline::Store(key,b,Value(key));Index::Store(Indexed(key),c,Value(key));int bv,cv;Expect("single high/low bit keys remain distinct",Baseline::Lookup(key,b,bv)&&Index::Lookup(Indexed(key),c,cv)&&bv==cv);}
  int extremes[]={INT_MIN,INT_MAX,-1,0,1,0x10000,0x40000000};
  for(int w=0;w<22;++w)for(int i=0;i<7;++i){Baseline::Key key=MakeKey((unsigned)(w*7+i));key.values[w]=extremes[i];Baseline::Store(key,b,Value(key));Index::Store(Indexed(key),c,Value(key));int bv=-7,cv=-7;Expect("extreme signed words exact",Baseline::Lookup(key,b,bv)==Index::Lookup(Indexed(key),c,cv)&&bv==cv);}
  CompareStats();}
 printf("HASH_BIT_MIX changes%u mean_changed_bits%.3f (quality sample, not a security claim)\n",changes,(double)totalFlips/changes);
 // Force all hashes equal while retaining every actual indexed guard/ring/
 // bucket/equality body. Exercise head/middle/tail links and FIFO duplicates.
 {Collision::Scope scope(8);long g;Collision::Context(g);for(unsigned i=0;i<24;++i){Baseline::Key key=MakeKey(i);Collision::Key k;memcpy(k.values,key.values,sizeof(k.values));Collision::Store(k,g,Value(key));Collision::Store(k,g,99999);int v=0;Expect("forced collision exact latest key",Collision::Lookup(k,g,v)&&v==Value(key));if(i>=8){Baseline::Key old=MakeKey(i-8);memcpy(k.values,old.values,sizeof(k.values));Expect("forced collision FIFO oldest",!Collision::Lookup(k,g,v));}}Collision::Invalidate();Collision::Context(g);Expect("forced collision epoch clears",Collision::nodes.empty()&&Collision::oldest==0);}
 // Actual candidate collisions: sort deterministic full hashes, not bucket
 // masks, and assert differing 88-byte keys can coexist with distinct values.
 vector<pair<size_t,unsigned> >hashes;hashes.reserve(180000);for(unsigned i=0;i<180000;++i)hashes.push_back(make_pair(Index::Hash()(Indexed(MakeKey(i))),i));sort(hashes.begin(),hashes.end());unsigned collisions=0;
 {Index::Scope scope(8);long g;Index::Context(g);for(size_t i=1;i<hashes.size();++i)if(hashes[i].first==hashes[i-1].first){Baseline::Key a=MakeKey(hashes[i-1].second),b=MakeKey(hashes[i].second);if(a==b)continue;++collisions;Index::Invalidate();Index::Context(g);Index::Store(Indexed(a),g,41);Index::Store(Indexed(b),g,73);int av=0,bv=0;Expect("actual full-hash collisions never merge",Index::Lookup(Indexed(a),g,av)&&Index::Lookup(Indexed(b),g,bv)&&av==41&&bv==73);}}
 printf("ACTUAL_HASH_COLLISIONS keys180000 collisions%u (forced collision path always tested)\n",collisions);
}
template<class Hash,class Key>double HashTime(const vector<Key>&pool,unsigned iterations){LARGE_INTEGER a,b,f;QueryPerformanceFrequency(&f);unsigned sum=0;Hash hash;QueryPerformanceCounter(&a);for(unsigned i=0;i<iterations;++i)sum+=(unsigned)hash(pool[(i*11939u)&16383]);checksum=sum;QueryPerformanceCounter(&b);return 1000.0*(b.QuadPart-a.QuadPart)/f.QuadPart;}
Baseline::Key MicroProfile(unsigned i){Baseline::Key key=MakeKey(i);if(i%8==0){key.values[11]=(i/2048)%8;key.values[12]=100+i%81;key.values[13]=(i/64)%300;key.values[20]=(i/33)%7;}if(i%16==0){key.values[6]=key.values[7]=key.values[8]=-1;key.values[9]=key.values[10]=0;}key.values[16]=i%8;key.values[21]=i%16==0?(i/97)%24:0;return key;}
void HashMicro(){vector<Baseline::Key>pool;vector<Index::Key>other;pool.reserve(16384);other.reserve(16384);for(unsigned i=0;i<16384;++i){pool.push_back(MicroProfile(i));other.push_back(Indexed(pool.back()));}const unsigned loops=4000000;
 for(int pass=0;pass<4;++pass){double b,c;if(pass%2==0){b=HashTime<Baseline::Hash>(pool,loops);c=HashTime<Index::Hash>(other,loops);}else{c=HashTime<Index::Hash>(other,loops);b=HashTime<Baseline::Hash>(pool,loops);}printf("HASH_ONLY pass%d queries%u old_ms%.3f new_ms%.3f ratio%.3f old_ns%.3f new_ns%.3f\n",pass,loops,b,c,b/c,b*1e6/loops,c*1e6/loops);}
}
'''
tests=tests.replace('int main(int argc,char**argv){',extras+'\nint main(int argc,char**argv){',1)
tests=tests.replace('Differential();FullCapacityCases();ConstructorAllocationFailure();if(!noBenchmark){','Differential();FullCapacityCases();ConstructorAllocationFailure();HashSpecificCases();if(!noBenchmark){HashMicro();',1)
fixture=prefix+header.replace('#pragma once','').replace('CvStackingStrengthCache','Baseline')+module.replace('CvStackingStrengthCache','Baseline')+header.replace('#pragma once','').replace('CvStackingStrengthCache','Index')+trial.replace('CvStackingStrengthCache','Index')+header.replace('#pragma once','').replace('CvStackingStrengthCache','Collision')+constant.replace('CvStackingStrengthCache','Collision')+tests
(out/'test.cpp').write_text(fixture,encoding='utf-8');fixture_hash=hashlib.sha256(fixture.encode()).hexdigest()
if args.emit_only:print(json.dumps({'emitted':str(out/'test.cpp'),'fixture_sha256':fixture_hash,'compilation':False}));raise SystemExit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe';build=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(build.stdout+build.stderr)
if build.returncode:print(build.stdout+build.stderr);raise SystemExit(build.returncode)
run=subprocess.run([str(exe)]+(['--no-benchmark'] if args.no_benchmark else []),cwd=out,capture_output=True,text=True,timeout=60);print(run.stdout+run.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,control=stage.CONTROL,variant=args.variant,production_applied=args.production,fixture_sha256=fixture_hash,source_sha256=hashlib.sha256(source.encode()).hexdigest(),candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest(),header_sha256=hashlib.sha256(header.encode()).hexdigest(),benchmark_executed=not args.no_benchmark,scope='Actual same indexed module with ONLY hash changed; inherited complete433k FIFO/guard/allocation regressions plus actual/forced collisions and high-bit keys. Synthetic profiles, not native end-turn ROI.'),indent=2)+'\n')
raise SystemExit(run.returncode)
