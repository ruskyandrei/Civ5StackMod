"""Actual CvDangerPlotContents::reset regression on VC9; no game/DLL build."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];out=root/'work/danger-reset-regression';out.mkdir(exist_ok=True)
src=(root/'CvGameCoreDLL_Expansion2/CvDangerPlots.h').read_text(encoding='utf-8-sig');start=src.index('\tvoid reset()');end=src.index('\n\tint GetDanger(',start);actual=src[start:end]
head=r"""
#include <vector>
#include <utility>
#include <cstdio>
#include <cstdlib>
#include <new>
static int allocationCount=0;
void* operator new(size_t n) throw(std::bad_alloc){++allocationCount;void*p=malloc(n?n:1);if(!p)throw std::bad_alloc();return p;}
void operator delete(void*p) throw(){free(p);}
typedef std::vector<std::pair<int,int> > DangerUnitVector;
typedef DangerUnitVector DangerCityVector;
struct CvDangerPlotContents{void*m_pPlot;bool m_bFlatPlotDamage;int m_iImprovementDamage,m_iFogCount;DangerUnitVector m_apUnits,m_apCities,m_apCaptureUnits;std::vector<int> m_stackDangerDamageIDs;bool m_stackDangerDamageIDsValid;
"""
tail=r"""
};
static int checks=0,failures=0;
void expect(bool ok,const char*name){++checks;if(!ok){++failures;printf("FAIL %s\n",name);}}
int main(){
 DangerUnitVector legacy;legacy.reserve(1024);legacy.push_back(std::make_pair(1,2));legacy.clear();legacy=DangerUnitVector();legacy.reserve(5);expect(legacy.capacity()==1024,"VC9 legacy empty assignment retains allocation");
 int sizes[]={0,1,4,5,6,32,1024};
 for(int j=0;j<7;++j){int n=sizes[j];CvDangerPlotContents d;d.m_pPlot=(void*)0x1234;d.m_bFlatPlotDamage=true;d.m_iImprovementDamage=25;d.m_iFogCount=9;d.m_apUnits.reserve(n);d.m_apCaptureUnits.reserve(n);d.m_apCities.reserve(7);
 for(int i=0;i<n;++i){d.m_apUnits.push_back(std::make_pair(i,i));d.m_apCaptureUnits.push_back(std::make_pair(i,i));}d.m_apCities.push_back(std::make_pair(1,2));
 d.m_stackDangerDamageIDs.push_back(42);d.m_stackDangerDamageIDsValid=true;size_t idsBefore=d.m_stackDangerDamageIDs.capacity();
 size_t before=d.m_apUnits.capacity(),captureBefore=d.m_apCaptureUnits.capacity(),citiesBefore=d.m_apCities.capacity();int allocBefore=allocationCount;d.reset();
 expect(d.m_apUnits.empty()&&d.m_apCities.empty()&&d.m_apCaptureUnits.empty(),"all danger sources cleared");expect(!d.m_bFlatPlotDamage&&d.m_iImprovementDamage==0&&d.m_iFogCount==0,"scalar danger reset");expect(d.m_pPlot==(void*)0x1234,"plot identity unchanged");expect(d.m_apUnits.capacity()==(before>5?5:before),"combat capacity trimmed only beyond existing threshold");expect(d.m_apCaptureUnits.capacity()==(captureBefore>5?0:captureBefore),"capture retention policy unchanged");expect(d.m_apCities.capacity()==citiesBefore,"city retention unchanged");expect(allocationCount-allocBefore==(before>5?1:0),"no normal-path allocation and only existing reserve5 on trim");
 expect(d.m_stackDangerDamageIDs.empty()&&!d.m_stackDangerDamageIDsValid&&d.m_stackDangerDamageIDs.capacity()==idsBefore,"projected source IDs invalidated and capacity reused");
 allocBefore=allocationCount;d.reset();expect(allocationCount==allocBefore,"repeat reset allocates nothing");expect(d.m_apUnits.capacity()<6,"repeat reset remains bounded");
 for(int i=0;i<5;++i)d.m_apUnits.push_back(std::make_pair(i,i+1));expect(d.m_apUnits.size()==5&&d.m_apUnits[4].second==5,"usable after reset");
 }
 printf("danger reset regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
"""
cpp=out/'danger-reset-source-test.cpp';cpp.write_text(head+actual+tail,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';inc=root/'work/toolchain/sdk/vc9/include';lib=root/'work/toolchain/sdk/vc9/lib';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(inc)+';'+str(sdk/'Include');env['LIB']=str(lib)+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=out/'danger-reset-source-test.exe';cmd=[str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_HAS_ITERATOR_DEBUGGING=0','/D_SECURE_SCL=0',str(cpp),'/Fo'+str(out/'danger-reset-source-test.obj'),'/Fe'+str(exe)]
c=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True);(out/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,env=env,capture_output=True,text=True);print(r.stdout+r.stderr,end='');result={'source_sha256':hashlib.sha256(src.encode()).hexdigest().upper(),'actual_reset_sha256':hashlib.sha256(actual.encode()).hexdigest().upper(),'compile_returncode':c.returncode,'test_returncode':r.returncode,'output':r.stdout+r.stderr,'scope':'actual extracted reset with real VC9 vector and allocation counter; confirms legacy capacity retention; no live memory-growth proof'};(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');sys.exit(r.returncode)
