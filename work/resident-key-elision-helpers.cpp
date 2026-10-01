static ParentStackPreparationCell* ResidentArrivalCell(const CvUnit* unit,const CvPlot* plot,
 const vector<const CvUnit*>& candidates,const SUnitIDValueContainer& damage,bool ownedLoan)
{
 ResidentArrivalRequest* request=gResidentArrivalRequest;
 if(!ownedLoan||!gUseIndexed||!request||request->unit!=unit||request->plot!=plot||
  &request->candidates!=&candidates||&request->damage!=&damage)return NULL;
 ParentStackPreparationView* view=gParentStackPreparationView;
 if(!view||!view->borrowed||!view->CanPrepare(request->position,true))return NULL;
 unsigned long serial=0;long epoch=0;
 if(CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch))return NULL;
 ParentStackPreparationStorage& storage=gParentStackPreparationStorage;
 const int index=plot->GetPlotIndex();size_t lo=0,hi=storage.count;
 while(lo<hi){const size_t middle=lo+(hi-lo)/2;if(storage.lookup[middle].first<index)lo=middle+1;else hi=middle;}
 if(lo==storage.count||storage.lookup[lo].first!=index)return NULL;
 return &storage.cells[storage.lookup[lo].second];
}
static bool HasResidentScalarCaptureContext(const CvUnit* unit,const CvPlot* plot,
 const vector<const CvUnit*>& candidates,const SUnitIDValueContainer& damage,bool ownedLoan)
{return ResidentArrivalCell(unit,plot,candidates,damage,ownedLoan)!=NULL;}
static bool PrepareResidentScalarKey(const CvUnit* unit,const CvPlot* plot,const vector<const CvUnit*>& candidates,
 const SUnitIDValueContainer& damage,const SUnitIDValueContainer& enemy,const int* fixed,bool canonical,bool ownedLoan,StackForecastKey& key)
{
 ParentStackPreparationCell* cell=ResidentArrivalCell(unit,plot,candidates,damage,ownedLoan);
 if(!cell)return false;
 ResidentScalarCertificate& certificate=cell->resident;int ignored=0;
 if(!certificate.valid||certificate.unit!=unit||certificate.extra!=gResidentArrivalRequest->extra||certificate.canonical!=canonical||
  certificate.key.size()<6||!std::equal(fixed,fixed+4,certificate.key.begin())||
  !gIndexed.TryReadScalarHandle(certificate.handle,ignored)) {++gResidentRejects;return false;}
 const int members=certificate.key[4];
 if(members<0||static_cast<size_t>(members)>(certificate.key.size()-6)/2) {++gResidentRejects;return false;}
 const size_t prefix=5+2*static_cast<size_t>(members);
 if(prefix>ResidentScalarKeyWork::MAX_PREFIX_WORDS||key.state.capacity()<certificate.key.size()) {++gResidentRejects;return false;}
 ResidentScalarKeyWork& work=gResidentScalarKeyWork;
 work.count=prefix;std::copy(certificate.key.begin(),certificate.key.begin()+prefix,work.prefix);
 work.certificate=&certificate;work.handle=certificate.handle;work.view=gParentStackPreparationView;work.request=gResidentArrivalRequest;
 // Exactly the original source reader/refresh/NULL fallback, once. Captured
 // prefix is copied before it can invalidate/release optional parent metadata.
 AppendStackDamageProjected(key,enemy,unit,plot);
 return true;
}
static bool ReadPreparedResidentScalar(int& result)
{
 ResidentScalarKeyWork& work=gResidentScalarKeyWork;
 if(gResidentArrivalRequest!=work.request||gParentStackPreparationView!=work.view||!work.view||work.view->disabled||
  !work.certificate||!work.certificate->valid)return false;
 const vector<int>& saved=work.certificate->key;
 if(saved.size()<work.count||saved.size()-work.count!=gStackDangerScratch.state.size()||
  !std::equal(saved.begin()+work.count,saved.end(),gStackDangerScratch.state.begin()))return false;
 if(!gIndexed.TryReadScalarHandle(work.handle,result))return false;
 ++gResidentHits;return true;
}
static void CompletePreparedResidentScalarKey(StackForecastKey& key)
{
 const size_t suffix=key.state.size();ResidentScalarKeyWork& work=gResidentScalarKeyWork;
 // Individual push_back preserves VC9 growth/admission capacity. Bulk front
 // insertion would choose a different capacity on some suffix mismatches.
 for(size_t i=0;i<work.count;++i)key.state.push_back(work.prefix[i]);
 std::rotate(key.state.begin(),key.state.begin()+suffix,key.state.end());
 ++gResidentRejects;
}
static void CaptureResidentScalarKey(const CvUnit* unit,const CvPlot* plot,const vector<const CvUnit*>& candidates,
 const SUnitIDValueContainer& damage,const int* fixed,bool canonical,bool ownedLoan,const StackForecastKey& key,
 const IndexedStore::ScalarHandle& handle)
{
 ParentStackPreparationCell* cell=ResidentArrivalCell(unit,plot,candidates,damage,ownedLoan);int ignored=0;
 if(!cell||!gIndexed.TryReadScalarHandle(handle,ignored)||key.state.size()<6)return;
 const int members=key.state[4];
 if(members<0||static_cast<size_t>(members)>(key.state.size()-6)/2||5+2*static_cast<size_t>(members)>ResidentScalarKeyWork::MAX_PREFIX_WORDS)return;
 ParentStackPreparationStorage& storage=gParentStackPreparationStorage;
 ParentStackPreparationView* const view=gParentStackPreparationView;
 ResidentArrivalRequest* const request=gResidentArrivalRequest;
 const unsigned long revision=gStackForecastRevision;const long scene=gStackForecastSceneEpoch;
 ResidentScalarCertificate& certificate=cell->resident;const size_t before=certificate.Bytes();certificate.valid=false;
 bool copied=false;
 try {certificate.key=key.state;copied=true;}
 catch(const std::bad_alloc&) {}
 // Optional allocation failures/invalidation never recompute the scalar hit.
 // Context was already validated at the original post-key seam. Check only
 // its captured ownership/lifetime fields before publishing this certificate.
 if(!copied||gParentStackPreparationView!=view||gResidentArrivalRequest!=request||!view||view->disabled||
  !storage.busy||revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch||
  scene!=CvStackingStrengthCache::SceneEpoch()||!gIndexed.TryReadScalarHandle(handle,ignored))
 {
  certificate.Release();storage.retainedBytes=0;
  for(size_t i=0;i<ParentStackPreparationStorage::MAX_CELLS;++i)storage.retainedBytes+=storage.CellBytes(i);
  return;
 }
 storage.retainedBytes=storage.retainedBytes-before+certificate.Bytes();
 if(storage.RetainedBytes()>gStackKeyPayloadLimit)
 {storage.retainedBytes-=certificate.Bytes();certificate.Release();return;}
 certificate.unit=unit;certificate.extra=request->extra;certificate.canonical=canonical;certificate.handle=handle;
 certificate.valid=true;++gResidentCaptures;
}
