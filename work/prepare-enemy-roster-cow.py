"""Stage only private enemy-roster CoW representation against frozen DLL76."""
from pathlib import Path
import difflib,hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/enemy-roster-cow-staged';CONTROL='9be3018e517233553bb069f7baf656fbfa5cd82d'
PREFIX='CvGameCoreDLL_Expansion2/'
old={n:subprocess.check_output(['git','show',CONTROL+':'+PREFIX+n],cwd=ROOT).decode('utf-8') for n in ('CvTacticalAI.cpp','CvTacticalAI.h')};new=old.copy()
def once(text,before,after):
 assert text.count(before)==1,(before[:80],text.count(before))
 return text.replace(before,after,1)
def block(text,signature):
 start=text.index(signature);end=text.index('{',start)+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
wrapper='''// Private roster value: copies share ordered membership until a real removal.
// Borrowed const views are consumed before mutation in all current callers;
// they must not be retained across a detach/clear/reinitialization.
class STacticalEnemyRoster
{
public:
 const vector<const CvUnit*>& read() const { return data.get() ? *data : Empty(); }
 vector<const CvUnit*>& write()
 {
  if (!data.get())
   data.reset(new vector<const CvUnit*>());
  else if (!data.unique())
   data.reset(new vector<const CvUnit*>(*data));
  return *data;
 }
 void push_back(const CvUnit* unit) { write().push_back(unit); }
 void clear() { data.reset(); }
 bool empty() const { return !data.get() || data->empty(); }
 const CvUnit* front() const { return read().front(); }
private:
 static const vector<const CvUnit*>& Empty();
 std::tr1::shared_ptr<vector<const CvUnit*> > data;
};

'''
empty='''// Empty copies own no control block and perform no reference-count atomics.
static const vector<const CvUnit*> gEmptyTacticalEnemyRoster;
const vector<const CvUnit*>& STacticalEnemyRoster::Empty()
{
 return gEmptyTacticalEnemyRoster;
}

'''
new['CvTacticalAI.h']=once(new['CvTacticalAI.h'],'#include "CvAStar.h"','#include "CvAStar.h"\n#include <memory>')
new['CvTacticalAI.h']=once(new['CvTacticalAI.h'],'class CvTacticalPlot\n',wrapper+'class CvTacticalPlot\n')
new['CvTacticalAI.h']=once(new['CvTacticalAI.h'],
 'const vector<const CvUnit*>& getEnemyUnits() const { return vEnemyUnits; }',
 'const vector<const CvUnit*>& getEnemyUnits() const { return vEnemyUnits.read(); }')
new['CvTacticalAI.h']=once(new['CvTacticalAI.h'],
 'vector<const CvUnit*> vEnemyUnits; // Every surviving defender, including over-capacity stacks.',
 'STacticalEnemyRoster vEnemyUnits; // Ordered surviving defenders; detach only on actual membership mutation.')
new['CvTacticalAI.cpp']=once(new['CvTacticalAI.cpp'],'CvTacticalPlot::CvTacticalPlot(',empty+'CvTacticalPlot::CvTacticalPlot(')
removed=block(old['CvTacticalAI.cpp'],'bool CvTacticalPlot::removeEnemyUnitIfPresent(')
candidate='''bool CvTacticalPlot::removeEnemyUnitIfPresent(int iUnitID)
{
 const vector<const CvUnit*>& enemies = vEnemyUnits.read();
 for (size_t index = 0; index < enemies.size(); ++index)
 {
  if (enemies[index]->GetID() != iUnitID)
   continue;
  // Search without detaching. Convert the matching iterator to an index before
  // write(), so no iterator/reference into shared storage survives its copy.
  vector<const CvUnit*>& remaining = vEnemyUnits.write();
  remaining.erase(remaining.begin() + index);
  aiEnemyDistance[TD_BOTH] = bEnemyCityPresent || !remaining.empty() ? 0 : TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
  aiEnemyDistance[TD_LAND] = aiEnemyDistance[TD_SEA] = bEnemyCityPresent ? 0 : TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
  for (size_t i = 0; i < remaining.size(); ++i)
   aiEnemyDistance[DomainForUnit(remaining[i])] = 0;
  // No reader in this method uses remaining after this last test. Drop the
  // final empty payload so later empty-plot copies have no refcount traffic.
  if (remaining.empty())
   vEnemyUnits.clear();
  return true;
 }
 return false;
}'''
new['CvTacticalAI.cpp']=once(new['CvTacticalAI.cpp'],removed,candidate)
restored=once(new['CvTacticalAI.cpp'],empty,'');restored=once(restored,candidate,removed)
assert restored==old['CvTacticalAI.cpp']
for signature in ('CvTacticalPlot::CvTacticalPlot(','void CvTacticalPlot::clearCapturedCity(','int CvTacticalPlot::getFixedFriendlyCount(','void CvTacticalPlot::resetVolatileProperties('):
 assert block(old['CvTacticalAI.cpp'],signature)==block(new['CvTacticalAI.cpp'],signature)
OUT.mkdir(exist_ok=True);patch=[]
for n in old:
 (OUT/('control-'+n)).write_text(old[n],encoding='utf-8',newline='');(OUT/n).write_text(new[n],encoding='utf-8',newline='')
 patch.extend(difflib.unified_diff(old[n].splitlines(keepends=True),new[n].splitlines(keepends=True),fromfile='a/'+PREFIX+n,tofile='b/'+PREFIX+n))
(OUT/'enemy-roster.patch').write_text(''.join(patch),encoding='utf-8',newline='')
manifest={'control':CONTROL,'production_applied':False,'constructor_and_capture_bodies_byte_exact':True,
 'cpp_restoration_byte_exact':True,'fixed_roster_unchanged':True,'const_accessor_return_type_unchanged':True,
 'borrowed_view_contract':'Current callers consume/copy views before membership mutation; detach/clear can invalidate old vector references.',
 'files':{n:{'original_sha256':hashlib.sha256(old[n].encode()).hexdigest(),'candidate_sha256':hashlib.sha256(new[n].encode()).hexdigest()}for n in old}}
(OUT/'staging-proof.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');print(json.dumps(manifest))
