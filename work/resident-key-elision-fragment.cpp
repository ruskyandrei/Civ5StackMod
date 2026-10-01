// A live UnitDanger call is the only admission route. Other full/solo roster
// queries cannot inherit a resident arrival certificate accidentally.
struct ResidentArrivalRequest
{
 const CvUnit* unit;const CvPlot* plot;const CvTacticalPosition& position;
 const vector<const CvUnit*>& candidates;const SUnitIDValueContainer& damage;
 int extra;ResidentArrivalRequest* previous;
 ResidentArrivalRequest(const CvUnit* u,const CvPlot* p,int d,const CvTacticalPosition& s,
  const vector<const CvUnit*>& c,const SUnitIDValueContainer& f);
 ~ResidentArrivalRequest();
};
static __declspec(thread) ResidentArrivalRequest* gResidentArrivalRequest=NULL;
ResidentArrivalRequest::ResidentArrivalRequest(const CvUnit* u,const CvPlot* p,int d,const CvTacticalPosition& s,
 const vector<const CvUnit*>& c,const SUnitIDValueContainer& f):unit(u),plot(p),position(s),candidates(c),damage(f),extra(d),previous(gResidentArrivalRequest)
{gResidentArrivalRequest=this;}
ResidentArrivalRequest::~ResidentArrivalRequest(){gResidentArrivalRequest=previous;}
struct ResidentScalarCertificate
{
 vector<int> key;const CvUnit* unit;int extra;bool canonical,valid;
 IndexedStore::ScalarHandle handle;
 ResidentScalarCertificate():unit(NULL),extra(0),canonical(false),valid(false){}
 size_t Bytes()const{return key.capacity()*sizeof(int);}
 void Release(){valid=false;vector<int>().swap(key);}
};
struct ParentStackPreparationView;
struct ResidentScalarKeyWork
{
 enum { MAX_PREFIX_WORDS=128 }; // Optional shortcut only; oversized keys use original path.
 int prefix[MAX_PREFIX_WORDS];size_t count;
 ResidentScalarCertificate* certificate;ParentStackPreparationView* view;
 ResidentArrivalRequest* request;IndexedStore::ScalarHandle handle;
 ResidentScalarKeyWork():count(0),certificate(NULL),view(NULL),request(NULL){}
};
// The original owned danger-key loan protects this scratch through projection.
// Private/nested/foreign callers never touch it; no Slot reference is retained.
static ResidentScalarKeyWork gResidentScalarKeyWork;
static bool PrepareResidentScalarKey(const CvUnit*,const CvPlot*,const vector<const CvUnit*>&,
 const SUnitIDValueContainer&,const SUnitIDValueContainer&,const int*,bool,bool,StackForecastKey&);
static bool ReadPreparedResidentScalar(int&);
static void CompletePreparedResidentScalarKey(StackForecastKey&);
static void CaptureResidentScalarKey(const CvUnit*,const CvPlot*,const vector<const CvUnit*>&,
 const SUnitIDValueContainer&,const int*,bool,bool,const StackForecastKey&,const IndexedStore::ScalarHandle&);

static bool HasResidentScalarCaptureContext(const CvUnit*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,bool);
