// Work-only algorithm scaffold, not a production patch or native ROI claim.
// The surrounding fixture supplies the ACTUAL StackForecastKey/hash, original
// builders, native context and original danger/outcome/extraction bodies.
#include <unordered_map>
#include <deque>

static StackForecastKey WorkLegacyDangerKey(const CvUnit*,const CvPlot*,const vector<const CvUnit*>&,
 const SUnitIDValueContainer&,const SUnitIDValueContainer&);
// Const fixture boundary. A production integration needs a bounded const
// descriptor reader; it must never bypass the ORIGINAL preceding dirty refresh.
static const CvDangerPlotContents* WorkPacketContents(const CvDangerPlots&,const CvPlot&);

struct SharedDangerPacketValue
{
 int scalar; // Legacy even-key hits read only this first integer.
 vector<pair<int,int> > memberScores;
 SharedDangerPacketValue(int value=0):scalar(value){}
};
struct SharedDangerPacketTrial
{
 typedef std::tr1::unordered_map<StackForecastKey,SharedDangerPacketValue,StackForecastKeyHash> Table;
 typedef std::tr1::unordered_map<StackForecastKey,const CvUnit*,StackForecastKeyHash> DefenderTable;
 Table danger;DefenderTable defender;
 deque<const StackForecastKey*> dangerFIFO,defenderFIFO;
 size_t entryLimit,payloadLimit,payloadBytes,peakBytes;
 unsigned long revision;long scene;
 bool building;
 unsigned long scalarHits,scalarBuilds,packetHits,packetBuilds,packetBypasses,evictions,clears,precomputations;
 SharedDangerPacketTrial(size_t entries,size_t bytes):entryLimit(entries),payloadLimit(bytes),payloadBytes(0),peakBytes(0),
  revision(gStackForecastRevision),scene(gStackForecastSceneEpoch),building(false),
  scalarHits(0),scalarBuilds(0),packetHits(0),packetBuilds(0),packetBypasses(0),evictions(0),clears(0),precomputations(0){}
 ~SharedDangerPacketTrial(){Clear();}
 struct BuildScope{bool&busy;BuildScope(bool&v):busy(v){busy=true;}~BuildScope(){busy=false;}};
 void Clear(){dangerFIFO.clear();defenderFIFO.clear();danger.clear();defender.clear();payloadBytes=0;++clears;}
 void Sync(){if(revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch){Clear();revision=gStackForecastRevision;scene=gStackForecastSceneEpoch;}}
 static size_t Bytes(const Table::value_type&e){return e.first.state.capacity()*sizeof(int)+e.second.memberScores.capacity()*sizeof(pair<int,int>);}
 bool Evict()
 {
  // Same larger-pool-first FIFO rule as the existing shared forecast pools.
  if(!dangerFIFO.empty()&&dangerFIFO.size()>=defenderFIFO.size())
  {Table::iterator i=danger.find(*dangerFIFO.front());if(i==danger.end()||Bytes(*i)>payloadBytes)return false;
   payloadBytes-=Bytes(*i);dangerFIFO.pop_front();danger.erase(i);++evictions;return true;}
  if(!defenderFIFO.empty())
  {DefenderTable::iterator i=defender.find(*defenderFIFO.front());if(i==defender.end())return false;
   const size_t bytes=i->first.state.capacity()*sizeof(int);if(bytes>payloadBytes)return false;
   payloadBytes-=bytes;defenderFIFO.pop_front();defender.erase(i);++evictions;return true;}
  return false;
 }
 bool Fit(size_t bytes)
 {
  if(!entryLimit||bytes>payloadLimit)return false; // Reject before useful eviction.
  while(danger.size()+defender.size()>=entryLimit||bytes>payloadLimit-payloadBytes)if(!Evict())return false;
  return true;
 }
 void StoreScalar(const StackForecastKey&key,int result)
 {
  // Matches old scalar preflight/copy accounting; empty value vectors add no
  // retained payload. Packet keys are never legal for this legacy API.
  if(key.state.size()%2||!Fit(key.state.capacity()*sizeof(int)))return;
  pair<Table::iterator,bool> added=danger.insert(make_pair(key,SharedDangerPacketValue(result)));
  if(!added.second)return;
  const size_t bytes=Bytes(*added.first);
  if(bytes>payloadLimit-payloadBytes){danger.erase(added.first);return;}
  payloadBytes+=bytes;dangerFIFO.push_back(&added.first->first);peakBytes=max(peakBytes,payloadBytes);
 }
 bool StorePacket(const StackForecastKey&key,const SharedDangerPacketValue&value)
 {
  if(!(key.state.size()%2)||value.memberScores.size()<2||danger.find(key)!=danger.end())return false;
  // These temporary copies are NOT part of a claimed peak-RSS bound. Reject
  // their measured copied capacities before evicting useful retained entries.
  StackForecastKey copiedKey=key;SharedDangerPacketValue copiedValue=value;
  const size_t copiedBytes=copiedKey.state.capacity()*sizeof(int)+copiedValue.memberScores.capacity()*sizeof(pair<int,int>);
  if(!Fit(copiedBytes))return false;
  pair<Table::iterator,bool> added=danger.insert(make_pair(copiedKey,copiedValue));if(!added.second)return false;
  const size_t bytes=Bytes(*added.first); // Charge ACTUAL retained capacities.
  if(bytes>payloadLimit-payloadBytes){danger.erase(added.first);return false;}
  try{dangerFIFO.push_back(&added.first->first);}catch(...){danger.erase(added.first);throw;}
  payloadBytes+=bytes;peakBytes=max(peakBytes,payloadBytes);return true;
 }
 void StoreDefender(const StackForecastKey&key,const CvUnit*unit)
 {
  if(!Fit(key.state.capacity()*sizeof(int)))return;
  pair<DefenderTable::iterator,bool> added=defender.insert(make_pair(key,unit));if(!added.second)return;
  size_t bytes=added.first->first.state.capacity()*sizeof(int);
  if(bytes>payloadLimit-payloadBytes){defender.erase(added.first);return;}
  payloadBytes+=bytes;defenderFIFO.push_back(&added.first->first);peakBytes=max(peakBytes,payloadBytes);
 }
 size_t FixedNodeEstimate()const
 {
  // Same original node estimate, plus the NEW fixed vector object for danger
  // values. This is not measured allocator memory or process RSS.
  const size_t oldPerEntry=sizeof(StackForecastKey)+sizeof(const CvUnit*)+9*sizeof(void*);
  return (danger.size()+defender.size())*oldPerEntry+danger.size()*(sizeof(SharedDangerPacketValue)-sizeof(int));
 }
 static bool UniqueDamage(const SUnitIDValueContainer&damage)
 {
  vector<int>ids;for(SUnitIDValueContainer::const_iterator i=damage.begin();i!=damage.end();++i)ids.push_back((*i).first);
  sort(ids.begin(),ids.end());return adjacent_find(ids.begin(),ids.end())==ids.end();
 }
 static void DamageWords(StackForecastKey&key,const SUnitIDValueContainer&damage)
 {
  vector<pair<int,int> >values;for(SUnitIDValueContainer::const_iterator i=damage.begin();i!=damage.end();++i)if((*i).second)values.push_back(*i);
  sort(values.begin(),values.end());key.state.push_back((int)values.size());
  for(size_t i=0;i<values.size();++i){key.state.push_back(values[i].first);key.state.push_back(values[i].second);}
 }
 static void SourceWords(StackForecastKey&key,const CvDangerPlotContents&c)
 {
  // Four versioned hazard words preserve odd namespace and precomputed ints.
  key.state.push_back(1);key.state.push_back(c.m_iImprovementDamage);key.state.push_back(c.m_iFogCount);key.state.push_back(c.m_bFlatPlotDamage?1:0);
  key.state.push_back((int)c.m_apUnits.size());for(size_t i=0;i<c.m_apUnits.size();++i){key.state.push_back(c.m_apUnits[i].first);key.state.push_back(c.m_apUnits[i].second);}
  key.state.push_back((int)c.m_apCities.size());for(size_t i=0;i<c.m_apCities.size();++i){key.state.push_back(c.m_apCities[i].first);key.state.push_back(c.m_apCities[i].second);}
 }
 bool PacketKey(CvDangerPlots&map,const CvUnit*unit,const CvPlot*plot,const vector<const CvUnit*>&roster,
  const SUnitIDValueContainer&friendly,const SUnitIDValueContainer&enemy,const StackForecastKey&legacy,
  StackForecastKey&key,StackForecastKey&sources,vector<const CvUnit*>&unique)
 {
  if(MOD_EVENTS_CAN_MOVE_INTO||MOD_EVENTS_CITY_BOMBARD||building||!unit||!plot||!unit->IsCombatUnit()||!unit->isNativeDomain(plot)||
   legacy.state.size()<6||legacy.state.size()%2||!UniqueDamage(friendly)||!UniqueDamage(enemy))return false;
  const CvDangerPlotContents*c=WorkPacketContents(map,*plot);if(!c)return false;
  bool present=false;const bool city=plot->isFriendlyCity(*unit);
  for(size_t i=0;i<roster.size();++i)
  {
   const CvUnit*u=roster[i];if(!u||u->getOwner()!=unit->getOwner()||u->getTeam()!=unit->getTeam()||
    !u->IsCombatUnit()||!u->isNativeDomain(plot)||plot->isFriendlyCity(*u)!=city||GET_PLAYER(u->getOwner()).getUnit(u->GetID())!=u)return false;
   present|=u==unit;if(find(unique.begin(),unique.end(),u)==unique.end())unique.push_back(u);
  }
  if(!present||unique.size()<2)return false;
  const int count=legacy.state[4];if(count<0||(size_t)count!=roster.size()||(size_t)count>(legacy.state.size()-5)/2)return false;
  const size_t suffix=5+2*(size_t)count;
  if(suffix>=legacy.state.size()||legacy.state[suffix]<0||legacy.state.size()-suffix!=1+2*(size_t)legacy.state[suffix])return false;
  key.state.push_back(unit->getOwner());key.state.push_back(unit->getTeam());key.state.push_back(plot->GetPlotIndex());key.state.push_back(city?1:0);key.state.push_back((int)roster.size());
  // Preserve the ORIGINAL live scalar protection field. Its city-health
  // dependency does not always advance SceneEpoch. The second explicit field
  // records any present city's HP state and keeps the odd word namespace.
  key.state.push_back(legacy.state[3]);key.state.push_back(plot->getPlotCity()?plot->getPlotCity()->getDamage():-1);
  for(size_t i=0;i<roster.size();++i){key.state.push_back(roster[i]->getOwner());key.state.push_back(roster[i]->GetID());}
  DamageWords(key,friendly);SourceWords(sources,*c);key.state.insert(key.state.end(),sources.state.begin(),sources.state.end());
  // Original helper already performed its dirty refresh and projection. Never
  // call a second refresh/foreign callback to build a packet's enemy suffix.
  key.state.insert(key.state.end(),legacy.state.begin()+suffix,legacy.state.end());
  return key.state.size()%2&&key.state.size()<=payloadLimit/sizeof(int);
 }
 bool Stable(CvDangerPlots&map,const CvPlot&plot,const StackForecastKey&sources,const StackForecastKey&packet,unsigned long beforeRevision,long beforeScene)
 {
  if(!StackForecastContext()||beforeRevision!=gStackForecastRevision||beforeScene!=gStackForecastSceneEpoch||
   beforeScene!=CvStackingStrengthCache::SceneEpoch()||MOD_EVENTS_CAN_MOVE_INTO||MOD_EVENTS_CITY_BOMBARD||map.IsDirty())return false;
  if(packet.state.size()<7||CvStacking::GetCityProtection(plot.getPlotCity())!=packet.state[5]||
   (plot.getPlotCity()?plot.getPlotCity()->getDamage():-1)!=packet.state[6])return false;
  const CvDangerPlotContents*c=WorkPacketContents(map,plot);if(!c)return false;StackForecastKey now;SourceWords(now,*c);return now==sources;
 }
 int Get(CvDangerPlots&map,const CvUnit*unit,const CvPlot*plot,const vector<const CvUnit*>&roster,
  const SUnitIDValueContainer&friendly,const SUnitIDValueContainer&enemy,StackDangerOutcomeBatch*outcome=NULL,bool packets=true)
 {
  int fixed=0;if(CvStacking::IsEnabled()&&map.TryGetFixedStackDanger(*plot,unit,fixed))return fixed;
  StackForecastKey legacy;bool cacheable=StackForecastContext();const unsigned long beforeRevision=cacheable?gStackForecastRevision:0;const long beforeScene=cacheable?gStackForecastSceneEpoch:0;
  if(cacheable)
  {
   legacy=WorkLegacyDangerKey(unit,plot,roster,friendly,enemy);
   cacheable=StackForecastContext()&&beforeRevision==gStackForecastRevision&&beforeScene==gStackForecastSceneEpoch;
   if(cacheable){Sync();Table::const_iterator hit=danger.find(legacy);if(hit!=danger.end()){++scalarHits;return hit->second.scalar;}}
  }
  StackForecastKey packet,sources;vector<const CvUnit*>members;
  bool eligible=packets&&cacheable&&PacketKey(map,unit,plot,roster,friendly,enemy,legacy,packet,sources,members);
  // Packet preparation is additional work after the original key guard. A
  // foreign invalidation during it must be observed BEFORE any packet hit.
  if(eligible)eligible=Stable(map,*plot,sources,packet,beforeRevision,beforeScene);
  if(eligible)
  {
   Table::const_iterator hit=danger.find(packet);
   if(hit!=danger.end())for(size_t i=0;i<hit->second.memberScores.size();++i)if(hit->second.memberScores[i].first==unit->GetID())
   {
    const int value=hit->second.memberScores[i].second;++packetHits;
    // Admit ONLY this actually queried legacy key, after exact packet checks.
    // Never preseed unqueried even keys whose old shape omits off-roster FD.
    StoreScalar(legacy,value);return value;
   }
  }
  int result=0;
  if(!eligible)
  {
   if(cacheable)++packetBypasses;
   if(!outcome||!outcome->TryGet(unit,plot,roster,friendly,enemy,result))result=map.GetStackDanger(*plot,unit,roster,friendly,enemy);
   if(cacheable&&StackForecastContext()&&beforeRevision==gStackForecastRevision&&beforeScene==gStackForecastSceneEpoch){++scalarBuilds;StoreScalar(legacy,result);}return result;
  }
  SUnitIDValueContainer localFinal;const SUnitIDValueContainer*final=NULL;bool fall=false,computed=false;
  {
   BuildScope inFlight(building);
   if(outcome)
   {
    computed=outcome->TryGet(unit,plot,roster,friendly,enemy,result);
    if(computed&&outcome->ready){final=&outcome->finalDamage;fall=outcome->cityCanFall;}
    else if(computed){++packetBypasses;return result;} // Released result: NEVER rebuild.
   }
   if(!computed){++packetBuilds;computed=map.GetStackDangerOutcome(*plot,unit,roster,friendly,enemy,localFinal,fall,result);final=&localFinal;}
   if(!computed){result=map.GetStackDanger(*plot,unit,roster,friendly,enemy);++packetBypasses;return result;}
   if(!Stable(map,*plot,sources,packet,beforeRevision,beforeScene)){++packetBypasses;return result;}
   SharedDangerPacketValue values(result);
   for(size_t i=0;i<members.size();++i)
   {
    int value=result;
    if(members[i]!=unit){++precomputations;if(!map.TryGetStackDangerFromOutcome(*plot,members[i],friendly,*final,fall,value)){++packetBypasses;return result;}}
    values.memberScores.push_back(make_pair(members[i]->GetID(),value));
   }
   if(Stable(map,*plot,sources,packet,beforeRevision,beforeScene))
   {
    // Odd packet first; the queried even scalar last keeps its cheap hit under
    // tiny budgets. Both compete in the SAME pool and capacity accounting.
    StorePacket(packet,values);StoreScalar(legacy,result);
   }
   else ++packetBypasses;
  }
  return result;
 }
};
