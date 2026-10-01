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
static bool ResidentScalarLexicalProof()
{
 const ResidentScalarKeyWork& work=gResidentScalarKeyWork;
 return work.certificate&&work.request&&gResidentArrivalRequest==work.request&&gParentStackPreparationView==work.view&&
  work.view&&work.view->borrowed&&!work.view->disabled&&gParentStackPreparationStorage.busy&&
  work.revision==gStackForecastRevision&&work.scene==gStackForecastSceneEpoch;
}
static bool HasResidentScalarCaptureContext(const CvUnit* unit,const CvPlot* plot,
 const vector<const CvUnit*>& candidates,const SUnitIDValueContainer& damage,bool ownedLoan)
{
 if(!ownedLoan||!ResidentScalarLexicalProof())return false;
 const ResidentArrivalRequest& request=*gResidentScalarKeyWork.request;
 return request.unit==unit&&request.plot==plot&&&request.candidates==&candidates&&&request.damage==&damage;
}
static bool PrepareResidentScalarKey(const CvUnit* unit,const CvPlot* plot,const vector<const CvUnit*>& candidates,
 const SUnitIDValueContainer& damage,const SUnitIDValueContainer& enemy,const int* fixed,bool canonical,bool ownedLoan,StackForecastKey& key)
{
 if(!ownedLoan)return false; // Private/foreign calls cannot disturb the owner's scratch.
 ResidentScalarKeyWork& work=gResidentScalarKeyWork;
 work.certificate=NULL;work.view=NULL;work.request=NULL;
 ParentStackPreparationCell* cell=ResidentArrivalCell(unit,plot,candidates,damage,true);
 if(!cell)return false;
 work.certificate=&cell->resident;work.view=gParentStackPreparationView;work.request=gResidentArrivalRequest;
 work.revision=gStackForecastRevision;work.scene=gStackForecastSceneEpoch;
 ResidentScalarCertificate& certificate=cell->resident;
 if(!certificate.valid||certificate.unit!=unit||certificate.extra!=work.request->extra||certificate.canonical!=canonical||
  !gIndexed.TryCopyScalarPrefix(certificate.handle,fixed,work.prefix,ResidentScalarKeyWork::MAX_PREFIX_WORDS,key.state.capacity(),work.count))
 {++gResidentRejects;return false;}
 work.handle=certificate.handle;
 // No retained slot/key pointer spans this original refreshing/callback seam.
 AppendStackDamageProjected(key,enemy,unit,plot);
 return true;
}
static bool ReadPreparedResidentScalar(int& result)
{
 ResidentScalarKeyWork& work=gResidentScalarKeyWork;
 if(!ResidentScalarLexicalProof()||!work.certificate->valid||gStackDangerScratch.state.empty())return false;
 if(!gIndexed.TryMatchScalarSuffix(work.handle,&gStackDangerScratch.state[0],gStackDangerScratch.state.size(),work.count,result))return false;
 ++gResidentHits;return true;
}
static void CompletePreparedResidentScalarKey(StackForecastKey& key)
{
 const size_t suffix=key.state.size();ResidentScalarKeyWork& work=gResidentScalarKeyWork;
 for(size_t i=0;i<work.count;++i)key.state.push_back(work.prefix[i]);
 std::rotate(key.state.begin(),key.state.begin()+suffix,key.state.end());
 ++gResidentRejects;
}
static void CaptureResidentScalarKey(const CvUnit* unit,const CvPlot* plot,const vector<const CvUnit*>& candidates,
 const SUnitIDValueContainer& damage,const int* fixed,bool canonical,bool ownedLoan,const StackForecastKey& key,
 const IndexedStore::ScalarHandle& handle)
{
 // The original post-key Context and existing full-key lookup precede this
 // allocation-free publication. No engine getters or callbacks intervene.
 if(!HasResidentScalarCaptureContext(unit,plot,candidates,damage,ownedLoan)||handle.table!=&gIndexed||handle.generation==0||key.state.size()<6)return;
 const int members=key.state[4];
 if(members<0||static_cast<size_t>(members)>(key.state.size()-6)/2||5+2*static_cast<size_t>(members)>ResidentScalarKeyWork::MAX_PREFIX_WORDS)return;
 ResidentScalarCertificate& certificate=*gResidentScalarKeyWork.certificate;
 certificate.unit=unit;certificate.extra=gResidentScalarKeyWork.request->extra;certificate.canonical=canonical;certificate.handle=handle;
 certificate.valid=true;++gResidentCaptures;
}
