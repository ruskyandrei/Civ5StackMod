"""VC9 actual-source path-session/FindPath/VerifyPath diagnostic regression."""
from pathlib import Path
import argparse,ast,hashlib,json,os,re,subprocess
ROOT=Path(__file__).resolve().parents[1];CONTROL='e0d85052b';STAGE=ROOT/'work/path-query-profile-bounded-staged';OUT=ROOT/'work/path-query-profile-bounded-regression';OUT.mkdir(exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--emit-only',action='store_true');parser.add_argument('--production',action='store_true');args=parser.parse_args()
def original(name):return subprocess.check_output(['git','show',CONTROL+':CvGameCoreDLL_Expansion2/'+name],cwd=ROOT).decode('utf-8-sig')
def function(text,name):
 a=text.index(name);b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
def blocks(text,name):return re.findall(r'^    // BEGIN '+name+r'\n(.*?)^    // END '+name+r'\n',text,re.M|re.S)
def strip(text):
 text=re.sub(r'^    // BEGIN PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY\n.*?^    // END PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY\n','',text,flags=re.M|re.S)
 text=''.join(x for x in text.splitlines(True) if 'PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY' not in x)
 text=text.replace(' || !strcmp(category,"PATH_SAMPLE")','')
 return text.replace('\tif (kToNodeCacheData.iGenerationID==finder->GetCurrentGenerationID())\n\t{\n\t\treturn;\n\t}', '\tif (kToNodeCacheData.iGenerationID==finder->GetCurrentGenerationID())\n\t\treturn;')
sources={n:(STAGE/n).read_text(encoding='utf-8') for n in ('CvStackingDiagnostics.h','CvStackingDiagnostics.cpp','CvAStar.cpp')}
if args.production:
 for name,expected in sources.items():
  current=(ROOT/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8-sig')
  assert current==expected,'Production entire file differs from reviewed stage: '+name
  sources[name]=current
proof={}
for n,s in sources.items():
 clean=strip(s)
 if n.endswith('.h'):clean=clean.replace('class CvCombatInfo;\nclass CvUnit;\nclass CvPlot;','class CvCombatInfo;')
 assert clean==original(n),'Unexpected non-diagnostic change: '+n
 proof[n]=dict(control_sha256=hashlib.sha256(clean.encode()).hexdigest(),stage_sha256=hashlib.sha256(s.encode()).hexdigest(),reverse_stripped_identical=True)
module=ast.parse((ROOT/'work/test-plan-sampled-timing.py').read_text(encoding='utf-8-sig'))
prefix=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='prefix' for t in n.targets))
prefix+=r'''
static unsigned long tickReads=0,metadataReads=0,sceneReads=0;
DWORD FixtureTick(){++tickReads;return(DWORD)(tick/1000);}
#define GetTickCount FixtureTick
namespace CvStackingStrengthCache{volatile LONG epoch=1;long SceneEpoch(){++sceneReads;return InterlockedCompareExchange(&epoch,0,0);}void Invalidate(){InterlockedIncrement(&epoch);}}
bool MOD_EVENTS_CAN_MOVE_INTO=false,MOD_EVENTS_AIRLIFT=false,MOD_EVENTS_SEALIFT=false,MOD_EVENTS_UNIT_RANGEATTACK=false,MOD_EVENTS_CITY_BOMBARD=false,MOD_EVENTS_REBASE=false;
struct CvUnit{int id,owner,hp,maxHP;CvUnit():id(1),owner(3),hp(100),maxHP(100){}int GetID()const{++metadataReads;return id;}int getOwner()const{++metadataReads;return owner;}int GetCurrHitPoints()const{++metadataReads;return hp;}int GetMaxHitPoints()const{++metadataReads;return maxHP;}};
struct CvPlot{int id;CvPlot(int i=1):id(i){}int GetPlotIndex()const{++metadataReads;return id;}};
struct DangerService{bool dirty;DangerService():dirty(false){}bool IsDirty()const{++metadataReads;return dirty;}};
struct PlayerService{DangerService danger;DangerService*GetDangerPlots(){++metadataReads;return&danger;}}player;
#define GET_PLAYER(id) player
'''
header=blocks(sources['CvStackingDiagnostics.h'],'PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY')[0]
globals=blocks(sources['CvStackingDiagnostics.cpp'],'PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY')[0]
implementation=blocks(sources['CvStackingDiagnostics.cpp'],'PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY')[1]
format_call=re.search(r'Record\(1,pathProfile\.actor,"PATH_SAMPLE",\s*("(?:\\.|[^"\\])*")\s*,(.*?)\);',implementation,re.S)
assert format_call,'Native path row formatter missing'
format_text=ast.literal_eval(format_call.group(1));format_args=[x.strip() for x in format_call.group(2).split(',')]
format_specs=re.findall(r'%(?:I64)?[udls]',format_text)
assert len(format_args)==len(format_specs),'Native formatter argument/specifier mismatch'
original_sampler_globals=blocks(sources['CvStackingDiagnostics.cpp'],'PLAN_SAMPLE_DIAGNOSTIC_ONLY')[0]
original_sampler_header=blocks(sources['CvStackingDiagnostics.h'],'PLAN_SAMPLE_DIAGNOSTIC_ONLY')[0]
category=function(sources['CvStackingDiagnostics.cpp'],'int categoryBit(')
reset=function(sources['CvStackingDiagnostics.cpp'],'void Reset()');setlevel=function(sources['CvStackingDiagnostics.cpp'],'void SetLevel(')
gate=function(sources['CvStackingDiagnostics.cpp'],'void SetTacticalSamplingEnabled(')
services=r'''
bool categoryEnabledUnlocked(int required,PlayerTypes actor,const char*category){return getLevelUnlocked()>=required&&!failed&&(testFilter<0||actor==testFilter)&&(testMask&categoryBit(category))!=0;}
std::vector<std::string>rowsSeen;size_t maximumRow=0;
namespace CvStackingDiagnostics{void Record(int required,PlayerTypes actor,const char*category,const char*format,...){if(!categoryEnabledUnlocked(required,actor,category))return;char buffer[3072];va_list args;va_start(args,format);int n=_vsnprintf_s(buffer,sizeof(buffer),_TRUNCATE,format,args);va_end(args);if(n<0)throw 991;rowsSeen.push_back(buffer);maximumRow=std::max(maximumRow,rowsSeen.back().size());++recordCalls;}}
enum CvAStarNodeAddOp{ASNC_INITIALADD};
struct SPathFinderUserData{int ePlayer,iUnitID,ePath,iFlags;SPathFinderUserData():ePlayer(3),iUnitID(1),ePath(0),iFlags(4){}};
struct CvAStarNode{int m_iX,m_iY,m_iTurns;CvAStarNode(int x=0,int y=0):m_iX(x),m_iY(y),m_iTurns(0){}};
struct SPathNode{int x,y;SPathNode(int a=0,int b=0):x(a),y(b){}};
struct SPath{std::vector<SPathNode>vPlots;SPathFinderUserData sConfig;int iTotalCost;SPath():iTotalCost(99){}};
typedef int(*Step)(const CvAStarNode*,const CvAStarNode*,const SPathFinderUserData&,const void*);typedef bool(*Dest)(int,int,const SPathFinderUserData&,const void*);typedef void(*Init)(const SPathFinderUserData&,void*);
CvUnit actor;CvPlot dangerPlot;
struct FlowTrace{int reset,init,uninit,dest,nodeAdd,best,children,valid,cost;FlowTrace():reset(0),init(0),uninit(0),dest(0),nodeAdd(0),best(0),children(0),valid(0),cost(0){}}flow;
bool destAllowed=true,configured=true,startAllowed=true,throwChildren=false;int dangerCalls=0;
int RawDanger(){++dangerCalls;tick+=40;return 97;}
int StepValid(const CvAStarNode*,const CvAStarNode*,const SPathFinderUserData&,const void*){++flow.valid;return true;}
int StepCost(const CvAStarNode*,const CvAStarNode*,const SPathFinderUserData&,const void*){++flow.cost;return 1;}
bool DestValid(int,int,const SPathFinderUserData&,const void*){++flow.dest;return destAllowed;}
void InitPath(const SPathFinderUserData&,void*){++flow.init;}void UninitPath(const SPathFinderUserData&,void*){++flow.uninit;}
// GetPath wrappers own the core lock in production. VerifyPath's exact original
// acquire/release branches are retained with these counted fixture services.
'''
prefix=prefix.replace('struct DLLService{bool HasGameCoreLock(){return ::GetCurrentThreadId()==ownerThread;}}dll;DLLService*gDLL=&dll;', 'struct DLLService{bool held;int acquires,releases;DLLService():held(true),acquires(0),releases(0){}bool HasGameCoreLock(){return held&&::GetCurrentThreadId()==ownerThread;}void GetGameCoreLock(){held=true;++acquires;}void ReleaseGameCoreLock(){held=false;++releases;}}dll;DLLService*gDLL=&dll;')
class_body=r'''
struct CvAStar{
 SPathFinderUserData m_sData;int m_iCurrentGenerationID,m_iXdest,m_iYdest,m_iXstart,m_iYstart,m_iRounds,m_iDestHitCount;CvAStarNode*m_pBest;CvAStarNode nodes[2][2];CvAStarNode*m_ppaaNodes[2];int cursor;
 Dest udDestValid;Init udInitializeFunc,udUninitializeFunc;Step udValid,udCost;
 CvAStar():m_iCurrentGenerationID(0),m_iXdest(1),m_iYdest(0),m_iXstart(0),m_iYstart(0),m_iRounds(0),m_iDestHitCount(0),m_pBest(NULL),cursor(0),udDestValid(DestValid),udInitializeFunc(InitPath),udUninitializeFunc(UninitPath),udValid(StepValid),udCost(StepCost){for(int x=0;x<2;++x){m_ppaaNodes[x]=nodes[x];for(int y=0;y<2;++y)nodes[x][y]=CvAStarNode(x,y);}}
 bool IsInitialized(int,int,int,int){return true;}void SanitizeFlags(){}void Reset(){++flow.reset;cursor=0;m_iRounds=0;m_iDestHitCount=0;}
 bool isValid(int x,int y){return startAllowed&&x>=0&&x<2&&y>=0&&y<2;}bool Configure(const SPathFinderUserData&data){m_sData=data;return configured;}
 CvAStarNode*GetNodeMutable(int x,int y){return&nodes[x][y];}void NodeAddedToPath(const CvAStarNode*,CvAStarNode*,int,CvAStarNodeAddOp){++flow.nodeAdd;}
 CvAStarNode*GetBest(){++flow.best;return cursor++==0?&nodes[0][0]:&nodes[1][0];}bool IsPathDest(int x,int y){return x==m_iXdest&&y==m_iYdest;}bool IsApproximateMode(){return false;}
 int udFunc(Step callback,const CvAStarNode*a,const CvAStarNode*b,const SPathFinderUserData&data){return callback(a,b,data,this);}
 void CreateChildren(CvAStarNode*){++flow.children;for(int i=0;i<20;++i){BODY}if(throwChildren)throw 7;}
 bool FindPathWithCurrentConfiguration(int,int,int,int);bool VerifyPath(const SPath&);
};
'''
find=function(sources['CvAStar.cpp'],'bool CvAStar::FindPathWithCurrentConfiguration(');verify=function(sources['CvAStar.cpp'],'bool CvAStar::VerifyPath(')
gameplay='namespace Legacy{'+class_body.replace('BODY','RawDanger();')+function(original('CvAStar.cpp'),'bool CvAStar::FindPathWithCurrentConfiguration(')+function(original('CvAStar.cpp'),'bool CvAStar::VerifyPath(')+'}\n'
gameplay+='namespace Candidate{'+class_body.replace('BODY','CvStackingDiagnostics::PathProfileScope scope(CvStackingDiagnostics::PATH_RAW_DANGER,&actor,&dangerPlot);RawDanger();')+find+verify+'}\n'
tests=r'''
using namespace CvStackingDiagnostics;
int checks=0,failures=0;void Expect(const char*name,bool yes){++checks;if(!yes){++failures;if(failures<20)printf("FAIL %s\n",name);}}
void Clean(){memset(&pathProfile,0,sizeof(pathProfile));pathProfileSerial=79;pathProfileDisabledEpoch=-1;pathProfileRowTurn=pathProfilePreviousCapTurn=-1;pathProfileRows=0;pathProfileCappedSelected=pathProfilePreviousCappedSelected=0;tacticalSamplingOverride=1;level=1;testTurn=252;testInterval=1;testMask=16;testFilter=-1;frequencyFailure=false;counterFailure=0;backward=false;qpcCalls=qpfCalls=ownerReads=settingReads=recordCalls=lockCalls=0;tickReads=metadataReads=sceneReads=0;rowsSeen.clear();actor=CvUnit();dangerPlot=CvPlot();player.danger.dirty=false;flow=FlowTrace();configured=startAllowed=destAllowed=true;throwChildren=false;dangerCalls=0;dll.held=true;dll.acquires=dll.releases=0;}
void SelectNext(PathProfilePart part){pathProfile.counter[part].calls=15-((pathProfile.phase+(unsigned long)part*7UL)&15);}
DWORD WINAPI Foreign(void*){LONG clocks=qpcCalls;unsigned long reads=metadataReads;for(int i=0;i<1000;++i){PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);CountPathNodeCache(false);}return clocks==qpcCalls&&reads==metadataReads?0:1;}
PathProfileScope*foreignScope=NULL;PathProfileState foreignState;
DWORD WINAPI ForeignFinish(void*){memcpy(&pathProfile,&foreignState,sizeof(pathProfile));LONG clocks=qpcCalls;foreignScope->Finish();return clocks==qpcCalls?0:1;}
int main(){
 Clean();Expect("performance category16",categoryBit("PATH_SAMPLE")==16);tacticalSamplingOverride=0;
 Expect("bounded TLS state below4KiB per thread",sizeof(PathProfileState)<=4096);
 {PathProfileSession disabled(3,1,0,1,4,0,0,1,0,false);LONG settings=settingReads,locks=lockCalls,allocs=allocationCalls;for(int i=0;i<10000;++i){PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);CountPathNodeCache(i%2!=0);}Expect("disabled per-node zero services",qpcCalls==0&&qpfCalls==0&&ownerReads==0&&metadataReads==0&&sceneReads==0&&tickReads==0&&recordCalls==0&&settingReads==settings&&lockCalls==locks&&allocationCalls==allocs);}Expect("off no row",rowsSeen.empty());
 {LONG settings=settingReads,locks=lockCalls;for(int i=0;i<1000;++i){PathProfileSession disabled(3,1,0,1,4,0,0,1,0,false);}Expect("warmed disabled query snapshot no lock/settings/clock",settingReads==settings&&lockCalls==locks&&qpcCalls==0&&qpfCalls==0);}SetTacticalSamplingEnabled(true);pathProfileSerial=79;{PathProfileSession enabled(3,1,0,1,4,0,0,1,0,false);Expect("sampling epoch invalidates disabled snapshot",pathProfile.enabled);}Expect("enabled after cached-off emits",recordCalls==1);
 for(int mode=0;mode<5;++mode){Clean();if(mode==0)level=0;if(mode==1)testMask=8;if(mode==2)testFilter=2;if(mode==3)testInterval=0;if(mode==4)testInterval=5;{PathProfileSession no(3,1,0,1,4,0,0,1,0,false);PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);}Expect("filter/level/interval zero calibration",qpcCalls==0&&qpfCalls==0&&recordCalls==0);}
 Clean();{PathProfileSession session(3,1,0,13,4,0,0,1,0,false);Expect("sampled query captured",pathProfile.enabled&&pathProfile.nodeGeneration==13);for(int i=0;i<200;++i){dangerPlot.id=i;PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);}Expect("bounded128 distinct slots",pathProfile.tracked==128&&pathProfile.untracked==72);dangerPlot.id=1;{PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);}Expect("known plot still repeated after saturation",pathProfile.repeats==1&&pathProfile.samePhysicalRepeats==1);actor.hp=90;{PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);}Expect("HP drift not same-physical repeat",pathProfile.repeats==2&&pathProfile.samePhysicalRepeats==1);CvStackingStrengthCache::Invalidate();{PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);}Expect("scene drift not same-physical repeat",pathProfile.samePhysicalRepeats==1);player.danger.dirty=true;{PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);}Expect("dirty separately counted",pathProfile.dirty==1&&pathProfile.samePhysicalRepeats==1);actor.owner=2;{PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);}Expect("actor mismatch separately counted",pathProfile.actorMismatch==1);CountPathNodeCache(true);CountPathNodeCache(false);Expect("node counters",pathProfile.cacheHits==1&&pathProfile.cacheBuilds==1);}
 Expect("one bounded query row",recordCalls==1&&rowsSeen[0].find("nodeGeneration=13")!=std::string::npos&&rowsSeen[0].find("origin=search")!=std::string::npos);
 Clean();{PathProfileSession session(3,1,0,13,4,0,0,1,0,true);SelectNext(PATH_RAW_DANGER);{PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);LONG clocks=qpcCalls,reads=metadataReads,locks=lockCalls;{PathProfileSession nested(3,1,0,14,4,0,0,1,0,false);for(int i=0;i<100;++i){PathProfileScope child(PATH_RAW_DANGER,&actor,&dangerPlot);}}Expect("nested suppresses hot services",clocks==qpcCalls&&reads==metadataReads&&locks==lockCalls);tick+=100;}Expect("inclusive nested sample captured once",pathProfile.counter[PATH_RAW_DANGER].samples==1&&pathProfile.nested==1);}
 Expect("verify distinct row origin",recordCalls==1&&rowsSeen[0].find("origin=verify")!=std::string::npos);
 Clean();{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);HANDLE worker=CreateThread(NULL,0,Foreign,NULL,0,NULL);DWORD result=1;if(worker){WaitForSingleObject(worker,10000);GetExitCodeThread(worker,&result);CloseHandle(worker);}Expect("foreign off TLS cannot inspect owner metadata",result==0);SelectNext(PATH_RAW_DANGER);{PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);foreignScope=&scope;memcpy(&foreignState,&pathProfile,sizeof(pathProfile));worker=CreateThread(NULL,0,ForeignFinish,NULL,0,NULL);if(worker){WaitForSingleObject(worker,10000);GetExitCodeThread(worker,&result);CloseHandle(worker);}Expect("foreign same-serial finish no clocks",result==0);scope.Finish();Expect("owner still finishes once",pathProfile.counter[PATH_RAW_DANGER].samples==1);}}
 for(int mode=0;mode<3;++mode){Clean();{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);SelectNext(PATH_RAW_DANGER);PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);if(mode==0)Reset();if(mode==1)SetLevel(0);if(mode==2)SetTacticalSamplingEnabled(false);LONG clocks=qpcCalls;scope.Finish();Expect("reset/toggle no stale completion clock",qpcCalls==clocks);}Expect("reset/toggle no stale query row",recordCalls==0&&pathProfile.depth==0);}
 Clean();{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);SetTacticalSamplingEnabled(false);unsigned long before=metadataReads;LONG clocks=qpcCalls;for(int i=0;i<100;++i){PathProfileScope off(PATH_RAW_DANGER,&actor,&dangerPlot);}Expect("live sampling disable stops metadata before reads",metadataReads==before&&qpcCalls==clocks);}
 Clean();{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);for(int i=0;i<40;++i){dangerPlot.id=i*128;PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);}Expect("collision censor bounded16 probes",pathProfile.tracked==16&&pathProfile.untracked==24);}
 for(int mode=0;mode<4;++mode){Clean();{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);SelectNext(PATH_RAW_DANGER);if(mode==0)counterFailure=1;{PathProfileScope scope(PATH_RAW_DANGER,&actor,&dangerPlot);if(mode==1)counterFailure=1;if(mode==2)backward=true;}backward=false;if(mode==3)testTurn++;Expect("failed/backward sample never invented",mode==3||pathProfile.counter[PATH_RAW_DANGER].samples==0);}Expect("turn drift no row or failures recorded",mode==3?recordCalls==0:recordCalls==1);}
 Clean();counterFailure=1;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}Expect("failed query start only one actual QPC",qpcCalls==1&&pathProfile.clockReads==1&&pathProfile.clockFailures==1&&rowsSeen[0].find("queryAvailable=0")!=std::string::npos);
 Clean();frequencyFailure=true;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}Expect("frequency failure no clock/row",qpcCalls==0&&recordCalls==0);
 // Full actual FindPath/VerifyPath functions retain the original branching,
 // callback sequence and generation updates. Path engine choices are services.
 for(int off=0;off<2;++off)for(int mode=0;mode<5;++mode){Clean();if(off)tacticalSamplingOverride=0;if(mode==1)destAllowed=false;if(mode==2)startAllowed=false;if(mode==3)configured=false;if(mode==4)throwChildren=true;Legacy::CvAStar baseline;bool a=false,b=false;int ta=0,tb=0;try{a=baseline.FindPathWithCurrentConfiguration(0,0,1,0);}catch(int e){ta=e;}FlowTrace before=flow;int raw=dangerCalls;flow=FlowTrace();dangerCalls=0;Candidate::CvAStar candidate;try{b=candidate.FindPathWithCurrentConfiguration(0,0,1,0);}catch(int e){tb=e;}Expect("actual Find result/exception exact",a==b&&ta==tb);Expect("actual Find callback/order counts exact",!memcmp(&before,&flow,sizeof(flow))&&raw==dangerCalls&&baseline.m_iCurrentGenerationID==candidate.m_iCurrentGenerationID&&baseline.m_iRounds==candidate.m_iRounds);Expect("actual Find RAII returns depth0",pathProfile.depth==0);if(off)Expect("actual Find OFF no clock/getter/I/O",qpcCalls==0&&qpfCalls==0&&metadataReads==0&&recordCalls==0);}
 for(int off=0;off<2;++off)for(int mode=0;mode<4;++mode){Clean();if(off)tacticalSamplingOverride=0;SPath path;path.vPlots.push_back(SPathNode(0,0));path.vPlots.push_back(SPathNode(1,0));if(mode==1)configured=false;if(mode==2)path.vPlots.clear();if(mode==3)path.iTotalCost=0;Legacy::CvAStar baseline;bool a=baseline.VerifyPath(path);FlowTrace before=flow;flow=FlowTrace();Candidate::CvAStar candidate;bool b=candidate.VerifyPath(path);Expect("actual Verify result/callbacks exact",a==b&&!memcmp(&before,&flow,sizeof(flow)));Expect("actual Verify RAII depth0",pathProfile.depth==0);if(off)Expect("actual Verify OFF no clock/getter/I/O",qpcCalls==0&&qpfCalls==0&&metadataReads==0&&recordCalls==0);}
 Clean();{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);pathProfile.nested=pathProfile.cacheHits=pathProfile.cacheBuilds=pathProfile.tracked=pathProfile.untracked=pathProfile.repeats=pathProfile.samePhysicalRepeats=pathProfile.dirty=pathProfile.actorMismatch=~(unsigned __int64)0;for(int i=0;i<PATH_PROFILE_PARTS;++i){PlanSampleCounter&c=pathProfile.counter[i];c.calls=c.selected=c.samples=c.ticks=c.maximum=~(unsigned __int64)0;}}
 Expect("maximum counters fit native row",recordCalls==1&&maximumRow<3072);

 Clean();for(int i=0;i<512;++i){pathProfileSerial=(unsigned long)i*128+79;PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}
 Expect("strict whole-turn128 rows",recordCalls==128&&pathProfileRows==128&&pathProfileCappedSelected==384);
 Expect("last row explicitly marks early cap",rowsSeen.back().find("turnRowOrdinal=128 capAfterThisRow=1")!=std::string::npos);
 {LONG clocks=qpcCalls,frequency=qpfCalls;unsigned long reads=metadataReads;pathProfileSerial=79;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);PathProfileScope raw(PATH_RAW_DANGER,&actor,&dangerPlot);}Expect("capped selected query no hot clocks or getters",qpcCalls==clocks&&qpfCalls==frequency&&metadataReads==reads);}
 SetTacticalSamplingEnabled(false);SetTacticalSamplingEnabled(true);pathProfileSerial=79;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}Expect("toggle does not reopen same-turn cap",recordCalls==128&&pathProfileRows==128);
 testTurn=253;pathProfileSerial=79;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}
 Expect("next turn opens bounded budget",recordCalls==129&&pathProfileRows==1);
 Expect("following-turn row reports prior selected censor",rowsSeen.back().find("previousCapTurn=252 previousCappedSelectedQueries=386")!=std::string::npos);
 Reset();tacticalSamplingOverride=1;level=1;pathProfileSerial=79;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}Expect("load reset clears cap and prior-turn proof",pathProfileRows==1&&pathProfilePreviousCapTurn==-1&&pathProfilePreviousCappedSelected==0);
 Clean();pathProfileRows=127;pathProfileRowTurn=252;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);pathProfileRows=128;}Expect("completion rechecks concurrent cap",recordCalls==0&&pathProfileCappedSelected==1);
 Clean();for(int serialValue=1;serialValue<=128;++serialValue){pathProfileSerial=serialValue-1;PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}Expect("one rotated selection per128 queries",recordCalls==1);
 printf("actual path query profile: %d checks,%d failures,maxRow%u; no gameplay/result reuse\n",checks,failures,(unsigned)maximumRow);return failures?1:0;}
'''
fixture=prefix+'namespace CvStackingDiagnostics{'+original_sampler_header+header+'}\nnamespace{'+original_sampler_globals+globals+'}\n'+category+services+'namespace CvStackingDiagnostics{'+reset+setlevel+gate+implementation+'}\n'+gameplay+tests
(OUT/'test.cpp').write_text(fixture,encoding='utf-8');(OUT/'source-equivalence.json').write_text(json.dumps(dict(control=CONTROL,production_bound=args.production,files=proof,native_row_format=dict(specifiers=len(format_specs),variadic_arguments=len(format_args),exact_arity=True)),indent=2)+'\n',encoding='utf-8')
if args.emit_only:print('Prepared actual source path profiler fixture; no compilation.');raise SystemExit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=OUT/'test.exe';compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(OUT/'test.cpp'),'/Fo'+str(OUT/'test.obj'),'/Fe'+str(exe)],cwd=OUT,env=env,capture_output=True,text=True,timeout=60);(OUT/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);raise SystemExit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=OUT,capture_output=True,text=True,timeout=60);print(run.stdout+run.stderr,end='');(OUT/'result.json').write_text(json.dumps(dict(control=CONTROL,production_bound=args.production,returncode=run.returncode,fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),output=run.stdout+run.stderr,scope='Actual path profiler/session/counter/Reset/toggle and full FindPath/VerifyPath functions with ON/OFF comparison; path engine choices and clocks/IO deterministic services; no raw-result reuse/whole game proof'),indent=2)+'\n',encoding='utf-8');raise SystemExit(run.returncode)
