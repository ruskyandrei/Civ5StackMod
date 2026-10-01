// A preparation view lasts only through one parent's const preferred-unit batch.
// No danger result or serialized key is retained. Borrowed query ownership is
// the admission witness; a private/nested query always follows the old builder.
struct ParentStackPreparationCell
{
 int plotIndex;
 VirtualFriendlyStackBuffer base;
 ParentStackPreparationCell():plotIndex(-1) {}
};
struct ParentStackPreparationStorage
{
 enum { MAX_CELLS = 255 };
 ParentStackPreparationCell cells[MAX_CELLS];
 pair<int,int> lookup[MAX_CELLS];
 size_t count,retainedBytes;
 bool busy;
 ParentStackPreparationStorage():count(0),retainedBytes(0),busy(false) {}
 void Reset()
 {
  for (size_t i=0;i<count;++i)
  {cells[i].base.candidates.clear();cells[i].base.damage.clear();cells[i].plotIndex=-1;}
  count=0;
 }
 size_t CellBytes(size_t i) const
 {
  return cells[i].base.candidates.capacity()*sizeof(const CvUnit*)+
   cells[i].base.damage.m_aExtraStorage.capacity()*sizeof(SUnitIDValueContainer::value_type);
 }
 size_t RetainedBytes() const {return retainedBytes;}
 void ReleaseCell(size_t i)
 {
  retainedBytes-=CellBytes(i);cells[i].base.release();
 }
 void ReleasePayload()
 {
  for(size_t i=0;i<MAX_CELLS;++i) cells[i].base.release();
  count=0;retainedBytes=0;
 }
 void Release(){ReleasePayload();busy=false;}
};
static ParentStackPreparationStorage gParentStackPreparationStorage;
struct ParentStackPreparationView;
static __declspec(thread) ParentStackPreparationView* gParentStackPreparationView=NULL;
static void ReleaseParentStackPreparationStorage()
{gParentStackPreparationStorage.Release();}

struct ParentStackPreparationView
{
 const CvTacticalPosition& parent;
 const CvTacticalPosition* child;
 ParentStackPreparationView* previous;
 unsigned long revision;
 long scene;
 bool disabled,borrowed;
 ParentStackPreparationView(const CvTacticalPosition& position):parent(position),child(NULL),
  previous(gParentStackPreparationView),revision(0),scene(0),disabled(previous!=NULL),borrowed(false)
 {
  if(previous) previous->disabled=true;
  gParentStackPreparationView=this;
 }
 ~ParentStackPreparationView()
 {
  if(borrowed) gParentStackPreparationStorage.busy=false;
  gParentStackPreparationView=previous;
 }
 void MarkChild(const CvTacticalPosition& from,const CvTacticalPosition& to)
 {
  child=NULL;
  if(!disabled&&&from==&parent&&&to!=&parent&&to.SharesVirtualStackInputs(parent)) child=&to;
 }
 bool CanPrepare(const CvTacticalPosition& position,bool ownedLoan)
 {
  // Short-circuit before owner-only globals/storage on a foreign/private call.
  if(!ownedLoan||disabled||(&position!=&parent&&&position!=child)||
   !position.SharesVirtualStackInputs(parent)) return false;
  if(!borrowed)
  {
   if(gParentStackPreparationStorage.busy) return false;
   // ownedLoan was granted by this callsite's original fresh Context check.
   revision=gStackForecastRevision;scene=gStackForecastSceneEpoch;
   gParentStackPreparationStorage.Reset();gParentStackPreparationStorage.busy=true;borrowed=true;
  }
  if(revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch) {disabled=true;return false;}
  return true;
 }
 bool Prepare(const CvTacticalPosition& position,const CvPlot* plot,const CvUnit* arriving,int extraDamage,
  vector<const CvUnit*>& candidates,SUnitIDValueContainer& damage,bool ownedLoan)
 {
  if(!candidates.empty()||(damage.begin()!=damage.end())||!CanPrepare(position,ownedLoan)) return false;
  ParentStackPreparationStorage& storage=gParentStackPreparationStorage;
  const int index=plot->GetPlotIndex();
  size_t lo=0,hi=storage.count;
  while(lo<hi){const size_t mid=lo+(hi-lo)/2;if(storage.lookup[mid].first<index)lo=mid+1;else hi=mid;}
  size_t cellIndex;
  if(lo<storage.count&&storage.lookup[lo].first==index) cellIndex=storage.lookup[lo].second;
  else
  {
   if(storage.count==ParentStackPreparationStorage::MAX_CELLS) return false;
   cellIndex=storage.count;
   ParentStackPreparationCell& cell=storage.cells[cellIndex];
   const size_t before=storage.CellBytes(cellIndex);
   try
   {
    GetVirtualFriendlyStack(parent,plot,NULL,0,cell.base.candidates,cell.base.damage);
    storage.retainedBytes=storage.retainedBytes-before+storage.CellBytes(cellIndex);
    if(storage.RetainedBytes()>gStackKeyPayloadLimit)
    {storage.ReleasePayload();disabled=true;return false;}
   }
   catch(const std::bad_alloc&)
   {storage.retainedBytes=storage.retainedBytes-before+storage.CellBytes(cellIndex);storage.ReleasePayload();disabled=true;return false;}
   if(disabled||revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch||
    scene!=CvStackingStrengthCache::SceneEpoch())
   {storage.ReleaseCell(cellIndex);disabled=true;return false;}
   cell.plotIndex=index;
   for(size_t i=storage.count;i>lo;--i) storage.lookup[i]=storage.lookup[i-1];
   storage.lookup[lo]=make_pair(index,(int)cellIndex);++storage.count;
  }
  try
  {candidates=storage.cells[cellIndex].base.candidates;damage=storage.cells[cellIndex].base.damage;}
  catch(const std::bad_alloc&)
  {candidates.clear();damage.clear();storage.ReleasePayload();disabled=true;return false;}
  // Keep the original pointer-dedup and exact arrival-wound overwrite order.
  if(arriving)
  {
   if(std::find(candidates.begin(),candidates.end(),arriving)==candidates.end()) candidates.push_back(arriving);
   damage.SetValue(arriving->GetID(),extraDamage);
  }
  // Warm reuse contains only vector copies and native GetID/GetPlotIndex.
  // Their caller already validated the live scene before granting ownedLoan.
  if(disabled||revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch)
  {candidates.clear();damage.clear();disabled=true;return false;}
  return true;
 }
private:
 ParentStackPreparationView(const ParentStackPreparationView&);
 ParentStackPreparationView& operator=(const ParentStackPreparationView&);
};
static void MarkParentStackPreparationChild(const CvTacticalPosition& from,const CvTacticalPosition& to)
{if(gParentStackPreparationView) gParentStackPreparationView->MarkChild(from,to);}
static void GetPreparedVirtualFriendlyStack(const CvTacticalPosition& position,const CvPlot* plot,
 const CvUnit* arriving,int extraDamage,vector<const CvUnit*>& candidates,SUnitIDValueContainer& damage,bool ownedLoan)
{
 ParentStackPreparationView* view=gParentStackPreparationView;
 if(!view||!view->Prepare(position,plot,arriving,extraDamage,candidates,damage,ownedLoan))
  GetVirtualFriendlyStack(position,plot,arriving,extraDamage,candidates,damage);
}
