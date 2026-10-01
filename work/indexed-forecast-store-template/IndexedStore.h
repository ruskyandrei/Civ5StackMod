// Work-only storage prototype. All input keys/values are the actual DLL86 types.
// No slot/payload reference is permitted to escape a small table operation.
class IndexedStore
{
public:
 enum { INLINE_WORDS=32, DANGER=0, DEFENDER=1 };
 struct Pending
 {
  size_t keyWords,members;
  int scalar;
  const CvUnit* defender;
  int* heap;
  int words[INLINE_WORDS];
  Pending():keyWords(0),members(0),scalar(0),defender(NULL),heap(NULL){}
  ~Pending(){delete[] heap;}
  const int* Data()const{return heap?heap:words;}
  size_t Words()const{return keyWords+2*members;}
  void Assign(const StackForecastKey& key,const StackDangerForecastValue* value,const CvUnit* unit)
  {
   keyWords=key.state.size();members=value?value->memberScores.size():0;
   scalar=value?value->scalar:0;defender=unit;
   if(members>(static_cast<size_t>(-1)-keyWords)/2)throw std::bad_alloc();
   const size_t count=Words();
   if(count>static_cast<size_t>(-1)/sizeof(int))throw std::bad_alloc();
   if(count>INLINE_WORDS)heap=new int[count];
   int* out=heap?heap:words;
   if(keyWords)std::memcpy(out,&key.state[0],keyWords*sizeof(int));
   for(size_t i=0;i<members;++i){out[keyWords+2*i]=value->memberScores[i].first;out[keyWords+2*i+1]=value->memberScores[i].second;}
  }
 private:Pending(const Pending&);Pending&operator=(const Pending&);
 };
 struct Slot
 {
  size_t hash,keyWords,members;
  int hashPrev,hashNext,queueNext;
  int scalar;
  const CvUnit* defender;
  int* heap;
  unsigned char kind,used;
  int words[INLINE_WORDS];
  Slot():hash(0),keyWords(0),members(0),hashPrev(-1),hashNext(-1),queueNext(-1),scalar(0),defender(NULL),heap(NULL),kind(0),used(0){}
  ~Slot(){delete[] heap;}
  const int* Data()const{return heap?heap:words;}
  size_t PayloadBytes()const{return (keyWords+2*members)*sizeof(int);}
 };
 IndexedStore():slots(NULL),buckets(NULL),slotCapacity(0),bucketCount(0),firstFree(-1),nextUnused(0),overflowBytes(0)
 {for(int i=0;i<2;++i){heads[i]=tails[i]=-1;counts[i]=queued[i]=0;}}
 ~IndexedStore(){Release();}
 void Init(size_t limit)
 {
  Release();if(!limit)return;
  if(limit>=static_cast<size_t>(INT_MAX)||limit>=static_cast<size_t>(-1)/sizeof(Slot)-1)throw std::bad_alloc();
  const size_t needed=limit+1; // One uncharged packet node may precede FIFO eviction.
  if(needed>static_cast<size_t>(-1)/2)throw std::bad_alloc();
  size_t bucketsNeeded=1;
  while(bucketsNeeded<needed*2){if(bucketsNeeded>static_cast<size_t>(-1)/2)throw std::bad_alloc();bucketsNeeded*=2;}
  try{slots=new Slot[needed];buckets=new int[bucketsNeeded];}
  catch(...){delete[] slots;slots=NULL;delete[] buckets;buckets=NULL;throw;}
  slotCapacity=needed;bucketCount=bucketsNeeded;
  for(size_t i=0;i<bucketCount;++i)buckets[i]=-1;
  firstFree=-1;nextUnused=0;
 }
 void Clear()
 {
  for(size_t i=0;i<nextUnused;++i)
  {
   Slot& s=slots[i];delete[] s.heap;s.heap=NULL;s.used=0;s.keyWords=s.members=0;
   s.hashPrev=s.queueNext=s.hashNext=-1;
  }
  for(size_t i=0;i<bucketCount;++i)buckets[i]=-1;
  for(int i=0;i<2;++i){heads[i]=tails[i]=-1;counts[i]=queued[i]=0;}
  firstFree=-1;nextUnused=0;overflowBytes=0;
 }
 void Release()
 {
  delete[] slots;delete[] buckets;slots=NULL;buckets=NULL;slotCapacity=bucketCount=nextUnused=overflowBytes=0;firstFree=-1;
  for(int i=0;i<2;++i){heads[i]=tails[i]=-1;counts[i]=queued[i]=0;}
 }
 size_t Count(int kind)const{return counts[kind];}
 size_t Total()const{return counts[0]+counts[1];}
 size_t ReservedBytes()const{return slotCapacity*sizeof(Slot)+bucketCount*sizeof(int)+overflowBytes;}
 size_t Capacity()const{return slotCapacity;}
 size_t Buckets()const{return bucketCount;}
 size_t OverflowBytes()const{return overflowBytes;}
 int Find(const StackForecastKey& key,int kind)const
 {
  if(!bucketCount)return -1;
  const size_t hash=StackForecastKeyHash()(key);
  for(int i=buckets[hash&(bucketCount-1)];i!=-1;i=slots[i].hashNext)
  {
   const Slot& s=slots[i];
   if(s.used&&s.kind==kind&&s.hash==hash&&s.keyWords==key.state.size()&&
    (!s.keyWords||!std::memcmp(s.Data(),&key.state[0],s.keyWords*sizeof(int))))return i;
  }
  return -1;
 }
 // Stable handle. The caller copies scalar/pointer/member data before Context.
 const Slot& At(int handle)const{return slots[handle];}
 int Insert(const StackForecastKey& key,Pending& pending,int kind,bool& inserted)
 {
  int duplicate=Find(key,kind);if(duplicate!=-1){inserted=false;return duplicate;}
  int handle;
  if(firstFree!=-1){handle=firstFree;firstFree=slots[handle].hashNext;}
  else{if(nextUnused>=slotCapacity)throw std::bad_alloc();handle=static_cast<int>(nextUnused++);}
  Slot& s=slots[handle];
  s.hash=StackForecastKeyHash()(key);s.keyWords=pending.keyWords;s.members=pending.members;
  s.scalar=pending.scalar;s.defender=pending.defender;s.kind=static_cast<unsigned char>(kind);s.used=1;
  s.heap=pending.heap;pending.heap=NULL;
  if(!s.heap&&pending.Words())std::memcpy(s.words,pending.words,pending.Words()*sizeof(int));
  if(s.heap)overflowBytes+=s.PayloadBytes();
  size_t bucket=s.hash&(bucketCount-1);s.hashPrev=-1;s.hashNext=buckets[bucket];s.queueNext=-1;
  if(s.hashNext!=-1)slots[s.hashNext].hashPrev=handle;
  buckets[bucket]=handle;++counts[kind];inserted=true;return handle;
 }
 void Erase(int handle)
 {
  Slot& s=slots[handle];const size_t bucket=s.hash&(bucketCount-1);
  if(s.hashPrev!=-1)slots[s.hashPrev].hashNext=s.hashNext;else buckets[bucket]=s.hashNext;
  if(s.hashNext!=-1)slots[s.hashNext].hashPrev=s.hashPrev;
  if(s.heap)overflowBytes-=s.PayloadBytes();
  delete[] s.heap;s.heap=NULL;--counts[s.kind];s.used=0;s.keyWords=s.members=0;
  s.hashPrev=s.queueNext=-1;s.hashNext=firstFree;firstFree=handle;
 }
 void Push(int handle)
 {
  Slot& s=slots[handle];int kind=s.kind;
  if(tails[kind]!=-1)slots[tails[kind]].queueNext=handle;else heads[kind]=handle;
  tails[kind]=handle;
 }
 int Head(int kind)const{return heads[kind];}
 size_t QueueCount(int kind)const
 {
  size_t count=0;for(int i=heads[kind];i!=-1;i=slots[i].queueNext){if(i<0||static_cast<size_t>(i)>=slotCapacity||++count>slotCapacity)return static_cast<size_t>(-1);}return count;
 }
 // O(1) FIFO count is separate from total entries, including pending packet.
 size_t FIFOCount(int kind)const{return queued[kind];}
 void QueuePush(int handle){Push(handle);++queued[slots[handle].kind];}
 void QueuePop(int kind)
 {
  int handle=heads[kind];heads[kind]=slots[handle].queueNext;if(heads[kind]==-1)tails[kind]=-1;
  slots[handle].queueNext=-1;--queued[kind];
 }
 int NextQueued(int handle)const{return slots[handle].queueNext;}
 void ResetQueued(){queued[0]=queued[1]=0;}
 bool Invariant(size_t logicalBytes,size_t limit,size_t payloadLimit)const
 {
  size_t bytes=0,total=0,heapBytes=0,freeCount=0;
  for(size_t i=0;i<slotCapacity;++i)if(slots[i].used){bytes+=slots[i].PayloadBytes();if(slots[i].heap)heapBytes+=slots[i].PayloadBytes();++total;}
  for(int i=firstFree;i!=-1;i=slots[i].hashNext){if(i<0||static_cast<size_t>(i)>=slotCapacity||slots[i].used||++freeCount>slotCapacity)return false;}
  return bytes==logicalBytes&&total==Total()&&total<=limit&&bytes<=payloadLimit&&heapBytes==overflowBytes&&nextUnused<=slotCapacity&&total+freeCount==nextUnused&&
   QueueCount(0)==queued[0]&&QueueCount(1)==queued[1]&&queued[0]==counts[0]&&queued[1]==counts[1];
 }
private:
 Slot* slots;int* buckets;size_t slotCapacity,bucketCount;int firstFree;size_t nextUnused;
 int heads[2],tails[2];size_t counts[2],queued[2],overflowBytes;
 IndexedStore(const IndexedStore&);IndexedStore&operator=(const IndexedStore&);
};

static IndexedStore gIndexed;
static bool gUseIndexed=false;
static void ClearStackForecastEntries()
{
 gIndexed.Clear();gIndexed.ResetQueued();gStackDangerOrder.clear();gStackDefenderOrder.clear();
 gStackDangerForecasts.clear();gStackDefenderForecasts.clear();gStackThreatFlags.clear();gStackKeyPayloadBytes=0;++gStackForecastRevision;
}

// Original Context/Invalidate functions are inserted here by the fixture builder.

