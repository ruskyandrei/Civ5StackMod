// BEGIN PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
// Metadata only: no result/assignment/cache admission reads these fields.
enum { PACKET_PROBE_SLOTS=128, PACKET_PROBE_WORDS=512, PACKET_PROBE_PAIRS=128 };
struct PacketProbeSlot
{
 bool used,city;
 unsigned count;
 unsigned long hash,seen,fresh;
 unsigned outputUpper;
 int words[PACKET_PROBE_WORDS];
};
struct PacketProbeState
{
 PacketProbeSlot slots[PACKET_PROBE_SLOTS];
 int key[PACKET_PROBE_WORDS],source[PACKET_PROBE_WORDS];
 unsigned count,sourceStart,sourceCount,next;
 unsigned long serial,thread,revision;
 long epoch,scene;
 PlayerTypes actor;
 int target;
 bool busy;
 unsigned __int64 misses,prefilter,cohort,groups,repeats,sameMember,crossMember;
 unsigned __int64 freshQueries,batchReuseQueries,freshRepeatQueries,freshCrossMemberQueries;
 unsigned __int64 rawCalls,outcomeBuildAttempts;
 unsigned __int64 fallback,oversized,unavailable,invalidated,reentrant,evictions,clears;
 unsigned __int64 fieldGroups,cityGroups,keyBytes,peakKeyBytes,outputUpperBytes,peakOutputUpperBytes;
 PacketProbeState():count(0),sourceStart(0),sourceCount(0),next(0),serial(0),thread(0),revision(0),epoch(0),scene(0),actor(NO_PLAYER),target(-1),busy(false),
  misses(0),prefilter(0),cohort(0),groups(0),repeats(0),sameMember(0),crossMember(0),freshQueries(0),batchReuseQueries(0),freshRepeatQueries(0),freshCrossMemberQueries(0),rawCalls(0),outcomeBuildAttempts(0),
  fallback(0),oversized(0),unavailable(0),invalidated(0),reentrant(0),evictions(0),clears(0),fieldGroups(0),cityGroups(0),keyBytes(0),peakKeyBytes(0),outputUpperBytes(0),peakOutputUpperBytes(0)
 { for(unsigned i=0;i<PACKET_PROBE_SLOTS;++i)slots[i].used=false; }
 void Clear(){for(unsigned i=0;i<PACKET_PROBE_SLOTS;++i)slots[i].used=false;next=0;keyBytes=outputUpperBytes=0;++clears;}
 bool Add(int value){if(count==PACKET_PROBE_WORDS)return false;key[count++]=value;return true;}
};
static __declspec(thread) PacketProbeState* gPacketProbeState=NULL;
static unsigned long PacketProbeMix(unsigned long value)
{ value^=value>>16;value*=0x7feb352dUL;value^=value>>15;value*=0x846ca68bUL;value^=value>>16;return value; }
static unsigned long PacketProbeHash(const int* words,unsigned count,unsigned long seed)
{ for(unsigned i=0;i<count;++i)seed^=(unsigned long)words[i]+0x9e3779b9UL+(seed<<6)+(seed>>2);return PacketProbeMix(seed); }
static bool PacketProbeUnique(const SUnitIDValueContainer& damage)
{
 int ids[PACKET_PROBE_PAIRS];unsigned count=0;
 for(SUnitIDValueContainer::const_iterator i=damage.begin();i!=damage.end();++i)
 {if(count==PACKET_PROBE_PAIRS)return false;int id=(*i).first;for(unsigned j=0;j<count;++j)if(ids[j]==id)return false;ids[count++]=id;}
 return true;
}
static bool PacketProbeDamage(PacketProbeState& state,const SUnitIDValueContainer& damage)
{
 pair<int,int> pairs[PACKET_PROBE_PAIRS];unsigned count=0;
 for(SUnitIDValueContainer::const_iterator i=damage.begin();i!=damage.end();++i)
 {if(count==PACKET_PROBE_PAIRS)return false;const SUnitIDValueContainer::value_type entry=*i;if(entry.second)pairs[count++]=entry;}
 std::sort(pairs,pairs+count);if(!state.Add((int)count))return false;
 for(unsigned i=0;i<count;++i)if(!state.Add(pairs[i].first)||!state.Add(pairs[i].second))return false;
 return true;
}
struct PacketProbeScope
{
 PacketProbeState* state;
 const void* threadState;
 PacketProbeScope(PlayerTypes actor,int target):state(NULL),threadState(&gPacketProbeState)
 {
  unsigned long serial=0;long epoch=0;
  if(gPacketProbeState||!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch))return;
  // Check once after the disabled TLS gate, before any owner-only shared reads.
  if(!IsStackForecastOwner()||!gStackForecastsActive||gStackForecastDepth!=1||MOD_EVENTS_CAN_MOVE_INTO)return;
  // A hard diagnostic bound, independent of every gameplay/result-cache cap.
  if(sizeof(PacketProbeState)>3*1024*1024)return;
  state=new(std::nothrow)PacketProbeState;if(!state)return;
  state->serial=serial;state->epoch=epoch;state->actor=actor;state->target=target;state->thread=GetCurrentThreadId();
  state->revision=gStackForecastRevision;state->scene=gStackForecastSceneEpoch;gPacketProbeState=state;
 }
 ~PacketProbeScope(){Finish();}
 void Finish()
 {
  if(!state||threadState!=&gPacketProbeState||gPacketProbeState!=state)return;
  PacketProbeState* done=state;state=NULL;gPacketProbeState=NULL;
  unsigned long serial=0;long epoch=0;
  if(CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)&&serial==done->serial&&epoch==done->epoch)
   CvStackingDiagnostics::Record(1,done->actor,"PLAN_PACKET_PROBE",
    "targetPlot=%d serial=%lu thread=%lu version=1 prefilterBits=2 cohortBits=3 slots=128 maxKeyWords=512 metadataBytes=%u misses=%I64u prefiltered=%I64u cohortQueries=%I64u groups=%I64u repeats=%I64u sameMember=%I64u crossMember=%I64u freshQueries=%I64u batchReuseQueries=%I64u freshRepeatQueries=%I64u freshCrossMemberQueries=%I64u rawCalls=%I64u outcomeBuildAttempts=%I64u fieldGroups=%I64u cityGroups=%I64u fallback=%I64u oversized=%I64u sourceUnavailable=%I64u invalidated=%I64u reentrant=%I64u evictions=%I64u clears=%I64u keyBytes=%I64u peakKeyBytes=%I64u outputUpperBytes=%I64u peakOutputUpperBytes=%I64u; metadata cohorts are censored by sampling/bounds/eviction; fresh fields count queries, build attempts may fail; no stride-scaled saved simulations; output bytes are an upper estimate, not actual retained capacity",
    done->target,done->serial,done->thread,(unsigned)sizeof(PacketProbeState),done->misses,done->prefilter,done->cohort,done->groups,done->repeats,done->sameMember,done->crossMember,
    done->freshQueries,done->batchReuseQueries,done->freshRepeatQueries,done->freshCrossMemberQueries,done->rawCalls,done->outcomeBuildAttempts,done->fieldGroups,done->cityGroups,done->fallback,done->oversized,done->unavailable,done->invalidated,done->reentrant,
    done->evictions,done->clears,done->keyBytes,done->peakKeyBytes,done->outputUpperBytes,done->peakOutputUpperBytes);
  delete done;
 }
private:PacketProbeScope(const PacketProbeScope&);PacketProbeScope&operator=(const PacketProbeScope&);
};
struct PacketProbeCall
{
 PacketProbeState* state;
 const void* threadState;
 const CvDangerPlots* danger;
 const CvPlot* plot;
 unsigned member,outputUpper;
 unsigned long beforeBuilds,revision;
 long scene;
 bool raw,city;
 PacketProbeCall(const CvUnit* unit,const CvPlot* target,const vector<const CvUnit*>& roster,
  const SUnitIDValueContainer& friendly,const SUnitIDValueContainer& enemy,const StackForecastKey& scalarKey,bool eligible):
  state(NULL),threadState(&gPacketProbeState),danger(NULL),plot(target),member(0),outputUpper(0),beforeBuilds(0),revision(0),scene(0),raw(false),city(false)
 {
  PacketProbeState* active=gPacketProbeState;unsigned long serial=0;long epoch=0;
  if(!active||!eligible)return;
  if(!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)||serial!=active->serial||epoch!=active->epoch)return;
  ++active->misses;if(active->busy){++active->reentrant;return;}
  if(active->revision!=gStackForecastRevision||active->scene!=gStackForecastSceneEpoch)
  {active->Clear();active->revision=gStackForecastRevision;active->scene=gStackForecastSceneEpoch;}
  if(scalarKey.state.size()<5){++active->fallback;return;}
  const unsigned long salt=PacketProbeMix(active->serial*2246822519UL+(unsigned long)active->scene+active->revision*3266489917UL);
  unsigned long hash=salt;
  // Equal supported full packet keys imply this same scalar tail. Omit only
  // query-ID and own-wound prefix; malformed injury storage is unsupported.
  for(size_t i=1;i<scalarKey.state.size();++i)if(i!=2)hash^=(unsigned long)scalarKey.state[i]+0x9e3779b9UL+(hash<<6)+(hash>>2);
  if(PacketProbeMix(hash)&3UL)return;++active->prefilter;
  if(!unit||!target||!unit->IsCombatUnit()||!unit->isNativeDomain(target)||roster.size()<2||!PacketProbeUnique(friendly)||!PacketProbeUnique(enemy))
  {++active->fallback;return;}
  const CvUnit* unique[32];unsigned uniques=0;bool found=false;
  for(size_t i=0;i<roster.size();++i)
  {
   const CvUnit* u=roster[i];
   if(!u||u->getOwner()!=unit->getOwner()){++active->fallback;return;}
   const CvPlayer& owner=GET_PLAYER(u->getOwner());if(owner.getUnit(u->GetID())!=u){++active->fallback;return;}
   unsigned j=0;for(;j<uniques;++j)if(unique[j]==u)break;
   if(j==uniques){if(uniques==32){++active->oversized;return;}unique[uniques++]=u;}
   if(u==unit){member=j;found=true;}
  }
  if(!found||uniques<2){++active->fallback;return;}
  active->count=0;city=target->isFriendlyCity(*unit);
  if(!active->Add(unit->getOwner())||!active->Add(unit->getTeam())||!active->Add(target->GetPlotIndex())||!active->Add(city?1:0)||!active->Add((int)roster.size())){++active->oversized;return;}
  for(size_t i=0;i<roster.size();++i)if(!active->Add(roster[i]->getOwner())||!active->Add(roster[i]->GetID())){++active->oversized;return;}
  if(!PacketProbeDamage(*active,friendly)){++active->oversized;return;}
  danger=GET_PLAYER(unit->getOwner()).GetDangerPlots();active->sourceStart=active->count;
  if(!danger||!danger->AppendStackDangerProbeSources(*target,active->key,PACKET_PROBE_WORDS,active->count)){++active->unavailable;return;}
  active->sourceCount=active->count-active->sourceStart;
  // The original scalar key has already freshly projected enemy injuries.
  const unsigned rosterWords=(unsigned)scalarKey.state[4];
  if(rosterWords!=roster.size()||rosterWords>(scalarKey.state.size()-5)/2){++active->fallback;return;}
  const size_t suffix=5+2*rosterWords;
  if(suffix>=scalarKey.state.size()||scalarKey.state[suffix]<0||scalarKey.state.size()-suffix!=1+2*(size_t)scalarKey.state[suffix]){++active->fallback;return;}
  for(size_t i=suffix;i<scalarKey.state.size();++i)if(!active->Add(scalarKey.state[i])){++active->oversized;return;}
  if(PacketProbeHash(active->key,active->count,salt^0xa5a5a5a5UL)&7UL)return;
  // Union of input-stored IDs and roster IDs bounds a copied final-ledger size;
  // it is not a measured vector capacity or a predicted packet residency cost.
  int ids[PACKET_PROBE_PAIRS+32];unsigned unions=0;
  for(SUnitIDValueContainer::const_iterator i=friendly.begin();i!=friendly.end();++i)ids[unions++]=(*i).first;
  for(unsigned i=0;i<uniques;++i){unsigned j=0;for(;j<unions;++j)if(ids[j]==unique[i]->GetID())break;if(j==unions)ids[unions++]=unique[i]->GetID();}
  outputUpper=unions*sizeof(SUnitIDValueContainer::value_type);
  ++active->cohort;active->busy=true;state=active;revision=gStackForecastRevision;scene=gStackForecastSceneEpoch;beforeBuilds=gStackOutcomeBuilds;
 }
 void MarkRaw(){raw=true;}
 ~PacketProbeCall(){Finish();}
 void Finish()
 {
  if(!state||threadState!=&gPacketProbeState||gPacketProbeState!=state)return;
  PacketProbeState* done=state;state=NULL;done->busy=false;
  unsigned long serial=0;long epoch=0;unsigned used=0;
  if(!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)||serial!=done->serial||epoch!=done->epoch||gStackForecastDepth!=1||
   revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch||scene!=CvStackingStrengthCache::SceneEpoch()||
   !danger->AppendStackDangerProbeSources(*plot,done->source,PACKET_PROBE_WORDS,used)||used!=done->sourceCount||
   std::memcmp(done->source,done->key+done->sourceStart,used*sizeof(int))){++done->invalidated;return;}
  const unsigned long attempts=gStackOutcomeBuilds-beforeBuilds;
  done->rawCalls+=raw?1:0;done->outcomeBuildAttempts+=attempts;
  const bool fresh=raw||attempts!=0;
  if(fresh)++done->freshQueries;else ++done->batchReuseQueries;
  const unsigned long hash=PacketProbeHash(done->key,done->count,0);
  unsigned selected=PACKET_PROBE_SLOTS;
  for(unsigned i=0;i<PACKET_PROBE_SLOTS;++i)if(done->slots[i].used&&done->slots[i].hash==hash&&done->slots[i].count==done->count&&
   !std::memcmp(done->slots[i].words,done->key,done->count*sizeof(int))){selected=i;break;}
  bool repeat=selected!=PACKET_PROBE_SLOTS;
  if(!repeat)
  {
   selected=done->next;done->next=(done->next+1)%PACKET_PROBE_SLOTS;PacketProbeSlot& s=done->slots[selected];
   if(s.used){done->keyBytes-=s.count*sizeof(int);done->outputUpperBytes-=s.outputUpper;++done->evictions;}
   s.used=true;s.city=city;s.count=done->count;s.hash=hash;s.seen=s.fresh=0;s.outputUpper=outputUpper;std::memcpy(s.words,done->key,done->count*sizeof(int));
   done->keyBytes+=s.count*sizeof(int);done->peakKeyBytes=std::max(done->peakKeyBytes,done->keyBytes);++done->groups;if(city)++done->cityGroups;else ++done->fieldGroups;
   done->outputUpperBytes+=outputUpper;done->peakOutputUpperBytes=std::max(done->peakOutputUpperBytes,done->outputUpperBytes);
  }
  PacketProbeSlot& s=done->slots[selected];const unsigned long bit=1UL<<member;
  if(repeat){++done->repeats;if(s.seen&bit)++done->sameMember;else ++done->crossMember;}
  if(fresh&&s.fresh){++done->freshRepeatQueries;if(!(s.fresh&bit))++done->freshCrossMemberQueries;}
  s.seen|=bit;if(fresh)s.fresh|=bit;
 }
private:PacketProbeCall(const PacketProbeCall&);PacketProbeCall&operator=(const PacketProbeCall&);
};
// END PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
