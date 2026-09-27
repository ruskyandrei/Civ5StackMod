"""Extract the actual AIR forecast branch into a VC9 engine-stub regression; no DLL/game build."""
from pathlib import Path
import os,subprocess,json,hashlib,sys
root=Path(r'E:\Projects\Civ5StackMod')
work=root/'work'/'air-leaf-regression';work.mkdir(exist_ok=True)
raw=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_bytes()
source=raw.decode('utf-8-sig').replace('\r\n','\n')
f=source.index('int TacticalAIHelpers::GetSimulatedDamageFromAttackOnUnit(')
a=source.index('\t\t\tiAttackerDamage = 0;',f)
b=source.index('\n\t\t}\n\t\telse',a)
actual=source[a:b]
prefix=r'''
#include <algorithm>
#include <cstdio>
using namespace std;
typedef __int64 int64;
enum { DOMAIN_LAND=0,DOMAIN_AIR=1,INTERCEPTION_SAME_STRENGTH_MIN_DAMAGE=2400,INTERCEPTION_SAME_STRENGTH_POSSIBLE_EXTRA_DAMAGE=1200 };
#define GD_INT_GET(x) x
struct CvSeeder {};
struct CvUnit;
struct CvPlot { const CvUnit* interceptor; mutable int lookups; CvPlot():interceptor(NULL),lookups(0){} const CvUnit*GetBestInterceptor(int,const CvUnit*,bool,bool)const{++lookups;return interceptor;} };
static int meanHit=30,mathCalls=0,lastBomberStrength=0,lastInterceptorStrength=0;
struct CvUnit {
 int hp,maxHP,chance,evasion,domain,strength,direct,retaliation,attempts;CvPlot*location;mutable int airCalls,lastSelf,lastOther;
 CvUnit(CvPlot*p):hp(100),maxHP(100),chance(100),evasion(0),domain(DOMAIN_LAND),strength(1000),direct(40),retaliation(10),attempts(0),location(p),airCalls(0),lastSelf(0),lastOther(0){}
 int GetCurrHitPoints()const{return hp;}int GetMaxHitPoints()const{return maxHP;}int getOwner()const{return 0;}int getDomainType()const{return domain;}CvPlot*plot()const{return location;}
 int getInterceptChance()const{return chance;}int evasionProbability()const{return evasion;}int GetInterceptionCombatModifier()const{return 0;}int GetInterceptionDefenseDamageModifier()const{return 0;}
 int GetMaxRangedCombatStrength(const CvUnit*,const void*,bool,const CvPlot*,const CvPlot*,bool,bool,int extra=0,int other=0)const{lastSelf=extra;lastOther=other;return strength-extra;}
 int GetMaxAttackStrength(const CvPlot*,const CvPlot*,const CvUnit*,bool,bool,int extra=0,int other=0)const{lastSelf=extra;lastOther=other;return strength-extra;}
 int GetAirCombatDamage(const CvUnit*,const void*,int,int&,bool,int extra,int other,const CvPlot*,const CvPlot*,bool)const{++airCalls;lastSelf=extra;lastOther=other;return direct;}
 int GetAirStrikeDefenseDamage(const CvUnit*,bool,const CvPlot*)const{return retaliation;}
};
struct CvUnitCombat {static int DoDamageMath(int interceptor,int bomber,int,int,bool,const CvSeeder&,int){++mathCalls;lastBomberStrength=bomber;lastInterceptorStrength=interceptor;return meanHit*100;}};
static int forecast(const CvUnit*pDefender,const CvUnit*pAttacker,const CvPlot*pDefenderPlot,const CvPlot*pAttackerPlot,int&iAttackerDamage,int iExtraSelfDamage=0,int iExtraDefenderDamage=0,bool bQuickAndDirty=false){int iDamage=0,iUnusedReferenceVariable=0;
'''
suffix=r'''
return iDamage;}
static int checks=0,failures=0;
static void expect(const char*name,int actual,int wanted){++checks;if(actual!=wanted){++failures;printf("FAIL %s actual=%d expected=%d\n",name,actual,wanted);}}
struct Fixture {CvPlot p;CvUnit bomber,defender,interceptor;int received;Fixture():bomber(&p),defender(&p),interceptor(&p),received(-99){bomber.domain=DOMAIN_AIR;p.interceptor=&interceptor;meanHit=30;mathCalls=0;lastBomberStrength=lastInterceptorStrength=0;}int run(int self=0,int target=0,bool quick=false){return forecast(&defender,&bomber,&p,&p,received,self,target,quick);}};
int main(){
 {Fixture f;f.p.interceptor=NULL;expect("unopposed direct",f.run(),40);expect("unopposed retaliation",f.received,10);}
 {Fixture f;expect("positive intercept aborts surviving bomber",f.run(),0);expect("abort has interception only",f.received,30);expect("live counters unchanged",f.interceptor.attempts,0);}
 {Fixture f;f.interceptor.chance=50;expect("half direct",f.run(),20);expect("exclusive weighted retaliation",f.received,20);}
 {Fixture f;f.interceptor.chance=250;f.bomber.evasion=50;expect("independent clamp direct",f.run(),20);expect("independent clamp risk",f.received,20);}
 {Fixture f;f.bomber.evasion=150;expect("full evasion",f.run(),40);expect("evasion ground retaliation only",f.received,10);}
 {Fixture f;f.bomber.evasion=-20;expect("negative evasion clamped",f.run(),0);expect("negative evasion incoming",f.received,30);}
 {Fixture f;f.interceptor.chance=-20;expect("negative intercept clamped",f.run(),40);expect("no negative risk",f.received,10);}
 {Fixture f;meanHit=0;expect("zero interception damage does not abort",f.run(),40);expect("zero hit ground retaliation",f.received,10);}
 {Fixture f;expect("quick raw hit",f.run(0,0,true),40);expect("quick raw retaliation",f.received,10);expect("quick no interceptor lookup",f.p.lookups,0);expect("quick no interception math",mathCalls,0);}
 {Fixture f;expect("virtually dead attacker no strike",f.run(100),0);expect("virtually dead attacker no future damage",f.received,0);expect("dead attacker no air leaves",f.bomber.airCalls,0);}
 {Fixture f;f.run(40);expect("assumed bomber HP in interception strength",lastBomberStrength,960);expect("assumed bomber HP in interceptor other damage",f.interceptor.lastOther,40);expect("assumed bomber HP in direct leaf",f.bomber.lastSelf,40);}
 {Fixture f;f.interceptor.domain=DOMAIN_AIR;f.run(25);expect("fighter interception sees virtual attacker damage",f.interceptor.lastOther,25);}
 {Fixture f;f.interceptor.chance=50;f.bomber.direct=1;f.defender.retaliation=0;meanHit=1;expect("small own damage floors",f.run(),0);expect("small incoming damage ceils",f.received,1);}
 {Fixture f;f.interceptor.hp=50;expect("wounded interceptor partial chance",f.run(),20);expect("wounded interceptor weighted risk",f.received,20);}
 {Fixture f;f.p.interceptor=&f.defender;expect("target interceptor virtual HP",f.run(0,50),20);expect("target interceptor virtual strength",lastInterceptorStrength,950);}
 {Fixture f;int dealt=forecast(&f.defender,&f.bomber,NULL,&f.p,f.received);expect("null target plot fallback",dealt,0);}
 {Fixture f;f.interceptor.chance=33;f.bomber.evasion=33;f.bomber.direct=100;f.defender.retaliation=10;meanHit=30;expect("basis10000 retains fractional product",f.run(),77);expect("fractional combined incoming",f.received,15);}
 {Fixture f;f.bomber.direct=1000000;f.interceptor.chance=50;expect("wide multiplication",f.run(),500000);}
 printf("air leaf source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
cpp=work/'air-leaf-source-test.cpp';cpp.write_text(prefix+actual+suffix,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=work/'air-leaf-source-test.exe'
compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/Od','/Z7',str(cpp),'/Fo'+str(work/'air-leaf-source-test.obj'),'/Fe'+str(exe)],cwd=work,env=env,capture_output=True,text=True)
(work/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=work,env=env,capture_output=True,text=True)
print(run.stdout+run.stderr,end='')
result={'source_file_sha256':hashlib.sha256(raw).hexdigest().upper(),'extracted_branch_sha256':hashlib.sha256(actual.encode()).hexdigest().upper(),'compile_returncode':compiled.returncode,'test_returncode':run.returncode,'output':run.stdout+run.stderr,'scope':'actual AIR branch extracted with deterministic engine stubs, native VC9; no VP DLL build or game run'}
(work/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
sys.exit(run.returncode)
