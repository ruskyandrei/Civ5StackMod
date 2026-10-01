"""Actual callback-safe DLL85 two-line loan differential; no core/game writes.

Prerequisite: stage-immediate-forecast-borrow.py. --production binds the entire
adopted Tactical file plus ten unchanged safety/math files to the reviewed
candidate. Numerical engine services are deterministic; Context, the provider,
the complete strength module, both wrapper/cache modules and all extracted
field/city/air/selector/collateral bodies are actual pinned85 source.
"""
from pathlib import Path
import ast,hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2'
out=root/'work/immediate-forecast-borrow-regression';out.mkdir(exist_ok=True)
stage=root/'work/immediate-forecast-borrow-stage';proof=json.loads((stage/'manifest.json').read_text())
production='--production' in sys.argv
original={n:subprocess.check_output(['git','show',proof['control']+':CvGameCoreDLL_Expansion2/'+n],cwd=root).decode('utf-8-sig').replace('\r\n','\n') for n in proof['original_whole_files_sha256']}
candidate=dict(original);candidate['CvTacticalAI.cpp']=(stage/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
live={n:(core/n).read_text(encoding='utf-8-sig') for n in original}
for n in original:
 assert hashlib.sha256(original[n].encode()).hexdigest()==proof['original_whole_files_sha256'][n],'Pinned original drift: '+n
 assert hashlib.sha256(candidate[n].encode()).hexdigest()==proof['candidate_whole_files_sha256'][n],'Reviewed candidate drift: '+n
 assert live[n]==(candidate[n] if production else original[n]),'Whole current '+('candidate' if production else 'control')+' mismatch: '+n
if production:candidate=live
old,new=original['CvTacticalAI.cpp'],candidate['CvTacticalAI.cpp']
assert new.replace('bool cacheable = query.scratch != NULL || StackForecastContext();','bool cacheable = StackForecastContext();')==old
assert new.count('bool cacheable = query.scratch != NULL || StackForecastContext();')==2

# Reuse only tracked extraction/services, never an old generated C++ fixture or
# a generator's current-production switch. Its strict math equality now pins85.
template=(root/'work/test-packet-probe.py').read_text(encoding='utf-8-sig')
block=template[template.index('def function('):template.index("headers='''")]
scope=dict(root=root,core=core,current=original,candidate=candidate,manifest={'control':proof['control']},subprocess=subprocess,hashlib=hashlib,re=re)
exec(compile(block,'pinned85 complete numerical extraction','exec'),scope)
function=scope['function'];base=scope['base'];math_bindings=scope['math_bindings']
values={}
for node in ast.parse(template).body:
 if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
  for target in node.targets:
   if isinstance(target,ast.Name):values[target.id]=node.value.value
headers,services=values['headers'],values['services']
epoch_stub='namespace CvStackingStrengthCache{volatile LONG fixtureEpoch=1;long SceneEpoch(){return InterlockedCompareExchange(&fixtureEpoch,0,0);}void Invalidate(){InterlockedIncrement(&fixtureEpoch);}}'
assert services.count(epoch_stub)==1;services=services.replace(epoch_stub,'',1)
services=services.replace('const int NO_PLAYER=-1,NO_TEAM=-1;static bool MOD_EVENTS_CAN_MOVE_INTO=false;','const int NO_PLAYER=-1,NO_TEAM=-1;',1)
# Explicit native world services for the real provider: mutable base/heavy/
# morale fields, player enumeration, all seven options and the actual lock.
native_services=r'''
const int MAX_PLAYERS=4;
static bool MOD_EVENTS_CAN_MOVE_INTO=false,MOD_EVENTS_AIRLIFT=false,MOD_EVENTS_SEALIFT=false,MOD_EVENTS_UNIT_RANGEATTACK=false,MOD_EVENTS_CITY_BOMBARD=false,MOD_EVENTS_REBASE=false,MOD_EVENTS_UNIT_ACTIONS=false;
static bool gameLock=true;
struct FixtureDLL{bool HasGameCoreLock()const{return gameLock;}}fixtureDLL;FixtureDLL*gDLL=&fixtureDLL;
static void OnUnitLookup();
'''
base=base.replace('bool defend,cargo,flank,flankTarget,anti;','bool defend,cargo,flank,flankTarget,anti,heavy;int morale;',1)
base=base.replace('anti(false),defense(25)','anti(false),heavy(false),morale(0),defense(25)',1)
base=base.replace('int GetID()const{return id;}','bool IsCanHeavyCharge()const{return heavy;}int GetMoraleBreakChance()const{return morale;}\n int GetID()const{return id;}',1)
base=base.replace('const CvUnit*getUnit(int i)const{','const CvUnit*getUnit(int i)const{OnUnitLookup();',1)
base=base.replace('int GetID()const{return id;}int getTeam()const{return team;}bool IsAtWarWith(int p)const{',r'''const CvUnit*firstUnit(int*cursor)const{*cursor=0;return units.empty()?NULL:units.begin()->second;}
 const CvUnit*nextUnit(int*cursor)const{++*cursor;map<int,CvUnit*>::const_iterator it=units.begin();for(int i=0;i<*cursor&&it!=units.end();++i)++it;return it==units.end()?NULL:it->second;}
 int GetID()const{return id;}int getTeam()const{return team;}bool IsAtWarWith(int p)const{''',1)
assert 'firstUnit(int*cursor)' in base and 'bool IsCanHeavyCharge()const' in base
# UpdateDanger is an engine service here; mirror the actual85 outer suspension
# around any rebuild/callback, not an invented always-safe Context.
services=services.replace('void UpdateDanger(){++refreshCalls;','void UpdateDanger(){CvStackingStrengthCache::PreviewSuspension callbackSuspension;++refreshCalls;',1)
services=services.replace('bool ActualProbeSources(const CvPlot&,int*,unsigned,unsigned&)const;','bool ActualProbeSources(const CvPlot&,int*,unsigned,unsigned&)const;\n bool AppendStackDangerCacheDescriptor(const CvPlot&,int*,unsigned,unsigned&)const;',1)
services=services.replace(' bool TryGetPlanSamplingContext(unsigned long&,long&);',' bool TryGetPlanSamplingContext(unsigned long&serial,long&epoch){if(!planSamples.enabled||planSamples.depth!=1||planSamples.epoch!=ReadPlanSampleEpoch())return false;serial=planSamples.serial;epoch=planSamples.epoch;return true;}',1)
strength_header=original['CvStackingStrengthCache.h'].replace('#pragma once','')
strength_module='\n'.join(line for line in original['CvStackingStrengthCache.cpp'].splitlines() if line not in ('#include "CvGameCoreDLLPCH.h"','#include "CvStackingStrengthCache.h"','#include "LintFree.h"'))
common='\n'.join(function(original['CvDangerPlots.cpp'],sig) for sig in ('const std::vector<int>& CvDangerPlotContents::GetStackDangerDamageIDs()', 'bool CvDangerPlotContents::TryGetFixedStackDanger(', 'int CvDangerPlots::GetStackDanger(', 'bool CvDangerPlots::GetStackDangerOutcome(', 'bool CvDangerPlots::TryGetStackDangerFromOutcome(', 'bool CvDangerPlots::TryGetFixedStackDanger(', 'const std::vector<int>* CvDangerPlots::GetStackDangerDamageIDs(', 'bool CvDangerPlots::AppendStackDangerCacheDescriptor('))
common=common.replace('int CvDangerPlots::GetStackDanger(','int CvDangerPlots::NativeStackDanger(',1)
common+='\n'+function(original['CvDangerPlots.cpp'],'bool CvDangerPlots::AppendStackDangerProbeSources(').replace('AppendStackDangerProbeSources','ActualProbeSources',1)
common+='\n'+function(original['CvPlot.cpp'],'bool CvPlot::isFriendlyCity(')+'\n'+function(old,'const CvUnit* TacticalAIHelpers::GetSimulatedGarrison(')

def cache_module(text):
 value=text[text.index('struct StackForecastKey\n'):text.index('// Bind immutable inputs only')]
 value+='\n'+function(text,'struct StackDangerOutcomeBatch\n')+';\n'
 value+='\n'+text[text.index('static bool AppendUniquePacketDamage('):text.index('static int GetCachedStackDanger(')]
 value+='\n'+function(text,'static int GetCachedStackDanger(')
 start=text.index('static int GetCachedStackDanger(')
 value+='\n'+function(text[text.index('static const CvUnit* SelectCachedStackDefender(',start):],'static const CvUnit* SelectCachedStackDefender(')
 return value
implementation=common
for namespace,text in [('Baseline',old),('Trial',new)]:
 body=cache_module(text)
 context=function(body,'static bool StackForecastContext(')
 body=body.replace(context,context.replace('{','{\n ++fixtureContextCalls;',1),1)
 ctor=function(body,'StackForecastQuery(StackForecastKey& buffer,bool& inUse):')
 body=body.replace(ctor,ctor.replace('key.state.clear();','key.state.clear();\n  if(fixtureInvalidateLoan){fixtureInvalidateLoan=false;CvStackingStrengthCache::Invalidate();}',1),1)
 implementation+='\nnamespace '+namespace+'{\nstatic unsigned fixtureContextCalls=0;static bool fixtureInvalidateLoan=false;\n'+body+'\n}\n'

tests=r'''
static unsigned checks=0,failures=0,leafCalls=0,seed=728199,lookupMutation=0,leafMutation=0,providerCalls=0,validationCalls=0;
static unsigned Next(){seed=seed*1664525u+1013904223u;return seed;}
static void Check(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<30)printf("FAIL %s\n",n);}}
static void OnUnitLookup(){if(lookupMutation){lookupMutation=0;CvStackingStrengthCache::Invalidate();}}
static void OnLeaf(){++leafCalls;if(leafMutation){leafMutation=0;CvStackingStrengthCache::Invalidate();}}
static bool ActualProvider(unsigned int&flags,bool scan){if(scan)++providerCalls;else ++validationCalls;return Baseline::StackPreviewCallbackCapabilities(flags,scan);}
static bool ActualInputs(const vector<const CvUnit*>&roster){vector<CvUnit*>inputs;for(size_t i=0;i<roster.size();++i)inputs.push_back(const_cast<CvUnit*>(roster[i]));return Baseline::StackPreviewInputsSupported(inputs);}
static void Reset(){gameLock=true;MOD_EVENTS_CAN_MOVE_INTO=MOD_EVENTS_AIRLIFT=MOD_EVENTS_SEALIFT=MOD_EVENTS_UNIT_RANGEATTACK=MOD_EVENTS_CITY_BOMBARD=MOD_EVENTS_REBASE=MOD_EVENTS_UNIT_ACTIONS=false;for(int p=0;p<4;++p){players[p]=CvPlayer();players[p].id=players[p].team=p;maps[p]=CvDangerPlots();for(int q=0;q<4;++q){teams[p].open[q]=false;if(p!=q)players[p].enemies.push_back(q);}}}
static void Limits(size_t entries,size_t bytes){Baseline::gStackEntryLimit=Trial::gStackEntryLimit=entries;Baseline::gStackKeyPayloadLimit=Trial::gStackKeyPayloadLimit=bytes;}
struct Snapshot{
 unsigned hits,misses,evictions,builds,reuses,packetHits,packetBuilds;size_t bytes,defenders;vector<pair<vector<int>,pair<int,vector<pair<int,int> > > > >values;
 template<class Map>void Read(const Map&m){for(typename Map::const_iterator i=m.begin();i!=m.end();++i)values.push_back(make_pair(i->first.state,make_pair(i->second.scalar,i->second.memberScores)));sort(values.begin(),values.end());}
 bool operator==(const Snapshot&o)const{return hits==o.hits&&misses==o.misses&&evictions==o.evictions&&builds==o.builds&&reuses==o.reuses&&packetHits==o.packetHits&&packetBuilds==o.packetBuilds&&bytes==o.bytes&&defenders==o.defenders&&values==o.values;}
};
static Snapshot SnapshotOld(){Snapshot s;s.hits=Baseline::gStackDangerHits;s.misses=Baseline::gStackDangerMisses;s.evictions=Baseline::gStackDangerEvictions;s.builds=Baseline::gStackOutcomeBuilds;s.reuses=Baseline::gStackOutcomeReuses;s.packetHits=Baseline::gStackPacketHits;s.packetBuilds=Baseline::gStackPacketBuilds;s.bytes=Baseline::gStackKeyPayloadBytes;s.defenders=Baseline::gStackDefenderForecasts.size();s.Read(Baseline::gStackDangerForecasts);return s;}
static Snapshot SnapshotNew(){Snapshot s;s.hits=Trial::gStackDangerHits;s.misses=Trial::gStackDangerMisses;s.evictions=Trial::gStackDangerEvictions;s.builds=Trial::gStackOutcomeBuilds;s.reuses=Trial::gStackOutcomeReuses;s.packetHits=Trial::gStackPacketHits;s.packetBuilds=Trial::gStackPacketBuilds;s.bytes=Trial::gStackKeyPayloadBytes;s.defenders=Trial::gStackDefenderForecasts.size();s.Read(Trial::gStackDangerForecasts);return s;}
struct ForeignArgs{const CvUnit*unit;const CvPlot*plot;const vector<const CvUnit*>*roster;};
static DWORD WINAPI Foreign(void*p){ForeignArgs*a=(ForeignArgs*)p;SUnitIDValueContainer none;unsigned hits=Trial::gStackDangerHits;size_t bytes=Trial::gStackKeyPayloadBytes;Trial::GetCachedStackDanger(a->unit,a->plot,*a->roster,none,none);return hits==Trial::gStackDangerHits&&bytes==Trial::gStackKeyPayloadBytes?0:1;}
int main(){
 Check("native32",sizeof(void*)==4);
 CvPlot target(0),nearby(1);CvCity city(7,0,&target),enemyCity(8,1,&nearby);CvUnit units[6],actors[9];
 for(int state=0;state<320;++state){Reset();CvDangerPlotContents&c=maps[0].m_DangerPlots[0];c.m_pPlot=&target;c.m_iFogCount=state%5;c.m_iImprovementDamage=state%17;c.m_bFlatPlotDamage=state%2!=0;target.city=state%3==0?&city:NULL;city.hp=20+Next()%280;city.protection=Next()%91;CvStacking::enabled=state%11!=0;CvStacking::selectionEnabled=state%7!=0;vector<const CvUnit*>r;SUnitIDValueContainer f,e;
  for(int i=0;i<6;++i){units[i]=CvUnit(i==0?0:i==1?-8:10+i,0,&target);units[i].hp=25+Next()%100;units[i].maxHP=units[i].hp+Next()%50;units[i].ranged=Next()%2!=0;units[i].defense=10+Next()%70;units[i].anti=Next()%2!=0;units[i].flankTarget=Next()%2!=0;units[i].terrainIgnore=Next()%2!=0;units[i].featureIgnore=Next()%2!=0;units[i].chance=Next()%151;units[i].domain=state%2&&i==5?DOMAIN_AIR:DOMAIN_LAND;players[0].units[units[i].id]=&units[i];players[0].possible.push_back(make_pair(units[i].id,0));if(i<5)r.push_back(&units[i]);f.SetValue(units[i].id,(int)(Next()%141)-10);}city.garrison=&units[state%5];if(state%4==0)r.push_back(&units[1]);if(state%7==0)reverse(r.begin(),r.end());
  for(int i=0;i<9;++i){actors[i]=CvUnit(i%5,1+i%2,&nearby);actors[i].ranged=Next()%2!=0;actors[i].domain=state%2&&i%4==0?DOMAIN_AIR:DOMAIN_LAND;actors[i].flank=Next()%2!=0;actors[i].aoe=Next()%4;actors[i].collateralLimit=Next()%5;actors[i].evasion=Next()%101;actors[i].strength=30+Next()%80;players[actors[i].owner].units[actors[i].id]=&actors[i];c.m_apUnits.push_back(make_pair(actors[i].owner,actors[i].id));e.SetValue(actors[i].id,(int)(Next()%71));}players[1].cities[8]=&enemyCity;c.m_apCities.push_back(make_pair(1,8));if(state%5==0)c.m_apCities.push_back(make_pair(1,8));
  CvStackingStrengthCache::Scope proof(128,ActualProvider);bool supported=ActualInputs(r);Baseline::StackForecastScope old(supported);Trial::StackForecastScope current(supported);Limits(5+state%6,500+state%8*250);Baseline::StackImmutableEnemyDamageScope oldDamage(e);Trial::StackImmutableEnemyDamageScope newDamage(e);
  for(int q=0;q<18;++q){const CvUnit*u=&units[q%6];int mean=c.GetStackDanger(u,r,f,e);int a=Baseline::GetCachedStackDanger(u,&target,r,f,e),b=Trial::GetCachedStackDanger(u,&target,r,f,e);Check("full numeric field/city/air/duplicate outcome exact",mean==a&&a==b);Check("exact keys/scalar/packets/FIFO/capacity/work counters",SnapshotOld()==SnapshotNew());}
 }
 Reset();target.city=NULL;CvStacking::enabled=CvStacking::selectionEnabled=true;vector<const CvUnit*>r;SUnitIDValueContainer none;
 for(int i=0;i<5;++i){units[i]=CvUnit(10+i,0,&target);units[i].hp=units[i].maxHP=500;players[0].units[10+i]=&units[i];r.push_back(&units[i]);}CvDangerPlotContents&c=maps[0].m_DangerPlots[0];c.m_pPlot=&target;actors[0]=CvUnit(44,1,&nearby);actors[0].ranged=true;actors[0].collateralLimit=0;players[1].units[44]=&actors[0];c.m_apUnits.push_back(make_pair(1,44));
 {CvStackingStrengthCache::Scope absent(128);Baseline::StackForecastScope old(true);Trial::StackForecastScope current(true);Baseline::fixtureContextCalls=Trial::fixtureContextCalls=0;int a=Baseline::GetCachedStackDanger(r[0],&target,r,none,none),b=Trial::GetCachedStackDanger(r[0],&target,r,none,none);Check("missing real provider is unsupported and private",a==b&&Baseline::fixtureContextCalls==Trial::fixtureContextCalls&&Baseline::gStackDangerForecasts.empty()&&Trial::gStackDangerForecasts.empty());}
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope current(true);Baseline::GetCachedStackDanger(r[0],&target,r,none,none);Trial::GetCachedStackDanger(r[0],&target,r,none,none);Baseline::fixtureContextCalls=Trial::fixtureContextCalls=0;unsigned validate=validationCalls;int a=Baseline::GetCachedStackDanger(r[0],&target,r,none,none);unsigned oldValidates=validationCalls-validate;validate=validationCalls;int b=Trial::GetCachedStackDanger(r[0],&target,r,none,none);Check("owned scalar hit exact/no new table work",a==b&&SnapshotOld()==SnapshotNew());Check("full real Context5to4 live validations5to4",Baseline::fixtureContextCalls==5&&Trial::fixtureContextCalls==4&&oldValidates==5&&validationCalls-validate==4);
  Baseline::SelectCachedStackDefender(&actors[0],&nearby,&target,r,none,true,0);Trial::SelectCachedStackDefender(&actors[0],&nearby,&target,r,none,true,0);Baseline::fixtureContextCalls=Trial::fixtureContextCalls=0;const CvUnit*oa=Baseline::SelectCachedStackDefender(&actors[0],&nearby,&target,r,none,true,0),*nb=Trial::SelectCachedStackDefender(&actors[0],&nearby,&target,r,none,true,0);Check("selector4to3 exact native identity",oa==nb&&Baseline::fixtureContextCalls==4&&Trial::fixtureContextCalls==3);
  Baseline::gStackDangerScratchBusy=Trial::gStackDangerScratchBusy=true;Baseline::fixtureContextCalls=Trial::fixtureContextCalls=0;a=Baseline::GetCachedStackDanger(r[0],&target,r,none,none);b=Trial::GetCachedStackDanger(r[0],&target,r,none,none);Check("busy private buffer retains full repeated validation",a==b&&Baseline::fixtureContextCalls==Trial::fixtureContextCalls);Baseline::gStackDangerScratchBusy=Trial::gStackDangerScratchBusy=false;
  ForeignArgs args={r[0],&target,&r};HANDLE t=CreateThread(NULL,0,Foreign,&args,0,NULL);Check("foreign created",t!=NULL);if(t){Check("foreign bounded return",WaitForSingleObject(t,5000)==WAIT_OBJECT_0);DWORD status=1;GetExitCodeThread(t,&status);CloseHandle(t);Check("foreign original cache/counters untouched",status==0);}
  {Baseline::StackForecastScope nestedOld(true);Trial::StackForecastScope nestedNew(true);Baseline::fixtureContextCalls=Trial::fixtureContextCalls=0;a=Baseline::GetCachedStackDanger(r[0],&target,r,none,none);b=Trial::GetCachedStackDanger(r[0],&target,r,none,none);Check("nested does not inherit positive witness",a==b&&Baseline::fixtureContextCalls==Trial::fixtureContextCalls);}
 }
 // Lock/options/current native fields are real negative cases, not a Context
 // stub returning a manufactured safe boolean. Original raw leaf still runs.
 bool*options[]={&MOD_EVENTS_CAN_MOVE_INTO,&MOD_EVENTS_AIRLIFT,&MOD_EVENTS_SEALIFT,&MOD_EVENTS_UNIT_RANGEATTACK,&MOD_EVENTS_CITY_BOMBARD,&MOD_EVENTS_REBASE,&MOD_EVENTS_UNIT_ACTIONS};
 for(int mode=0;mode<11;++mode){CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope current(true);CvUnit unsafe(99,0,&nearby);if(mode<7)*options[mode]=true;if(mode==7)gameLock=false;if(mode==8){unsafe.domain=DOMAIN_AIR;unsafe.strength=1;players[0].units[99]=&unsafe;}if(mode==9||mode==10){unsafe.heavy=mode==9;unsafe.morale=mode==10?1:0;players[0].units[99]=&unsafe;players[0].possible.push_back(make_pair(99,0));}Baseline::fixtureContextCalls=Trial::fixtureContextCalls=0;unsigned before=leafCalls;int a=Baseline::GetCachedStackDanger(r[0],&target,r,none,none),b=Trial::GetCachedStackDanger(r[0],&target,r,none,none);Check("actual callback/lock/AIR/interceptor proof private fallback",a==b&&leafCalls==before+2&&Baseline::fixtureContextCalls==Trial::fixtureContextCalls&&Baseline::gStackDangerForecasts.empty()&&Trial::gStackDangerForecasts.empty());if(mode<7)*options[mode]=false;gameLock=true;players[0].units.erase(99);players[0].possible.clear();}
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Trial::StackForecastScope current(true);Trial::GetCachedStackDanger(r[0],&target,r,none,none);unsigned hits=Trial::gStackDangerHits,before=leafCalls;Trial::fixtureInvalidateLoan=true;int got=Trial::GetCachedStackDanger(r[0],&target,r,none,none);Check("foreign epoch afterloan rejects hit/computes once/no admission",Trial::gStackDangerHits==hits&&leafCalls==before+1&&Trial::gStackDangerForecasts.empty()&&got==c.GetStackDanger(r[0],r,none,none)&&!Trial::gStackDangerScratchBusy);}
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Trial::StackForecastScope current(true);Trial::SelectCachedStackDefender(&actors[0],&nearby,&target,r,none,true,0);unsigned hits=Trial::gStackDefenderHits;Trial::fixtureInvalidateLoan=true;const CvUnit*got=Trial::SelectCachedStackDefender(&actors[0],&nearby,&target,r,none,true,0);Check("selector mandatory final check rejects afterloan epoch",got!=NULL&&Trial::gStackDefenderHits==hits&&Trial::gStackDefenderForecasts.empty()&&!Trial::gStackDefenderScratchBusy);}
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Trial::StackForecastScope current(true);Trial::GetCachedStackDanger(r[0],&target,r,none,none);unsigned hits=Trial::gStackDangerHits,before=leafCalls,refresh=refreshCalls;maps[0].m_bDirty=true;int a=Trial::GetCachedStackDanger(r[0],&target,r,none,none);Check("dirty refresh suspension rejects stale scalar",Trial::gStackDangerHits==hits&&leafCalls==before+1&&refreshCalls==refresh+1&&a==c.GetStackDanger(r[0],r,none,none)&&!CvStackingStrengthCache::IsPreviewSuspended());}
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old;Trial::StackForecastScope current;Baseline::fixtureContextCalls=Trial::fixtureContextCalls=0;int a=Baseline::GetCachedStackDanger(r[0],&target,r,none,none),b=Trial::GetCachedStackDanger(r[0],&target,r,none,none);Check("default unsupported scope retains original full checks",a==b&&Baseline::fixtureContextCalls==Trial::fixtureContextCalls&&Baseline::gStackDangerForecasts.empty()&&Trial::gStackDangerForecasts.empty());}
 Check("complete safety module still uses scans/validation/suspension fields",providerCalls>0&&validationCalls>0);
 Check("outer loan and packet payload released",Trial::gStackPacketScratch.value.memberScores.capacity()==0&&Trial::gStackKeyPayloadBytes==0&&!Trial::gStackDangerScratchBusy&&!Trial::gStackDefenderScratchBusy);
 printf("IMMEDIATE BORROW ACTUAL85:%u checks,%u failures; full native Context/provider,5to4scalar/4to3selector; no native ROI\n",checks,failures);return failures?1:0;
}
'''
code=headers+strength_header+strength_module+native_services+base+services+implementation+tests
(out/'test.cpp').write_text(code,encoding='utf-8')
if '--emit-only' in sys.argv:print('Actual callback-safe85 two-line fixture emitted; no compilation');sys.exit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
built=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fe'+str(out/'test.exe')],cwd=out,env=env,capture_output=True,text=True,timeout=90);(out/'compile.log').write_text(built.stdout+built.stderr)
if built.returncode:print(built.stdout+built.stderr);sys.exit(built.returncode)
run=subprocess.run([str(out/'test.exe')],cwd=out,capture_output=True,text=True,timeout=40);print(run.stdout+run.stderr,end='')
(out/('production-result.json' if production else 'result.json')).write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,control=proof['control'],source_sha256=proof['source_sha256'],candidate_sha256=proof['candidate_sha256'],fixture_sha256=hashlib.sha256(code.encode()).hexdigest(),production_untouched=True,bound_current_production=production,actual_whole_source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in live.items()},actual_context_and_whole_strength_module=True,actual_provider=True,complete_math_bindings=math_bindings,scope='Exactly two wrapper bools; full pinned85 math/cache/storage/provider/module against deterministic engine services. Missing provider/options/lock/live unsafe AIR/interceptors/nesting/foreign/default unsupported and afterloan/dirty invalidation retain original checks. No native speedup claim.'),indent=2));sys.exit(run.returncode)
