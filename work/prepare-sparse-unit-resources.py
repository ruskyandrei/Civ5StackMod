"""Stage immutable positive unit-resource metadata; never apply production edits."""
from pathlib import Path
import difflib,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/sparse-unit-resources-staged';OUT.mkdir(exist_ok=True)
CONTROL='9c4b9915e'
paths=['CvGameCoreDLL_Expansion2/CvUnitClasses.h','CvGameCoreDLL_Expansion2/CvUnitClasses.cpp','CvGameCoreDLL_Expansion2/CvPlayer.cpp']
original={p:subprocess.check_output(['git','show',CONTROL+':'+p],cwd=ROOT).decode('utf-8-sig') for p in paths}
changed=dict(original)
header=changed[paths[0]]
header=header.replace('\tint GetResourceQuantityTotal(int i) const;','\tint GetResourceQuantityTotal(int i) const;\n\tconst std::vector<int>* GetResourceQuantityCheckIDs() const;',1)
header=header.replace('\tstd::map<int, int> m_piResourceQuantityTotals;', '\tstd::map<int, int> m_piResourceQuantityTotals;\n\t// Derived immutable metadata; NULL getter fallback until fully loaded.\n\tstd::vector<int> m_vResourceQuantityCheckIDs;\n\tint m_iResourceQuantityCheckInfoCount;\n\tvoid CacheResourceQuantityCheckIDs();',1)
changed[paths[0]]=header
cpp=changed[paths[1]]
cpp=cpp.replace('\tm_piResourceQuantityTotals(),','\tm_piResourceQuantityTotals(),\n\tm_vResourceQuantityCheckIDs(),\n\tm_iResourceQuantityCheckInfoCount(-1),',1)
cpp=cpp.replace('bool CvUnitEntry::CacheResults(Database::Results& kResults, CvDatabaseUtility& kUtility)\n{','bool CvUnitEntry::CacheResults(Database::Results& kResults, CvDatabaseUtility& kUtility)\n{\n\t// A failed/repeated load must not expose stale derived metadata.\n\tm_iResourceQuantityCheckInfoCount = -1;\n\tm_vResourceQuantityCheckIDs.clear();',1)
cpp=cpp.replace('\t// Calculate military Power and cache it\n\tDoUpdatePower();','\t// Both resource requirements and total-quantity rows are now loaded.\n\tCacheResourceQuantityCheckIDs();\n\t// Calculate military Power and cache it\n\tDoUpdatePower();',1)
helper=r'''// Only positive requirements/totals can enter the live resource checks. Keep
// their union in original ascending ID order, independent of feature flags.
void CvUnitEntry::CacheResourceQuantityCheckIDs()
{
 m_iResourceQuantityCheckInfoCount = -1;
 m_vResourceQuantityCheckIDs.clear();
 const int count = GC.getNumResourceInfos();
 for (int resource = 0; resource < count; ++resource)
  if (GetResourceQuantityRequirement(resource) > 0 || GetResourceQuantityTotal(resource) > 0)
   m_vResourceQuantityCheckIDs.push_back(resource);
 m_iResourceQuantityCheckInfoCount = count;
}

const std::vector<int>* CvUnitEntry::GetResourceQuantityCheckIDs() const
{
 // Custom/reloading databases with a changed resource count retain the full
 // original scan; default/failed entry loads use that same path.
 return m_iResourceQuantityCheckInfoCount == GC.getNumResourceInfos() ? &m_vResourceQuantityCheckIDs : NULL;
}

'''
cpp=cpp.replace('/// Initial set of promotions for this unit',helper+'/// Initial set of promotions for this unit',1)
changed[paths[1]]=cpp
player=changed[paths[2]]
start=player.index('bool CvPlayer::HasResourceForNewUnit(')
before='\tfor (int iResourceLoop = 0; iResourceLoop < GC.getNumResourceInfos(); iResourceLoop++)\n\t{\n\t\tconst ResourceTypes eResource = static_cast<ResourceTypes>(iResourceLoop);'
after='\tconst std::vector<int>* resourceIDs = pUnitInfo->GetResourceQuantityCheckIDs();\n\tfor (int iResourceCheck = 0; iResourceCheck < (resourceIDs ? (int)resourceIDs->size() : GC.getNumResourceInfos()); iResourceCheck++)\n\t{\n\t\tconst int iResourceLoop = resourceIDs ? (*resourceIDs)[iResourceCheck] : iResourceCheck;\n\t\tconst ResourceTypes eResource = static_cast<ResourceTypes>(iResourceLoop);'
assert before in player[start:]
player=player[:start]+player[start:].replace(before,after,1)
changed[paths[2]]=player
patch=[];hashes={}
for p in paths:
 old,new=original[p],changed[p];assert old!=new,p
 (OUT/Path(p).name).write_text(new,encoding='utf-8')
 patch.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+p,tofile='b/'+p))
 hashes[p]=dict(source_sha256=hashlib.sha256(old.encode()).hexdigest(),candidate_sha256=hashlib.sha256(new.encode()).hexdigest())
(OUT/'sparse-resources.patch').write_text(''.join(patch),encoding='utf-8')
(OUT/'staging-proof.json').write_text(json.dumps(dict(control=CONTROL,production_applied=False,files=hashes,positive_union_ascending=True,live_resource_body_unchanged=True,unknown_or_changed_resource_count_original_fallback=True,feature_flags_not_cached=True),indent=2)+'\n',encoding='utf-8')
print('Staged sparse unit-resource proposal; production unchanged.')
