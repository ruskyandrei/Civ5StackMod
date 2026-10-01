// WORK-ONLY native staging fragment; inserted after StackDangerOutcomeBatch.
static bool AppendUniquePacketDamage(StackForecastKey* key,const SUnitIDValueContainer& damage)
{
 StackForecastPairQuery query;vector<pair<int,int> >& entries=query.entries;
 for(SUnitIDValueContainer::const_iterator i=damage.begin();i!=damage.end();++i)entries.push_back(*i);
 std::sort(entries.begin(),entries.end());
 int nonzero=0;
 for(size_t i=0;i<entries.size();++i)
 {
  if(i&&entries[i-1].first==entries[i].first)return false;
  if(entries[i].second)++nonzero;
 }
 if(key){key->state.push_back(nonzero);for(size_t i=0;i<entries.size();++i)if(entries[i].second){key->state.push_back(entries[i].first);key->state.push_back(entries[i].second);}}
 return true;
}
static bool StackPacketSourcesHaveNoLoadingCallback(const vector<int>& source)
{
 // Custom air melee can enter canEnterTerrain -> canLoad -> CanLoadAt, whose
 // fallback Lua hook is independent of CAN_MOVE_INTO/CITY_BOMBARD flags.
 // Standard ranged aircraft do not use that ground-attack legality route.
 if(source.size()<6||source[0]!=1||source[4]<0||(size_t)source[4]>(source.size()-6)/2)return false;
 for(int i=0;i<source[4];++i)
 {
  const CvUnit* threat=GET_PLAYER((PlayerTypes)source[5+2*i]).getUnit(source[6+2*i]);
  if(threat&&threat->getDomainType()==DOMAIN_AIR&&!threat->IsCanAttackRanged())return false;
 }
 return true;
}
static bool PrepareStackDangerPacket(StackDangerPacketQuery& query,const CvUnit* unit,const CvPlot* plot,
 const vector<const CvUnit*>& roster,const SUnitIDValueContainer& friendly,const SUnitIDValueContainer& enemy,const StackForecastKey& legacy)
{
 if(!query.borrowed||MOD_EVENTS_CAN_MOVE_INTO||MOD_EVENTS_CITY_BOMBARD||!unit||!plot||!unit->IsCombatUnit()||!unit->isNativeDomain(plot)||
  legacy.state.size()<6||legacy.state.size()%2)return false;
 StackDangerPacketBuffer& b=query.buffer;const bool city=plot->isFriendlyCity(*unit);bool found=false;
 for(size_t i=0;i<roster.size();++i)
 {
  const CvUnit* member=roster[i];
  if(!member||member->getOwner()!=unit->getOwner()||member->getTeam()!=unit->getTeam()||member->getDomainType()!=unit->getDomainType()||!member->IsCombatUnit()||!member->isNativeDomain(plot)||
   plot->isFriendlyCity(*member)!=city||GET_PLAYER(member->getOwner()).getUnit(member->GetID())!=member)return false;
  found|=member==unit;if(std::find(b.members.begin(),b.members.end(),member)==b.members.end())b.members.push_back(member);
 }
 if(!found||b.members.size()<2)return false;
 const int count=legacy.state[4];if(count<0||(size_t)count!=roster.size()||(size_t)count>(legacy.state.size()-5)/2)return false;
 const size_t suffix=5+2*(size_t)count;
 if(suffix>=legacy.state.size()||legacy.state[suffix]<0||legacy.state.size()-suffix!=1+2*(size_t)legacy.state[suffix])return false;
 // Scalars: 6+2*N (even). Complete packets: 15+2*N (odd), deliberately
 // disjoint without adding a kind/hash field to millions of scalar hits.
 b.key.state.push_back(unit->getOwner());b.key.state.push_back(unit->getTeam());b.key.state.push_back(plot->GetPlotIndex());
 b.key.state.push_back(city?1:0);b.key.state.push_back((int)roster.size());
 b.key.state.push_back(legacy.state[3]);b.key.state.push_back(plot->getPlotCity()?plot->getPlotCity()->getDamage():-1);
 for(size_t i=0;i<roster.size();++i){b.key.state.push_back(roster[i]->getOwner());b.key.state.push_back(roster[i]->GetID());}
 if(!AppendUniquePacketDamage(&b.key,friendly)||!AppendUniquePacketDamage(NULL,enemy))return false;
 const CvDangerPlots* map=GET_PLAYER(unit->getOwner()).GetDangerPlots();unsigned used=0;
 if(!map->AppendStackDangerCacheDescriptor(*plot,b.descriptor,sizeof(b.descriptor)/sizeof(b.descriptor[0]),used))return false;
 b.source.assign(b.descriptor,b.descriptor+used);b.key.state.insert(b.key.state.end(),b.source.begin(),b.source.end());
 if(!StackPacketSourcesHaveNoLoadingCallback(b.source))return false;
 b.key.state.insert(b.key.state.end(),legacy.state.begin()+suffix,legacy.state.end());
 return b.key.state.size()%2&&b.key.state.size()<=gStackKeyPayloadLimit/sizeof(int);
}
static bool ValidateStackDangerPacket(StackDangerPacketQuery& query,const CvUnit* unit,const CvPlot* plot,
 unsigned long revision,long scene)
{
 if(!StackForecastContext()||revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch||scene!=CvStackingStrengthCache::SceneEpoch()||
  MOD_EVENTS_CAN_MOVE_INTO||MOD_EVENTS_CITY_BOMBARD)return false;
 StackDangerPacketBuffer& b=query.buffer;const CvDangerPlots* map=GET_PLAYER(unit->getOwner()).GetDangerPlots();
 if(map->IsDirty()||b.key.state.size()<7||CvStacking::GetCityProtection(plot->getPlotCity())!=b.key.state[5]||
  (plot->getPlotCity()?plot->getPlotCity()->getDamage():-1)!=b.key.state[6])return false;
 unsigned used=0;if(!map->AppendStackDangerCacheDescriptor(*plot,b.descriptor,sizeof(b.descriptor)/sizeof(b.descriptor[0]),used)||used!=b.source.size())return false;
 if(!std::equal(b.source.begin(),b.source.end(),b.descriptor)||!StackPacketSourcesHaveNoLoadingCallback(b.source))return false;
 // Descriptor/source-unit getters are additional preparation work. Recheck
 // the owning scene after them, before using an iterator or admitting values.
 return StackForecastContext()&&revision==gStackForecastRevision&&scene==gStackForecastSceneEpoch&&scene==CvStackingStrengthCache::SceneEpoch();
}
static bool ResolveStackDangerPacket(StackDangerPacketQuery& query,const CvUnit* unit,const CvPlot* plot,
 const vector<const CvUnit*>& roster,const SUnitIDValueContainer& friendly,const SUnitIDValueContainer& enemy,
 const StackForecastKey& legacy,unsigned long revision,long scene,StackDangerOutcomeBatch* outcome,int& result)
{
 if(!PrepareStackDangerPacket(query,unit,plot,roster,friendly,enemy,legacy))return false;
 if(!ValidateStackDangerPacket(query,unit,plot,revision,scene))return false;
 StackDangerPacketBuffer& b=query.buffer;
 StackDangerForecasts::const_iterator hit=gStackDangerForecasts.find(b.key);
 if(hit!=gStackDangerForecasts.end())
  for(size_t i=0;i<hit->second.memberScores.size();++i)if(hit->second.memberScores[i].first==unit->GetID())
  {
   // Copy before a validating context call, which may clear the owning table.
   const int cachedResult=hit->second.memberScores[i].second;
   if(!ValidateStackDangerPacket(query,unit,plot,revision,scene))return false;
   result=cachedResult;query.scalarValid=true;++gStackPacketHits;return true;
  }
 CvDangerPlots* map=GET_PLAYER(unit->getOwner()).GetDangerPlots();
 SUnitIDValueContainer localFinal;const SUnitIDValueContainer* finalDamage=NULL;bool cityCanFall=false,computed=false;
 if(outcome)
 {
  computed=outcome->TryGet(unit,plot,roster,friendly,enemy,result);
  if(computed&&outcome->ready){finalDamage=&outcome->finalDamage;cityCanFall=outcome->cityCanFall;}
  else if(computed)
  {
   // A computed local ledger was released on invalidation/budget failure.
   // Retain this one query value; never replay the original callbacks/math.
   query.scalarValid=ValidateStackDangerPacket(query,unit,plot,revision,scene);++gStackPacketBypasses;return true;
  }
 }
 if(!computed)
 {
  ++gStackPacketBuilds;++gStackOutcomeBuilds;
  computed=map->GetStackDangerOutcome(*plot,unit,roster,friendly,enemy,localFinal,cityCanFall,result);finalDamage=&localFinal;
 }
 if(!computed)return false; // The native false-return contract computes no leaf.
 if(!ValidateStackDangerPacket(query,unit,plot,revision,scene)){++gStackPacketBypasses;return true;}
 b.value.scalar=result;
 for(size_t i=0;i<b.members.size();++i)
 {
  int memberResult=result;
  if(b.members[i]!=unit&&!map->TryGetStackDangerFromOutcome(*plot,b.members[i],friendly,*finalDamage,cityCanFall,memberResult))
  {++gStackPacketBypasses;return true;}
  b.value.memberScores.push_back(make_pair(b.members[i]->GetID(),memberResult));
 }
 if(ValidateStackDangerPacket(query,unit,plot,revision,scene)){query.storePacket=true;query.scalarValid=true;}
 else ++gStackPacketBypasses;
 return true;
}
