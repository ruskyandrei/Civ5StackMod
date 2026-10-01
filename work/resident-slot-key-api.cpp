// Owner-only APIs copy data before callbacks; no key/slot reference escapes.
 bool TryCopyScalarPrefix(const ScalarHandle& handle,const int* fixed,int* out,size_t capacity,
  size_t warmedCapacity,size_t& prefixWords)const
 {
  if(handle.table!=this||!scalarHandlesEnabled||scalarLifetimeExhausted||handle.lifetime!=scalarLifetime||
   !slots||handle.slot<0||static_cast<size_t>(handle.slot)>=slotCapacity||handle.generation==0)return false;
  const Slot& value=slots[handle.slot];
  if(!value.used||value.kind!=DANGER||value.keyWords%2!=0||value.members!=0||value.scalarGeneration!=handle.generation||
   value.keyWords<6||value.keyWords>warmedCapacity||!fixed||!out)return false;
  const int* data=value.Data();if(!std::equal(fixed,fixed+4,data))return false;
  const int members=data[4];
  if(members<0||static_cast<size_t>(members)>(value.keyWords-6)/2)return false;
  const size_t count=5+2*static_cast<size_t>(members);if(count>capacity)return false;
  std::copy(data,data+count,out);prefixWords=count;return true;
 }
 bool TryMatchScalarSuffix(const ScalarHandle& handle,const int* suffix,size_t suffixWords,
  size_t prefixWords,int& result)const
 {
  if(handle.table!=this||!scalarHandlesEnabled||scalarLifetimeExhausted||handle.lifetime!=scalarLifetime||
   !slots||handle.slot<0||static_cast<size_t>(handle.slot)>=slotCapacity||handle.generation==0)return false;
  const Slot& value=slots[handle.slot];
  if(!value.used||value.kind!=DANGER||value.keyWords%2!=0||value.members!=0||value.scalarGeneration!=handle.generation||
   prefixWords>value.keyWords||suffixWords!=value.keyWords-prefixWords||!suffix)return false;
  if(!std::equal(suffix,suffix+suffixWords,value.Data()+prefixWords))return false;
  result=value.scalar;return true;
 }
