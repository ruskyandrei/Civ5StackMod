"""Work-only, actual-source packet-opportunity diagnostics regression.

Prerequisite: work/stage-packet-probe.py and packet-probe-fixture-services.h.
No generated fixture scaffold is required. No production writes, full DLL
build, game calls or timing claims. --production strictly binds all five current
production files to the staged candidate before compiling its actual bodies.
"""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2'
stage=root/'work/packet-probe-candidate';out=root/'work/packet-probe-regression';out.mkdir(exist_ok=True)
manifest=json.loads((stage/'manifest.json').read_text());production='--production' in sys.argv
live={n:(core/n).read_text(encoding='utf-8-sig') for n in manifest['source_sha256']}
current={n:subprocess.check_output(['git','show',manifest['control']+':CvGameCoreDLL_Expansion2/'+n],cwd=root).decode('utf-8-sig').replace('\r\n','\n') for n in live}
staged={n:(stage/n).read_text(encoding='utf-8-sig') for n in current}
for n,s in current.items():assert hashlib.sha256(s.encode()).hexdigest()==manifest['source_sha256'][n], 'Control hash mismatch: '+n
for n,s in staged.items():assert hashlib.sha256(s.encode()).hexdigest()==manifest['candidate_sha256'][n], 'Candidate hash mismatch: '+n
for n,s in live.items():assert s==(staged[n] if production else current[n]), 'Current production does not match '+('candidate: ' if production else 'control: ')+n
candidate=live if production else staged
def function(s,start):
 a=s.index(start);b=s.index('{',a)+1;depth=1
 while depth:depth+=(s[b]=='{')-(s[b]=='}');b+=1
 return s[a:b]
unit=(core/'CvUnit.h').read_text(encoding='utf-8-sig');combat=(core/'CvUnitCombat.cpp').read_text(encoding='utf-8-sig');rules=(core/'CvStackingRules.cpp').read_text(encoding='utf-8-sig');rules_header=(core/'CvStackingRules.h').read_text(encoding='utf-8-sig')
container=unit[unit.index('struct SUnitIDValueContainer\n'):unit.index('\nnamespace std {',unit.index('struct SUnitIDValueContainer\n'))]
contents=candidate['CvDangerPlots.h'][candidate['CvDangerPlots.h'].index('struct CvDangerPlotContents\n'):candidate['CvDangerPlots.h'].index('//++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++',candidate['CvDangerPlots.h'].index('struct CvDangerPlotContents\n'))]
numerical_services=(root/'work/packet-probe-fixture-services.h').read_text(encoding='utf-8-sig')
base=numerical_services.replace('// ACTUAL_CONTAINER_INSERT',container,1)
# Bind every typed setting to its exact production enum ordinal/name. The
# deterministic setting service preserves configurable test toggles and default
# fallbacks; this is not another XML-loader test or a hardcoded hot-value mirror.
enum=function(rules_header,'enum HotSettingKey')+';'
names=re.search(r'const char\* const HOT_SETTING_NAMES\[CvStacking::HOT_SETTING_COUNT\] =\s*\{(.*?)\};',rules,re.S).group(1)
enum_names=re.findall(r'HOT_([A-Za-z][A-Za-z0-9_]*)\s*[,=]',enum)
name_values=re.findall(r'"([^"]+)"',names)
assert enum_names==name_values and len(name_values)==24,'Revisit numerical typed-key service after enum/name changes'
typed='namespace CvStacking{'+enum+'static const char*const numericalHotNames[HOT_SETTING_COUNT]={'+names+'};int GetIntByKey(HotSettingKey k,int fallback){return k<0||k>=HOT_SETTING_COUNT?fallback:GetInt(numericalHotNames[k],fallback);}}\n'
base+='\n'+typed+contents+'\nstatic bool MOD_GLOBAL_SUBS_UNDER_ICE_IMMUNITY=false;const int FEATURE_ICE=-1;\n'
math_bindings={}
for file,sigs in [('CvUnitCombat.cpp',['static bool IsStackCombatCandidate(','static void GetStackExchange(',
 'const CvUnit* CvUnitCombat::SelectStackDefender(','const CvUnit* CvUnitCombat::SelectStackDefenderForCity(',
 'std::vector<std::pair<const CvUnit*, int> > CvUnitCombat::GetStackCollateralDamage(']),
 ('CvDangerPlots.cpp',['static int StackAirStrikeChance(','static int StackExpectedStrikeDamage(',
 'static int SimulateStackCityThreats(','int CvDangerPlotContents::GetStackDangerFromOutcome(',
 'int CvDangerPlotContents::GetStackDanger(','void CvDangerPlotContents::GetStackDangerOutcome('])]:
 actual=combat if file=='CvUnitCombat.cpp' else candidate[file]
 pinned=subprocess.check_output(['git','show',manifest['control']+':CvGameCoreDLL_Expansion2/'+file],cwd=root).decode('utf-8-sig').replace('\r\n','\n')
 for sig in sigs:
  body=function(actual,sig);assert body==function(pinned,sig),'Original math changed: '+sig
  base+='\n'+body;math_bindings[sig]=hashlib.sha256(body.encode()).hexdigest()
base=base.replace('static size_t allocationCalls=0;', 'static size_t allocationCalls=0;static bool failAllocation=false;',1)
base=base.replace('++allocationCalls;void*p=malloc(n?n:1);','++allocationCalls;if(failAllocation)throw std::bad_alloc();void*p=malloc(n?n:1);',1)
headers='''#define NOMINMAX
#include <windows.h>
#undef near
#undef far
#include <unordered_map>
#include <deque>
#include <cstdarg>
'''
services=r'''
const int NO_PLAYER=-1,NO_TEAM=-1;static bool MOD_EVENTS_CAN_MOVE_INTO=false;
namespace CvStackingStrengthCache{volatile LONG fixtureEpoch=1;long SceneEpoch(){return InterlockedCompareExchange(&fixtureEpoch,0,0);}void Invalidate(){InterlockedIncrement(&fixtureEpoch);}}
static unsigned readerCalls=0,refreshCalls=0,rawSequences=0;
struct CvDangerPlots{
 vector<CvDangerPlotContents>m_DangerPlots;bool m_bDirty;CvDangerPlots():m_bDirty(false){m_DangerPlots.resize(1);}
 bool IsDirty()const{return m_bDirty;}void UpdateDanger(){++refreshCalls;m_bDirty=false;CvStackingStrengthCache::Invalidate();}
 bool AppendStackDangerProbeSources(const CvPlot&p,int*w,unsigned c,unsigned&u)const{++readerCalls;return ActualProbeSources(p,w,c,u);}
 bool ActualProbeSources(const CvPlot&,int*,unsigned,unsigned&)const;
 int NativeStackDanger(const CvPlot&,const CvUnit*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&);
 int GetStackDanger(const CvPlot&p,const CvUnit*u,const vector<const CvUnit*>&r,const SUnitIDValueContainer&f,const SUnitIDValueContainer&e){++rawSequences;return NativeStackDanger(p,u,r,f,e);}
 bool GetStackDangerOutcome(const CvPlot&,const CvUnit*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&,SUnitIDValueContainer&,bool&,int&);
 bool TryGetStackDangerFromOutcome(const CvPlot&,const CvUnit*,const SUnitIDValueContainer&,const SUnitIDValueContainer&,bool,int&);
 bool TryGetFixedStackDanger(const CvPlot&,const CvUnit*,int&);
 const vector<int>*GetStackDangerDamageIDs(const CvPlot&);
};
static CvDangerPlots maps[4];CvDangerPlots*CvPlayer::GetDangerPlots()const{return &maps[id];}
struct CvTeam{bool open[4];bool IsAllowsOpenBordersToTeam(int t)const{return t>=0&&t<4&&open[t];}};static CvTeam teams[4];
#define GET_TEAM(x) teams[x]
int CvCity::getTeam()const{return players[owner].getTeam();}
int CvPlot::getTeam()const{return city?city->getTeam():(owner<0?NO_TEAM:players[owner].getTeam());}
struct Storage{int getSizeLimit()const{return 6000;}}gTactPosStorage;const int TACTSIM_MAX_UNITS=13;
namespace CvStackingDiagnostics{
 enum Part{PLAN_DANGER_KEY,PLAN_DANGER_LEAF};struct PlanSampleScope{PlanSampleScope(Part,bool=true){}void Finish(){}};
 struct State{bool enabled;unsigned depth;unsigned long serial;long epoch;};
 static __declspec(thread)State planSamples={false,0,0,1};static volatile LONG sampleEpoch=1;static unsigned records=0,maxRowBytes=0;static char lastRow[3072];
 static long ReadPlanSampleEpoch(){return InterlockedCompareExchange(&sampleEpoch,0,0);}
 void Record(int,PlayerTypes,const char*category,const char*format,...){++records;va_list a;va_start(a,format);_vsnprintf_s(lastRow,sizeof(lastRow),_TRUNCATE,format,a);va_end(a);maxRowBytes=std::max(maxRowBytes,(unsigned)strlen(lastRow));if(strcmp(category,"PLAN_PACKET_PROBE"))abort();}
 bool TryGetPlanSamplingContext(unsigned long&,long&);
}
'''
implementation='\n'.join(function(current['CvDangerPlots.cpp'],s) for s in [
 'const std::vector<int>& CvDangerPlotContents::GetStackDangerDamageIDs()',
 'bool CvDangerPlotContents::TryGetFixedStackDanger(',
 'int CvDangerPlots::GetStackDanger(',
 'bool CvDangerPlots::GetStackDangerOutcome(',
 'bool CvDangerPlots::TryGetStackDangerFromOutcome(',
 'bool CvDangerPlots::TryGetFixedStackDanger(',
 'const std::vector<int>* CvDangerPlots::GetStackDangerDamageIDs('])
implementation=implementation.replace('int CvDangerPlots::GetStackDanger(', 'int CvDangerPlots::NativeStackDanger(',1)
implementation+='\n'+function(candidate['CvDangerPlots.cpp'],'bool CvDangerPlots::AppendStackDangerProbeSources(').replace('AppendStackDangerProbeSources','ActualProbeSources',1)
implementation+='\n'+function(current['CvPlot.cpp'] if 'CvPlot.cpp' in current else (core/'CvPlot.cpp').read_text(encoding='utf-8-sig'),'bool CvPlot::isFriendlyCity(')
implementation+='\n'+function(current['CvTacticalAI.cpp'],'const CvUnit* TacticalAIHelpers::GetSimulatedGarrison(')
implementation+='\nnamespace CvStackingDiagnostics{\n'+function(candidate['CvStackingDiagnostics.cpp'],'bool TryGetPlanSamplingContext(')+'\n}\n'
tact=current['CvTacticalAI.cpp'];implementation+='\n'+tact[tact.index('struct StackForecastKey\n'):tact.index('// Bind immutable inputs only')]
implementation+='\n'+function(tact,'struct StackDangerOutcomeBatch\n')+';\n'
fragment=(root/'work/packet-probe-tactical-fragment.cpp').read_text(encoding='utf-8-sig')
assert fragment in candidate['CvTacticalAI.cpp']
implementation+='\n'+fragment+'\n'
implementation+='\n'+function(tact,'static int GetCachedStackDanger(').replace('GetCachedStackDanger','OriginalCachedStackDanger',1)
implementation+='\n'+function(candidate['CvTacticalAI.cpp'],'static int GetCachedStackDanger(')
tests=r'''
static unsigned checks=0,failures=0,leafCalls=0,mutation=0;static unsigned randomSeed=2817;
static unsigned Next(){randomSeed=randomSeed*1664525u+1013904223u;return randomSeed;}
static void Check(const char*n,bool okay){++checks;if(!okay){++failures;if(failures<20)printf("FAIL %s\n",n);}}
static void OnLeaf(){++leafCalls;if(mutation){unsigned m=mutation;mutation=0;if(m==1)CvStackingStrengthCache::Invalidate();else if(m==2)++gStackForecastRevision;else if(m==3)reverse(maps[0].m_DangerPlots[0].m_apUnits.begin(),maps[0].m_DangerPlots[0].m_apUnits.end());else if(m==4)InterlockedIncrement(&CvStackingDiagnostics::sampleEpoch);else if(m==5)throw 17;}}
static void Enable(bool on,unsigned long serial=7){using namespace CvStackingDiagnostics;planSamples.enabled=on;planSamples.depth=on?1:0;planSamples.serial=serial;planSamples.epoch=ReadPlanSampleEpoch();}
static void ResetPlayers(){for(int p=0;p<4;++p){players[p]=CvPlayer();players[p].id=players[p].team=p;maps[p]=CvDangerPlots();for(int q=0;q<4;++q){teams[p].open[q]=false;if(q!=p)players[p].enemies.push_back(q);}}}
static StackForecastKey ScalarKey(const CvUnit*u,const CvPlot*p,const vector<const CvUnit*>&r,const SUnitIDValueContainer&f,const SUnitIDValueContainer&e){StackForecastKey k;k.state.push_back(u->GetID());k.state.push_back(p->GetPlotIndex());k.state.push_back(f.GetValue(u->GetID()));k.state.push_back(CvStacking::GetCityProtection(p->getPlotCity()));AppendStackCandidates(k,r,f,!p->isCity()&&CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled,1)!=0);AppendStackDamageProjected(k,e,u,p);return k;}
static bool Selected(const CvUnit*u,const CvPlot*p,const vector<const CvUnit*>&r,const SUnitIDValueContainer&f,const SUnitIDValueContainer&e){StackForecastKey k=ScalarKey(u,p,r,f,e);PacketProbeCall c(u,p,r,f,e,k,true);bool result=c.state!=NULL;c.MarkRaw();return result;}
static unsigned FindSelected(const CvUnit*u,const CvPlot*p,const vector<const CvUnit*>&r,SUnitIDValueContainer&f,const SUnitIDValueContainer&e,int offset=0){for(unsigned i=1;i<50000;++i){f.SetValue(999,(int)i+offset);f.SetValue(r[0]->GetID(),((int)i+offset)%137);if(Selected(u,p,r,f,e))return i;}Check("selected cohort found",false);return 0;}
struct Snapshot{unsigned hits,misses,raw,builds,reuses,bypass,leaf,evictions;size_t bytes;vector<pair<vector<int>,int> >values;Snapshot():hits(gStackDangerHits),misses(gStackDangerMisses),raw(rawSequences),builds(gStackOutcomeBuilds),reuses(gStackOutcomeReuses),bypass(gStackOutcomeBypasses),leaf(leafCalls),evictions(gStackDangerEvictions),bytes(gStackKeyPayloadBytes){for(StackDangerForecasts::const_iterator i=gStackDangerForecasts.begin();i!=gStackDangerForecasts.end();++i)values.push_back(make_pair(i->first.state,i->second));sort(values.begin(),values.end());}bool operator==(const Snapshot&o)const{return hits==o.hits&&misses==o.misses&&raw==o.raw&&builds==o.builds&&reuses==o.reuses&&bypass==o.bypass&&leaf==o.leaf&&evictions==o.evictions&&bytes==o.bytes&&values==o.values;}};
struct Foreign{PacketProbeScope*scope;PacketProbeCall*call;PacketProbeState*owner;};
static DWORD WINAPI OtherThread(void*data){Foreign*x=(Foreign*)data;unsigned long serial=19;long epoch=3;Check("foreign sampler token false",!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)&&serial==19&&epoch==3);Enable(true,7);PacketProbeScope stranger(0,0);Check("foreign forecast cannot start probe",!stranger.state&&!gPacketProbeState);x->call->Finish();x->scope->Finish();Check("foreign finish cannot mutate owner payload",x->owner->busy&&x->call->state==x->owner&&x->scope->state==x->owner);return 0;}
int main(){
 Check("native x86",sizeof(void*)==4&&sizeof(unsigned long)==4);
 Check("fixed metadata bound",sizeof(PacketProbeState)<3*1024*1024&&PACKET_PROBE_SLOTS==128&&PACKET_PROBE_WORDS==512);
 ResetPlayers();CvPlot target(0),actorPlot(1);CvUnit units[5],actors[2];CvCity city(7,0,&target),enemyCity(8,1,&actorPlot);vector<const CvUnit*>roster;
 for(int i=0;i<5;++i){units[i]=CvUnit(10+i,0,&target);units[i].hp=500;units[i].maxHP=500;units[i].ranged=i%2!=0;players[0].units[10+i]=&units[i];roster.push_back(&units[i]);}
 for(int i=0;i<2;++i){actors[i]=CvUnit(44+i,1,&actorPlot);actors[i].ranged=i==0;actors[i].aoe=i;actors[i].collateralLimit=2;players[1].units[44+i]=&actors[i];}
 CvDangerPlotContents&contents=maps[0].m_DangerPlots[0];contents.m_pPlot=&target;contents.m_apUnits.push_back(make_pair(1,44));contents.m_apUnits.push_back(make_pair(1,45));players[1].cities[8]=&enemyCity;
 SUnitIDValueContainer empty;
 unsigned long serial=31;long epoch=29;Enable(false);Check("disabled token leaves outputs",!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)&&serial==31&&epoch==29);
 {StackForecastScope native;size_t a=allocationCalls;unsigned reads=readerCalls,rows=CvStackingDiagnostics::records;PacketProbeScope off(0,0);StackForecastKey k=ScalarKey(&units[0],&target,roster,empty,empty);a=allocationCalls;PacketProbeCall c(&units[0],&target,roster,empty,empty,k,true);c.MarkRaw();c.Finish();off.Finish();Check("inactive probe no allocation/source/record",!off.state&&!gPacketProbeState&&allocationCalls==a&&readerCalls==reads&&CvStackingDiagnostics::records==rows);}
 {StackForecastScope native;Enable(true);failAllocation=true;PacketProbeScope failed(0,0);failAllocation=false;Check("allocation failure safely skips metadata",!failed.state&&!gPacketProbeState);Enable(false);}
 // Original/staged whole scalar wrapper, actual field math, real cache/FIFO.
 for(int trial=0;trial<120;++trial){
  contents.m_apCities.clear();target.city=trial%3==0?&city:NULL;contents.m_iFogCount=trial%4;contents.m_iImprovementDamage=trial%11;contents.m_bFlatPlotDamage=trial%2!=0;city.hp=30+trial%170;city.garrison=&units[trial%5];if(trial%7==0)contents.m_apCities.push_back(make_pair(1,8));contents.InvalidateStackDangerDamageIDs();
  SUnitIDValueContainer friendly,enemy;for(int i=0;i<5;++i)friendly.SetValue(units[i].GetID(),(int)(Next()%100));friendly.SetValue(99,(int)Next()%20);enemy.SetValue(44,trial%30);enemy.SetValue(-8,trial%15);
  vector<int>expected,actual;Snapshot*reference=NULL;
  for(int pass=0;pass<2;++pass){rawSequences=leafCalls=0;StackForecastScope native;gStackEntryLimit=4;gStackKeyPayloadLimit=1200;Enable(pass!=0,trial+1);PacketProbeScope observation(0,0);StackImmutableEnemyDamageScope immutable(enemy);
   {StackDangerOutcomeBatch batch(&target,roster,friendly,enemy);for(int q=0;q<10;++q){int result=pass?GetCachedStackDanger(&units[q%5],&target,roster,friendly,enemy,&batch):OriginalCachedStackDanger(&units[q%5],&target,roster,friendly,enemy,&batch);(pass?actual:expected).push_back(result);} }
   if(!pass)reference=new Snapshot;else{Snapshot result;Check("all scalar outputs unchanged",expected==actual);Check("cache/FIFO/budget/build/sequence unchanged",*reference==result);delete reference;}
   Enable(false);
  }
 }
 target.city=NULL;contents.m_apCities.clear();contents.InvalidateStackDangerDamageIDs();contents.m_bFlatPlotDamage=false;
 // Reader proves duplicate/order preservation; it never refreshes dirty state.
 int words[512];unsigned used=0;unsigned refresh=refreshCalls;contents.m_apCities.push_back(make_pair(1,8));contents.m_apCities.push_back(make_pair(1,8));
 Check("const source reader exact ordered duplicates",maps[0].ActualProbeSources(target,words,512,used)&&used==10&&words[0]==2&&words[1]==1&&words[2]==44&&words[5]==2&&words[6]==1&&words[7]==8&&words[8]==1&&words[9]==8);
 maps[0].m_bDirty=true;used=0;Check("dirty reader does not refresh",!maps[0].ActualProbeSources(target,words,512,used)&&!used&&maps[0].m_bDirty&&refreshCalls==refresh);maps[0].m_bDirty=false;
 used=0;Check("source reader capacity rejects atomically",!maps[0].ActualProbeSources(target,words,9,used)&&used==0);used=513;Check("source reader invalid used count",!maps[0].ActualProbeSources(target,words,512,used));used=UINT_MAX-1;Check("source reader extreme remaining cannot overflow",!maps[0].ActualProbeSources(target,words,UINT_MAX,used)&&used==UINT_MAX-1);used=0;Check("source reader invalid null/index",!maps[0].ActualProbeSources(target,NULL,512,used)&&!maps[0].ActualProbeSources(CvPlot(-1),words,512,used)&&!maps[0].ActualProbeSources(CvPlot(1),words,512,used));
 contents.m_apCities.clear();contents.InvalidateStackDangerDamageIDs();
 {
  StackForecastScope native;Enable(true,700);PacketProbeScope scope(0,0);Check("active scope owns state",scope.state&&gPacketProbeState==scope.state);PacketProbeState&s=*scope.state;SUnitIDValueContainer friendly;
  unsigned selected=FindSelected(&units[0],&target,roster,friendly,empty);Check("cohort selects whole group",selected&&s.groups==1);
  for(int q=1;q<5;++q)Check("query identity omitted consistently",Selected(&units[q],&target,roster,friendly,empty));
  Check("five members one group/four first cross repeats",s.groups==1&&s.crossMember==4&&s.freshCrossMemberQueries==4);
  Selected(&units[0],&target,roster,friendly,empty);Check("same member classified separately",s.sameMember==1&&s.freshRepeatQueries==5);
  StackForecastKey k=ScalarKey(&units[0],&target,roster,friendly,empty);unsigned reads=readerCalls;size_t alloc=allocationCalls;{PacketProbeCall batchReuse(&units[0],&target,roster,friendly,empty,k,true);batchReuse.Finish();}Check("sampled queries allocate no metadata",allocationCalls==alloc&&readerCalls==reads+2&&s.batchReuseQueries==1);
  {PacketProbeCall attempt(&units[0],&target,roster,friendly,empty,k,true);++gStackOutcomeBuilds;attempt.MarkRaw();attempt.Finish();}Check("query vs attempted simulations clear",s.outcomeBuildAttempts==1&&s.rawCalls==7&&s.freshQueries==7);
  // A scalar hit returns before observation, including token/source reads.
  GetCachedStackDanger(&units[0],&target,roster,friendly,empty);unsigned misses=(unsigned)s.misses;reads=readerCalls;rawSequences=0;GetCachedStackDanger(&units[0],&target,roster,friendly,empty);Check("scalar hit performs no probe work",s.misses==misses&&readerCalls==reads&&rawSequences==0);
  // Reentrant pending observations cannot corrupt outer key/sources.
  {PacketProbeCall outer(&units[0],&target,roster,friendly,empty,k,true);Check("selected outer holds scratch",s.busy);vector<int>saved(s.key,s.key+s.count);PacketProbeCall inner(&units[1],&target,roster,friendly,empty,k,true);Check("nested callback suppressed without overwriting",!inner.state&&s.reentrant==1&&saved==vector<int>(s.key,s.key+s.count));outer.MarkRaw();}
  // Foreign Finish leaves original owning TLS untouched, even same serial.
  {PacketProbeCall pending(&units[0],&target,roster,friendly,empty,k,true);Foreign f={&scope,&pending,&s};HANDLE thread=CreateThread(NULL,0,OtherThread,&f,0,NULL);Check("foreign thread created",thread!=NULL);WaitForSingleObject(thread,INFINITE);CloseHandle(thread);pending.MarkRaw();pending.Finish();Check("owner can still finish same observation",!s.busy&&pending.state==NULL);}
  // Native sources can change order without changing raw projected IDs.
  for(int mode=0;mode<4;++mode){k=ScalarKey(&units[0],&target,roster,friendly,empty);PacketProbeCall pending(&units[0],&target,roster,friendly,empty,k,true);if(!pending.state){FindSelected(&units[0],&target,roster,friendly,empty);k=ScalarKey(&units[0],&target,roster,friendly,empty);PacketProbeCall valid(&units[0],&target,roster,friendly,empty,k,true);if(mode==0)reverse(contents.m_apUnits.begin(),contents.m_apUnits.end());if(mode==1)++gStackForecastRevision;if(mode==2)CvStackingStrengthCache::Invalidate();if(mode==3)maps[0].m_bDirty=true;unsigned before=(unsigned)s.invalidated;valid.Finish();Check("changed input invalidates pending observation",s.invalidated==before+1);}
   else{if(mode==0)reverse(contents.m_apUnits.begin(),contents.m_apUnits.end());if(mode==1)++gStackForecastRevision;if(mode==2)CvStackingStrengthCache::Invalidate();if(mode==3)maps[0].m_bDirty=true;unsigned before=(unsigned)s.invalidated;pending.Finish();Check("changed input invalidates pending observation",s.invalidated==before+1);}maps[0].m_bDirty=false;StackForecastContext();}
  Check("revision changes clear bounded metadata",s.clears>0);
  FindSelected(&units[0],&target,roster,friendly,empty);k=ScalarKey(&units[0],&target,roster,friendly,empty);
  {PacketProbeCall pending(&units[0],&target,roster,friendly,empty,k,true);InterlockedIncrement(&CvStackingDiagnostics::sampleEpoch);unsigned before=(unsigned)s.invalidated;pending.Finish();Check("runtime epoch cancels pending samples",s.invalidated==before+1);}
  unsigned rows=CvStackingDiagnostics::records;scope.Finish();Check("reset/toggle suppresses stale summary and releases",!gPacketProbeState&&!scope.state&&CvStackingDiagnostics::records==rows);Enable(false);
 }
 // FIFO diagnostic metadata is independent of every original result budget.
 {StackForecastScope native;Enable(true,800);PacketProbeScope scope(0,0);PacketProbeState&s=*scope.state;SUnitIDValueContainer f;for(unsigned group=0;group<150;++group)FindSelected(&units[0],&target,roster,f,empty,(int)group*50000);Check("fixed slot FIFO evicts only metadata",s.groups==150&&s.evictions==22);Check("bounded retained key bytes",s.keyBytes<=128*512*sizeof(int)&&s.peakKeyBytes<=128*512*sizeof(int));Check("union output estimate bounded",s.outputUpperBytes<=128*(128+32)*sizeof(pair<int,int>));unsigned rows=CvStackingDiagnostics::records;scope.Finish();Check("one bounded summary row",CvStackingDiagnostics::records==rows+1&&strlen(CvStackingDiagnostics::lastRow)<3072&&strstr(CvStackingDiagnostics::lastRow,"no stride-scaled saved simulations")!=NULL);Enable(false);}
 // Unsupported metadata inputs never change native pools or dereference
 // malformed roster entries. Use a selected original scalar prefix so these
 // tests exercise the full admission checks rather than miss the prefilter.
 {StackForecastScope native;Enable(true,900);PacketProbeScope scope(0,0);PacketProbeState&s=*scope.state;SUnitIDValueContainer f;FindSelected(&units[0],&target,roster,f,empty);StackForecastKey k=ScalarKey(&units[0],&target,roster,f,empty);unsigned before=(unsigned)s.fallback;
  {PacketProbeCall c(NULL,&target,roster,f,empty,k,true);Check("null member rejected",!c.state);}Check("null counted as unsupported",s.fallback==before+1);
  {PacketProbeCall c(&units[0],NULL,roster,f,empty,k,true);Check("null target rejected",!c.state);}
  {vector<const CvUnit*>solo(1,&units[0]);PacketProbeCall c(&units[0],&target,solo,f,empty,k,true);Check("singleton keeps original scalar path",!c.state);}
  {CvUnit outside(93,0,&target);players[0].units[93]=&outside;PacketProbeCall c(&outside,&target,roster,f,empty,k,true);Check("outside queried native identity rejected",!c.state);players[0].units.erase(93);}
  {vector<const CvUnit*>mixed=roster;CvUnit other(97,2,&target);mixed[4]=&other;PacketProbeCall c(&units[0],&target,mixed,f,empty,k,true);Check("mixed-owner roster rejected",!c.state);}
  {vector<const CvUnit*>nullMember=roster;nullMember[3]=NULL;PacketProbeCall c(&units[0],&target,nullMember,f,empty,k,true);Check("null roster member rejected",!c.state);}
  {vector<const CvUnit*>aliases=roster;CvUnit clone=units[4];aliases[4]=&clone;PacketProbeCall c(&units[0],&target,aliases,f,empty,k,true);Check("aliased native identity rejected",!c.state);}
  {units[0].cargo=true;PacketProbeCall c(&units[0],&target,roster,f,empty,k,true);Check("embarked/nonnative queried member rejected",!c.state);units[0].cargo=false;}
  {units[0].civilian=true;PacketProbeCall c(&units[0],&target,roster,f,empty,k,true);Check("civilian queried member rejected",!c.state);units[0].civilian=false;}
  {SUnitIDValueContainer malformed=f;malformed.m_aExtraStorage.push_back(malformed.m_aExtraStorage[0]);PacketProbeCall c(&units[0],&target,roster,malformed,empty,k,true);Check("malformed friendly duplicate IDs rejected",!c.state);}
  {SUnitIDValueContainer malformed;malformed.SetValue(44,1);malformed.SetValue(45,2);malformed.m_aExtraStorage.push_back(make_pair(44,3));PacketProbeCall c(&units[0],&target,roster,f,malformed,k,true);Check("malformed enemy duplicate IDs rejected",!c.state);}
  {SUnitIDValueContainer wide;for(int i=0;i<129;++i)wide.SetValue(200+i,i);PacketProbeCall c(&units[0],&target,roster,wide,empty,k,true);Check("injury pair bound rejects without truncation",!c.state);}
  {vector<const CvUnit*>wide=roster;CvUnit extra[33];for(int i=0;i<33;++i){extra[i]=CvUnit(200+i,0,&target);players[0].units[200+i]=&extra[i];wide.push_back(&extra[i]);}PacketProbeCall c(&units[0],&target,wide,f,empty,k,true);Check("distinct-member mask bound",!c.state);for(int i=0;i<33;++i)players[0].units.erase(200+i);}
  {vector<const CvUnit*>wide=roster;wide.insert(wide.end(),300,&units[0]);PacketProbeCall c(&units[0],&target,wide,f,empty,k,true);Check("ordered duplicate roster key word bound",!c.state);}
  {vector<pair<int,int> >old=contents.m_apUnits;contents.m_apUnits.insert(contents.m_apUnits.end(),300,make_pair(1,44));PacketProbeCall c(&units[0],&target,roster,f,empty,k,true);Check("ordered source bound rejects without truncation",!c.state);contents.m_apUnits=old;}
  // Missing versus explicit zero entries share the numerical group, while
  // the first admitted group's output-pair upper estimate remains qualified.
  unsigned groups=(unsigned)s.groups;SUnitIDValueContainer zeros=f;zeros.SetValue(777,0);Check("stored zero aliases missing numerical injury",Selected(&units[1],&target,roster,zeros,empty)&&s.groups==groups);
  // Hash collisions never authorize metadata equality: forge the same hash
  // for a different full key, and verify it cannot merge into that slot.
  s.Clear();{PacketProbeCall c(&units[0],&target,roster,f,empty,k,true);Check("collision test selected",c.state!=NULL);PacketProbeSlot&wrong=s.slots[0];wrong.used=true;wrong.city=false;wrong.count=s.count;wrong.hash=PacketProbeHash(s.key,s.count,0);wrong.seen=wrong.fresh=0;wrong.outputUpper=0;memcpy(wrong.words,s.key,s.count*sizeof(int));++wrong.words[s.count-1];s.next=1;s.keyBytes=wrong.count*sizeof(int);unsigned oldGroups=(unsigned)s.groups;c.MarkRaw();c.Finish();Check("full equality rejects forged hash collision",s.groups==oldGroups+1&&s.slots[1].used&&s.slots[0].words[s.count-1]!=s.slots[1].words[s.count-1]);}
  Check("unsupported probe never admits gameplay cache",gStackDangerForecasts.empty()&&gStackKeyPayloadBytes==0&&gStackDangerHits==0&&gStackDangerMisses==0);
  scope.Finish();Enable(false);
 }
 // Exact shared inputs include off-roster AA injuries, city/field mode and
 // raw source order/owner aliases, even when the original scalar tail is the
 // same. Inspect the fully prepared fixed scratch after the cheap prefilter;
 // cohort selection itself is allowed to differ for unequal complete keys.
 {StackForecastScope native;Enable(true,901);PacketProbeScope scope(0,0);PacketProbeState&s=*scope.state;SUnitIDValueContainer f;FindSelected(&units[0],&target,roster,f,empty);StackForecastKey k=ScalarKey(&units[0],&target,roster,f,empty);vector<int>original;{PacketProbeCall c(&units[0],&target,roster,f,empty,k,true);original.assign(s.key,s.key+s.count);}
  SUnitIDValueContainer aa=f;aa.SetValue(888,47);{PacketProbeCall c(&units[0],&target,roster,aa,empty,k,true);Check("off-roster AA exact numerical key",original!=vector<int>(s.key,s.key+s.count));}
  reverse(contents.m_apUnits.begin(),contents.m_apUnits.end());{PacketProbeCall c(&units[0],&target,roster,f,empty,k,true);Check("ordered sources fresh despite same raw ID set",original!=vector<int>(s.key,s.key+s.count));}reverse(contents.m_apUnits.begin(),contents.m_apUnits.end());
  contents.m_apUnits[0].first=2;{PacketProbeCall c(&units[0],&target,roster,f,empty,k,true);Check("raw source owner aliases remain distinct",original!=vector<int>(s.key,s.key+s.count));}contents.m_apUnits[0].first=1;
  target.city=&city;city.garrison=&units[0];{PacketProbeCall c(&units[0],&target,roster,f,empty,k,true);Check("native friendly city mode exact key",original!=vector<int>(s.key,s.key+s.count));}target.city=NULL;
  vector<const CvUnit*>ordered=roster;reverse(ordered.begin(),ordered.end());{PacketProbeCall c(&units[0],&target,ordered,f,empty,k,true);Check("candidate order/ties not canonicalized away",original!=vector<int>(s.key,s.key+s.count));}
  scope.Finish();Enable(false);
 }
 // Invalidation inside original raw computation never repeats that method.
 // There are two native attack sources; the full graph still runs once, and
 // pending diagnostic metadata is discarded without altering its return.
 for(unsigned mode=1;mode<=4;++mode){if(mode==3)continue;StackForecastScope native;Enable(true,1000+mode);PacketProbeScope scope(0,0);SUnitIDValueContainer f;FindSelected(&units[0],&target,roster,f,empty);int expected=contents.GetStackDanger(&units[0],roster,f,empty);rawSequences=0;mutation=mode;int got=GetCachedStackDanger(&units[0],&target,roster,f,empty);Check("callback invalidation keeps original scalar once",got==expected&&rawSequences==1&&mutation==0&&scope.state->invalidated>0);if(mode!=4)Check("invalidated original cache admission unchanged",gStackDangerForecasts.empty());scope.Finish();Enable(false);}
 {StackForecastScope native;Enable(true);PacketProbeScope scope(0,0);SUnitIDValueContainer f;FindSelected(&units[0],&target,roster,f,empty);StackForecastKey k=ScalarKey(&units[0],&target,roster,f,empty);try{PacketProbeCall call(&units[0],&target,roster,f,empty,k,true);throw 17;}catch(int){}Check("early exception RAII releases scratch",!scope.state->busy);scope.Finish();Enable(false);}
 {StackForecastScope native;Enable(true);MOD_EVENTS_CAN_MOVE_INTO=true;PacketProbeScope scripted(0,0);Check("script callbacks conservatively bypass scope",!scripted.state);MOD_EVENTS_CAN_MOVE_INTO=false;CvStackingDiagnostics::planSamples.depth=2;PacketProbeScope nested(0,0);Check("nested sampler bypass scope",!nested.state);Enable(false);}
 {StackForecastScope native;Enable(true,ULONG_MAX);PacketProbeScope scope(INT_MIN,INT_MIN);PacketProbeState&s=*scope.state;s.thread=ULONG_MAX;
  s.misses=s.prefilter=s.cohort=s.groups=s.repeats=s.sameMember=s.crossMember=s.freshQueries=s.batchReuseQueries=s.freshRepeatQueries=s.freshCrossMemberQueries=s.rawCalls=s.outcomeBuildAttempts=s.fallback=s.oversized=s.unavailable=s.invalidated=s.reentrant=s.evictions=s.clears=s.fieldGroups=s.cityGroups=s.keyBytes=s.peakKeyBytes=s.outputUpperBytes=s.peakOutputUpperBytes=~(unsigned __int64)0;scope.Finish();Check("maximum numeric summary row does not truncate",strlen(CvStackingDiagnostics::lastRow)<3071&&strstr(CvStackingDiagnostics::lastRow,"not actual retained capacity")!=NULL);Enable(false);}
 printf("packet probe actual source: %u checks,%u failures; fixed metadata %u bytes; maximum formatted row %u bytes; original field/scalar/FIFO sequences unchanged; one metadata row per PLAN\n",checks,failures,(unsigned)sizeof(PacketProbeState),CvStackingDiagnostics::maxRowBytes);return failures?1:0;
}
'''
code=headers+base+services+implementation+tests
(out/'test.cpp').write_text(code,encoding='utf-8')
if '--emit-only' in sys.argv:print('Packet probe fixture emitted; no compilation');sys.exit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe';build=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(build.stdout+build.stderr)
if build.returncode:print(build.stdout+build.stderr);sys.exit(build.returncode)
run=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(run.stdout+run.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,control=manifest['control'],production_untouched=True,bound_current_production=production,five_file_reverse_strip=True,current_immutable_enemy_scope_included=True,current_five_file_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in live.items()},math_body_sha256=math_bindings,typed_key_names_bound=name_values,no_generated_scaffold_dependency=True,fixture_sha256=hashlib.sha256(code.encode()).hexdigest(),scope='Actual current/staged observer/token/const reader and pinned original scalar wrapper; complete actual forecast FIFO/cache/batch/key/immutable-fragment code; pinned-equivalent current field/city/air/selector/exchange/collateral graph with deterministic native strength/damage/setting services. All 24 typed names match actual enum ordinals; original math byte-identical to DLL73. No native overlap, profiler overhead or end-turn improvement claim.'),indent=2))
sys.exit(run.returncode)
