"""Actual Tactical cache hash-only differential and bounded synthetic VC9 timing."""
from pathlib import Path
import ast,hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];out=root/'work/tactical-key-hash-regression';out.mkdir(exist_ok=True);production='--production' in sys.argv
stage=root/'work/tactical-key-hash-stage';proof=json.loads((stage/'manifest.json').read_text())
old=(stage/'control.cpp').read_text(encoding='utf-8-sig');new=(stage/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
assert hashlib.sha256(old.encode()).hexdigest()==proof['source_sha256'] and hashlib.sha256(new.encode()).hexdigest()==proof['candidate_sha256']
bound_hashes={}
if production:
 actual=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
 assert hashlib.sha256(actual.encode()).hexdigest()==proof['candidate_sha256'],'Actual whole TacticalAI does not match reviewed hash candidate'
 new=actual;bound_hashes['CvTacticalAI.cpp']=hashlib.sha256(new.encode()).hexdigest()
 # These whole files supply the actual numerical engine-facing bodies and
 # deterministic-service enum/container bindings. Pin every input to82;
 # a future callback/math migration must be reviewed rather than hidden.
 for name in ('CvUnit.cpp','CvUnit.h','CvUnitCombat.cpp','CvDangerPlots.cpp','CvDangerPlots.h','CvPlot.cpp','CvStackingRules.cpp','CvStackingRules.h'):
  reference=subprocess.check_output(['git','show',proof['control']+':CvGameCoreDLL_Expansion2/'+name],cwd=root).decode('utf-8-sig').replace('\r\n','\n')
  current=(root/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8-sig')
  assert current==reference,'Actual whole numerical input changed from82: '+name
  bound_hashes[name]=hashlib.sha256(current.encode()).hexdigest()
generator=(root/'work/test-shared-packet-native-stage.py').read_text(encoding='utf-8-sig');prefix=generator[:generator.index("\ntests=r'''")]
scope={'__file__':str(root/'work/test-shared-packet-native-stage.py')};arguments=sys.argv
try:
 sys.argv=[arg for arg in arguments if arg!='--production'];exec(compile(prefix,'actual tactical hash modules','exec'),scope)
finally:sys.argv=arguments
function=scope['function'];old_hash=function(old,'struct StackForecastKeyHash\n');new_hash=function(new,'struct StackForecastKeyHash\n')
assert new.replace(new_hash,old_hash,1)==old,'Not an isolated whole-file hash delta'
constant=new.replace(new_hash,'struct StackForecastKeyHash{size_t operator()(const StackForecastKey&)const{return 0;}}',1)
module=scope['cache_module'];implementation=scope['common']+'\nnamespace Control{\n'+module(scope['old'],False)+'\n}\n'
for name,text in [('Baseline',old),('Trial',new),('Collision',constant)]:implementation+='\nnamespace '+name+'{\n'+module(text,True)+'\n}\n'
tests=None
for node in ast.parse(generator).body:
 if isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='tests' for x in node.targets):tests=ast.literal_eval(node.value)
assert tests
extras=r'''
static volatile unsigned hashChecksum=0;
#define HASH_ADAPTER(NAME,NS) struct NAME{typedef NS::StackForecastKey Key;typedef NS::StackForecastKeyHash Hash;typedef NS::StackForecastScope Scope;static void Limits(unsigned n,size_t bytes){NS::gStackEntryLimit=n;NS::gStackKeyPayloadLimit=bytes;}static bool Lookup(const Key&k,int&value){if(!NS::StackForecastContext())return false;NS::StackDangerForecasts::const_iterator i=NS::gStackDangerForecasts.find(k);if(i==NS::gStackDangerForecasts.end())return false;value=i->second.scalar;return true;}static void Store(const Key&k,int value){NS::StoreStackDangerForecast(k,value);}static unsigned Evictions(){return NS::gStackDangerEvictions;}static vector<pair<vector<int>,int> > Snapshot(){vector<pair<vector<int>,int> >v;for(NS::StackDangerForecasts::const_iterator i=NS::gStackDangerForecasts.begin();i!=NS::gStackDangerForecasts.end();++i)v.push_back(make_pair(i->first.state,i->second.scalar));sort(v.begin(),v.end());return v;}static size_t Bytes(){return NS::gStackKeyPayloadBytes;}};
HASH_ADAPTER(OldHash,Baseline) HASH_ADAPTER(NewHash,Trial) HASH_ADAPTER(CollisionHash,Collision)
static vector<int> HashWords(unsigned number,unsigned length){vector<int>w(length);for(unsigned i=0;i<length;++i)w[i]=(int)(number*11939u+i*0x9e3779b9u);if(length>=6){w[0]=1000+number%1024;w[1]=number%4800;w[2]=number%101;w[3]=number%91;w[4]=(length-6)/2;w[length-1]=number%7;}if(length>9&&number%3==0)w[7]=-(int)(number%88);return w;}
template<class C>typename C::Key KeyOf(const vector<int>&words){typename C::Key key;key.state=words;return key;}
static void TacticalHashDifferential(){Check("hash native32bit",sizeof(unsigned int)==4&&sizeof(size_t)==4);unsigned lengths[]={0,1,2,3,4,6,8,9,10,12,16,22,31,64,127,256,511,512};
 for(unsigned cap=1;cap<=64;cap=cap==1?3:cap==3?12:cap==12?64:65){Baseline::StackForecastScope old;Trial::StackForecastScope trial;Collision::StackForecastScope coll;OldHash::Limits(cap,8192);NewHash::Limits(cap,8192);CollisionHash::Limits(cap,8192);
  for(unsigned step=0;step<9000;++step){unsigned n=(step*11939u)%257,len=lengths[(n+step/4)%18];vector<int>w=HashWords(n,len);OldHash::Key a=KeyOf<OldHash>(w);NewHash::Key b=KeyOf<NewHash>(w);CollisionHash::Key c=KeyOf<CollisionHash>(w);int av=777,bv=777,cv=777;bool ah=OldHash::Lookup(a,av),bh=NewHash::Lookup(b,bv),ch=CollisionHash::Lookup(c,cv);Check("full-equality variable key lookup identical",ah==bh&&bh==ch&&av==bv&&bv==cv);if(step%5!=0){OldHash::Store(a,(int)n);NewHash::Store(b,(int)n);CollisionHash::Store(c,(int)n);}if(step%31==0){Check("full cache/FIFO same under forced all-hash collision",OldHash::Snapshot()==NewHash::Snapshot()&&OldHash::Snapshot()==CollisionHash::Snapshot());Check("payload/evictions unchanged",OldHash::Bytes()==NewHash::Bytes()&&OldHash::Bytes()==CollisionHash::Bytes()&&OldHash::Evictions()==NewHash::Evictions()&&OldHash::Evictions()==CollisionHash::Evictions());}}
 }
 unsigned extremes[]={0,1,0xffffffffu,0x80000000u,0x7fffffffu,0x10000u,0x40000000u};
 for(unsigned length=0;length<=512;++length){vector<int>w(length,0);if(length<=8)Check("shortkey hash exactlyoriginal",OldHash::Hash()(KeyOf<OldHash>(w))==NewHash::Hash()(KeyOf<NewHash>(w)));if(length){unsigned position=(length*11939u+17u)%length;for(unsigned e=0;e<7;++e){w[position]=(int)extremes[e];OldHash::Key a=KeyOf<OldHash>(w);NewHash::Key b=KeyOf<NewHash>(w);Check("signed/highbit key remains exact wholevector",a.state==b.state);if(length<=8)Check("short signed hash exactlyoriginal",OldHash::Hash()(a)==NewHash::Hash()(b));}}
 }
 vector<int>zero(512,0);size_t empty=NewHash::Hash()(KeyOf<NewHash>(zero));unsigned flips=0,changed=0;
 for(unsigned i=0;i<512;++i){unsigned changedHere=0;for(unsigned bit=0;bit<32;++bit){vector<int>w=zero;w[i]=(int)(1u<<bit);unsigned h=(unsigned)NewHash::Hash()(KeyOf<NewHash>(w));if(h!=empty){++changed;++changedHere;}unsigned delta=h^(unsigned)empty;for(;delta;delta&=delta-1)++flips;}Check("every variable word participates in full-bit mixer",changedHere>=30);}
 printf("VECTOR_HASH_BIT_SAMPLE changed=%u of16384 mean_changed_bits=%.3f (collisions permitted/full equality tested)\n",changed,(double)flips/16384);
}
template<class C>vector<typename C::Key> Pool(unsigned profile,unsigned count){vector<typename C::Key>pool;pool.reserve(count);unsigned danger[]={8,8,8,8,10,10,12,16,20,28},packet[]={19,31,51,99,255,511};for(unsigned n=0;n<count;++n){unsigned length=profile==0?8:profile==1?danger[n%10]:profile==2?packet[n%6]:512;pool.push_back(KeyOf<C>(HashWords(n,length)));}return pool;}
template<class C>double HashTime(const vector<typename C::Key>&pool,unsigned loops){LARGE_INTEGER a,b,f;QueryPerformanceFrequency(&f);unsigned checksum=0;typename C::Hash hash;QueryPerformanceCounter(&a);for(unsigned i=0;i<loops;++i)checksum+=(unsigned)hash(pool[(i*11939u)&(pool.size()-1)]);hashChecksum=checksum;QueryPerformanceCounter(&b);return 1000.0*(b.QuadPart-a.QuadPart)/f.QuadPart;}
template<class C>double CacheTime(unsigned profile,unsigned repeat,unsigned loops,unsigned&evictions){typename C::Scope scope;C::Limits(6000,2*1024*1024);vector<typename C::Key>pool=Pool<C>(profile,16384);for(unsigned i=0;i<6000;++i)C::Store(pool[i],(int)i);LARGE_INTEGER a,b,f;QueryPerformanceFrequency(&f);unsigned checksum=0;QueryPerformanceCounter(&a);for(unsigned i=0;i<loops;++i){unsigned id=i%50==0?6000+(i/50)%10384:(i*11939u)%repeat;int value=0;if(!C::Lookup(pool[id],value)){C::Store(pool[id],(int)id);value=id;}checksum+=value;}QueryPerformanceCounter(&b);hashChecksum=checksum;evictions=C::Evictions();return 1000.0*(b.QuadPart-a.QuadPart)/f.QuadPart;}
static void TacticalHashBenchmark(){const unsigned hashLoops=1000000,cacheLoops=600000;for(unsigned profile=0;profile<4;++profile){vector<OldHash::Key>old=Pool<OldHash>(profile,16384);vector<NewHash::Key>trial=Pool<NewHash>(profile,16384);for(unsigned pass=0;pass<4;++pass){double a,b;if(pass%2){b=HashTime<NewHash>(trial,hashLoops);a=HashTime<OldHash>(old,hashLoops);}else{a=HashTime<OldHash>(old,hashLoops);b=HashTime<NewHash>(trial,hashLoops);}printf("TACT_HASH profile=%u pass=%u queries=%u old_ms=%.3f new_ms=%.3f ratio=%.3f\n",profile,pass,hashLoops,a,b,a/b);}
  if(profile<3)for(unsigned repeat=512;repeat<=6000;repeat=repeat==512?6000:6001)for(unsigned pass=0;pass<4;++pass){double a,b;unsigned ae,be;if(pass%2){b=CacheTime<NewHash>(profile,repeat,cacheLoops,be);a=CacheTime<OldHash>(profile,repeat,cacheLoops,ae);}else{a=CacheTime<OldHash>(profile,repeat,cacheLoops,ae);b=CacheTime<NewHash>(profile,repeat,cacheLoops,be);}Check("synthetic full cache same eviction trace",ae==be);printf("TACT_CACHE profile=%u repeat=%u pass=%u queries=%u old_ms=%.3f new_ms=%.3f ratio=%.3f evictions=%u/%u\n",profile,repeat,pass,cacheLoops,a,b,a/b,ae,be);}
 }
}
'''
tests=tests.replace('int main(){',extras+'\nint main(){',1)
anchor=' Check("outer scope releases native packet scratch"';assert tests.count(anchor)==1
tests=tests.replace(anchor,' TacticalHashDifferential();\n if(!getenv("HASH_NO_BENCHMARK"))TacticalHashBenchmark();\n'+anchor,1)
code=scope['headers']+scope['base']+scope['services']+implementation+tests;(out/'test.cpp').write_text(code,encoding='utf-8')
if '--emit-only' in sys.argv:print('Actual variable-key hash fixture emitted');sys.exit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
if '--no-benchmark' in sys.argv:env['HASH_NO_BENCHMARK']='1'
built=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fe'+str(out/'test.exe')],cwd=out,env=env,capture_output=True,text=True,timeout=90);(out/'compile.log').write_text(built.stdout+built.stderr)
if built.returncode:print(built.stdout+built.stderr);sys.exit(built.returncode)
run=subprocess.run([str(out/'test.exe')],cwd=out,env=env,capture_output=True,text=True,timeout=60);print(run.stdout+run.stderr,end='')
(out/('production-result.json' if production else 'result.json')).write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,control=proof['control'],source_sha256=proof['source_sha256'],candidate_sha256=proof['candidate_sha256'],fixture_sha256=hashlib.sha256(code.encode()).hexdigest(),production_untouched=True,bound_current_production=production,current_whole_source_sha256=bound_hashes,benchmark_executed='--no-benchmark' not in sys.argv,scope='Actual82 cache/wrapper/key/FIFO/budget/guards math identical with ONLY hash changed, original77 numerical oracle; strict whole Tactical/Unit/Combat/Danger/Plot/Rules82 inputs when production selected. Variable0..512/highbit/forced collision differential plus synthetic hash and same-container owned cache traces. Not native captured-key/end-turn ROI.'),indent=2));sys.exit(run.returncode)
