"""Actual-source sparse resource-loop differential; --prepare-only never compiles."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/sparse-unit-resources-regression';OUT.mkdir(exist_ok=True)
STAGE=ROOT/'work/sparse-unit-resources-staged';CONTROL='9c4b9915e'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--production',action='store_true',help='Require all three current production files to match the reviewed staged candidate exactly.');args=parser.parse_args()

def block(source,signature,semicolon=False):
 start=source.index(signature);end=source.index('{',start)+1;depth=1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 if semicolon:assert source[end]==';';end+=1
 return source[start:end]

paths=['CvGameCoreDLL_Expansion2/CvUnitClasses.h','CvGameCoreDLL_Expansion2/CvUnitClasses.cpp','CvGameCoreDLL_Expansion2/CvPlayer.cpp']
old={p:subprocess.check_output(['git','show',CONTROL+':'+p],cwd=ROOT).decode('utf-8-sig') for p in paths}
staged={p:(STAGE/Path(p).name).read_text(encoding='utf-8') for p in paths}
new={p:(ROOT/p).read_text(encoding='utf-8-sig') for p in paths} if args.production else staged
proof=json.loads((STAGE/'staging-proof.json').read_text(encoding='utf-8'))
assert proof['control']==CONTROL
for p in paths:
 assert new[p]==staged[p],'Current production differs from reviewed stage: '+p
 assert proof['files'][p]['source_sha256']==hashlib.sha256(old[p].encode()).hexdigest()
 assert proof['files'][p]['candidate_sha256']==hashlib.sha256(new[p].encode()).hexdigest()
classes=paths[1];player=paths[2]
methods=[]
for signature in ('int CvUnitEntry::GetResourceQuantityRequirement(','int CvUnitEntry::GetResourceQuantityTotal('):
 assert block(old[classes],signature)==block(new[classes],signature),'Quantity getter changed'
 method=block(new[classes],signature).replace('{\n','{\n ++quantityGetterCalls;\n',1)
 methods.append(method)
for signature in ('void CvUnitEntry::CacheResourceQuantityCheckIDs(','const std::vector<int>* CvUnitEntry::GetResourceQuantityCheckIDs('):methods.append(block(new[classes],signature))
legacy=block(old[player],'bool CvPlayer::HasResourceForNewUnit(')
sparse=block(new[player],'bool CvPlayer::HasResourceForNewUnit(')
before='\tfor (int iResourceLoop = 0; iResourceLoop < GC.getNumResourceInfos(); iResourceLoop++)\n\t{\n\t\tconst ResourceTypes eResource = static_cast<ResourceTypes>(iResourceLoop);'
after='\tconst std::vector<int>* resourceIDs = pUnitInfo->GetResourceQuantityCheckIDs();\n\tfor (int iResourceCheck = 0; iResourceCheck < (resourceIDs ? (int)resourceIDs->size() : GC.getNumResourceInfos()); iResourceCheck++)\n\t{\n\t\tconst int iResourceLoop = resourceIDs ? (*resourceIDs)[iResourceCheck] : iResourceCheck;\n\t\tconst ResourceTypes eResource = static_cast<ResourceTypes>(iResourceLoop);'
assert sparse.replace(after,before,1)==legacy,'Live body changed beyond iteration selection'
cache=block(new[classes],'bool CvUnitEntry::CacheResults(')
invalidate=cache[cache.index('\tm_iResourceQuantityCheckInfoCount = -1;'):cache.index('\tif(!CvBaseInfo::CacheResults')]
assert invalidate=='\tm_iResourceQuantityCheckInfoCount = -1;\n\tm_vResourceQuantityCheckIDs.clear();\n'
requirement_line='\tkUtility.PopulateArrayByValue(m_piResourceQuantityRequirements, "Resources", "Unit_ResourceQuantityRequirements", "ResourceType", "UnitType", szUnitType, "Cost");'
totals_start=cache.index('\n\t{',cache.index('//Populate m_piResourceQuantityTotals'))+1
totals=block(cache[totals_start:],'{')
assert cache.index(requirement_line)<totals_start<cache.index('\tCacheResourceQuantityCheckIDs();')<cache.index('\tDoUpdatePower();')
assert 'm_iResourceQuantityCheckInfoCount(-1)' in new[classes]
assert 'std::vector<int> m_vResourceQuantityCheckIDs;' in new[paths[0]]
restored_header=new[paths[0]].replace('\n\tconst std::vector<int>* GetResourceQuantityCheckIDs() const;','',1)
restored_header=restored_header.replace('\n\t// Derived immutable metadata; NULL getter fallback until fully loaded.\n\tstd::vector<int> m_vResourceQuantityCheckIDs;\n\tint m_iResourceQuantityCheckInfoCount;\n\tvoid CacheResourceQuantityCheckIDs();','',1)
assert restored_header==old[paths[0]],'Header changed beyond reviewed derived metadata'
restored_classes=new[classes].replace('\n\tm_vResourceQuantityCheckIDs(),\n\tm_iResourceQuantityCheckInfoCount(-1),','',1)
restored_classes=restored_classes.replace('\n\t// A failed/repeated load must not expose stale derived metadata.\n\tm_iResourceQuantityCheckInfoCount = -1;\n\tm_vResourceQuantityCheckIDs.clear();','',1)
restored_classes=restored_classes.replace('\t// Both resource requirements and total-quantity rows are now loaded.\n\tCacheResourceQuantityCheckIDs();\n','',1)
helper_start=restored_classes.index('// Only positive requirements/totals can enter the live resource checks.')
helper_end=restored_classes.index('/// Initial set of promotions for this unit',helper_start)
restored_classes=restored_classes[:helper_start]+restored_classes[helper_end:]
assert restored_classes==old[classes],'Unit classes changed beyond reviewed metadata lifecycle'
assert new[player].replace(sparse,legacy,1)==old[player],'Player changed outside the exact iteration choice'
actual_source_sha256={p:hashlib.sha256(new[p].encode()).hexdigest() for p in paths}
prefetch=subprocess.check_output(['git','show',CONTROL+':CvGameCoreDLL_Expansion2/CvDllDatabaseUtility.cpp'],cwd=ROOT).decode('utf-8-sig')
assert prefetch.index('PrefetchCollection(GC.getResourceInfo(), "Resources")')<prefetch.index('PrefetchCollection(GC.getUnitInfo(), "Units")')

prefix=r'''
#define NOMINMAX
#define PRECONDITION(...) ((void)0)
#define ASSERT(...) ((void)0)
#include <windows.h>
#include <algorithm>
#include <map>
#include <vector>
#include <string>
#include <cstdio>
#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <new>
using namespace std;
typedef int UnitTypes;typedef int ResourceTypes;const int NO_UNIT=-1;
bool MOD_UNITS_RESOURCE_QUANTITY_TOTALS=true;
int quantityGetterCalls=0;vector<string>events;
static size_t allocations=0;void*operator new(size_t n){++allocations;void*p=malloc(n?n:1);if(!p)throw bad_alloc();return p;}void operator delete(void*p){free(p);}void*operator new[](size_t n){return ::operator new(n);}void operator delete[](void*p){::operator delete(p);}
struct CvString:string{using string::operator=;void Format(const char*format,...){char buffer[1024];va_list args;va_start(args,format);vsprintf_s(buffer,sizeof(buffer),format,args);va_end(args);assign(buffer);}};
string event(int kind,int id,int flag=0){char text[80];sprintf_s(text,"%d:%d:%d",kind,id,flag);return text;}
struct CvResourceInfo{CvString icon,description,key;CvResourceInfo(){}void init(int id){icon.Format("I%d",id);description.Format("Resource%d",id);key.Format("KEY%d",id);}const char*GetIconString()const{return icon.c_str();}const char*GetDescription()const{return description.c_str();}const char*GetTextKey()const{return key.c_str();}};
namespace Database{struct Results{vector<pair<int,int> >rows;size_t cursor;Results():cursor(0){}void Bind(int,const char*,size_t,bool){}bool Step(){if(cursor<rows.size()){++cursor;return true;}return false;}int GetInt(int field)const{return field?rows[cursor-1].second:rows[cursor-1].first;}void Reset(){cursor=0;}};}
struct CvUnitEntry{
 int*m_piResourceQuantityRequirements;map<int,int>m_piResourceQuantityTotals;vector<int>m_vResourceQuantityCheckIDs;int m_iResourceQuantityCheckInfoCount;
 CvUnitEntry():m_piResourceQuantityRequirements(NULL),m_iResourceQuantityCheckInfoCount(-1){}
 ~CvUnitEntry(){delete[]m_piResourceQuantityRequirements;}
 int GetResourceQuantityRequirement(int)const;int GetResourceQuantityTotal(int)const;
 void CacheResourceQuantityCheckIDs();const vector<int>*GetResourceQuantityCheckIDs()const;
 bool LoadResourceSections(struct CvDatabaseUtility&,bool);
};
struct Game{
 void BuildCannotPerformActionHelpText(CvString*sink,const char*key,const char*a){if(!sink)return;events.push_back(string("text:")+key+":"+a);*sink+=string(key)+"("+a+")";}
 void BuildCannotPerformActionHelpText(CvString*sink,const char*key,const char*icon,const char*name,int amount){if(!sink)return;char n[32];sprintf_s(n,"%d",amount);events.push_back(string("text:")+key+":"+icon+":"+name+":"+n);*sink+=string(key)+"("+icon+","+name+","+n+")";}
};
struct Globals{
 int count,aluminum;CvUnitEntry*units[3];CvResourceInfo infos[128];Game game;
 Globals():count(57),aluminum(31){for(int i=0;i<3;++i)units[i]=NULL;for(int i=0;i<128;++i)infos[i].init(i);}
 int getNumResourceInfos()const{return count;}CvUnitEntry*getUnitInfo(int i)const{return i>=0&&i<3?units[i]:NULL;}
 CvResourceInfo*getResourceInfo(int i){events.push_back(event(3,i));return &infos[i];}
 int getInfoTypeForString(const char*)const{events.push_back(event(4,aluminum));return aluminum;}Game&getGame(){return game;}
}GC;
struct CvDatabaseUtility{
 int requirements[128];Database::Results result;bool returnExisting;CvDatabaseUtility():returnExisting(true){for(int i=0;i<128;++i)requirements[i]=0;}
 void PopulateArrayByValue(int*&values,const char*,const char*,const char*,const char*,const char*,const char*){delete[]values;values=new int[128];for(int i=0;i<128;++i)values[i]=requirements[i];}
 Database::Results*GetResults(const string&){return returnExisting?&result:NULL;}
 Database::Results*PrepareResults(const string&,const char*){return &result;}
};
struct CvPlayer{
 bool major;int totals[128],available[128],imported[128],spaceship,core;
 CvPlayer():major(true),spaceship(0),core(0){for(int i=0;i<128;++i)totals[i]=available[i]=imported[i]=5;}
 bool isMajorCiv()const{events.push_back("major");return major;}
 int getNumResourceTotal(int id)const{events.push_back(event(1,id));return totals[id];}
 int getNumResourceAvailable(int id,bool imports=false)const{events.push_back(event(2,id,imports));return available[id]+(imports?imported[id]:0);}
 int GetNumAluminumStillNeededForSpaceship()const{events.push_back("spaceship");return spaceship;}
 int GetNumAluminumStillNeededForCoreCities()const{events.push_back("core");return core;}
 bool Legacy(const UnitTypes,const bool,const bool,const UnitTypes,const bool,CvString* =NULL)const;
 bool Sparse(const UnitTypes,const bool,const bool,const UnitTypes,const bool,CvString* =NULL)const;
};
'''
load='bool CvUnitEntry::LoadResourceSections(CvDatabaseUtility& kUtility, bool baseSuccess)\n{\n'+invalidate+' if(!baseSuccess)return false;\n const char*szUnitType="TEST";const size_t lenUnitType=strlen(szUnitType);\n'+requirement_line+'\n'+totals+'\n CacheResourceQuantityCheckIDs();return true;\n}\n'
fixture=prefix+'\n'+'\n'.join(methods)+'\n'+load+'\n'+legacy.replace('CvPlayer::HasResourceForNewUnit','CvPlayer::Legacy')+'\n'+sparse.replace('CvPlayer::HasResourceForNewUnit','CvPlayer::Sparse')
tests=r'''
int checks=0,failures=0;void check(bool ok,const char*label){++checks;if(!ok){if(failures<15)printf("FAIL %s\n",label);++failures;}}
unsigned long rng=163991;unsigned long rnd(){rng=rng*1664525u+1013904223u;return rng;}
void compare(const CvPlayer&p,int unit,bool none,bool aluminum,int from,bool continued,bool tooltip){
 CvString a,b;if(tooltip)a=b="Existing";events.clear();quantityGetterCalls=0;bool x=p.Legacy(unit,none,aluminum,from,continued,tooltip?&a:NULL);vector<string>oldEvents=events;int oldGetters=quantityGetterCalls;
 events.clear();quantityGetterCalls=0;bool y=p.Sparse(unit,none,aluminum,from,continued,tooltip?&b:NULL);
 check(x==y,"resource eligibility exact");check(a==b,"full tooltip bytes exact");check(oldEvents==events,"live callback/getter ordering exact");check(quantityGetterCalls<=oldGetters,"never increases quantity getter work");
}
int main(){
 CvUnitEntry unit,from;GC.units[0]=&unit;GC.units[1]=&from;CvDatabaseUtility db;CvPlayer player;
 check(unit.GetResourceQuantityCheckIDs()==NULL,"default/unloaded metadata fallback");compare(player,0,false,true,1,false,true);compare(player,-1,false,true,1,false,true);
 // Positives at ID31 prove aluminum uses the raw resource ID, not sparse index0.
 db.requirements[31]=2;db.result.rows.push_back(make_pair(31,3));db.result.rows.push_back(make_pair(55,-4));check(unit.LoadResourceSections(db,true),"real sections load");check(unit.GetResourceQuantityCheckIDs()->size()==1&&(*unit.GetResourceQuantityCheckIDs())[0]==31,"positive union/raw ID ascending");
 from.m_piResourceQuantityRequirements=new int[128];for(int i=0;i<128;++i)from.m_piResourceQuantityRequirements[i]=0;from.m_piResourceQuantityRequirements[31]=5;
 player.spaceship=3;player.core=2;player.available[31]=-1;
 for(int flags=0;flags<32;++flags)compare(player,0,flags&1,flags&2,(flags&4)?1:NO_UNIT,flags&8,flags&16);
 // Failed reload invalidates the list before any existing metadata is touched.
 check(!unit.LoadResourceSections(db,false),"failed load retained failure");check(unit.GetResourceQuantityCheckIDs()==NULL,"failed reload list not reused");compare(player,0,false,true,1,true,true);
 // Original totals map retains absent rows on same-object reload; preserve it.
 db.requirements[31]=0;db.requirements[7]=4;db.result.rows.clear();db.returnExisting=false;unit.LoadResourceSections(db,true);
 check(unit.GetResourceQuantityCheckIDs()->size()==2&&(*unit.GetResourceQuantityCheckIDs())[0]==7&&(*unit.GetResourceQuantityCheckIDs())[1]==31,"repeated load rebuilds from actual retained map and fresh requirements");
 compare(player,0,false,true,1,true,true);
 // Resource count mismatch chooses the complete original range dynamically.
 GC.count=56;check(unit.GetResourceQuantityCheckIDs()==NULL,"shrunk count fallback");compare(player,0,false,true,1,false,true);GC.count=58;check(unit.GetResourceQuantityCheckIDs()==NULL,"expanded count fallback");compare(player,0,false,true,1,false,true);GC.count=57;
 // NULL requirement storage can still have positive total rows.
 delete[]unit.m_piResourceQuantityRequirements;unit.m_piResourceQuantityRequirements=NULL;unit.CacheResourceQuantityCheckIDs();check(unit.GetResourceQuantityCheckIDs()->size()==1&&(*unit.GetResourceQuantityCheckIDs())[0]==31,"NULL requirements still captures positive total");compare(player,0,false,true,1,false,true);
 // Empty union eliminates all metadata scans; no live gameplay getter was skipped.
 unit.m_piResourceQuantityTotals.clear();unit.CacheResourceQuantityCheckIDs();quantityGetterCalls=0;events.clear();bool oldOk=player.Legacy(0,false,false,NO_UNIT,true,NULL);int oldWork=quantityGetterCalls;
 quantityGetterCalls=0;events.clear();bool newOk=player.Sparse(0,false,false,NO_UNIT,true,NULL);check(oldOk==newOk&&oldWork==114&&quantityGetterCalls==0,"zero-resource rows114 to0 workcount");check(events.empty(),"empty union no live callbacks");
 size_t before=allocations;for(int i=0;i<1000;++i)player.Sparse(0,false,false,NO_UNIT,true,NULL);check(allocations==before,"empty warmed path no allocation");
 // All counts/flags/negative quantities, tooltips, upgrades, majors/minors.
 long oldRows=0,newRows=0;
 for(int seed=0;seed<12000;++seed){
  GC.count=(int)(rnd()%90);GC.aluminum=(int)(rnd()%100);MOD_UNITS_RESOURCE_QUANTITY_TOTALS=(seed%2)==0;player.major=seed%3!=0;player.spaceship=(int)(rnd()%12);player.core=(int)(rnd()%12);
  db.result.rows.clear();unit.m_piResourceQuantityTotals.clear();
  for(int i=0;i<128;++i){db.requirements[i]=(rnd()%18==0)?(int)(rnd()%11)-3:0;if(rnd()%20==0)db.result.rows.push_back(make_pair(i,(int)(rnd()%13)-4));player.totals[i]=(int)(rnd()%16)-6;player.available[i]=(int)(rnd()%18)-7;player.imported[i]=(int)(rnd()%9)-3;from.m_piResourceQuantityRequirements[i]=(int)(rnd()%7)-2;}
  unit.LoadResourceSections(db,true);
  if(seed%29==0){GC.count=(GC.count+1)%91;check(unit.GetResourceQuantityCheckIDs()==NULL,"random count mismatch fallback");}
  if(seed%37==0){unit.LoadResourceSections(db,false);check(unit.GetResourceQuantityCheckIDs()==NULL,"random failed reload fallback");}
  bool no=seed%7==0,aluminum=seed%5==0,continued=seed%2==0,tip=seed%3!=0;int fromID=(seed%4==0)?1:((seed%4==1)?2:NO_UNIT);
  compare(player,0,no,aluminum,fromID,continued,tip);
  const vector<int>*ids=unit.GetResourceQuantityCheckIDs();if(ids){for(size_t i=1;i<ids->size();++i)check((*ids)[i-1]<(*ids)[i],"strict ascending deduplicated union");for(int id=0;id<GC.count;++id)check(binary_search(ids->begin(),ids->end(),id)==(unit.GetResourceQuantityRequirement(id)>0||unit.GetResourceQuantityTotal(id)>0),"exact positive union");oldRows+=GC.count;newRows+=ids->size();}
 }
 printf("metadata workcount over eligible fixture entries: original rows%ld, sparse rows%ld; native gain unmeasured\n",oldRows,newRows);
 printf("actual sparse unit resource differential: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
fixture+='\n'+tests
(OUT/'test.cpp').write_text(fixture,encoding='utf-8')
scope='Actual full old/new HasResourceForNewUnit, unchanged quantity getters, new union builder/getter, actual resource-related CacheResults sections/order/invalidation. Other DB loading/player/localization services are deterministic substitutes. No whole CacheResults/database loader/full healing/native timing claim.'
if args.prepare_only:
 (OUT/'scaffold.json').write_text(json.dumps(dict(prepared=True,compiled=False,control=CONTROL,production_applied=args.production,actual_source_sha256=actual_source_sha256,fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),scope=scope),indent=2)+'\n',encoding='utf-8');print('Prepared sparse resource actual-source scaffold; no compilation.');raise SystemExit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=OUT/'test.exe';compile=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(OUT/'test.cpp'),'/Fo'+str(OUT/'test.obj'),'/Fe'+str(exe)],cwd=OUT,env=env,capture_output=True,text=True,timeout=60)
(OUT/'compile.log').write_text(compile.stdout+compile.stderr,encoding='utf-8')
if compile.returncode:print(compile.stdout+compile.stderr);raise SystemExit(compile.returncode)
run=subprocess.run([str(exe)],cwd=OUT,capture_output=True,text=True,timeout=40);print(run.stdout+run.stderr,end='')
(OUT/'result.json').write_text(json.dumps(dict(control=CONTROL,production_applied=args.production,actual_source_sha256=actual_source_sha256,compiled=True,returncode=run.returncode,output=run.stdout+run.stderr,fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),scope=scope),indent=2)+'\n',encoding='utf-8');raise SystemExit(run.returncode)
