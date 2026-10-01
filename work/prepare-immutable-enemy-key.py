"""Stage exact immutable enemy-ledger key reuse; never edit production files."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work' / 'immutable-enemy-key-staged'
CONTROL = 'ee180b91d'
PATH = 'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
original = subprocess.check_output(['git', 'show', f'{CONTROL}:{PATH}'], cwd=ROOT).decode('utf-8')

helper = r'''// A const preferred-assignment call does not mutate its enemy wound ledger.
// Bind only that lexical lifetime, never a persistent container-pointer cache.
// Keep a separate loan: holding gStackSortScratch here would allocate a private
// membership-sort vector for each scalar query in the same candidate loop.
struct StackImmutableEnemyDamageScope;
static StackImmutableEnemyDamageScope* gStackImmutableEnemyDamageScope = NULL;
static vector<pair<int,int> > gStackImmutableEnemyDamageScratch;
static bool gStackImmutableEnemyDamageScratchBusy = false;
struct StackImmutableEnemyDamageScope
{
 const SUnitIDValueContainer& damage;
 StackImmutableEnemyDamageScope* previous;
 unsigned long revision;
 long scene;
 bool registered, borrowed, ready, oversized;
 StackImmutableEnemyDamageScope(const SUnitIDValueContainer& immutableDamage):
  damage(immutableDamage),previous(NULL),revision(0),scene(0),
  registered(false),borrowed(false),ready(false),oversized(false)
 {
  // Check ownership before touching another thread's pointer or scratch flag.
  if (!IsStackForecastOwner() || !StackForecastContext())
   return;
  registered = true;
  previous = gStackImmutableEnemyDamageScope;
  gStackImmutableEnemyDamageScope = this;
  revision = gStackForecastRevision;
  scene = gStackForecastSceneEpoch;
  borrowed = !gStackImmutableEnemyDamageScratchBusy;
  if (borrowed)
  {
   gStackImmutableEnemyDamageScratchBusy = true;
   gStackImmutableEnemyDamageScratch.clear();
  }
 }
 ~StackImmutableEnemyDamageScope()
 {
  if (!registered)
   return;
  gStackImmutableEnemyDamageScope = previous;
  if (borrowed)
  {
   gStackImmutableEnemyDamageScratch.clear();
   gStackImmutableEnemyDamageScratchBusy = false;
  }
 }
 bool TryAppend(StackForecastKey& key, const SUnitIDValueContainer& queriedDamage,
  const vector<int>* freshSourceIDs)
 {
  if (!borrowed || oversized || &damage != &queriedDamage || !StackForecastContext() ||
   revision != gStackForecastRevision || scene != gStackForecastSceneEpoch)
   return false;
  vector<pair<int,int> >& entries = gStackImmutableEnemyDamageScratch;
  if (!ready)
  {
   size_t count = 0;
   for (SUnitIDValueContainer::const_iterator it = damage.begin(); it != damage.end(); ++it)
    if ((*it).second != 0)
     ++count;
   // One bounded temporary fragment; no new memo entries or admission policy.
   if (count > gStackKeyPayloadLimit / sizeof(pair<int,int>))
   {
    oversized = true;
    return false;
   }
   entries.reserve(count);
   if (entries.capacity() > gStackKeyPayloadLimit / sizeof(pair<int,int>))
   {
    vector<pair<int,int> >().swap(entries);
    oversized = true;
    return false;
   }
   for (SUnitIDValueContainer::const_iterator it = damage.begin(); it != damage.end(); ++it)
    if ((*it).second != 0)
     entries.push_back(*it);
   std::sort(entries.begin(), entries.end());
   ready = true;
  }
  const size_t countIndex = key.state.size();
  key.state.push_back(0);
  int count = 0;
  for (size_t i = 0; i < entries.size(); ++i)
   if (!freshSourceIDs || std::binary_search(freshSourceIDs->begin(), freshSourceIDs->end(), entries[i].first))
   {
    key.state.push_back(entries[i].first);
    key.state.push_back(entries[i].second);
    ++count;
   }
  key.state[countIndex] = count;
  return true;
 }
private:
 StackImmutableEnemyDamageScope(const StackImmutableEnemyDamageScope&);
 StackImmutableEnemyDamageScope& operator=(const StackImmutableEnemyDamageScope&);
};
static bool AppendImmutableEnemyDamage(StackForecastKey& key, const SUnitIDValueContainer& damage,
 const vector<int>* freshSourceIDs)
{
 if (!IsStackForecastOwner())
  return false;
 StackImmutableEnemyDamageScope* scope = gStackImmutableEnemyDamageScope;
 return scope && scope->TryAppend(key, damage, freshSourceIDs);
}

'''

def replace_once(text, before, after):
    if text.count(before) != 1:
        raise RuntimeError(f'Expected one exact anchor, got {text.count(before)}: {before[:100]!r}')
    return text.replace(before, after, 1)

candidate = replace_once(original,
    '// Virtual membership is rebuilt for each query, but its temporary storage can',
    helper + '// Virtual membership is rebuilt for each query, but its temporary storage can')
candidate = replace_once(candidate,
    '   vector<pair<int,int> >().swap(gStackSortScratch);',
    '   vector<pair<int,int> >().swap(gStackSortScratch);\n   vector<pair<int,int> >().swap(gStackImmutableEnemyDamageScratch);')
source_anchor = ' const vector<int>* sourceIDs = GET_PLAYER(unit->getOwner()).GetDangerPlots()->GetStackDangerDamageIDs(*plot);\n'
candidate = replace_once(candidate, source_anchor,
    source_anchor + ' if (AppendImmutableEnemyDamage(key, damage, sourceIDs))\n  return;\n')
bind_anchor = '\tif (!pUnit || !assumedUnitPlot)\n\t\treturn;\n\n\tCvTacticalPosition tempPosition;'
candidate = replace_once(candidate, bind_anchor,
    '\tif (!pUnit || !assumedUnitPlot)\n\t\treturn;\n\n'
    '\tStackImmutableEnemyDamageScope immutableEnemyDamage(GetUnitDamageDealt());\n\n\tCvTacticalPosition tempPosition;')

# Reverse the four narrowly scoped edits as a byte-exact source proof.
restored = candidate.replace(helper, '', 1)
restored = restored.replace('\n   vector<pair<int,int> >().swap(gStackImmutableEnemyDamageScratch);', '', 1)
restored = restored.replace(' if (AppendImmutableEnemyDamage(key, damage, sourceIDs))\n  return;\n', '', 1)
restored = restored.replace('\tStackImmutableEnemyDamageScope immutableEnemyDamage(GetUnitDamageDealt());\n\n', '', 1)
assert restored == original
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'CvTacticalAI-control.cpp').write_text(original, encoding='utf-8', newline='')
(OUT / 'CvTacticalAI.cpp').write_text(candidate, encoding='utf-8', newline='')
(OUT / 'enemy-key.patch').write_text(''.join(difflib.unified_diff(
    original.splitlines(keepends=True), candidate.splitlines(keepends=True),
    fromfile='a/' + PATH, tofile='b/' + PATH)), encoding='utf-8', newline='')
(OUT / 'staging-proof.json').write_text(json.dumps({
    'control': CONTROL,
    'path': PATH,
    'source_restored_byte_exact': restored == original,
    'production_applied': False,
    'source_sha256': hashlib.sha256(original.encode()).hexdigest(),
    'candidate_sha256': hashlib.sha256(candidate.encode()).hexdigest(),
    'scope': 'Dedicated immutable enemy-ledger lexical scratch, fresh per-query source metadata, no forecast entries or limits changed.'
}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'staged': str(OUT), 'source_restored_byte_exact': True, 'production_applied': False}))
