// WORK-ONLY native staging fragment; inserted before StackForecastScope.
struct StackDangerPacketBuffer
{
 StackForecastKey key;
 vector<int> source;
 vector<const CvUnit*> members;
 StackDangerForecastValue value;
 int descriptor[512];
 void clear(){key.state.clear();source.clear();members.clear();value.memberScores.clear();value.scalar=0;}
 void release(){vector<int>().swap(key.state);vector<int>().swap(source);vector<const CvUnit*>().swap(members);vector<pair<int,int> >().swap(value.memberScores);}
};
static StackDangerPacketBuffer gStackPacketScratch;
static bool gStackPacketScratchBusy=false;
static unsigned long gStackPacketHits=0,gStackPacketBuilds=0,gStackPacketBypasses=0;
struct StackDangerPacketQuery
{
 StackDangerPacketBuffer local;
 bool borrowed,storePacket,scalarValid;
 StackDangerPacketBuffer& buffer;
 StackDangerPacketQuery(bool cacheable):borrowed(cacheable&&!gStackPacketScratchBusy),storePacket(false),scalarValid(false),
  buffer(borrowed?gStackPacketScratch:local)
 {if(borrowed)gStackPacketScratchBusy=true;buffer.clear();}
 ~StackDangerPacketQuery(){if(borrowed)gStackPacketScratchBusy=false;}
private:StackDangerPacketQuery(const StackDangerPacketQuery&);StackDangerPacketQuery&operator=(const StackDangerPacketQuery&);
};
