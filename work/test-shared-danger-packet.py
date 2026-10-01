"""Work-only full mathematical differential for the shared-packet scaffold.

No production patch is applied. Actual original cache/wrapper/keys and complete
field/city/air/selector math are compiled against deterministic engine services.
This is an algorithm/storage proof, not a native hit-path/ROI benchmark.
"""
from pathlib import Path
import ast,hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2';out=root/'work/shared-danger-packet-regression';out.mkdir(exist_ok=True)
control='cf8f842e2733841255a1d5bc741e4d95a387299b'
files=['CvDangerPlots.h','CvDangerPlots.cpp','CvTacticalAI.cpp']
current={n:(core/n).read_text(encoding='utf-8-sig') for n in files};candidate=current
manifest=dict(control=control)
# Reuse the tracked pure source-extraction block, not an ignored generated C++
# scaffold or the probe's CLI/execution. This block performs no filesystem writes.
template=(root/'work/test-packet-probe.py').read_text(encoding='utf-8-sig')
block=template[template.index('def function('):template.index("headers='''")]
scope=dict(root=root,core=core,current=current,candidate=candidate,manifest=manifest,subprocess=subprocess,hashlib=hashlib,re=re)
exec(compile(block,'tracked packet numerical source extraction','exec'),scope)
function=scope['function'];base=scope['base'];math_bindings=scope['math_bindings']
values={}
for node in ast.parse(template).body:
 if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
  for target in node.targets:
   if isinstance(target,ast.Name):values[target.id]=node.value.value
headers,services=values['headers'],values['services']
services=services.replace('static bool MOD_EVENTS_CAN_MOVE_INTO=false;','static bool MOD_EVENTS_CAN_MOVE_INTO=false,MOD_EVENTS_CITY_BOMBARD=false;static bool OnDangerRefresh();',1)
services=services.replace('m_bDirty=false;CvStackingStrengthCache::Invalidate();','m_bDirty=false;if(!OnDangerRefresh())CvStackingStrengthCache::Invalidate();',1)
danger=current['CvDangerPlots.cpp'];tact=current['CvTacticalAI.cpp'];plot=(core/'CvPlot.cpp').read_text(encoding='utf-8-sig')
implementation='\n'.join(function(danger,s) for s in ['const std::vector<int>& CvDangerPlotContents::GetStackDangerDamageIDs()',
 'bool CvDangerPlotContents::TryGetFixedStackDanger(','int CvDangerPlots::GetStackDanger(',
 'bool CvDangerPlots::GetStackDangerOutcome(','bool CvDangerPlots::TryGetStackDangerFromOutcome(',
 'bool CvDangerPlots::TryGetFixedStackDanger(','const std::vector<int>* CvDangerPlots::GetStackDangerDamageIDs('])
implementation=implementation.replace('int CvDangerPlots::GetStackDanger(','int CvDangerPlots::NativeStackDanger(',1)
implementation+='\n'+function(plot,'bool CvPlot::isFriendlyCity(')+'\n'+function(tact,'const CvUnit* TacticalAIHelpers::GetSimulatedGarrison(')
implementation+='\n'+tact[tact.index('struct StackForecastKey\n'):tact.index('// Bind immutable inputs only')]
implementation+='\n'+function(tact,'struct StackDangerOutcomeBatch\n')+';\n'
legacy=function(tact,'static int GetCachedStackDanger(')
legacy=re.sub(r'^.*PacketProbeCall packetProbeCall.*\n|^.*packetProbeCall\.Finish\(\).*\n','',legacy,flags=re.M)
legacy=re.sub(r'result = \(packetProbeCall\.MarkRaw\(\), (.*?)\); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY',r'result = \1;',legacy)
# Strict original-wrapper parity/source contract, including one store caller.
pinned=subprocess.check_output(['git','show','ddab3d933:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig').replace('\r\n','\n')
assert legacy==function(pinned,'static int GetCachedStackDanger('),'Revisit legacy wrapper after a source change'
assert len(re.findall(r'StoreStackDangerForecast\(',tact))==2,'Revisit parity namespace after a new scalar store caller'
implementation+='\n'+legacy
boundary=r'''
static void WorkOnPacketPreparation();
static StackForecastKey WorkLegacyDangerKey(const CvUnit*u,const CvPlot*p,const vector<const CvUnit*>&r,const SUnitIDValueContainer&f,const SUnitIDValueContainer&e){StackForecastKey k;k.state.push_back(u->GetID());k.state.push_back(p->GetPlotIndex());k.state.push_back(f.GetValue(u->GetID()));k.state.push_back(CvStacking::GetCityProtection(p->getPlotCity()));AppendStackCandidates(k,r,f,!p->isCity()&&CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled,1)!=0);AppendStackDamageProjected(k,e,u,p);return k;}
static const CvDangerPlotContents*WorkPacketContents(const CvDangerPlots&map,const CvPlot&p){int i=p.GetPlotIndex();return map.IsDirty()||i<0||(size_t)i>=map.m_DangerPlots.size()||!map.m_DangerPlots[i].m_pPlot?NULL:&map.m_DangerPlots[i];}
'''
trial=(root/'work/shared-danger-packet-experiment.h').read_text(encoding='utf-8-sig')
needle='return key.state.size()%2&&key.state.size()<=payloadLimit/sizeof(int);'
assert trial.count(needle)==1
trial=trial.replace(needle,'WorkOnPacketPreparation();'+needle,1) # Deterministic service boundary, not production callback.
tests=r'''
static unsigned checks=0,failures=0,leafCalls=0,leafMutation=0,prepMutation=0;static unsigned seed=91763;static CvUnit*refreshAA=NULL;
static unsigned Next(){seed=seed*1664525u+1013904223u;return seed;}
static void Check(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<20)printf("FAIL %s\n",n);}}
static void OnLeaf(){++leafCalls;if(leafMutation){unsigned m=leafMutation;leafMutation=0;if(m==1)CvStackingStrengthCache::Invalidate();else if(m==2)++gStackForecastRevision;else if(m==3)maps[0].m_DangerPlots[0].m_iFogCount+=3;else if(m==4)throw 13;else if(m==5)maps[0].m_DangerPlots[0].m_pPlot->getPlotCity()->hp=1;}}
static void WorkOnPacketPreparation(){if(prepMutation){unsigned m=prepMutation;prepMutation=0;if(m==1)CvStackingStrengthCache::Invalidate();else if(m==2)++gStackForecastRevision;else if(m==3)maps[0].m_bDirty=true;else if(m==4)maps[0].m_DangerPlots[0].m_iFogCount+=3;}}
static bool OnDangerRefresh(){if(MOD_EVENTS_CITY_BOMBARD&&refreshAA){++refreshAA->made;return true;}return false;}
static void Reset(){for(int p=0;p<4;++p){players[p]=CvPlayer();players[p].id=players[p].team=p;maps[p]=CvDangerPlots();for(int q=0;q<4;++q){teams[p].open[q]=false;if(p!=q)players[p].enemies.push_back(q);}}}
static size_t Recount(const SharedDangerPacketTrial&t){size_t bytes=0;for(SharedDangerPacketTrial::Table::const_iterator i=t.danger.begin();i!=t.danger.end();++i)bytes+=SharedDangerPacketTrial::Bytes(*i);for(SharedDangerPacketTrial::DefenderTable::const_iterator i=t.defender.begin();i!=t.defender.end();++i)bytes+=i->first.state.capacity()*sizeof(int);return bytes;}
static void Invariant(const SharedDangerPacketTrial&t){Check("shared entry/FIFO ceiling",t.danger.size()+t.defender.size()<=t.entryLimit&&t.dangerFIFO.size()==t.danger.size()&&t.defenderFIFO.size()==t.defender.size());Check("actual retained output/key capacities charged",t.payloadBytes==Recount(t)&&t.payloadBytes<=t.payloadLimit);for(size_t q=0;q<t.dangerFIFO.size();++q){SharedDangerPacketTrial::Table::const_iterator i=t.danger.find(*t.dangerFIFO[q]);Check("FIFO key pointers retain native nodes",i!=t.danger.end()&&&i->first==t.dangerFIFO[q]);}}
struct ForeignArgs{SharedDangerPacketTrial*trial;CvUnit*unit;CvPlot*plot;vector<const CvUnit*>*roster;SUnitIDValueContainer*damage;};
static DWORD WINAPI ForeignQuery(void*p){ForeignArgs*a=(ForeignArgs*)p;unsigned hits=a->trial->scalarHits+a->trial->packetHits,builds=a->trial->packetBuilds+a->trial->scalarBuilds;size_t bytes=a->trial->payloadBytes,entries=a->trial->danger.size();a->trial->Get(maps[0],a->unit,a->plot,*a->roster,*a->damage,*a->damage);Check("foreign query touches no owning table/counters",hits==a->trial->scalarHits+a->trial->packetHits&&builds==a->trial->packetBuilds+a->trial->scalarBuilds&&bytes==a->trial->payloadBytes&&entries==a->trial->danger.size());return 0;}
int main(){Check("genuine x86",sizeof(void*)==4);CvPlot target(0),nearby(1);CvCity city(7,0,&target),enemyCity(8,1,&nearby);CvUnit units[6],actors[9];
 for(int state=0;state<450;++state){Reset();CvDangerPlotContents&c=maps[0].m_DangerPlots[0];c.m_pPlot=&target;c.m_iFogCount=state%5;c.m_iImprovementDamage=state%19;c.m_bFlatPlotDamage=state%2!=0;target.city=state%3==0?&city:NULL;city.hp=20+Next()%280;city.protection=Next()%91;CvStacking::enabled=state%11!=0;CvStacking::selectionEnabled=state%7!=0;
  vector<const CvUnit*>roster;SUnitIDValueContainer f,e;
  for(int i=0;i<6;++i){units[i]=CvUnit(i==0?0:i==1?-8:10+i,0,&target);units[i].hp=25+Next()%100;units[i].maxHP=units[i].hp+Next()%50;units[i].ranged=Next()%2!=0;units[i].defense=10+Next()%70;units[i].terrainIgnore=Next()%2!=0;units[i].featureIgnore=Next()%2!=0;units[i].anti=Next()%2!=0;units[i].flankTarget=Next()%2!=0;units[i].chance=Next()%151;units[i].domain=i==5?DOMAIN_AIR:DOMAIN_LAND;players[0].units[units[i].id]=&units[i];players[0].possible.push_back(make_pair(units[i].id,0));if(i<5)roster.push_back(&units[i]);f.SetValue(units[i].id,(int)(Next()%141)-10);}
  CvUnit aa(99,0,&nearby);aa.domain=DOMAIN_AIR;aa.strength=400;players[0].units[99]=&aa;players[0].possible.push_back(make_pair(99,0));f.SetValue(99,(int)(Next()%121));city.garrison=&units[state%5];if(state%4==0)roster.push_back(&units[1]);if(state%7==0)reverse(roster.begin(),roster.end());
  for(int i=0;i<9;++i){actors[i]=CvUnit(i%5,1+i%2,&nearby);actors[i].ranged=Next()%2!=0;actors[i].domain=i%4==0?DOMAIN_AIR:DOMAIN_LAND;actors[i].flank=Next()%2!=0;actors[i].aoe=Next()%4;actors[i].collateralLimit=Next()%5;actors[i].evasion=Next()%101;actors[i].strength=30+Next()%80;players[actors[i].owner].units[actors[i].id]=&actors[i];c.m_apUnits.push_back(make_pair(actors[i].owner,actors[i].id));e.SetValue(actors[i].id,(int)(Next()%71));}players[1].cities[8]=&enemyCity;c.m_apCities.push_back(make_pair(1,8));if(state%5==0)c.m_apCities.push_back(make_pair(1,8));
  StackForecastScope native;SharedDangerPacketTrial trial(9,2800);
  for(int q=0;q<12;++q){const CvUnit*u=&units[q%6];int actual=c.GetStackDanger(u,roster,f,e);int old=GetCachedStackDanger(u,&target,roster,f,e);int got=trial.Get(maps[0],u,&target,roster,f,e);Check("all member scalar/outcome numerics",got==actual&&got==old);Invariant(trial);StackForecastKey key=WorkLegacyDangerKey(u,&target,roster,f,e);Check("legacy scalar encoding always even",key.state.size()%2==0);}
  SUnitIDValueContainer wounded=f;wounded.SetValue(99,100);int expected=c.GetStackDanger(&units[0],roster,wounded,e);trial.Clear();Check("offstack AA numerical injury input",trial.Get(maps[0],&units[0],&target,roster,wounded,e)==expected);Invariant(trial);
 }
 Reset();CvStacking::enabled=CvStacking::selectionEnabled=true;target.city=NULL;vector<const CvUnit*>roster;SUnitIDValueContainer none;
 for(int i=0;i<5;++i){units[i]=CvUnit(10+i,0,&target);units[i].hp=units[i].maxHP=500;players[0].units[10+i]=&units[i];roster.push_back(&units[i]);}CvDangerPlotContents&c=maps[0].m_DangerPlots[0];c.m_pPlot=&target;actors[0]=CvUnit(44,1,&nearby);actors[0].ranged=true;actors[0].collateralLimit=0;players[1].units[44]=&actors[0];c.m_apUnits.push_back(make_pair(1,44));
 {StackForecastScope native;SharedDangerPacketTrial t(12,4000);unsigned start=leafCalls;for(int q=0;q<5;++q)Check("cold cross-member results exact",t.Get(maps[0],&units[q],&target,roster,none,none)==c.GetStackDanger(&units[q],roster,none,none));Check("one outcome build precomputes five",t.packetBuilds==1&&t.packetHits==4&&t.precomputations==4&&leafCalls-start==6);for(int q=0;q<5;++q){unsigned hits=t.scalarHits;t.Get(maps[0],&units[q],&target,roster,none,none);Check("queried members retain cheap scalar hits",t.scalarHits==hits+1);}Check("one odd group plus queried even entries",t.danger.size()==6);Invariant(t);}
 {StackForecastScope native;SharedDangerPacketTrial t(1,4000);t.Get(maps[0],&units[0],&target,roster,none,none);Check("one entry retains queried cheap even scalar",t.danger.size()==1&&t.danger.begin()->first.state.size()%2==0);unsigned hits=t.scalarHits;t.Get(maps[0],&units[0],&target,roster,none,none);Check("tiny budget repeated scalar fast hit",t.scalarHits==hits+1);Invariant(t);}
 for(size_t bytes=0;bytes<=800;bytes+=40){StackForecastScope native;SharedDangerPacketTrial t(6,bytes);for(int q=0;q<5;++q)Check("budget cannot change returned danger",t.Get(maps[0],&units[q],&target,roster,none,none)==c.GetStackDanger(&units[q],roster,none,none));Invariant(t);}
 for(int mode=1;mode<=4;++mode){StackForecastScope native;SharedDangerPacketTrial t(12,4000);t.Get(maps[0],&units[0],&target,roster,none,none);unsigned hits=t.packetHits;prepMutation=mode;unsigned before=rawSequences;int got=t.Get(maps[0],&units[1],&target,roster,none,none);Check("post-key mutation cannot return cached packet",t.packetHits==hits&&got==c.GetStackDanger(&units[1],roster,none,none)&&rawSequences==before+1);maps[0].m_bDirty=false;}
 for(int mode=1;mode<=3;++mode){StackForecastScope native;SharedDangerPacketTrial t(12,4000);leafMutation=mode;unsigned start=leafCalls;t.Get(maps[0],&units[0],&target,roster,none,none);Check("invalidated outcome computed once",leafCalls==start+1&&t.danger.empty()&&!t.building);}
 {StackForecastScope native;SharedDangerPacketTrial t(12,4000);leafMutation=4;bool caught=false;try{t.Get(maps[0],&units[0],&target,roster,none,none);}catch(int){caught=true;}Check("throwing outcome releases in-flight state",caught&&!t.building&&t.danger.empty());}
 {StackForecastScope native;SharedDangerPacketTrial t(12,4000);StackDangerOutcomeBatch batch(&target,roster,none,none);unsigned start=leafCalls;t.Get(maps[0],&units[0],&target,roster,none,none,&batch);Check("ready local batch not duplicated",leafCalls==start+1&&batch.ready);for(int q=1;q<5;++q)t.Get(maps[0],&units[q],&target,roster,none,none,&batch);Check("local batch and packet agree",leafCalls==start+1);}
 {StackForecastScope native;SharedDangerPacketTrial t(12,4000);gStackKeyPayloadLimit=0;actors[0].aoe=2;StackDangerOutcomeBatch batch(&target,roster,none,none);unsigned start=leafCalls;t.Get(maps[0],&units[0],&target,roster,none,none,&batch);Check("released computed local batch never rebuilt",leafCalls==start+1&&!batch.ready&&t.danger.empty());actors[0].aoe=0;}
 // CITY_BOMBARD dirty refresh can mutate off-stack AA with no SceneEpoch.
 {StackForecastScope native;SharedDangerPacketTrial t(12,4000);CvUnit aa(99,0,&nearby);aa.domain=DOMAIN_AIR;aa.attempts=1;aa.chance=100;aa.strength=500;players[0].units[99]=&aa;players[0].possible.push_back(make_pair(99,0));actors[0].domain=DOMAIN_AIR;t.Get(maps[0],&units[0],&target,roster,none,none);unsigned hits=t.packetHits;long epoch=CvStackingStrengthCache::SceneEpoch();MOD_EVENTS_CITY_BOMBARD=true;refreshAA=&aa;maps[0].m_bDirty=true;unsigned refresh=refreshCalls;int got=t.Get(maps[0],&units[1],&target,roster,none,none);Check("script refresh mutation preserved once",refreshCalls==refresh+1&&aa.made==1&&CvStackingStrengthCache::SceneEpoch()==epoch);Check("new member script packet bypass despite unchanged sources",t.packetHits==hits&&got==c.GetStackDanger(&units[1],roster,none,none));MOD_EVENTS_CITY_BOMBARD=false;refreshAA=NULL;actors[0].domain=DOMAIN_LAND;}
 {StackForecastScope native;SharedDangerPacketTrial t(12,4000);target.city=&city;city.hp=city.maxHP;city.garrison=&units[0];t.Get(maps[0],&units[0],&target,roster,none,none);city.hp=1;unsigned builds=t.packetBuilds;t.Get(maps[0],&units[1],&target,roster,none,none);Check("city damage/protection keyed without scene change",t.packetBuilds==builds+1);target.city=NULL;}
 {StackForecastScope native;SharedDangerPacketTrial t(4,1500);StackForecastKey a;a.state.push_back(1);a.state.push_back(2);t.StoreDefender(a,&units[0]);for(int q=0;q<5;++q)t.Get(maps[0],&units[q],&target,roster,none,none);Check("packet and scalar compete with defender under same budget",t.evictions>0);Invariant(t);t.Clear();Check("clear releases every charged capacity",t.payloadBytes==0&&t.danger.empty()&&t.defender.empty());}
 // Each unsupported shape is a cold query so a preexisting legitimate scalar
 // hit cannot hide the packet guard; no arbitrary cloned-native identity is
 // treated as valid merely because its raw owner/ID happen to match.
 for(int mode=0;mode<8;++mode){StackForecastScope native;SharedDangerPacketTrial t(12,4000);vector<const CvUnit*>r=roster;CvUnit other(91,0,&target);SUnitIDValueContainer f,e;
  if(mode==0)r.resize(1);if(mode==1){other.owner=2;r[4]=&other;}if(mode==2)r[4]=NULL;if(mode==3){other=units[4];r[4]=&other;}if(mode==4)units[0].cargo=true;if(mode==5)units[0].civilian=true;if(mode==6){f.SetValue(10,1);f.SetValue(11,2);f.m_aExtraStorage.push_back(make_pair(10,3));}if(mode==7){e.SetValue(44,1);e.SetValue(45,2);e.m_aExtraStorage.push_back(make_pair(44,3));}
  // Nulls in the FULL field graph are outside the native consumer contract;
  // validate its PacketKey guard directly instead of dereferencing a null.
  if(mode==2){StackForecastKey legacy=WorkLegacyDangerKey(&units[0],&target,r,f,e),key,sources;vector<const CvUnit*>members;Check("null roster cannot enter packet",!t.PacketKey(maps[0],&units[0],&target,r,f,e,legacy,key,sources,members));}
  else{int expected=c.GetStackDanger(&units[0],r,f,e);Check("unsupported shape original numerical fallback",t.Get(maps[0],&units[0],&target,r,f,e)==expected&&t.packetBuilds==0&&t.packetHits==0);}units[0].cargo=units[0].civilian=false;
 }
 {StackForecastScope native;SharedDangerPacketTrial t(12,4000);MOD_EVENTS_CAN_MOVE_INTO=true;unsigned start=rawSequences;t.Get(maps[0],&units[0],&target,roster,none,none);Check("scripted movement uses original scalar once",rawSequences==start+1&&t.packetBuilds==0);MOD_EVENTS_CAN_MOVE_INTO=false;}
 {StackForecastScope native;SharedDangerPacketTrial t(12,4000);t.Get(maps[0],&units[0],&target,roster,none,none);ForeignArgs a={&t,&units[1],&target,&roster,&none};HANDLE thread=CreateThread(NULL,0,ForeignQuery,&a,0,NULL);Check("foreign fixture thread created",thread!=NULL);WaitForSingleObject(thread,INFINITE);CloseHandle(thread);
  {StackForecastScope nested;unsigned builds=t.packetBuilds,old=t.scalarBuilds,hits=t.scalarHits+t.packetHits;t.Get(maps[0],&units[1],&target,roster,none,none);Check("nested search does not touch owned storage",t.packetBuilds==builds&&t.scalarBuilds==old&&t.scalarHits+t.packetHits==hits);}t.Get(maps[0],&units[2],&target,roster,none,none);Check("returning owner clears invalidated packet entries",t.clears>0);Invariant(t);
 }
 printf("shared packet work-only proof:%u checks,%u failures; one outcome/five member ints; queried scalar hits retained; same shared limits; no native ROI claim\n",checks,failures);return failures?1:0;
}
'''
code=headers+base+services+implementation+boundary+trial+tests
(out/'test.cpp').write_text(code,encoding='utf-8')
if '--emit-only' in sys.argv:print('Shared packet differential emitted; no compilation or production changes');sys.exit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for k in ('CL','_CL_','LINK'):env.pop(k,None)
exe=out/'test.exe';built=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);(out/'compile.log').write_text(built.stdout+built.stderr)
if built.returncode:print(built.stdout+built.stderr);sys.exit(built.returncode)
run=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=40);print(run.stdout+run.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,control=control,production_untouched=True,math_body_sha256=math_bindings,fixture_sha256=hashlib.sha256(code.encode()).hexdigest(),scope='Actual unchanged full scalar/outcome/extraction/air/city/selector/exchange/collateral/native-friendly-city/garrison functions, actual original cache/FIFO/key/immutable enemy helpers; isolated same-budget packet value/table algorithm. Deterministic engine services/model allocation paths; not a production scratch/key-stage equivalence or native ROI proof.'),indent=2))
sys.exit(run.returncode)
