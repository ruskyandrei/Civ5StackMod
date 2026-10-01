// Admission/control-flow mirrors the actual DLL86 storage helpers. Only the
// representation, owned-copy construction and key/queue lookup are replaced.
static bool EvictOldestStackForecast()
{
 if(!gUseIndexed)return LegacyEvictOldestStackForecast();
 if(gIndexed.FIFOCount(IndexedStore::DANGER)&&gIndexed.FIFOCount(IndexedStore::DANGER)>=gIndexed.FIFOCount(IndexedStore::DEFENDER))
 {
  int victim=gIndexed.Head(IndexedStore::DANGER);const size_t payload=gIndexed.At(victim).PayloadBytes();
  if(payload>gStackKeyPayloadBytes)return false;
  gIndexed.QueuePop(IndexedStore::DANGER);gStackKeyPayloadBytes-=payload;gIndexed.Erase(victim);++gStackDangerEvictions;return true;
 }
 if(gIndexed.FIFOCount(IndexedStore::DEFENDER))
 {
  int victim=gIndexed.Head(IndexedStore::DEFENDER);const size_t payload=gIndexed.At(victim).PayloadBytes();
  if(payload>gStackKeyPayloadBytes)return false;
  gIndexed.QueuePop(IndexedStore::DEFENDER);gStackKeyPayloadBytes-=payload;gIndexed.Erase(victim);++gStackDefenderEvictions;return true;
 }
 return false;
}
static bool CanStoreStackForecast(const StackForecastKey& key)
{
 if(!gUseIndexed)return LegacyCanStoreStackForecast(key);
 if(!StackForecastContext())return false;
 const size_t payload=key.state.capacity()*sizeof(int);
 if(gStackEntryLimit==0||payload>gStackKeyPayloadLimit){++gStackInsertBypasses;return false;}
 while(gIndexed.Total()>=gStackEntryLimit||payload>gStackKeyPayloadLimit-gStackKeyPayloadBytes)
  if(!EvictOldestStackForecast()){++gStackInsertBypasses;return false;}
 return true;
}
static size_t EstimatedStackForecastBytes()
{
 if(!gUseIndexed)return LegacyEstimatedStackForecastBytes();
 // The original empty fallback containers remain available throughout search.
 // This is requested-payload/container estimation, excluding heap bookkeeping.
 return gIndexed.ReservedBytes()+sizeof(gIndexed)+sizeof(gStackDangerForecasts)+sizeof(gStackDefenderForecasts)
  +(gStackDangerForecasts.bucket_count()+gStackDefenderForecasts.bucket_count()+2)*sizeof(void*)
  +sizeof(StackDangerForecasts::value_type)+sizeof(StackDefenderForecasts::value_type)+4*sizeof(void*)
  +sizeof(gStackDangerOrder)+sizeof(gStackDefenderOrder)+sizeof(gStackThreatFlags)
  +gStackThreatFlags.size()*(sizeof(StackThreatFlags::value_type)+4*sizeof(void*));
}
static void UpdateStackForecastPeaks()
{
 if(!gUseIndexed){LegacyUpdateStackForecastPeaks();return;}
 gStackPeakEntries=max(gStackPeakEntries,gIndexed.Total());
 gStackPeakKeyBytes=max(gStackPeakKeyBytes,gStackKeyPayloadBytes);
 gStackPeakEstimatedBytes=max(gStackPeakEstimatedBytes,EstimatedStackForecastBytes());
}
static void StoreStackDangerForecast(const StackForecastKey& key,int result)
{
 if(!gUseIndexed){LegacyStoreStackDangerForecast(key,result);return;}
 if(!CanStoreStackForecast(key))return;
 IndexedStore::Pending pending;StackDangerForecastValue value(result);pending.Assign(key,&value,NULL);
 bool inserted=false;int handle=gIndexed.Insert(key,pending,IndexedStore::DANGER,inserted);
 if(inserted)
 {
  const size_t payload=gIndexed.At(handle).PayloadBytes();
  if(payload<=gStackKeyPayloadLimit-gStackKeyPayloadBytes)
  {gStackKeyPayloadBytes+=payload;BeforeQueuePush();gIndexed.QueuePush(handle);UpdateStackForecastPeaks();}
  else{gIndexed.Erase(handle);++gStackInsertBypasses;}
 }
}
static void StoreStackDangerPacketForecast(const StackForecastKey& key,const StackDangerForecastValue& value)
{
 if(!gUseIndexed){LegacyStoreStackDangerPacketForecast(key,value);return;}
 if(!StackForecastContext())return;
 if(key.state.size()%2==0||value.memberScores.size()<2||gStackEntryLimit==0){++gStackInsertBypasses;return;}
 if(gIndexed.Find(key,IndexedStore::DANGER)!=-1)return;
 const unsigned long revision=gStackForecastRevision;const long scene=gStackForecastSceneEpoch;
 IndexedStore::Pending pending;pending.Assign(key,&value,NULL);
 if(pending.keyWords>gStackKeyPayloadLimit/sizeof(int)){++gStackInsertBypasses;return;}
 const size_t copiedKeyBytes=pending.keyWords*sizeof(int);
 if(pending.members>(gStackKeyPayloadLimit-copiedKeyBytes)/sizeof(pair<int,int>)){++gStackInsertBypasses;return;}
 if(!StackForecastContext()||revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch){++gStackInsertBypasses;return;}
 bool inserted=false;int handle=gIndexed.Insert(key,pending,IndexedStore::DANGER,inserted);
 if(!inserted)return;
 if(!gStackForecastsActive||gStackForecastDepth!=1||revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch||scene!=CvStackingStrengthCache::SceneEpoch())
 {gIndexed.Erase(handle);++gStackInsertBypasses;return;}
 const IndexedStore::Slot& stored=gIndexed.At(handle);
 if(stored.keyWords>gStackKeyPayloadLimit/sizeof(int)){gIndexed.Erase(handle);++gStackInsertBypasses;return;}
 const size_t keyBytes=stored.keyWords*sizeof(int);
 if(stored.members>(gStackKeyPayloadLimit-keyBytes)/sizeof(pair<int,int>)){gIndexed.Erase(handle);++gStackInsertBypasses;return;}
 const size_t payload=stored.PayloadBytes();
 while(gIndexed.Total()>gStackEntryLimit||payload>gStackKeyPayloadLimit-gStackKeyPayloadBytes)
  if(!EvictOldestStackForecast()){gIndexed.Erase(handle);++gStackInsertBypasses;return;}
 try{BeforeQueuePush();gIndexed.QueuePush(handle);}
 catch(...){gIndexed.Erase(handle);throw;}
 gStackKeyPayloadBytes+=payload;UpdateStackForecastPeaks();
}
static void StoreStackDefenderForecast(const StackForecastKey& key,const CvUnit* result)
{
 if(!gUseIndexed){LegacyStoreStackDefenderForecast(key,result);return;}
 if(!CanStoreStackForecast(key))return;
 IndexedStore::Pending pending;pending.Assign(key,NULL,result);
 bool inserted=false;int handle=gIndexed.Insert(key,pending,IndexedStore::DEFENDER,inserted);
 if(inserted)
 {
  const size_t payload=gIndexed.At(handle).PayloadBytes();
  if(payload<=gStackKeyPayloadLimit-gStackKeyPayloadBytes)
  {gStackKeyPayloadBytes+=payload;BeforeQueuePush();gIndexed.QueuePush(handle);UpdateStackForecastPeaks();}
  else{gIndexed.Erase(handle);++gStackInsertBypasses;}
 }
}
