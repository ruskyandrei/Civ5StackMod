"""Actual DLL97 old/new allocation-free resident slot-key oracle."""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
P=argparse.ArgumentParser(description=__doc__);P.add_argument('--emit-only',action='store_true');P.add_argument('--production',action='store_true');P.add_argument('--control',default='fbde19541');args=P.parse_args();BASE=args.control
assert BASE=='fbde19541'
subprocess.run([sys.executable,str(ROOT/'work/stage-resident-slot-key.py')],check=True,capture_output=True)
STAGE=ROOT/'work/resident-slot-key-staged';OUT=ROOT/'work/resident-slot-key-regression';OUT.mkdir(exist_ok=True)
control=(STAGE/'control.cpp').read_text(encoding='utf-8');candidate=(STAGE/'CvTacticalAI.cpp').read_text(encoding='utf-8');proof=json.loads((STAGE/'manifest.json').read_text())
names=('CvTacticalAI.cpp','CvTacticalAI.h','CvUnit.cpp','CvDangerPlots.cpp','CvStackingStrengthCache.h','CvStackingStrengthCache.cpp','CvDangerPlots.h','CvUnit.h','CvUnitCombat.cpp','CvPlot.cpp','CvStackingRules.h','CvStackingRules.cpp','CvStackingDiagnostics.h','CvStackingDiagnostics.cpp')
source={n:subprocess.check_output(['git','show',BASE+':CvGameCoreDLL_Expansion2/'+n],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n') for n in names};assert source['CvTacticalAI.cpp']==control
actual_hashes={}
if args.production:
 for name,text in source.items():
  actual=(ROOT/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8-sig')
  assert actual==(candidate if name=='CvTacticalAI.cpp' else text),'Whole candidate/dependency mismatch: '+name
  actual_hashes[name]=hashlib.sha256(actual.encode()).hexdigest()
# Reuse tracked complete numerical extraction/services, pinned to selected control.
# Skip its unrelated historical two-line equality assertion and all execution.
generator=(ROOT/'work/test-immediate-forecast-borrow.py').read_text(encoding='utf-8-sig')
prefix=generator[:generator.index('\ndef cache_module(')]
a=prefix.index("stage=root/'work/immediate-forecast-borrow-stage'");b=prefix.index('# Reuse only tracked extraction/services,',a)
setup="proof={'control':extraction_control}\noriginal=extraction_sources\ncandidate=dict(original)\nold=new=original['CvTacticalAI.cpp']\n"
prefix=prefix[:a]+setup+prefix[b:]
line="template=(root/'work/test-packet-probe.py').read_text(encoding='utf-8-sig')"
prefix=prefix.replace(line,line+"\nfor name in ('CvUnit.h','CvUnitCombat.cpp','CvStackingRules.cpp','CvStackingRules.h'):\n template=template.replace(\"(core/'\"+name+\"').read_text(encoding='utf-8-sig')\",\"current['\"+name+\"']\")\n",1)
scope={'__file__':str(ROOT/'work/test-immediate-forecast-borrow.py'),'extraction_control':BASE,'extraction_sources':source}
exec(compile(prefix,'tracked pinned numerical services','exec'),scope)
function=scope['function'];base=scope['base'];services=scope['services']
base=base.replace('if(failAllocation)throw std::bad_alloc();','if(failAllocation){failAllocation=false;throw std::bad_alloc();}',1)
services=services.replace('bool TryGetPlanSamplingContext(unsigned long&serial,long&epoch){','bool TryGetPlanSamplingContext(unsigned long&serial,long&epoch){',1)
# Minimal position services are solely for the unchanged disabled kernel probe.

def section(s,a,b):
 i=s.index(a);return s[i:s.index(b,i)]
# Deterministic tactical plot/stat services; CoW, first-match, preview child,
# query/parent preparation, backend/keys and numerical danger are actual source.
cow=section(source['CvTacticalAI.h'],'template<typename T>\nstruct SCoWField','class CvBasePosition')
shares=section(source['CvTacticalAI.h'],'\tbool SharesVirtualStackInputs(','\n\tconst CvTacticalPlot* getTactPlot(')
engine=r'''
static unsigned long statsReads=0,unitReads=0,virtualBuilds=0,serializedPrefixes=0,scalarLookups=0,residentReturnCount=0,cellAcquisitions=0,metadataKeyCopies=0;
struct SUnitStats{int iUnitID,iSelfDamage;SUnitStats(int id=0,int d=0):iUnitID(id),iSelfDamage(d){}};
struct STacticalUnit{int iUnitID;STacticalUnit(int id=0):iUnitID(id){}};
struct CvTacticalPlot{int index;vector<const CvUnit*>fixed;vector<STacticalUnit>moving;CvTacticalPlot(int i=0):index(i){}const vector<const CvUnit*>&getFixedFriendlyUnits()const{return fixed;}const vector<STacticalUnit>&getUnitsAtPlot()const{return moving;}};
struct CvBasePosition{SCoWField<vector<SUnitStats> >availableUnits,notQuiteFinishedUnits,finishedUnits;PlayerTypes ePlayer;CvBasePosition():ePlayer(0){}const SUnitStats*GetUnitStats(int)const;};
struct CvTacticalPosition:public CvBasePosition{
 SCoWField<vector<pair<int,int> > >tactPlotLookup;SCoWField<vector<CvTacticalPlot> >tactPlots;SCoWField<SUnitIDValueContainer>unitDamageDealt;
 const CvTacticalPlot*getTactPlot(int i)const{const vector<CvTacticalPlot>&ps=tactPlots.read();for(size_t n=0;n<ps.size();++n)if(ps[n].index==i)return&ps[n];return NULL;}
 int getPlayer()const{return ePlayer;}const SUnitIDValueContainer&GetUnitDamageDealt()const{return unitDamageDealt.read();}
 void initFromParent(const CvTacticalPosition&parent){ePlayer=parent.ePlayer;tactPlotLookup.inheritFrom(parent.tactPlotLookup.read());tactPlots.inheritFrom(parent.tactPlots.read());availableUnits.inheritFrom(parent.availableUnits.read());notQuiteFinishedUnits.inheritFrom(parent.notQuiteFinishedUnits.read());finishedUnits.inheritFrom(parent.finishedUnits.read());unitDamageDealt.inheritFrom(parent.unitDamageDealt.read());}
 void ChangeUnitDamage(int id,int d){unitDamageDealt.write().ChangeValue(id,d);}void ChangeCityDamage(int id,int d){unitDamageDealt.write().ChangeValue(-id,d);}
 SHARES
};
struct STacticalAssignment{SUnitIDValueContainer unitDamage;int iDamagedCityId,iCityDamage;STacticalAssignment():iDamagedCityId(-1),iCityDamage(0){}};
'''.replace(' SHARES',shares)
# Native non-stacking raw fallback is deliberately opaque; both paths use it
# identically and never certify AIR/noncombat arrivals.
# Container appears after CvUnit, so forward-declare the type explicitly.
base=base.replace('struct CvUnit;struct CvCity;','struct CvUnit;struct CvCity;struct SUnitIDValueContainer;',1)
base=base.replace('int GetID()const{return id;}','int GetDanger(const CvPlot*,const SUnitIDValueContainer&,int)const;int GetID()const{return id;}',1)
services=services.replace('enum Part{PLAN_DANGER_KEY,PLAN_DANGER_LEAF};','enum Part{PLAN_DANGER_KEY,PLAN_DANGER_LEAF,PLAN_UNIT_DANGER};',1)
services=services.replace('struct Storage{int getSizeLimit()const{return 6000;}}gTactPosStorage;',r'''struct LegacyDangerCache{bool findDanger(int,int,int,const SUnitIDValueContainer&,int&){return false;}void storeDanger(int,int,int,const SUnitIDValueContainer&,int){}};
struct Storage{LegacyDangerCache danger;LegacyDangerCache&getDangerCache(){return danger;}int getSizeLimit()const{return 6000;}}gTactPosStorage;
int CvUnit::GetDanger(const CvPlot*,const SUnitIDValueContainer&,int)const{return 87;}''',1)
base=base.replace('static bool failAllocation=false;', 'static bool failAllocation=false;',1)
# Fixture-only observer callbacks track unmodified scalar service boundaries.
services=services.replace('static unsigned readerCalls=0,refreshCalls=0,rawSequences=0;', 'static unsigned readerCalls=0,refreshCalls=0,rawSequences=0;',1)

def module(text):
 body=cow+engine+'\n'+section(text,'const SUnitStats* CvBasePosition::GetUnitStats(','const STacticalAssignment* CvBasePosition::getInitialAssignment(')
 body=body.replace('{\n\tconst vector<SUnitStats>& availableUnits_r','{\n ++statsReads;\n\tconst vector<SUnitStats>& availableUnits_r',1)
 body+=text[text.index('struct StackForecastKey\n'):text.index('// Bind immutable inputs only')]
 body+='\n'+function(text,'struct StackDangerOutcomeBatch\n')+';\n'
 body+='\n'+text[text.index('static bool AppendUniquePacketDamage('):text.index('static int GetCachedStackDanger(')]
 body+='\n'+function(text,'static int GetCachedStackDanger(')
 start=text.index('static int GetCachedStackDanger(')
 body+='\n'+function(text[text.index('static const CvUnit* SelectCachedStackDefender(',start):],'static const CvUnit* SelectCachedStackDefender(')
 body+='\n'+section(text,'static void GetVirtualFriendlyStack(','// A same-tile escort counts only')
 body+='\n'+section(text,'static int GetUnitDangerForPlot(','static unsigned char GetStackAttackThreatFlags(')
 body+='\n'+function(text,'static void GetNextPosition(')
 body=body.replace('{\n const CvTacticalPlot* tactical = position.getTactPlot(plot->GetPlotIndex());','{\n ++virtualBuilds;\n const CvTacticalPlot* tactical = position.getTactPlot(plot->GetPlotIndex());',1)
 # Optional test counters do not alter original ordered serialization/math.
 app=function(body,'static void AppendStackCandidates(')
 body=body.replace(app,app.replace('{','{\n ++serializedPrefixes;',1),1)
 lookup=function(body,'static bool FindStackDangerForecastScalar(')
 body=body.replace(lookup,lookup.replace('{','{\n ++scalarLookups;',1),1)
 body=body.replace('private:\n Slot* slots;','public: // fixture-only exhaustion injection\n Slot* slots;',1)
 body=body.replace('++gResidentHits;return true;','++gResidentHits;++residentReturnCount;return true;',1)
 acquire=function(body,'static ParentStackPreparationCell* ResidentArrivalCell(')
 body=body.replace(acquire,acquire.replace('{','{\n ++cellAcquisitions;',1),1)
 body=body.replace('certificate.key=key.state;','++metadataKeyCopies;certificate.key=key.state;',1)
 context=function(body,'static bool StackForecastContext(')
 body=body.replace(context,context.replace('{','{\n ++fixtureContextCalls;',1),1)
 return body
implementation=scope['common']
projection=function(implementation,'const std::vector<int>* CvDangerPlots::GetStackDangerDamageIDs(')
implementation=implementation.replace(projection,projection.replace('{','{\n if(fixtureProjectionRefresh){fixtureProjectionRefresh=false;m_bDirty=true;}',1),1)
services='static bool fixtureProjectionRefresh=false;\n'+services
for name,text in [('Baseline',control),('Trial',candidate)]:implementation+='\nnamespace '+name+'{\nstatic unsigned fixtureContextCalls=0;\n'+module(text)+'\n}\n'

tests=r'''

static unsigned checks=0,failures=0,leafCalls=0,seed=718213,lookupMutation=0,leafMutation=0;
static bool throwLeaf=false,nestLeaf=false,throwLeafAllocation=false;static unsigned providerCalls=0,validationCalls=0;
static unsigned Next(){seed=seed*1664525u+1013904223u;return seed;}
static void Check(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<25)printf("FAIL %s\n",n);}}
static void OnUnitLookup(){if(lookupMutation){lookupMutation=0;CvStackingStrengthCache::Invalidate();}}
static void OnLeaf(){++leafCalls;if(throwLeaf)throw 91;if(throwLeafAllocation){throwLeafAllocation=false;throw std::bad_alloc();}if(leafMutation){leafMutation=0;CvStackingStrengthCache::Invalidate();}if(nestLeaf){nestLeaf=false;CvStackingStrengthCache::Scope nested(128);}}
static bool ActualProvider(unsigned int&flags,bool scan){if(scan)++providerCalls;else ++validationCalls;return Baseline::StackPreviewCallbackCapabilities(flags,scan);}
static bool ActualInputs(const vector<const CvUnit*>&roster){vector<CvUnit*>in;for(size_t i=0;i<roster.size();++i)in.push_back(const_cast<CvUnit*>(roster[i]));return Baseline::StackPreviewInputsSupported(in);}
static void Reset(){gameLock=true;MOD_EVENTS_CAN_MOVE_INTO=MOD_EVENTS_AIRLIFT=MOD_EVENTS_SEALIFT=MOD_EVENTS_UNIT_RANGEATTACK=MOD_EVENTS_CITY_BOMBARD=MOD_EVENTS_REBASE=MOD_EVENTS_UNIT_ACTIONS=false;for(int p=0;p<4;++p){players[p]=CvPlayer();players[p].id=players[p].team=p;maps[p]=CvDangerPlots();for(int q=0;q<4;++q){teams[p].open[q]=false;if(p!=q)players[p].enemies.push_back(q);}}}
static void Limits(size_t e,size_t b){Baseline::gStackEntryLimit=Trial::gStackEntryLimit=e;Baseline::gStackKeyPayloadLimit=Trial::gStackKeyPayloadLimit=b;}
struct Entry{int kind,scalar;size_t defender;vector<int>key;vector<pair<int,int> >members;bool operator<(const Entry&o)const{return kind!=o.kind?kind<o.kind:key<o.key;}bool operator==(const Entry&o)const{return kind==o.kind&&scalar==o.scalar&&defender==o.defender&&key==o.key&&members==o.members;}};
struct Snapshot{vector<Entry>entries;vector<vector<int> >queue[2];vector<unsigned long>counters;bool operator==(const Snapshot&o)const{return entries==o.entries&&queue[0]==o.queue[0]&&queue[1]==o.queue[1]&&counters==o.counters;}};
#define SNAPSHOT(name,NS) static Snapshot name(){Snapshot s;for(size_t i=0;i<NS::gIndexed.Capacity();++i){const NS::IndexedStore::Slot&slot=NS::gIndexed.At((int)i);if(!slot.used)continue;Entry e;e.kind=slot.kind;e.scalar=slot.scalar;e.defender=(size_t)slot.defender;e.key.assign(slot.Data(),slot.Data()+slot.keyWords);for(size_t j=0;j<slot.members;++j)e.members.push_back(make_pair(slot.Data()[slot.keyWords+2*j],slot.Data()[slot.keyWords+2*j+1]));s.entries.push_back(e);}for(int kind=0;kind<2;++kind)for(int i=NS::gIndexed.Head(kind);i!=-1;i=NS::gIndexed.NextQueued(i)){const NS::IndexedStore::Slot&slot=NS::gIndexed.At(i);s.queue[kind].push_back(vector<int>(slot.Data(),slot.Data()+slot.keyWords));}sort(s.entries.begin(),s.entries.end());s.counters.push_back(NS::gStackDangerHits);s.counters.push_back(NS::gStackDangerMisses);s.counters.push_back(NS::gStackDangerEvictions);s.counters.push_back(NS::gStackDefenderHits);s.counters.push_back(NS::gStackDefenderMisses);s.counters.push_back(NS::gStackDefenderEvictions);s.counters.push_back(NS::gStackOutcomeBuilds);s.counters.push_back(NS::gStackOutcomeReuses);s.counters.push_back(NS::gStackOutcomeBypasses);s.counters.push_back(NS::gStackPacketHits);s.counters.push_back(NS::gStackPacketBuilds);s.counters.push_back(NS::gStackPacketBypasses);s.counters.push_back((unsigned long)NS::gStackKeyPayloadBytes);s.counters.push_back(NS::gStackInsertBypasses);s.counters.push_back((unsigned long)NS::gStackDangerScratch.state.capacity());s.counters.push_back((unsigned long)NS::gStackPacketScratch.key.state.capacity());s.counters.push_back((unsigned long)NS::gStackPacketScratch.source.capacity());s.counters.push_back((unsigned long)NS::gStackPacketScratch.members.capacity());s.counters.push_back((unsigned long)NS::gStackPacketScratch.value.memberScores.capacity());return s;}
SNAPSHOT(OldSnapshot,Baseline) SNAPSHOT(NewSnapshot,Trial)
static size_t metadataPeak=0;static unsigned residentTotal=0,savedPrefixes=0;
static void Metadata(){size_t sum=0;for(size_t i=0;i<Trial::ParentStackPreparationStorage::MAX_CELLS;++i)sum+=Trial::gParentStackPreparationStorage.CellBytes(i);Check("metadata measured capacity reconciles",sum==Trial::gParentStackPreparationStorage.RetainedBytes());Check("optional payload bounded by unchanged budget",sum<=Trial::gStackKeyPayloadLimit);metadataPeak=max(metadataPeak,sum);}
static void Pair(CvUnit*u,CvPlot*p,int hp,const Baseline::CvTacticalPosition&a,const Trial::CvTacticalPosition&b,bool destination=false){unsigned before=leafCalls;Baseline::MovementDestinationStackQuery oq;int x=Baseline::GetUnitDangerForPlot(u,p,hp,a,destination?&oq:NULL);unsigned oldLeaves=leafCalls-before;before=leafCalls;Trial::MovementDestinationStackQuery nq;unsigned hits=Trial::gResidentHits;int y=Trial::GetUnitDangerForPlot(u,p,hp,b,destination?&nq:NULL);Check("actual mathematical value including INT_MAX clamp",x==y);Check("leaf/callback call graph unchanged",oldLeaves==leafCalls-before);Check("exact stored keys/FIFO/payload/all recorded logical cache counters",OldSnapshot()==NewSnapshot());Check("loans unwind",!Baseline::gStackDangerScratchBusy&&!Trial::gStackDangerScratchBusy&&!Baseline::gStackVirtualScratchBusy&&!Trial::gStackVirtualScratchBusy);Check("resident scalar matches original actual hit",Trial::gResidentHits==hits||Trial::gStackDangerHits>0);Metadata();}
static void Positions(Baseline::CvTacticalPosition&a,Trial::CvTacticalPosition&b,CvUnit*units,int count){Baseline::CvTacticalPlot oa(0);Trial::CvTacticalPlot ob(0);for(int i=0;i<count;++i){int id=10+i%5;if(i%3==0){oa.fixed.push_back(&units[i%5]);ob.fixed.push_back(&units[i%5]);}else{oa.moving.push_back(Baseline::STacticalUnit(id));ob.moving.push_back(Trial::STacticalUnit(id));}int hp=(i*7)%90;a.availableUnits.write().push_back(Baseline::SUnitStats(id,hp));b.availableUnits.write().push_back(Trial::SUnitStats(id,hp));a.notQuiteFinishedUnits.write().push_back(Baseline::SUnitStats(id,77));b.notQuiteFinishedUnits.write().push_back(Trial::SUnitStats(id,77));}a.tactPlots.write().push_back(oa);b.tactPlots.write().push_back(ob);}
struct ForeignArgs{const Trial::CvTacticalPosition*position;CvUnit*unit;CvPlot*plot;};
static DWORD WINAPI Foreign(void*ptr){ForeignArgs*a=(ForeignArgs*)ptr;unsigned hits=Trial::gResidentHits;Trial::ParentStackPreparationView view(*a->position);Trial::GetUnitDangerForPlot(a->unit,a->plot,0,*a->position);return hits==Trial::gResidentHits&&!view.borrowed&&Trial::gResidentArrivalRequest==NULL?0:1;}
int main(){setvbuf(stdout,NULL,_IONBF,0);Check("native VC9 x86",sizeof(void*)==4&&sizeof(int)==4);CvUnit units[5],actors[3];CvPlot target(0),nearby(1);CvCity city(7,0,&target);
 for(int state=0;state<380;++state){Reset();CvStacking::enabled=true;CvStacking::selectionEnabled=state%4!=0;target.city=state%3==0?&city:NULL;city.hp=40+Next()%260;city.protection=Next()%91;CvDangerPlotContents&c=maps[0].m_DangerPlots[0];c.m_pPlot=&target;c.m_iFogCount=state%5;c.m_iImprovementDamage=state%13;c.m_bFlatPlotDamage=state%2;
  for(int i=0;i<5;++i){units[i]=CvUnit(10+i,0,&target);units[i].hp=50+Next()%51;units[i].ranged=i%2;units[i].defense=20+Next()%50;players[0].units[10+i]=&units[i];}city.garrison=&units[state%5];
  for(int i=0;i<3;++i){actors[i]=CvUnit(44+i,1,&nearby);actors[i].ranged=i%2;actors[i].strength=30+Next()%80;actors[i].aoe=i%3;actors[i].collateralLimit=i%3;players[1].units[44+i]=&actors[i];c.m_apUnits.push_back(make_pair(1,44+i));}
  Baseline::CvTacticalPosition a;Trial::CvTacticalPosition b;Positions(a,b,units,state%12);a.unitDamageDealt.write().SetValue(44,state%50);b.unitDamageDealt.write().SetValue(44,state%50);
  CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);Limits(8+state%15,1200+state%8*1000);Baseline::ParentStackPreparationView oa(a);Trial::ParentStackPreparationView ob(b);
  for(int q=0;q<12;++q)Pair(&units[0],&target,state%41,a,b,q%3==0);
  Baseline::CvTacticalPosition ac;Trial::CvTacticalPosition bc;Baseline::STacticalAssignment aa;Trial::STacticalAssignment ab;aa.unitDamage.SetValue(97,1);ab.unitDamage.SetValue(97,1);Baseline::GetNextPosition(a,&aa,ac);Trial::GetNextPosition(b,&ab,bc);
  for(int q=0;q<5;++q)Pair(&units[0],&target,state%41,ac,bc);
  aa.unitDamage.SetValue(44,9);ab.unitDamage.SetValue(44,9);Baseline::GetNextPosition(a,&aa,ac);Trial::GetNextPosition(b,&ab,bc);for(int q=0;q<4;++q)Pair(&units[0],&target,state%41,ac,bc);
  Pair(&units[1],&target,state%41,a,b);Pair(&units[1],&target,state%41,a,b);Pair(&units[1],&target,state%41,a,b);
  residentTotal+=Trial::gResidentHits;
 }
 printf("randomized full native field/city math completed checks=%u failures=%u\n",checks,failures);
 Reset();target.city=NULL;CvStacking::enabled=CvStacking::selectionEnabled=true;for(int i=0;i<5;++i){units[i]=CvUnit(10+i,0,&target);units[i].hp=units[i].maxHP=500;players[0].units[10+i]=&units[i];}actors[0]=CvUnit(44,1,&nearby);actors[0].ranged=true;actors[0].strength=30;players[1].units[44]=&actors[0];CvDangerPlotContents&c=maps[0].m_DangerPlots[0];c.m_pPlot=&target;c.m_apUnits.push_back(make_pair(1,44));Baseline::CvTacticalPosition a;Trial::CvTacticalPosition b;Positions(a,b,units,4);
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);Baseline::ParentStackPreparationView oa(a);Trial::ParentStackPreparationView ob(b);Pair(&units[0],&target,20,a,b);Pair(&units[0],&target,20,a,b);unsigned first=Trial::gResidentHits;Pair(&units[0],&target,20,a,b);Check("third arrival takes resident path",Trial::gResidentHits==first+1);
  size_t before=Trial::gStackDangerScratch.state.capacity();Baseline::CvTacticalPosition ac;Trial::CvTacticalPosition bc;Baseline::STacticalAssignment aa;Trial::STacticalAssignment ab;aa.unitDamage.SetValue(44,8);ab.unitDamage.SetValue(44,8);Baseline::GetNextPosition(a,&aa,ac);Trial::GetNextPosition(b,&ab,bc);Pair(&units[0],&target,20,ac,bc);Check("projected suffix mismatch retains growth capacity",Baseline::gStackDangerScratch.state.capacity()==Trial::gStackDangerScratch.state.capacity()&&Trial::gStackDangerScratch.state.capacity()>=before);
  aa.unitDamage.SetValue(99,7);ab.unitDamage.SetValue(99,7);Baseline::GetNextPosition(a,&aa,ac);Trial::GetNextPosition(b,&ab,bc);for(int i=0;i<3;++i)Pair(&units[0],&target,20,ac,bc);Check("unrelated projected wounds can certify",Trial::gResidentHits>first);
  Baseline::gStackDangerScratchBusy=Trial::gStackDangerScratchBusy=true;unsigned cert=Trial::gResidentHits;int x=Baseline::GetUnitDangerForPlot(&units[0],&target,20,a),y=Trial::GetUnitDangerForPlot(&units[0],&target,20,b);Check("private busy scratch no certificate",x==y&&Trial::gResidentHits==cert);Baseline::gStackDangerScratchBusy=Trial::gStackDangerScratchBusy=false;
  {Baseline::StackForecastScope no(true);Trial::StackForecastScope nt(true);x=Baseline::GetUnitDangerForPlot(&units[0],&target,20,a);y=Trial::GetUnitDangerForPlot(&units[0],&target,20,b);Check("nested lookup follows original",x==y&&Trial::gResidentHits==cert);}
 }
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);Baseline::ParentStackPreparationView oa(a);Trial::ParentStackPreparationView ob(b);for(int i=0;i<3;++i)Pair(&units[0],&target,20,a,b);ForeignArgs arg={&b,&units[0],&target};HANDLE h=CreateThread(NULL,0,Foreign,&arg,0,NULL);Check("foreign thread created",h!=NULL);if(h){Check("foreign thread finishes",WaitForSingleObject(h,5000)==WAIT_OBJECT_0);DWORD result=1;GetExitCodeThread(h,&result);CloseHandle(h);Check("foreign cannot touch resident token/global cache",result==0);}
  unsigned hits=Trial::gResidentHits;CvStackingDiagnostics::planSamples.enabled=true;CvStackingDiagnostics::planSamples.depth=1;CvStackingDiagnostics::planSamples.serial=8;CvStackingDiagnostics::planSamples.epoch=CvStackingDiagnostics::ReadPlanSampleEpoch();Pair(&units[0],&target,20,a,b);Check("sampling forces original full key",Trial::gResidentHits==hits);CvStackingDiagnostics::planSamples.enabled=false;
 }
 // Both cold/hit graphs remain; new capture has no allocation seam at all.
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);Baseline::ParentStackPreparationView oa(a);Trial::ParentStackPreparationView ob(b);Pair(&units[0],&target,20,a,b);Check("cold miss does not capture",Trial::gResidentCaptures==0);failAllocation=true;int expected=Baseline::GetUnitDangerForPlot(&units[0],&target,20,a);failAllocation=false;failAllocation=true;int got=Trial::GetUnitDangerForPlot(&units[0],&target,20,b);bool armed=failAllocation;failAllocation=false;Check("new capture allocates nothing even while allocator failure armed",armed&&got==expected&&Trial::gResidentCaptures==1&&Baseline::gResidentCaptures==0&&OldSnapshot()==NewSnapshot());Metadata();Pair(&units[0],&target,20,a,b);Pair(&units[0],&target,20,a,b);}
 // Backend-disabled constructor fallback keeps legacy complete keys/results.
 for(int q=0;q<2;++q){CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);Baseline::gUseIndexed=Trial::gUseIndexed=false;Baseline::ParentStackPreparationView oa(a);Trial::ParentStackPreparationView ob(b);for(int i=0;i<3;++i)Pair(&units[0],&target,20,a,b);Check("legacy backend no certificate",Trial::gResidentHits==0);}
 // The new APIs are owner-only and preserve outputs on every failed guard.
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Trial::StackForecastScope trial(true);Trial::ParentStackPreparationView ob(b);unsigned oldPrefixes=Trial::serializedPrefixes,oldLookups=Trial::scalarLookups,oldReturns=Trial::residentReturnCount,oldAcquires=Trial::cellAcquisitions;for(int i=0;i<3;++i)Trial::GetUnitDangerForPlot(&units[0],&target,20,b);Trial::IndexedStore::ScalarHandle h=Trial::gParentStackPreparationStorage.cells[0].resident.handle;vector<int>full(Trial::gIndexed.At(h.slot).Data(),Trial::gIndexed.At(h.slot).Data()+Trial::gIndexed.At(h.slot).keyWords);int prefix[128];size_t count=771;Check("guarded slot copies exact immutable prefix",Trial::gIndexed.TryCopyScalarPrefix(h,&full[0],prefix,128,full.size(),count)&&count==5+2*(size_t)full[4]&&equal(prefix,prefix+count,full.begin()));int value=997;Check("guarded slot matches exact suffix and returns original scalar",Trial::gIndexed.TryMatchScalarSuffix(h,&full[count],full.size()-count,count,value)&&value==Trial::gIndexed.At(h.slot).scalar);for(int mode=0;mode<6;++mode){Trial::IndexedStore::ScalarHandle bad=h;int fixed[4];copy(full.begin(),full.begin()+4,fixed);size_t capacity=128,warmed=full.size(),out=772;prefix[0]=998;if(mode==0)bad.slot=-1;if(mode==1)++bad.lifetime;if(mode==2)++bad.generation;if(mode==3)++fixed[3];if(mode==4)capacity=count-1;if(mode==5)warmed=full.size()-1;Check("prefix failure preserves copied output/count",!Trial::gIndexed.TryCopyScalarPrefix(bad,fixed,prefix,capacity,warmed,out)&&out==772&&prefix[0]==998);}value=997;Check("suffix mismatch preserves result",!Trial::gIndexed.TryMatchScalarSuffix(h,&full[count],full.size()-count,count+1,value)&&value==997);Trial::gIndexed.Clear();Trial::gStackKeyPayloadBytes=0;value=997;Check("post-copy Clear rejects suffix before recycled/freed slot access",!Trial::gIndexed.TryMatchScalarSuffix(h,&full[count],full.size()-count,count,value)&&value==997);Trial::serializedPrefixes=oldPrefixes;Trial::scalarLookups=oldLookups;Trial::residentReturnCount=oldReturns;Trial::cellAcquisitions=oldAcquires;}
 // Directed shared FIFO eviction invalidates the certificate before any slot read.
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);Limits(1,624000);Baseline::ParentStackPreparationView oa(a);Trial::ParentStackPreparationView ob(b);for(int i=0;i<3;++i)Pair(&units[0],&target,20,a,b);unsigned hit=Trial::gResidentHits;Baseline::StackForecastKey x;Trial::StackForecastKey y;for(int i=0;i<6;++i){x.state.push_back(999+i);y.state.push_back(999+i);}Baseline::StoreStackDangerForecast(x,123);Trial::StoreStackDangerForecast(y,123);Pair(&units[0],&target,20,a,b);Check("eviction/recycled slot rejects old generation",Trial::gResidentHits==hit);for(int i=0;i<3;++i)Pair(&units[0],&target,20,a,b);
  Trial::gIndexed.nextScalarGeneration=ULONG_MAX;Baseline::StoreStackDangerForecast(x,321);Trial::StoreStackDangerForecast(y,321);Pair(&units[0],&target,20,a,b);Check("generation exhaustion preserves cache but disables certification",!Trial::gIndexed.scalarHandlesEnabled);Check("original shared cache unaffected by handle exhaustion",OldSnapshot()==NewSnapshot());
  Trial::gIndexed.Clear();Baseline::gIndexed.Clear();Baseline::gStackKeyPayloadBytes=Trial::gStackKeyPayloadBytes=0;Pair(&units[0],&target,20,a,b);Check("Clear changes handle lifetime",Trial::gResidentHits==hit+2);}
 // Directed genuine full-hash collisions: solve the final recurrence word.
 // Full vector equality, not a modified/constant hash service, selects results.
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);Limits(80,624000);for(int n=0;n<24;++n){Baseline::StackForecastKey x;Trial::StackForecastKey y;size_t hash=0;for(int j=0;j<5;++j){int word=300+n*13+j;x.state.push_back(word);y.state.push_back(word);hash^=(size_t)word+0x9e3779b9+(hash<<6)+(hash>>2);}int finalWord=(int)(hash-(0x9e3779b9+(hash<<6)+(hash>>2)));x.state.push_back(finalWord);y.state.push_back(finalWord);Check("genuine full-key hash collision generated",Baseline::StackForecastKeyHash()(x)==0&&Trial::StackForecastKeyHash()(y)==0);Baseline::StoreStackDangerForecast(x,n*17);Trial::StoreStackDangerForecast(y,n*17);int av=-1,bv=-1;Check("collision chain finds exact full key",Baseline::FindStackDangerForecastScalar(x,av)&&Trial::FindStackDangerForecastScalar(y,bv)&&av==n*17&&bv==av);Check("collision shared FIFO/accounting exact",OldSnapshot()==NewSnapshot());}}
 // Actual Scope constructor allocation failure selects its original backend.
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);failAllocation=true;Baseline::StackForecastScope old(true);failAllocation=true;Trial::StackForecastScope trial(true);failAllocation=false;Check("real constructor bad_alloc uses legacy backend",!Baseline::gUseIndexed&&!Trial::gUseIndexed);Baseline::ParentStackPreparationView oa(a);Trial::ParentStackPreparationView ob(b);for(int i=0;i<3;++i)Pair(&units[0],&target,20,a,b);Check("constructor fallback never certifies",Trial::gResidentHits==0);}
 // NULL projected source IDs preserve the original full numerical enemy suffix.
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);CvPlot outside(2);Baseline::ParentStackPreparationView oa(a);Trial::ParentStackPreparationView ob(b);for(int i=0;i<3;++i)Pair(&units[0],&outside,20,a,b);Baseline::CvTacticalPosition ac;Trial::CvTacticalPosition bc;Baseline::STacticalAssignment aa;Trial::STacticalAssignment ab;aa.unitDamage.SetValue(44,7);ab.unitDamage.SetValue(44,7);Baseline::GetNextPosition(a,&aa,ac);Trial::GetNextPosition(b,&ab,bc);for(int i=0;i<3;++i)Pair(&units[0],&outside,20,ac,bc);}
 // Larger duplicate rosters and ordered-city keys retain original fallback.
 {Baseline::CvTacticalPosition ac;Trial::CvTacticalPosition bc;Positions(ac,bc,units,80);target.city=&city;CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);Baseline::ParentStackPreparationView oa(ac);Trial::ParentStackPreparationView ob(bc);for(int i=0;i<4;++i)Pair(&units[0],&target,20,ac,bc);Check("oversized prefix uses original keys",Trial::gResidentHits==0);target.city=NULL;}
 // Unregistered provider and script flags retain exact original/private paths.
 for(int mode=0;mode<2;++mode){MOD_EVENTS_CAN_MOVE_INTO=mode==1;CvStackingStrengthCache::Scope proof(128,mode?ActualProvider:NULL);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);Baseline::ParentStackPreparationView oa(a);Trial::ParentStackPreparationView ob(b);for(int i=0;i<3;++i)Pair(&units[0],&target,20,a,b);Check("missing/callback provider denies certificate",Trial::gResidentHits==0);MOD_EVENTS_CAN_MOVE_INTO=false;}
 // Refresh suspends/invalidate actual Context between prefix and suffix.
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);Baseline::ParentStackPreparationView oa(a);Trial::ParentStackPreparationView ob(b);for(int i=0;i<3;++i)Pair(&units[0],&target,20,a,b);unsigned hit=Trial::gResidentHits;maps[0].m_bDirty=true;int x=Baseline::GetUnitDangerForPlot(&units[0],&target,20,a);maps[0].m_bDirty=true;int y=Trial::GetUnitDangerForPlot(&units[0],&target,20,b);Check("refresh invalidation returns once and rejects resident hit",x==y&&Trial::gResidentHits==hit);}
 // Mutation occurs inside the actual source projection reader, after loan/prefix.
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Trial::StackForecastScope trial(true);unsigned oldPrefixes=Trial::serializedPrefixes,oldLookups=Trial::scalarLookups,oldReturns=Trial::residentReturnCount,oldAcquires=Trial::cellAcquisitions;Trial::ParentStackPreparationView ob(b);for(int i=0;i<3;++i)Trial::GetUnitDangerForPlot(&units[0],&target,20,b);unsigned hits=Trial::gResidentHits,scalarHits=Trial::gStackDangerHits,leaves=leafCalls;fixtureProjectionRefresh=true;int got=Trial::GetUnitDangerForPlot(&units[0],&target,20,b);Check("post-projection Context rejects prepared resident token",Trial::gResidentHits==hits&&Trial::gStackDangerHits==scalarHits&&Trial::gIndexed.Total()==0);Check("invalid prepared miss computes once",leafCalls==leaves+1&&got>=0&&!Trial::gStackDangerScratchBusy);Metadata();Trial::serializedPrefixes=oldPrefixes;Trial::scalarLookups=oldLookups;Trial::residentReturnCount=oldReturns;Trial::cellAcquisitions=oldAcquires;}
 // Terminal table-lifetime exhaustion is certification-only; no extra clear.
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope trial(true);Baseline::ParentStackPreparationView oa(a);Trial::ParentStackPreparationView ob(b);for(int i=0;i<3;++i)Pair(&units[0],&target,20,a,b);Trial::gIndexed.scalarLifetime=ULONG_MAX;Trial::gIndexed.Clear();Baseline::gIndexed.Clear();Baseline::gStackKeyPayloadBytes=Trial::gStackKeyPayloadBytes=0;for(int i=0;i<3;++i)Pair(&units[0],&target,20,a,b);Check("lifetime exhaustion permanently denies handles",Trial::gIndexed.scalarLifetimeExhausted&&!Trial::gIndexed.scalarHandlesEnabled);}
 savedPrefixes=Baseline::serializedPrefixes-Trial::serializedPrefixes;
 Check("lookup work difference equals additional certified returns",Baseline::scalarLookups-Trial::scalarLookups==Trial::residentReturnCount-Baseline::residentReturnCount);Check("new capture never copies metadata keys",Trial::metadataKeyCopies==0&&Baseline::metadataKeyCopies>0);Check("single acquisition eliminates duplicate helper work",Trial::cellAcquisitions<Baseline::cellAcquisitions);
 Check("actual stronger Context/provider exercised",providerCalls>0&&validationCalls>0);Check("resident result reuse still exercised",residentTotal>0);Check("teardown releases optional metadata",Trial::gParentStackPreparationStorage.RetainedBytes()==0&&Trial::gResidentArrivalRequest==NULL);
 printf("RESIDENT SLOT-KEY ACTUAL97: %u checks, %u failures; residentHits=%u eliminatedPrefixBuilds=%u metadataPeak=%u cellDelta=%d storeDelta=%d oldCellAcquisitions=%lu newCellAcquisitions=%lu oldMetadataKeyCopies=%lu newMetadataKeyCopies=%lu\n",checks,failures,Trial::residentReturnCount,savedPrefixes,(unsigned)metadataPeak,(int)sizeof(Trial::ParentStackPreparationCell)-(int)sizeof(Baseline::ParentStackPreparationCell),(int)sizeof(Trial::IndexedStore)-(int)sizeof(Baseline::IndexedStore),Baseline::cellAcquisitions,Trial::cellAcquisitions,Baseline::metadataKeyCopies,Trial::metadataKeyCopies);return failures?1:0;
}
'''
code=scope['headers']+'\n#include <cassert>\n'+scope['strength_header']+scope['strength_module']+scope['native_services']+base+services+implementation+tests
(OUT/'test.cpp').write_text(code,encoding='utf-8',newline='\n')
report=dict(proof,production_bound=args.production,actual_whole_hashes=actual_hashes,unchanged_dependencies={n:hashlib.sha256(s.encode()).hexdigest() for n,s in source.items() if n!='CvTacticalAI.cpp'},complete_math_bindings=scope['math_bindings'],fixture_sha256=hashlib.sha256(code.encode()).hexdigest(),scope='actual pinned Context/provider/strength/indexed/backend/packet/keys/CoW/GetUnitStats/ParentPreparation/GetNext/UnitDanger + full field/city/air/collateral math; deterministic engine/tactical plot services; no native ROI')
(OUT/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
if args.emit_only:print(OUT/'test.cpp');sys.exit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
build=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/GS','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(OUT/'test.cpp'),'/Fo'+str(OUT/'test.obj'),'/Fe'+str(OUT/'test.exe')],cwd=OUT,env=env,capture_output=True,text=True,timeout=90);(OUT/'compile.log').write_text(build.stdout+build.stderr)
if build.returncode:print(build.stdout+build.stderr);sys.exit(build.returncode)
run=subprocess.run([str(OUT/'test.exe')],cwd=OUT,capture_output=True,text=True,timeout=45);print(run.stdout+run.stderr,end='');report.update(compile_returncode=build.returncode,test_returncode=run.returncode,output=run.stdout+run.stderr);(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');sys.exit(run.returncode)
