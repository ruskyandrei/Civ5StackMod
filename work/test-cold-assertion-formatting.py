"""VC9 actual-header cold failure differential; work only, no game calls.

--prepare-only emits reviewed source without compiling. --production requires
all three live files to equal the candidate. Normal mode requires the pinned86
control. A fake dialog/break/trap service records the original inputs; the
actual CvString formatter, CvEnumMap and selected numeric getter bodies run.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/cold-assertion-formatting-regression'
STAGE = ROOT / 'work/cold-assertion-formatting-staged'
OUT.mkdir(exist_ok=True)
manifest = json.loads((STAGE / 'manifest.json').read_text())
production = '--production' in sys.argv
spec = importlib.util.spec_from_file_location('cold_stage', ROOT / 'work/stage-cold-assertion-formatting.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
old = {name: stage.read_control(name) for name in stage.FILES}
new = {name: (STAGE / name).read_text(encoding='utf-8-sig') for name in stage.FILES}
assert stage.transform(old) == new
for name in old:
    assert stage.sha(old[name]) == manifest['original_sha256'][name]
    assert stage.sha(new[name]) == manifest['candidate_sha256'][name]
    assert (ROOT / name).read_text(encoding='utf-8-sig') == (new[name] if production else old[name]), 'Current whole source drift: ' + name


def pinned(name):
    return subprocess.check_output(['git', 'show', manifest['control'] + ':' + name], cwd=ROOT).decode('utf-8-sig').replace('\r\n', '\n')


def function(source, signature):
    start = source.index(signature)
    begin = source.index('{', start)
    depth = 0
    for end in range(begin, len(source)):
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
            if not depth:
                return source[start:end+1], source[:start].count('\n')+1
    raise AssertionError('Unclosed actual function ' + signature)


enum_header = pinned('CvGameCoreDLL_Expansion2/CvEnumMap.h')
string_header = pinned('CvGameCoreDLLUtil/include/CvString.h')
unit_source = pinned('CvGameCoreDLL_Expansion2/CvUnit.cpp')
player_source = pinned('CvGameCoreDLL_Expansion2/CvPlayerAI.cpp')
bindings = {name: stage.sha(pinned(name)) for name in (
    'CvGameCoreDLL_Expansion2/CvEnumMap.h', 'CvGameCoreDLLUtil/include/CvString.h',
    'CvGameCoreDLL_Expansion2/CvUnit.cpp', 'CvGameCoreDLL_Expansion2/CvPlayerAI.cpp')}
for include in ('#include "CvAssert.h"', '#include "CvAlignedStorage.h"', '#include "CvEnumsUtil.h"'):
    assert enum_header.count(include) == 1
    enum_header = enum_header.replace(include, '// Explicit fixed-enum service, checked macros provided above', 1)
assert string_header.count('#include "CvAssert.h"') == 1
string_header = string_header.replace('#include "CvAssert.h"', '// Actual checked macros provided above', 1)

SERVICES = r'''
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include <sstream>
#include <algorithm>
#include <iterator>
#include <cstdarg>
#include <cstddef>
#include <new>
using namespace std;
struct Trap {};
static unsigned checks=0,failures=0,exprCalls=0,argCalls=0,formats=0;
static int handlerMode=0;
static vector<string> events;
static void Check(const char*label,bool ok){++checks;if(!ok){++failures;fprintf(stderr,"FAIL %s\n",label);}}
static string Inputs(const char*kind,const char*expr,const char*file,unsigned line,const char*message){ostringstream out;out<<kind<<'|'<<expr<<'|'<<file<<'|'<<line<<'|'<<message;return out.str();}
static void FixtureBreak(){events.push_back("BREAK");}
static __declspec(noreturn) void FixtureTrap(){events.push_back("TRAP");throw Trap();}
static int FixtureVsnprintf(char*buffer,size_t length,const char*format,va_list args){++formats;return _vsnprintf(buffer,length,format,args);}
bool CvAssertDlg(const char*expr,const char*file,unsigned line,bool&ignore,const char*message){events.push_back(Inputs("ASSERT",expr,file,line,message));if(handlerMode==1)ignore=true;return handlerMode==2;}
void CvPreconditionDlg(const char*expr,const char*file,unsigned line,const char*message){events.push_back(Inputs("PRECONDITION",expr,file,line,message));}
static bool Expr(bool result){++exprCalls;return result;}
static int Arg(int value){++argCalls;return value;}
static const char* Fmt(){++argCalls;return "number=%d float=%.3f text=%s";}
enum PlayerTypes{NO_PLAYER=-1,PLAYER_0=0,PLAYER_1=1,BARBARIAN_PLAYER=3};
const int MAX_PLAYERS=4;
enum DomainTypes{DOMAIN_LAND=0,DOMAIN_SEA=1,DOMAIN_AIR=2};
template<class T>struct CvAlignedStorage{typedef T Type;};
namespace CvEnumsUtil{template<class E>struct Traits{enum{IsFixed=true,CountConstant=4};};template<class E>size_t Count(){return Traits<E>::CountConstant;}}
#define FNEW(value,...) new value
#define SAFE_DELETE_ARRAY(value) do{delete [] value;value=NULL;}while(0)
const int c_eCiv5GameplayDLL=0;
'''

MODELS = r'''
struct CvPlayerAI{int id;CvPlayerAI():id(0){}static CvPlayerAI&getPlayer(PlayerTypes player);};
static CvEnumMap<PlayerTypes,CvPlayerAI> s_players;
struct Entry{DomainTypes domain;Entry():domain(DOMAIN_LAND){}DomainTypes GetDomainType()const{return domain;}};
struct CvPlot{int id;CvPlot():id(0){}};
struct FixtureMap{CvPlot value;CvPlot*plotCheckInvalid(int x,int y){return x>=0&&y>=0?&value:NULL;}};
struct FixtureGC{FixtureMap map;FixtureMap&getMap(){return map;}}GC;
struct CvUnit{Entry entry;Entry*m_pUnitInfo;int base,modifier,change,m_iDamage,x,y;
 CvUnit():m_pUnitInfo(&entry),base(100),modifier(0),change(0),m_iDamage(0),x(0),y(0){}
 int getMaxHitPointsBase()const{return base;}int getMaxHitPointsModifier()const{return modifier;}int getMaxHitPointsChange()const{return change;}
 int getX()const{return x;}int getY()const{return y;}
 DomainTypes getDomainType()const;int GetMaxHitPoints()const;int GetCurrHitPoints()const;int getDamage()const;CvPlot*plot()const;
};
'''

TESTS = r'''
// Deliberately keep one ASSERT site for the static-ignore lifecycle test.
#line 501 "fixture-callsite.cpp"
static void IgnoreSite(){ASSERT(Expr(false),"ignored=%d",Arg(44));}
#line 601 "fixture-callsite.cpp"
static void AssertPass(){ASSERT(Expr(true),Fmt(),Arg(6),1.25,"untouched");}
#line 611 "fixture-callsite.cpp"
static void AssertFail(){ASSERT(Expr(false),Fmt(),Arg(-17),1.25,"exact");}
#line 621 "fixture-callsite.cpp"
static void AssertEmpty(){ASSERT(Expr(false));}
#line 631 "fixture-callsite.cpp"
static void DebugSite(){ASSERT_DEBUG(Expr(false),"debug=%d",Arg(71));}
#line 641 "fixture-callsite.cpp"
static void PrePass(){PRECONDITION(Expr(true),"fatal=%d",Arg(0));}
#line 651 "fixture-callsite.cpp"
static void PreFail(){PRECONDITION(Expr(false),"fatal=%d",Arg(-123));}
#line 661 "fixture-callsite.cpp"
static void PreEmpty(){PRECONDITION(Expr(false));}
#line 671 "fixture-callsite.cpp"
static void NestedFormat(){ASSERT(Expr(false),"nested=%d",Arg(Arg(77)));}
#line 681 "fixture-callsite.cpp"
static void LongFormat(const char*text){ASSERT(Expr(false),"%s/%d",text,Arg(19));}
#line 691 "fixture-callsite.cpp"
static void DoubleSite(){ASSERT(Expr(false),"first");ASSERT(Expr(false),"second");}
#line 1000 "fixture-control.cpp"
__declspec(noinline) int ReadMap(PlayerTypes player){return CvPlayerAI::getPlayer(player).id;}
__declspec(noinline) int ReadUnit(const CvUnit*unit){return unit->getDamage()+unit->GetMaxHitPoints()+(int)unit->getDomainType();}
int main(){
 unsigned beforeExpr=exprCalls,beforeArg=argCalls;AssertPass();
#ifdef CVASSERT_ENABLE
 Check("successful assert expression exactly once",exprCalls==beforeExpr+1);
#else
 Check("disabled assert expression not evaluated",exprCalls==beforeExpr);
#endif
 Check("successful assert formatting arguments skipped",argCalls==beforeArg);
 handlerMode=0;AssertFail();AssertEmpty();NestedFormat();DoubleSite();
 string longText(9000,'x');LongFormat(longText.c_str());
 handlerMode=2;AssertFail();handlerMode=1;beforeExpr=exprCalls;beforeArg=argCalls;IgnoreSite();IgnoreSite();
#ifdef CVASSERT_ENABLE
 Check("same site ignore skips expression and arguments",exprCalls==beforeExpr+1&&argCalls==beforeArg+1);
#else
 Check("inactive ignore sites skip all evaluation",exprCalls==beforeExpr&&argCalls==beforeArg);
#endif
 handlerMode=0;beforeExpr=exprCalls;beforeArg=argCalls;DebugSite();
#if defined(CVASSERT_ENABLE)&&defined(_DEBUG)
 Check("debug site active",exprCalls==beforeExpr+1&&argCalls==beforeArg+1);
#else
 Check("debug site inactive",exprCalls==beforeExpr&&argCalls==beforeArg);
#endif
 beforeExpr=exprCalls;beforeArg=argCalls;PrePass();Check("precondition success remains checked",exprCalls==beforeExpr+1&&argCalls==beforeArg);
 unsigned traps=0;try{PreFail();}catch(const Trap&){++traps;}try{PreEmpty();}catch(const Trap&){++traps;}
 Check("preconditions trap in every configuration",traps==2);
 s_players.init();for(int i=0;i<MAX_PLAYERS;++i)s_players[i].id=i*7;
 CvUnit unit;
 for(int i=0;i<12000;++i){unit.base=80+i%141;unit.modifier=i%80-20;unit.change=i%25;unit.m_iDamage=i%60;unit.entry.domain=(DomainTypes)(i%3);Check("full actual unit getter result",ReadUnit(&unit)==unit.m_iDamage+unit.base*(100+unit.modifier)/100+unit.change+(i%3));Check("actual current HP math",unit.GetCurrHitPoints()==unit.GetMaxHitPoints()-unit.m_iDamage);Check("actual plot getter pointer",unit.plot()==&GC.map.value);Check("checked player/map result",ReadMap((PlayerTypes)(i%4))==(i%4)*7);}
 try{CvPlayerAI::getPlayer(NO_PLAYER);Check("invalid player cannot return",false);}catch(const Trap&){++traps;}
 try{CvPlayerAI::getPlayer((PlayerTypes)MAX_PLAYERS);Check("upper invalid player cannot return",false);}catch(const Trap&){++traps;}
 Check("player precondition checks retained",traps==4);
 s_players.uninit();
#ifdef CVASSERT_ENABLE
 CvEnumMap<PlayerTypes,int> neverInitialized;handlerMode=1;neverInitialized.data();handlerMode=0;
#endif
 for(size_t i=0;i<events.size();++i)printf("EVENT %s\n",events[i].c_str());
 printf("RESULT checks=%u failures=%u expr=%u args=%u formats=%u events=%u traps=%u\n",checks,failures,exprCalls,argCalls,formats,(unsigned)events.size(),traps);
 return failures?1:0;
}
'''

units = []
for signature in ('DomainTypes CvUnit::getDomainType()', 'int CvUnit::GetMaxHitPoints()',
                  'int CvUnit::GetCurrHitPoints()', 'int CvUnit::getDamage()', 'CvPlot* CvUnit::plot()'):
    body, line = function(unit_source, signature)
    units.append('#line %d "CvUnit.cpp"\n%s\n' % (line, body))
player, player_line = function(player_source, 'CvPlayerAI& CvPlayerAI::getPlayer(')
sources = {}
for label, files in (('old', old), ('new', new)):
    pre = next(line for line in files[stage.FILES[1]].splitlines() if line.startswith('#define PRECONDITION('))
    helpers = stage.HELPERS if label == 'new' else ''
    header = files[stage.FILES[0]]
    code = SERVICES + '\n' + pre + '\n#line 1 "CvAssert.h"\n' + header
    code += '\n#undef CVASSERT_BREAKPOINT\n#define CVASSERT_BREAKPOINT FixtureBreak()\n#define BUILTIN_TRAP() FixtureTrap()\n'
    code += '\n#define _vsnprintf FixtureVsnprintf\n#line 1 "CvString.h"\n' + string_header + '\n#undef _vsnprintf\n'
    code += '\n#line 1 "CvEnumMap.h"\n' + enum_header + '\n' + MODELS
    code += '\n' + helpers + '\n' + '\n'.join(units) + '\n#line %d "CvPlayerAI.cpp"\n%s\n' % (player_line, player)
    code += '\n' + TESTS
    path = OUT / (label + '.cpp')
    path.write_text(code, encoding='utf-8')
    sources[label] = hashlib.sha256(code.encode()).hexdigest()
(OUT / 'source-proof.json').write_text(json.dumps(dict(control=manifest['control'], sources=sources,
    whole_original_sha256=manifest['original_sha256'], whole_candidate_sha256=manifest['candidate_sha256'],
    actual_auxiliary_sha256=bindings, current_production_candidate=production,
    actual_getter_bodies=True, actual_enummap_header=True, actual_string_formatting=True,
    explicit_fake_handler=True, no_core_writes=True), indent=2) + '\n')
if '--prepare-only' in sys.argv:
    print('Actual cold-failure sources emitted; no compilation or tests.')
    raise SystemExit(0)

vc = ROOT / 'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
sdk = ROOT / 'work/toolchain/sdk/windows'
env = os.environ.copy()
env['PATH'] = str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','')
env['INCLUDE'] = str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include')
env['LIB'] = str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL', '_CL_', 'LINK'):
    env.pop(key, None)
modes = dict(release=['FINAL_RELEASE','NDEBUG','VPRELEASE_ERRORMSG'],
             debug=['_DEBUG'], disabled=['FINAL_RELEASE','NDEBUG','DISABLE_CVASSERT'],
             quiet=['FINAL_RELEASE','NDEBUG'])
results = {}
for mode, defines in modes.items():
    mode_dir = OUT / mode
    mode_dir.mkdir(exist_ok=True)
    outputs = []
    for label in ('old', 'new'):
        command = [str(vc/'Vc7/bin/cl.exe'), '/nologo','/EHsc', '/MTd' if mode == 'debug' else '/MT','/O2','/GS','/FAc',
                   '/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0'] + ['/D'+d for d in defines]
        command += [str(OUT/(label+'.cpp')), '/Fa'+str(mode_dir/(label+'.cod')), '/Fo'+str(mode_dir/(label+'.obj')), '/Fe'+str(mode_dir/(label+'.exe'))]
        built = subprocess.run(command, cwd=mode_dir, env=env, capture_output=True, text=True, timeout=75)
        (mode_dir/(label+'-compile.log')).write_text(built.stdout+built.stderr)
        if built.returncode:
            print(built.stdout+built.stderr)
            raise SystemExit(built.returncode)
        run = subprocess.run([str(mode_dir/(label+'.exe'))],cwd=mode_dir,capture_output=True,text=True,timeout=25)
        (mode_dir/(label+'-result.txt')).write_text(run.stdout+run.stderr)
        assert run.returncode == 0, (mode, label, run.stdout, run.stderr)
        outputs.append(run.stdout)
    assert outputs[0] == outputs[1], 'Actual failure metadata/evaluation/result differential: ' + mode
    result = re.search(r'RESULT checks=(\d+) failures=(\d+) expr=(\d+) args=(\d+) formats=(\d+) events=(\d+) traps=(\d+)',outputs[0])
    assert result
    results[mode] = dict(zip(('checks','failures','expr','args','formats','events','traps'),map(int,result.groups())))

report = dict(control=manifest['control'], results=results, total_checks=sum(r['checks'] for r in results.values()),
              sources=sources, bound_current_production=production,
              actual_getter_bodies=True, actual_formatter=True, disabled_debug_modes=True,
              global_GS_enabled=True, disassembly_pending=True,
              limitations='Deterministic actual-source tests use explicit fixed count/player/unit services and fake dialog/break/trap handlers. No game timing claim; compiler assembly must be reviewed separately. No original assertion/check/GS removal.')
(OUT / ('production-result.json' if production else 'result.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
