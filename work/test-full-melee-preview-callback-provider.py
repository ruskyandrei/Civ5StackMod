"""Preserve complete existing full-math oracle with explicit native provider.

The existing generator's pure source preparation is reused; its compiler/main
Python section is never executed. Staged five-file source is strictly bound to
DLL82. Every original numerical/work-count assertion is retained unchanged.
Engine substitutes explicitly register the two live model units; their domain2
is HOVER, with AIR=3 reserved for the independent loading-callback fixture.
"""
from pathlib import Path
import hashlib,importlib.util,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/full-melee-preview-callback-regression';OUT.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('preview_stage',ROOT/'work/stage-preview-callback-capability.py')
stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
old,new=stage.generate()
production='--production' in sys.argv
if production:
    live={name:(ROOT/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8-sig').replace('\r\n','\n') for name in stage.NAMES}
    for name in stage.NAMES:assert live[name]==new[name],'Actual production does not exactly match staged proof: '+name
    new=live
generator=(ROOT/'work/test-full-melee-strength-cache.py').read_text(encoding='utf-8-sig')
prefix=generator[:generator.index("fixture=prefix+enum+")]
prefix=prefix.replace("text=(core/'CvUnit.cpp').read_text(encoding='utf-8-sig')","text=staged['CvUnit.cpp']",1)
prefix=prefix.replace("header=(core/'CvStackingStrengthCache.h').read_text()","header=staged['CvStackingStrengthCache.h']",1)
prefix=prefix.replace("module=(core/'CvStackingStrengthCache.cpp').read_text()","module=staged['CvStackingStrengthCache.cpp']",1)
scope={'__file__':str(ROOT/'work/test-full-melee-strength-cache.py'),'staged':new}
exec(compile(prefix,'full-melee actual-source preparation only','exec'),scope)
cpp_prefix=scope['prefix']
cpp_prefix=cpp_prefix.replace('DOMAIN_LAND=0,DOMAIN_SEA=1,TERRAIN_HILL=2,AE_SAPPER=3;',
    'DOMAIN_LAND=0,DOMAIN_SEA=1,DOMAIN_HOVER=2,DOMAIN_AIR=3,TERRAIN_HILL=2,AE_SAPPER=3,MAX_PLAYERS=4;',1)
cpp_prefix=cpp_prefix.replace('unsigned int fallbackEvents=0,blockadeEvents=0;',
    '''bool MOD_EVENTS_AIRLIFT=false,MOD_EVENTS_SEALIFT=false,MOD_EVENTS_UNIT_RANGEATTACK=false,MOD_EVENTS_CITY_BOMBARD=false,MOD_EVENTS_REBASE=false,MOD_EVENTS_UNIT_ACTIONS=false;
struct PreviewDLL { bool HasGameCoreLock()const{return true;} } previewDLL;PreviewDLL*gDLL=&previewDLL;
unsigned int fallbackEvents=0,blockadeEvents=0;''',1)
cpp_prefix=cpp_prefix.replace('struct CvPlayer{int attackTurns',
    '''struct CvPlayer{vector<const CvUnit*> units;vector<pair<int,int> >interceptors;
 const CvUnit*firstUnit(int*cursor)const{*cursor=0;return units.empty()?NULL:units[0];}
 const CvUnit*nextUnit(int*cursor)const{++*cursor;return (size_t)*cursor<units.size()?units[*cursor]:NULL;}
 const vector<pair<int,int> >&GetPossibleInterceptors()const{return interceptors;}
 const CvUnit*getUnit(int id)const;
 int attackTurns''',1)
unitdecl=scope['unitdecl'].replace(' int getOwner()const{return owner;}',
    ' bool IsDead()const{return damage>=maxHP;}bool isDelayedDeath()const{return false;}bool IsCanAttackRanged()const{return GetBaseRangedCombatStrength()>0;}int GetMoraleBreakChance()const{return 0;}\n int getOwner()const{return owner;}',1)
provider=stage.function(new['CvTacticalAI.cpp'],'static bool StackPreviewCallbackCapabilities(')
provider+='\nconst CvUnit*CvPlayer::getUnit(int id)const{for(size_t i=0;i<units.size();++i)if(units[i]->id==id)return units[i];return NULL;}\nbool ActualProvider(unsigned int& flags,bool scan){return StackPreviewCallbackCapabilities(flags,scan);}\n'
services=scope['services']
services=re.sub(r'CvStackingStrengthCache::Scope (\w+)\(([^,;\n]*)\);',r'CvStackingStrengthCache::Scope \1(\2,ActualProvider);',services)
tests=scope['tests']
tests=tests.replace(' for(int i=0;i<4;++i)players[i]=CvPlayer();',
    ' for(int i=0;i<4;++i)players[i]=CvPlayer();players[a.owner].units.push_back(&a);players[b.owner].units.push_back(&b);',1)
tests=re.sub(r'(?<!::)Scope (\w+)\(([^,;\n]*)\);',r'Scope \1(\2,ActualProvider);',tests)
assert 'Scope scope(16384);' not in tests and 'players[a.owner].units.push_back(&a)' in tests
# Preserve every old assert/expect expression; only explicit provider argument
# and supported physical registry services are added around the same tests.
assert tests.count('expect(')==scope['tests'].count('expect(')
fixture=cpp_prefix+scope['enum']+unitdecl+scope['header'].replace('#pragma once','')+scope['module']+provider+services+'\n'.join(scope['leafmath'])+scope['key']+scope['wrappers']+'\n'.join(scope['bodies']+scope['references'])+tests
(OUT/'test.cpp').write_text(fixture,encoding='utf-8')
if '--emit-only' in sys.argv:print('Whole full-math explicit-provider fixture emitted; no compilation');sys.exit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=OUT/'test.exe';built=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(OUT/'test.cpp'),'/Fe'+str(exe)],cwd=OUT,env=env,capture_output=True,text=True,timeout=45);(OUT/'compile.log').write_text(built.stdout+built.stderr,encoding='utf-8')
if built.returncode:print(built.stdout+built.stderr);sys.exit(built.returncode)
run=subprocess.run([str(exe)],cwd=OUT,capture_output=True,text=True,timeout=20);print(run.stdout+run.stderr,end='');(OUT/'result.json').write_text(json.dumps(dict(control=stage.BASE,math_control=scope['control_commit'],returncode=run.returncode,output=run.stdout+run.stderr,production_untouched=True,bound_current_production=production,source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in new.items()},fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),unchanged_original_assertions=True,scope='Complete actual unchanged DLL47 full attack/defense/wound/embark bodies, current staged keys/wrappers/cache, original numeric/work-count assertions, explicit actual native provider over registered deterministic unit/player/lock services. Separate actual loading callback subgraph fixture covers AIR compatibility edge.'),indent=2),encoding='utf-8');sys.exit(run.returncode)
