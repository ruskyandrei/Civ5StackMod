"""Stage or bind current production indexed mirrors for24 hot XML settings.

The original string GetInt body stays byte-identical. Actual native VC9 loader,
reset and typed lookup compile with deterministic database/reentrant services.
--production --no-benchmark strictly binds current files to the mirror-only
delta from67 before compiling current bodies; it does not rerun timing.
Optional stage timing lives in a separate translation unit, no LTCG/inlining.
"""
from pathlib import Path
import ast, difflib, hashlib, json, os, re, subprocess, sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2'
production='--production' in sys.argv;no_benchmark='--no-benchmark' in sys.argv
control='8aac77ca7'
out=root/('work/hot-stacking-settings-production-regression' if production else 'work/hot-stacking-settings-regression');out.mkdir(exist_ok=True)
stage=root/'work/hot-stacking-settings-candidate';stage.mkdir(exist_ok=True)
names=['DefenderSelectionEnabled','FlankingEnabled','CollateralEnabled','DisableCityRangedAttacks','AIEnabled',
       'BaseCapacity','MaximumCapacity','LandCapacityBonus','SeaCapacityBonus','CityCapacityBonus','MinorCapacityBonus','BarbarianCapacityBonus',
       'CollateralPercent','CollateralHPFloorPercent','CollateralMinimumDamage','CityProtectionMaximumPercent','CityProtectionScalesWithHP',
       'AIStackCollateralWeight','AIStackProtectionWeight','AIStackJoinBonus','AIStackAntiFlankBonus','AIStackConcentrationFreeUnits','AIStackConcentrationPenalty','AIStackLeaveProtectorPenalty']
files=['CvStackingRules.h','CvStackingRules.cpp','CvUnitCombat.cpp','CvTacticalAI.cpp']
current={name:(core/name).read_text(encoding='utf-8-sig') for name in files}
original={name:subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/'+name],cwd=root).decode('utf-8-sig').replace('\r\n','\n') for name in files}
candidate=dict(original)
enum='\tenum HotSettingKey\n\t{\n'+''.join('\t\tHOT_'+name+',\n' for name in names)+'\t\tHOT_SETTING_COUNT\n\t};\n\tint GetIntByKey(HotSettingKey eKey, int iFallback);\n'
candidate['CvStackingRules.h']=candidate['CvStackingRules.h'].replace('\tint GetInt(const char* szName, int iFallback);', '\tint GetInt(const char* szName, int iFallback);\n'+enum,1)
table='\tconst char* const HOT_SETTING_NAMES[CvStacking::HOT_SETTING_COUNT] =\n\t{\n'+''.join('\t\t"'+name+'",\n' for name in names)+'\t};\n'
rules=candidate['CvStackingRules.cpp'];anchor='\t// Names stored here are process-lifetime literals'
rules=rules.replace(anchor,table+anchor,1)
rules=rules.replace('\t\tbool enabled;','\t\tbool enabled;\n\t\tbool hotReady;\n\t\tint hotValues[CvStacking::HOT_SETTING_COUNT];\n\t\tbool hotPresent[CvStacking::HOT_SETTING_COUNT];',1)
rules=rules.replace('\t\tRulesCache() : loaded(false), enabled(false) {}','''\t\tRulesCache() : loaded(false), enabled(false), hotReady(false)
\t\t{
\t\t\tfor (size_t i = 0; i < CvStacking::HOT_SETTING_COUNT; ++i)
\t\t\t{ hotValues[i] = 0; hotPresent[i] = false; }
\t\t}''',1)
finalize='''\tvoid FinalizeHotSettings(RulesCache& cache)
\t{
\t\tfor (size_t i = 0; i < CvStacking::HOT_SETTING_COUNT; ++i)
\t\t{
\t\t\tSettingMap::const_iterator found = cache.settings.find(HOT_SETTING_NAMES[i]);
\t\t\tcache.hotPresent[i] = found != cache.settings.end();
\t\t\tcache.hotValues[i] = cache.hotPresent[i] ? found->second : 0;
\t\t}
\t\t// Reentrant loader queries keep the original string lookup until here.
\t\tcache.hotReady = cache.loaded;
\t}
'''
rules=rules.replace('\tint Clamp(int value,',finalize+'\tint Clamp(int value,',1)
rules=rules.replace('\t\t\tcache.enabled = false;\n\t\t\treturn;', '\t\t\tcache.enabled = false;\n\t\t\tFinalizeHotSettings(cache);\n\t\t\treturn;',1)
log='\t\tCUSTOMLOG("Stacking: loaded XML configuration, enabled=%d, base=%d, maximum=%d, technology rows=%d.", cache.settings["Enabled"], cache.settings["BaseCapacity"], cache.settings["MaximumCapacity"], (int)cache.technologies.size());'
assert rules.count(log)==1
rules=rules.replace(log,log+'\n\t\tFinalizeHotSettings(cache);',1)
typed='''\tint GetIntByKey(HotSettingKey key, int fallback)
\t{
\t\tif (key < 0 || key >= HOT_SETTING_COUNT)
\t\t\treturn GetInt(NULL, fallback);
\t\tconst RulesCache& cache = Cache();
\t\tif (!cache.hotReady)
\t\t\treturn GetInt(HOT_SETTING_NAMES[key], fallback);
\t\treturn cache.hotPresent[key] ? cache.hotValues[key] : fallback;
\t}
'''
rules=rules.replace('\tbool IsEnabled()\n',typed+'\tbool IsEnabled()\n',1)
# Replace only the proven hot public settings and literal fallback expressions.
call_pattern=re.compile(r'(?P<prefix>CvStacking::)?GetInt\("(?P<name>'+ '|'.join(names) +r')",\s*(?P<fallback>-?\d+)\)')
substitutions={}
for file in ['CvStackingRules.cpp','CvUnitCombat.cpp','CvTacticalAI.cpp']:
    source=rules if file=='CvStackingRules.cpp' else candidate[file]
    substitutions[file]=[]
    def replace(match):
        name=match.group('name');prefix=match.group('prefix') or ''
        substitutions[file].append(dict(name=name,fallback=int(match.group('fallback')),original=match.group(0)))
        return prefix+'GetIntByKey('+prefix+'HOT_'+name+', '+match.group('fallback')+')'
    source=call_pattern.sub(replace,source)
    if file=='CvStackingRules.cpp':
        old='GetInt(domain == DOMAIN_LAND ? "LandCapacityBonus" : "SeaCapacityBonus", 0)'
        assert source.count(old)==1
        source=source.replace(old,'GetIntByKey(domain == DOMAIN_LAND ? HOT_LandCapacityBonus : HOT_SeaCapacityBonus, 0)',1)
        substitutions[file].append(dict(name='domain Land/SeaCapacityBonus',fallback=0,original=old))
    candidate[file]=source

def function(text,signature):
    a=text.index(signature);b=text.index('{',a)+1;depth=1
    while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
    return text[a:b]
assert function(candidate['CvStackingRules.cpp'],'int GetInt(')==function(original['CvStackingRules.cpp'],'int GetInt(')
if production:
    for name in files:
        assert current[name]==candidate[name], 'Current production exceeds reviewed typed-mirror-only delta: '+name
    candidate=current
    h=current['CvStackingRules.h'];start=h.index('\tenum HotSettingKey\n')
    enum=h[start:h.index('\n\tint GetCapacity(',start)]
for name,source in candidate.items():(stage/name).write_text(source,encoding='utf-8')
patch=''.join(''.join(difflib.unified_diff(original[name].splitlines(True),candidate[name].splitlines(True),fromfile='a/CvGameCoreDLL_Expansion2/'+name,tofile='b/CvGameCoreDLL_Expansion2/'+name)) for name in files)
(stage/'hot-settings.patch').write_text(patch,encoding='utf-8')
(stage/'manifest.json').write_text(json.dumps(dict(scope='production binding' if production else 'staged only; no production writes',control=control,keys=names,substitutions=substitutions,original_sha256={name:hashlib.sha256(source.encode()).hexdigest() for name,source in original.items()},string_getter_byte_identical=True),indent=2))
if '--stage-only' in sys.argv:print('Staged24-key patch; production untouched');sys.exit(0)

values={}
for n in ast.parse((root/'work/test-stacking-setting-lookup.py').read_text()).body:
    if isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str):
        for target in n.targets:
            if isinstance(target,ast.Name):values[target.id]=n.value.value
prefix,tests=values['prefix'],values['tests']
prefix=prefix.replace('static void probe(){','namespace CvStacking{'+enum+'}\nstatic void probe(){',1)
source=candidate['CvStackingRules.cpp']
implementation=source[source.index('namespace\n{'):source.index('\tbool Lookup(')]+'}\nnamespace CvStacking{\n'
implementation+='\n'.join(function(source,s) for s in ['void ResetCache()','int GetInt(','int GetIntByKey(','bool IsEnabled()'])+'\n'
implementation+=function(original['CvStackingRules.cpp'],'int GetInt(').replace('GetInt(', 'OriginalGetInt(',1)+'\n'
implementation+=function(subprocess.check_output(['git','show','6c863259f:CvGameCoreDLL_Expansion2/CvStackingRules.cpp'],cwd=root).decode('utf-8-sig'),'bool IsEnabled()').replace('IsEnabled','OriginalEnabled')+'\n}\n'
benchmark_implementation=implementation
implementation=implementation.replace('return strcmp(left, right) < 0;','++settingComparisons;return strcmp(left, right) < 0;')
tests=tests[:tests.index(' // A reference string-keyed map')]
# Extend all existing default, min, max, reset and failure checks with typed keys.
body='''
 for(int k=0;k<CvStacking::HOT_SETTING_COUNT;++k){
  int fallback=-917;expect("typed loaded/missing result equals original getter",CvStacking::GetIntByKey((CvStacking::HotSettingKey)k,fallback)==CvStacking::OriginalGetInt(HOT_SETTING_NAMES[k],fallback));
 }
'''
check=function(tests,'void checkAllValues(')
tests=tests.replace(check,check[:-1]+body+'}',1)
probe=function(tests,'static void probeEnabled()')
tests=tests.replace(probe,probe[:-1]+'''for(int k=0;k<CvStacking::HOT_SETTING_COUNT;++k){++probeChecks;if(CvStacking::GetIntByKey((CvStacking::HotSettingKey)k,-419)!=CvStacking::OriginalGetInt(HOT_SETTING_NAMES[k],-419))++probeFailures;}'''+ '}',1)
tests=tests.replace(' expect("null name gives its fallback",', ' expect("typed noDB equals fallback and retryable",CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled,-233)==-233&&!Cache().loaded&&!Cache().hotReady);\n expect("invalid typed key cold fallback",CvStacking::GetIntByKey((CvStacking::HotSettingKey)-1,131)==131&&!Cache().hotReady);\n expect("null name gives its fallback",',1)
tests+=r'''
 expect("all completed normal loads finalize mirror",Cache().hotReady&&Cache().loaded);
 for(int i=0;i<CvStacking::HOT_SETTING_COUNT;++i){char name[128];strcpy_s(name,sizeof(name),HOT_SETTING_NAMES[i]);expect("content-alias lookup unchanged",CvStacking::GetInt(name,-3)==CvStacking::GetIntByKey((CvStacking::HotSettingKey)i,-3));}
 expect("invalid typed index upper bound fallback",CvStacking::GetIntByKey(CvStacking::HOT_SETTING_COUNT,77)==77);
 expect("invalid typed index extreme fallback",CvStacking::GetIntByKey((CvStacking::HotSettingKey)INT_MAX,78)==78);
 CvStacking::ResetCache();expect("reset clears ready/presence/value arrays",!Cache().hotReady&&!Cache().loaded);for(int i=0;i<CvStacking::HOT_SETTING_COUNT;++i)expect("reset clears each POD cell",!Cache().hotPresent[i]&&Cache().hotValues[i]==0);
 db.schema=false;expect("missing schema typed respects caller fallback",CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled,43)==43&&Cache().hotReady);
 expect("typed fallbacks remain caller-specific",CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled,44)==44);db.schema=true;expect("late schema remains absent until reset",CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled,45)==45);
 CvStacking::ResetCache();db.settings.clear();db.settings.push_back(Database::Row("DefenderSelectionEnabled",0));expect("fresh load typed XML override",CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled,9)==0);db.settings[0].name.assign(256,'?');db.settings.clear();expect("typed mirror owns no DB row pointer",CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled,9)==0);
 CvStacking::ResetCache();checkAllValues(0);
 settingComparisons=0;for(int i=0;i<100000;++i)CvStacking::OriginalGetInt("DefenderSelectionEnabled",-1);unsigned long treeComparisons=settingComparisons;
 settingComparisons=0;for(int i=0;i<100000;++i)CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled,-1);expect("warm indexed values eliminate name comparisons",treeComparisons>100000&&settingComparisons==0);
 expect("reentrant typed getters follow original partial load",probeChecks>1000&&probeFailures==0);
 printf("hot-setting actual source: %d checks,%d failures;24keys original100kcalls%lu comparisons vs0 indexed;reentrant%lu probes,%lu failures; POD mirror%u bytes\n",checks,failures,treeComparisons,probeChecks,probeFailures,(unsigned)(sizeof(Cache().hotValues)+sizeof(Cache().hotPresent)+sizeof(Cache().hotReady)));
 RunBenchmark();return failures?1:0;}
'''
bench=r'''
#include <windows.h>
#include <cstdio>
namespace Bench{namespace CvStacking{ENUM int GetInt(const char*,int);}void Initialize();}
static volatile unsigned long checksum=0;
void RunBenchmark(){
 Bench::Initialize();LARGE_INTEGER frequency,begin,end;QueryPerformanceFrequency(&frequency);
 const int calls=4000000;const char*names[]={"DefenderSelectionEnabled","AIEnabled","AIStackProtectionWeight","AIStackConcentrationPenalty"};
 const Bench::CvStacking::HotSettingKey keys[]={Bench::CvStacking::HOT_DefenderSelectionEnabled,Bench::CvStacking::HOT_AIEnabled,Bench::CvStacking::HOT_AIStackProtectionWeight,Bench::CvStacking::HOT_AIStackConcentrationPenalty};
 for(int round=0;round<3;++round){double tree,index;unsigned long a=0,b=0;
  if(round%2==0){QueryPerformanceCounter(&begin);for(int i=0;i<calls;++i)a+=Bench::CvStacking::GetInt(names[i&3],-1);QueryPerformanceCounter(&end);tree=(end.QuadPart-begin.QuadPart)*1000.0/frequency.QuadPart;QueryPerformanceCounter(&begin);for(int i=0;i<calls;++i)b+=Bench::CvStacking::GetIntByKey(keys[i&3],-1);QueryPerformanceCounter(&end);index=(end.QuadPart-begin.QuadPart)*1000.0/frequency.QuadPart;}
  else{QueryPerformanceCounter(&begin);for(int i=0;i<calls;++i)b+=Bench::CvStacking::GetIntByKey(keys[i&3],-1);QueryPerformanceCounter(&end);index=(end.QuadPart-begin.QuadPart)*1000.0/frequency.QuadPart;QueryPerformanceCounter(&begin);for(int i=0;i<calls;++i)a+=Bench::CvStacking::GetInt(names[i&3],-1);QueryPerformanceCounter(&end);tree=(end.QuadPart-begin.QuadPart)*1000.0/frequency.QuadPart;}
  checksum+=a+b;printf("hot-setting separateTU timing round%d calls%d tree_ms%.3f indexed_ms%.3f result_equal%d\n",round,calls,tree,index,a==b?1:0);
 }
}
'''.replace('ENUM',enum)
benchmark_declaration='\nvoid RunBenchmark(){printf("Timing benchmark deliberately omitted in production binding\\n");}\n' if no_benchmark else '\nvoid RunBenchmark();\n'
(out/'test.cpp').write_text(prefix+implementation+benchmark_declaration+tests,encoding='utf-8')
(out/'benchmark.cpp').write_text(bench,encoding='utf-8')
# Timed lookup bodies stay uninstrumented and in a third translation unit.
# Include directives stay outside the private module namespace; global new is
# supplied by the test TU and its allocation counter is disabled during timing.
bench_headers,bench_prefix=prefix.split('using namespace std;',1)
bench_prefix=re.sub(r'^void\* operator new(?:\[\])?\(.*$', '',bench_prefix,flags=re.M)
bench_prefix=re.sub(r'^void operator delete(?:\[\])?\(.*$', '',bench_prefix,flags=re.M)
bench_module=bench_headers+'\nnamespace Bench{\nusing namespace std;'+bench_prefix+benchmark_implementation+'\nvoid Initialize(){static Database::Connection db;GC.database=&db;CvStacking::GetInt("BaseCapacity",-1);}\n}\n'
(out/'benchmark-module.cpp').write_text(bench_module,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
compile_sources=[str(out/'test.cpp')] if no_benchmark else [str(out/'test.cpp'),str(out/'benchmark.cpp'),str(out/'benchmark-module.cpp')]
exe=out/'test.exe';compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0']+compile_sources+['/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr)
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(run.stdout+run.stderr,end='')
timings=[dict(round=int(a),calls=int(b),tree_ms=float(c),indexed_ms=float(d),result_equal=int(e)) for a,b,c,d,e in re.findall(r'timing round(\d+) calls(\d+) tree_ms([\d.]+) indexed_ms([\d.]+) result_equal(\d+)',run.stdout)]
(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,timings=timings,production_files_read_only=True,bound_current_production=production,control=control,only_reviewed_mirror_delta=True,string_GetInt_byte_identical=True,timing_omitted=no_benchmark,production_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in current.items()} if production else {},fixture_sha256=hashlib.sha256((prefix+implementation+tests+('' if no_benchmark else bench)).encode()).hexdigest(),scope='Actual current production loader/defaults/clamps/reset/reentrant partial loading against unchanged original string getter; strict67 mirror-only delta binding. Deterministic database services. Timing omitted in production binding; historical separate-TU results synthetic, no native end-turn speed claim.' if production else 'Actual staged loader/defaults/clamps/reset/reentrant partial loading vs original string getter on identical cache. GenuineVC9 separate-TU warm-call microbenchmark; no native end-turn speed claim.'),indent=2))
sys.exit(run.returncode)
