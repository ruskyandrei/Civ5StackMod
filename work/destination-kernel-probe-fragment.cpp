// BEGIN DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
// Observe original destination kernels. This metadata NEVER returns a score,
// admits a forecast, changes a candidate or substitutes for original work.
enum { KERNEL_PROBE_SLOTS=128,KERNEL_PROBE_WORDS=2048,KERNEL_PROBE_PARTICIPANTS=128,KERNEL_PROBE_SOURCE_WORDS=512,KERNEL_PROBE_STRIDE=64,KERNEL_PROBE_STATES=8192,KERNEL_PROBE_STATE_LOOKUP_LIMIT=64 };
struct DestinationKernelProbeSlot
{
 bool used;unsigned count,kind;unsigned long hash;int result;
 unsigned __int64 incarnation;
 int words[KERNEL_PROBE_WORDS];
};
struct DestinationKernelProbeCounts
{
 unsigned __int64 calls,selected,complete,groups,repeats,sameState,crossState,parentChild,unknownRelation,mismatches,zeroKeys;
 unsigned __int64 keyVisits,scalarHits,scalarMisses,outcomeBuilds,prepInsideTicks,prepOutsideTicks,kernelTicks;
 DestinationKernelProbeCounts():calls(0),selected(0),complete(0),groups(0),repeats(0),sameState(0),crossState(0),parentChild(0),unknownRelation(0),mismatches(0),zeroKeys(0),keyVisits(0),scalarHits(0),scalarMisses(0),outcomeBuilds(0),prepInsideTicks(0),prepOutsideTicks(0),kernelTicks(0){}
};
struct DestinationKernelStateIncarnation{const CvTacticalPosition* state;unsigned __int64 incarnation,parent;DestinationKernelStateIncarnation():state(NULL),incarnation(0),parent(0){}};
struct DestinationKernelProbeState
{
 DestinationKernelProbeSlot slots[KERNEL_PROBE_SLOTS];DestinationKernelProbeCounts kinds[2];
 DestinationKernelStateIncarnation states[KERNEL_PROBE_STATES];unsigned __int64 nextIncarnation,unknownStates;
 int words[KERNEL_PROBE_WORDS],beforeSource[KERNEL_PROBE_SOURCE_WORDS],afterSource[KERNEL_PROBE_SOURCE_WORDS];
 const CvUnit* participants[KERNEL_PROBE_PARTICIPANTS];unsigned participantOffsets[KERNEL_PROBE_PARTICIPANTS];
 unsigned count,sourceCount,participantCount,next;bool busy;
 unsigned long serial,revision;long epoch,scene;PlayerTypes owner;int target;
 unsigned __int64 frequency,evictions,clears,oversized,unavailable,invalidated,nested,allocationFailed,keyBytes,peakKeyBytes;
 DestinationKernelProbeState():nextIncarnation(0),unknownStates(0),count(0),sourceCount(0),participantCount(0),next(0),busy(false),serial(0),revision(0),epoch(0),scene(0),owner(NO_PLAYER),target(-1),frequency(0),evictions(0),clears(0),oversized(0),unavailable(0),invalidated(0),nested(0),allocationFailed(0),keyBytes(0),peakKeyBytes(0)
 {for(unsigned i=0;i<KERNEL_PROBE_SLOTS;++i)slots[i].used=false;}
 void Clear(){for(unsigned i=0;i<KERNEL_PROBE_SLOTS;++i)slots[i].used=false;next=0;keyBytes=0;++clears;}
 bool Add(int v){if(count==KERNEL_PROBE_WORDS)return false;words[count++]=v;return true;}
};
typedef char DestinationKernelProbeMetadataBound[sizeof(DestinationKernelProbeState)<=3*1024*1024?1:-1];
static __declspec(thread) DestinationKernelProbeState* gDestinationKernelProbe=NULL;
struct DestinationKernelProbeFrame;
static __declspec(thread) DestinationKernelProbeFrame* gDestinationKernelFrame=NULL;
static unsigned long KernelProbeHash(const int* words,unsigned count,unsigned long seed=0)
{for(unsigned i=0;i<count;++i)seed^=(unsigned long)words[i]+0x9e3779b9UL+(seed<<6)+(seed>>2);seed^=seed>>16;seed*=0x7feb352dUL;seed^=seed>>15;seed*=0x846ca68bUL;return seed^(seed>>16);}
static DestinationKernelStateIncarnation* KernelProbeIncarnation(DestinationKernelProbeState& probe,const CvTacticalPosition* position)
{
 if(!position)return NULL;const int pointer=(int)(size_t)position;const unsigned bucket=KernelProbeHash(&pointer,1)&(KERNEL_PROBE_STATES-1);
 for(unsigned i=0;i<KERNEL_PROBE_STATE_LOOKUP_LIMIT;++i)
 {DestinationKernelStateIncarnation& slot=probe.states[(bucket+i)&(KERNEL_PROBE_STATES-1)];if(slot.state==position)return &slot;if(!slot.state){slot.state=position;slot.incarnation=++probe.nextIncarnation;return &slot;}}
 ++probe.unknownStates;return NULL;
}
// Reused stack temporaries and rejected position slots can share their old
// address, ID and generation. Explicit reset/mutation hooks give each a fresh
// diagnostic token; these tokens never participate in gameplay or equality.
static inline void ObserveKernelStateMutation(const CvTacticalPosition* position,const CvTacticalPosition* parent)
{
 DestinationKernelProbeState* probe=gDestinationKernelProbe;if(!probe)return;
 DestinationKernelStateIncarnation* slot=KernelProbeIncarnation(*probe,position);if(!slot)return;
 DestinationKernelStateIncarnation* ancestor=KernelProbeIncarnation(*probe,parent);
 slot->incarnation=++probe->nextIncarnation;slot->parent=ancestor?ancestor->incarnation:0;
}
static unsigned __int64 KernelProbeTick(){LARGE_INTEGER tick;if(!QueryPerformanceCounter(&tick)||tick.QuadPart<0)return 0;return(unsigned __int64)tick.QuadPart;}
static unsigned __int64 KernelProbeElapsed(unsigned __int64 a,unsigned __int64 b){return a&&b>=a?b-a:0;}
// Direct values deliberately strengthen the old scalar keys. This is still
// an observed footprint, NOT certification of every deeper combat dependency.
static unsigned KernelProbeUnitWords(const CvUnit* unit,int* values)
{
 if(!unit)return 0;
 values[0]=(int)(size_t)unit;values[1]=unit->getOwner();values[2]=unit->getTeam();values[3]=unit->GetID();
 values[4]=unit->getDomainType();values[5]=unit->GetCurrHitPoints();values[6]=unit->GetMaxHitPoints();
 values[7]=unit->IsCombatUnit()?1:0;values[8]=unit->isCargo()?1:0;values[9]=unit->isDelayedDeath()?1:0;
 values[10]=unit->IsCanAttackRanged()?1:0;values[11]=unit->IsCanDefend()?1:0;values[12]=CvStacking::IsAntiCavalry(unit)?1:0;
 values[13]=unit->ignoreTerrainDamage()?1:0;values[14]=unit->ignoreFeatureDamage()?1:0;
 values[15]=unit->extraTerrainDamage();values[16]=unit->extraFeatureDamage();return 17;
}
static bool KernelProbeAddUnit(DestinationKernelProbeState& state,const CvUnit* unit)
{
 if(state.participantCount==KERNEL_PROBE_PARTICIPANTS)return false;
 int values[17];unsigned count=KernelProbeUnitWords(unit,values);if(!count)return false;
 state.participants[state.participantCount]=unit;state.participantOffsets[state.participantCount++]=state.count;
 for(unsigned i=0;i<count;++i)if(!state.Add(values[i]))return false;return true;
}
static bool KernelProbeAddDamage(DestinationKernelProbeState& state,const SUnitIDValueContainer& damage)
{
 unsigned at=state.count;if(!state.Add(0))return false;unsigned count=0;
 for(SUnitIDValueContainer::const_iterator i=damage.begin();i!=damage.end();++i)
 {if(!state.Add((*i).first)||!state.Add((*i).second))return false;++count;}
 state.words[at]=(int)count;return true; // Raw order/zeros/duplicates are retained.
}
struct DestinationKernelProbeSession
{
 DestinationKernelProbeState* state;
 DestinationKernelProbeSession(PlayerTypes owner,int target):state(NULL)
 {
  unsigned long serial=0;long epoch=0;
  if(gDestinationKernelProbe||!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch))return;
  if(!IsStackForecastOwner()||!StackForecastContext())return;
  try{state=new DestinationKernelProbeState;}catch(std::bad_alloc&){return;}
  LARGE_INTEGER frequency;if(QueryPerformanceFrequency(&frequency)&&frequency.QuadPart>0)state->frequency=(unsigned __int64)frequency.QuadPart;
  state->serial=serial;state->epoch=epoch;state->revision=gStackForecastRevision;state->scene=gStackForecastSceneEpoch;state->owner=owner;state->target=target;
  gDestinationKernelProbe=state;
 }
 ~DestinationKernelProbeSession(){Finish();}
 void Finish()
 {
  if(!state||gDestinationKernelProbe!=state)return;
  DestinationKernelProbeState* done=state;unsigned long serial=0;long epoch=0;
  if(CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)&&serial==done->serial&&epoch==done->epoch)
  {
   const DestinationKernelProbeCounts& a=done->kinds[0];const DestinationKernelProbeCounts& b=done->kinds[1];
   CvStackingDiagnostics::Record(1,done->owner,"PLAN_KERNEL_PROBE",
    "version=1 serial=%lu target=%d thread=%lu stride=64 slots=128 words=2048 stateSlots=8192 frequency=%I64u metadataBytes=%u unitCalls=%I64u unitSelected=%I64u unitComplete=%I64u unitGroups=%I64u unitRepeats=%I64u unitSameIncarnation=%I64u unitCrossIncarnation=%I64u unitParentAtMutation=%I64u unitUnknownRelation=%I64u unitMismatches=%I64u unitZeroKeys=%I64u unitKeyVisits=%I64u unitScalarHits=%I64u unitScalarMisses=%I64u unitOutcomeBuilds=%I64u unitPrepInsideTicks=%I64u unitPrepOutsideTicks=%I64u unitKernelTicks=%I64u stackCalls=%I64u stackSelected=%I64u stackComplete=%I64u stackGroups=%I64u stackRepeats=%I64u stackSameIncarnation=%I64u stackCrossIncarnation=%I64u stackParentAtMutation=%I64u stackUnknownRelation=%I64u stackMismatches=%I64u stackZeroKeys=%I64u stackKeyVisits=%I64u stackScalarHits=%I64u stackScalarMisses=%I64u stackOutcomeBuilds=%I64u stackPrepInsideTicks=%I64u stackPrepOutsideTicks=%I64u stackKernelTicks=%I64u evictions=%I64u clears=%I64u oversized=%I64u unavailable=%I64u invalidated=%I64u nested=%I64u unknownStates=%I64u keyBytes=%I64u peakKeyBytes=%I64u note=observed_footprint_not_certified_reuse_no_stride_scaling_inclusive_kernel_overlaps_prepInside",
    done->serial,done->target,GetCurrentThreadId(),done->frequency,(unsigned)sizeof(*done),
    a.calls,a.selected,a.complete,a.groups,a.repeats,a.sameState,a.crossState,a.parentChild,a.unknownRelation,a.mismatches,a.zeroKeys,a.keyVisits,a.scalarHits,a.scalarMisses,a.outcomeBuilds,a.prepInsideTicks,a.prepOutsideTicks,a.kernelTicks,
    b.calls,b.selected,b.complete,b.groups,b.repeats,b.sameState,b.crossState,b.parentChild,b.unknownRelation,b.mismatches,b.zeroKeys,b.keyVisits,b.scalarHits,b.scalarMisses,b.outcomeBuilds,b.prepInsideTicks,b.prepOutsideTicks,b.kernelTicks,
    done->evictions,done->clears,done->oversized,done->unavailable,done->invalidated,done->nested,done->unknownStates,done->keyBytes,done->peakKeyBytes);
  }
  gDestinationKernelProbe=NULL;gDestinationKernelFrame=NULL;state=NULL;delete done;
 }
private:DestinationKernelProbeSession(const DestinationKernelProbeSession&);DestinationKernelProbeSession& operator=(const DestinationKernelProbeSession&);
};
struct DestinationKernelProbeFrame
{
 DestinationKernelProbeState* state;const CvUnit* unit;const CvPlot* plot;const CvTacticalPosition* position;
 unsigned kind,keyVisits;bool valid;unsigned long revision;long scene;
 unsigned __int64 begun,prepTicks,insideTicks,incarnation,parentIncarnation;unsigned long beforeHits,beforeMisses,beforeBuilds;
 DestinationKernelProbeFrame(unsigned kind,const CvUnit* unit,const CvPlot* plot,const CvTacticalPosition& position,int extra,
  const vector<const CvUnit*>* candidates=NULL,const SUnitIDValueContainer* damage=NULL):state(NULL)
 {if(gDestinationKernelProbe)BeginActive(kind,unit,plot,position,extra,candidates,damage);}
 void BeginActive(unsigned kind,const CvUnit* unit,const CvPlot* plot,const CvTacticalPosition& position,int extra,
  const vector<const CvUnit*>* candidates,const SUnitIDValueContainer* damage)
 {
  this->unit=unit;this->plot=plot;this->position=&position;this->kind=kind;keyVisits=0;valid=false;revision=0;scene=0;begun=prepTicks=insideTicks=incarnation=parentIncarnation=0;beforeHits=beforeMisses=beforeBuilds=0;
  DestinationKernelProbeState* active=gDestinationKernelProbe;if(!active||kind>1)return;
  ++active->kinds[kind].calls;
  if(gDestinationKernelFrame||active->busy){++active->nested;return;}
  if(!unit||!plot||sizeof(void*)!=4){++active->unavailable;return;}
  const int cohort[4]={(int)kind,unit->getOwner(),unit->GetID(),plot->GetPlotIndex()};
  if(KernelProbeHash(cohort,4)&(KERNEL_PROBE_STRIDE-1))return;
  ++active->kinds[kind].selected;unsigned __int64 prepare=KernelProbeTick();
  unsigned long serial=0;long epoch=0;
  if(!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)||serial!=active->serial||epoch!=active->epoch||!StackForecastContext())
  {++active->unavailable;return;}
  if(active->revision!=gStackForecastRevision||active->scene!=gStackForecastSceneEpoch)
  {active->Clear();active->revision=gStackForecastRevision;active->scene=gStackForecastSceneEpoch;}
  const unsigned long preparingRevision=gStackForecastRevision;const long preparingScene=gStackForecastSceneEpoch;
  struct PreparingGuard{bool& busy;bool committed;PreparingGuard(bool& b):busy(b),committed(false){busy=true;}~PreparingGuard(){if(!committed)busy=false;}} preparing(active->busy);
  const CvDangerPlots* map=GET_PLAYER(unit->getOwner()).GetDangerPlots();unsigned used=0;
  if(map->IsDirty()||!map->AppendStackDangerCacheDescriptor(*plot,active->beforeSource,KERNEL_PROBE_SOURCE_WORDS,used))
  {++active->unavailable;return;} // Never refresh a source before original work.
  active->count=active->participantCount=0;active->sourceCount=used;
  bool okay=active->Add((int)kind)&&active->Add(plot->GetPlotIndex())&&active->Add(extra)&&KernelProbeAddUnit(*active,unit)&&KernelProbeAddDamage(*active,position.GetUnitDamageDealt());
  for(unsigned i=0;i<used&&okay;++i)okay=active->Add(active->beforeSource[i]);
  if(candidates&&damage)
  {okay=okay&&active->Add((int)candidates->size())&&KernelProbeAddDamage(*active,*damage);for(size_t i=0;i<candidates->size()&&okay;++i)okay=KernelProbeAddUnit(*active,(*candidates)[i]);}
  if(!okay){++active->oversized;return;}
  if(!StackForecastContext()||preparingRevision!=gStackForecastRevision||preparingScene!=gStackForecastSceneEpoch||preparingScene!=CvStackingStrengthCache::SceneEpoch()){++active->invalidated;return;}
  DestinationKernelStateIncarnation* identity=KernelProbeIncarnation(*active,&position);if(identity){incarnation=identity->incarnation;parentIncarnation=identity->parent;}
  revision=gStackForecastRevision;scene=gStackForecastSceneEpoch;beforeHits=gStackDangerHits;beforeMisses=gStackDangerMisses;beforeBuilds=gStackOutcomeBuilds;
  state=active;valid=true;gDestinationKernelFrame=this;preparing.committed=true;prepTicks=KernelProbeElapsed(prepare,KernelProbeTick());begun=KernelProbeTick();
 }
 ~DestinationKernelProbeFrame(){if(state)Release();} // Exceptions never complete a result.
 void Release(){if(state&&state==gDestinationKernelProbe&&gDestinationKernelFrame==this){state->busy=false;gDestinationKernelFrame=NULL;state=NULL;}}
 void AddDanger(const CvUnit* queried,const CvPlot* target,const vector<const CvUnit*>& candidates,
  const SUnitIDValueContainer& friendly,const StackForecastKey& key,bool cacheable)
 {
  if(!state||state!=gDestinationKernelProbe||gDestinationKernelFrame!=this||!valid)return;
  unsigned __int64 prepare=KernelProbeTick();
  if(!cacheable||target!=plot){valid=false;++state->unavailable;return;}
  ++keyVisits;bool okay=state->Add(0x4b4559)&&state->Add((int)key.state.size())&&KernelProbeAddUnit(*state,queried)&&state->Add((int)candidates.size())&&KernelProbeAddDamage(*state,friendly);
  for(size_t i=0;i<candidates.size()&&okay;++i)okay=KernelProbeAddUnit(*state,candidates[i]);
  for(size_t i=0;i<key.state.size()&&okay;++i)okay=state->Add(key.state[i]);
  if(!okay){valid=false;++state->oversized;}
  insideTicks+=KernelProbeElapsed(prepare,KernelProbeTick());
 }
 int Finish(int result){if(state)FinishActive(result);return result;}
 void FinishActive(int result)
 {
  if(!state||state!=gDestinationKernelProbe||gDestinationKernelFrame!=this)return;
  unsigned __int64 end=KernelProbeTick(),prepare=KernelProbeTick();DestinationKernelProbeState& s=*state;DestinationKernelProbeCounts& counts=s.kinds[kind];
  unsigned long serial=0;long epoch=0;unsigned used=0;
  bool okay=valid&&CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)&&serial==s.serial&&epoch==s.epoch&&StackForecastContext()&&
   revision==gStackForecastRevision&&scene==gStackForecastSceneEpoch;
  if(okay)
  {
   const CvDangerPlots* map=GET_PLAYER(unit->getOwner()).GetDangerPlots();
   okay=!map->IsDirty()&&map->AppendStackDangerCacheDescriptor(*plot,s.afterSource,KERNEL_PROBE_SOURCE_WORDS,used)&&
    used==s.sourceCount&&std::equal(s.beforeSource,s.beforeSource+used,s.afterSource)&&
    StackForecastContext()&&revision==gStackForecastRevision&&scene==gStackForecastSceneEpoch;
  }
  for(unsigned i=0;i<s.participantCount&&okay;++i){int values[17];unsigned n=KernelProbeUnitWords(s.participants[i],values);okay=n==17&&std::equal(values,values+n,s.words+s.participantOffsets[i]);}
  okay=okay&&StackForecastContext()&&revision==gStackForecastRevision&&scene==gStackForecastSceneEpoch;
  if(!okay){++s.invalidated;Release();return;}
  ++counts.complete;counts.keyVisits+=keyVisits;counts.scalarHits+=gStackDangerHits-beforeHits;counts.scalarMisses+=gStackDangerMisses-beforeMisses;counts.outcomeBuilds+=gStackOutcomeBuilds-beforeBuilds;if(!keyVisits)++counts.zeroKeys;
  unsigned long hash=KernelProbeHash(s.words,s.count);DestinationKernelProbeSlot* found=NULL;
  for(unsigned i=0;i<KERNEL_PROBE_SLOTS;++i)if(s.slots[i].used&&s.slots[i].hash==hash&&s.slots[i].count==s.count&&std::equal(s.words,s.words+s.count,s.slots[i].words)){found=&s.slots[i];break;}
  if(found)
  {
   ++counts.repeats;if(found->result!=result)++counts.mismatches;
   if(!incarnation||!found->incarnation)++counts.unknownRelation;
   else if(found->incarnation==incarnation)++counts.sameState;else ++counts.crossState;
   if(parentIncarnation&&parentIncarnation==found->incarnation)++counts.parentChild;
  }
  else
  {
   ++counts.groups;found=&s.slots[s.next];s.next=(s.next+1)%KERNEL_PROBE_SLOTS;
   if(found->used){++s.evictions;s.keyBytes-=found->count*sizeof(int);}found->used=true;found->count=s.count;found->hash=hash;found->kind=kind;found->result=result;
   std::copy(s.words,s.words+s.count,found->words);s.keyBytes+=s.count*sizeof(int);s.peakKeyBytes=std::max(s.peakKeyBytes,s.keyBytes);
  }
  found->incarnation=incarnation;
  counts.kernelTicks+=KernelProbeElapsed(begun,end);counts.prepInsideTicks+=insideTicks;counts.prepOutsideTicks+=prepTicks+KernelProbeElapsed(prepare,KernelProbeTick());Release();
 }
private:DestinationKernelProbeFrame(const DestinationKernelProbeFrame&);DestinationKernelProbeFrame& operator=(const DestinationKernelProbeFrame&);
};
static inline void ObserveDestinationDangerKey(const CvUnit* unit,const CvPlot* plot,const vector<const CvUnit*>& candidates,
 const SUnitIDValueContainer& friendly,const StackForecastKey& key,bool cacheable)
{if(gDestinationKernelFrame)gDestinationKernelFrame->AddDanger(unit,plot,candidates,friendly,key,cacheable);}
// END DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
