"""Small actual-source VC9 gate for the packet source owner's enum conversion.

The broad mathematical fixture deliberately substitutes engine service types.
This separate check uses the actual PlayerTypes enum and getPlayer declaration;
its pre-fix control must be rejected by the same native compiler.
"""
from pathlib import Path
import hashlib, json, os, re, subprocess, sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2'
out=root/'work/shared-packet-type-regression';out.mkdir(exist_ok=True)
def function(s,signature):
 a=s.index(signature);b=s.index('{',a)+1;depth=1
 while depth:depth+=(s[b]=='{')-(s[b]=='}');b+=1
 return s[a:b]
tact=(core/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
body=function(tact,'static bool StackPacketSourcesHaveNoLoadingCallback(')
enums=(root/'CvGameCoreDLLUtil/include/CvEnums.h').read_text(encoding='utf-8-sig')
player=function(enums,'enum OPEN_ENUM PlayerTypes')+';'
signature=re.search(r'static CvPlayerAI& getPlayer\(PlayerTypes ePlayer\);',(core/'CvPlayerAI.h').read_text(encoding='utf-8-sig')).group(0)
cast='(PlayerTypes)source[5+2*i]';assert body.count(cast)==1,'Revisit gate after owner reader changes'
prefix='''#include <vector>
#include <cstdio>
using namespace std;
#define OPEN_ENUM
'''+player+'''
enum DomainTypes{DOMAIN_LAND,DOMAIN_SEA,DOMAIN_AIR};
struct CvUnit{DomainTypes domain;bool ranged;DomainTypes getDomainType()const{return domain;}bool IsCanAttackRanged()const{return ranged;}};
struct CvPlayerAI{'''+signature+'''const CvUnit*getUnit(int)const;};
static CvPlayerAI fixturePlayer;static CvUnit fixtureUnit={DOMAIN_AIR,true};
CvPlayerAI& CvPlayerAI::getPlayer(PlayerTypes){return fixturePlayer;}
const CvUnit*CvPlayerAI::getUnit(int id)const{return id==1?&fixtureUnit:NULL;}
#define GET_PLAYER CvPlayerAI::getPlayer
'''
tests='''
int main(){vector<int>s;s.push_back(1);s.push_back(0);s.push_back(0);s.push_back(0);s.push_back(1);s.push_back(0);s.push_back(1);s.push_back(0);
 unsigned checks=0,failures=0;
 #define CHECK(x) ++checks;if(!(x))++failures
 CHECK(StackPacketSourcesHaveNoLoadingCallback(s));fixtureUnit.ranged=false;CHECK(!StackPacketSourcesHaveNoLoadingCallback(s));
 fixtureUnit.domain=DOMAIN_LAND;CHECK(StackPacketSourcesHaveNoLoadingCallback(s));s[6]=2;CHECK(StackPacketSourcesHaveNoLoadingCallback(s));
 s[4]=-1;CHECK(!StackPacketSourcesHaveNoLoadingCallback(s));s[4]=2;CHECK(!StackPacketSourcesHaveNoLoadingCallback(s));
 s.clear();CHECK(!StackPacketSourcesHaveNoLoadingCallback(s));
 printf("packet native enum gate:%u checks,%u failures\\n",checks,failures);return failures?1:0;}
'''
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','')
env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
flags=['/nologo','/EHsc','/MT','/O2','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0']
def compile_code(name,code):
 path=out/(name+'.cpp');path.write_text(code,encoding='utf-8')
 result=subprocess.run([str(vc/'Vc7/bin/cl.exe')]+flags+[str(path),'/Fe'+str(out/(name+'.exe'))],cwd=out,env=env,capture_output=True,text=True,timeout=20)
 (out/(name+'-compile.log')).write_text(result.stdout+result.stderr,encoding='utf-8');return result
positive=compile_code('native',prefix+body+tests)
if positive.returncode:print(positive.stdout+positive.stderr);sys.exit(positive.returncode)
run=subprocess.run([str(out/'native.exe')],capture_output=True,text=True,timeout=5)
negative=compile_code('pre-fix',prefix+body.replace(cast,'source[5+2*i]',1)+tests)
rejected=negative.returncode!=0 and 'C2664' in negative.stdout+negative.stderr
result=dict(returncode=run.returncode if rejected else 1,output=run.stdout+run.stderr,pre_fix_rejected_C2664=rejected,
 actual_enum_sha256=hashlib.sha256(player.encode()).hexdigest(),actual_getPlayer_declaration=signature,
 actual_helper_sha256=hashlib.sha256(body.encode()).hexdigest(),
 scope='Actual packet raw-source helper, actual PlayerTypes enum and native getPlayer signature under minimal deterministic unit lookup. No full engine/callback/math/ROI claim.')
(out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(run.stdout,end='');print('pre-fix missing owner cast rejected C2664:',rejected)
sys.exit(result['returncode'])
