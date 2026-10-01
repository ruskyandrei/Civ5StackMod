"""Stage only native packet value/storage accounting against frozen DLL77.

No production edits, compilation, game connection or budget changes. The
forecast agent composes this with its separate key/query/wrapper stage.
"""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/shared-packet-storage-staged'
CONTROL = 'cf8f842e2733841255a1d5bc741e4d95a387299b'
PATH = 'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
old = subprocess.check_output(['git', 'show', CONTROL + ':' + PATH], cwd=ROOT).decode('utf-8')
new = old


def once(text, before, after):
    assert text.count(before) == 1, (before[:90], text.count(before))
    return text.replace(before, after, 1)


def function(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


value = '''// Scalar hits read only this first integer. Odd packet keys retain the
// precomputed exact member integers in the same bounded danger table.
struct StackDangerForecastValue
{
 int scalar;
 vector<pair<int,int> > memberScores;
 StackDangerForecastValue(int value=0):scalar(value){}
};
'''
old_typedef = 'typedef std::tr1::unordered_map<StackForecastKey, int, StackForecastKeyHash> StackDangerForecasts;'
new_typedef = 'typedef std::tr1::unordered_map<StackForecastKey, StackDangerForecastValue, StackForecastKeyHash> StackDangerForecasts;'
new = once(new, old_typedef, value + new_typedef)

payload_helper = '''// Retained capacities, including packet outputs, share the original payload
// ceiling. Scalar value vectors are empty and retain no output allocation.
static size_t StackDangerForecastPayloadBytes(const StackDangerForecasts::value_type& entry)
{
 return entry.first.state.capacity() * sizeof(int)
  + entry.second.memberScores.capacity() * sizeof(pair<int,int>);
}

'''
new = once(new, 'static bool EvictOldestStackForecast()', payload_helper + 'static bool EvictOldestStackForecast()')
old_evict = function(old, 'static bool EvictOldestStackForecast(')
assert old_evict.count('const size_t payload = victim->first.state.capacity() * sizeof(int);') == 2
new_evict = old_evict.replace('const size_t payload = victim->first.state.capacity() * sizeof(int);',
                              'const size_t payload = StackDangerForecastPayloadBytes(*victim);', 1)
new = once(new, old_evict, new_evict)

old_estimate = function(old, 'static size_t EstimatedStackForecastBytes(')
new_estimate = once(old_estimate,
                    '  + sizeof(gStackDangerOrder) + sizeof(gStackDefenderOrder)',
                    '  + gStackDangerForecasts.size() * (sizeof(StackDangerForecastValue) - sizeof(int))\n'
                    '  + sizeof(gStackDangerOrder) + sizeof(gStackDefenderOrder)')
new = once(new, old_estimate, new_estimate)

old_scalar = function(old, 'static void StoreStackDangerForecast(')
new_scalar = once(old_scalar, 'gStackDangerForecasts.insert(make_pair(key, result))',
                  'gStackDangerForecasts.insert(make_pair(key, StackDangerForecastValue(result)))')
new_scalar = once(new_scalar, 'const size_t payload = stored.first->first.state.capacity() * sizeof(int);',
                  'const size_t payload = StackDangerForecastPayloadBytes(*stored.first);')
new = once(new, old_scalar, new_scalar)

packet_store = '''// Insert one temporary uncharged node to measure its ACTUAL copied vector
// capacities before evicting useful entries. No node reference escapes this
// helper; retained entries still use the original shared FIFO/entry ceiling.
static void StoreStackDangerPacketForecast(const StackForecastKey& key, const StackDangerForecastValue& value)
{
 if (!StackForecastContext())
  return;
 if (key.state.size() % 2 == 0 || value.memberScores.size() < 2 || gStackEntryLimit == 0)
 {
  ++gStackInsertBypasses;
  return;
 }
 if (gStackDangerForecasts.find(key) != gStackDangerForecasts.end())
  return;
 const unsigned long revision = gStackForecastRevision;
 const long scene = gStackForecastSceneEpoch;
 pair<StackForecastKey,StackDangerForecastValue> pending(key,value);
 // Reject copied payloads that cannot fit before inserting or evicting.
 if (pending.first.state.capacity() > gStackKeyPayloadLimit / sizeof(int))
 {
  ++gStackInsertBypasses;
  return;
 }
 const size_t copiedKeyBytes = pending.first.state.capacity() * sizeof(int);
 if (pending.second.memberScores.capacity() > (gStackKeyPayloadLimit - copiedKeyBytes) / sizeof(pair<int,int>))
 {
  ++gStackInsertBypasses;
  return;
 }
 // Copying may allocate; observe a changed scene before touching the table.
 if (!StackForecastContext() || revision != gStackForecastRevision || scene != gStackForecastSceneEpoch)
 {
  ++gStackInsertBypasses;
  return;
 }
 pair<StackDangerForecasts::iterator,bool> stored = gStackDangerForecasts.insert(pending);
 if (!stored.second)
  return;
 // Do not call a clearing context helper while owning this iterator. These
 // reads only validate the still-owned pure preview; erase first on failure.
 if (!gStackForecastsActive || gStackForecastDepth != 1 || revision != gStackForecastRevision ||
  scene != gStackForecastSceneEpoch || scene != CvStackingStrengthCache::SceneEpoch())
 {
  gStackDangerForecasts.erase(stored.first);
  ++gStackInsertBypasses;
  return;
 }
 if (stored.first->first.state.capacity() > gStackKeyPayloadLimit / sizeof(int))
 {
  gStackDangerForecasts.erase(stored.first);
  ++gStackInsertBypasses;
  return;
 }
 const size_t keyBytes = stored.first->first.state.capacity() * sizeof(int);
 if (stored.first->second.memberScores.capacity() > (gStackKeyPayloadLimit - keyBytes) / sizeof(pair<int,int>))
 {
  gStackDangerForecasts.erase(stored.first);
  ++gStackInsertBypasses;
  return;
 }
 const size_t payload = StackDangerForecastPayloadBytes(*stored.first);
 // The pending node is already included in size(), but is not in either
 // FIFO yet. Use > for entries; eviction still chooses the larger FIFO.
 while (gStackDangerForecasts.size() + gStackDefenderForecasts.size() > gStackEntryLimit ||
  payload > gStackKeyPayloadLimit - gStackKeyPayloadBytes)
 {
  if (!EvictOldestStackForecast())
  {
   gStackDangerForecasts.erase(stored.first);
   ++gStackInsertBypasses;
   return;
  }
 }
 try
 {
  gStackDangerOrder.push_back(&stored.first->first);
 }
 catch (...)
 {
  // The payload has not been charged. Roll back the otherwise orphan node;
  // previous FIFO evictions are not transactional and remain, as with the
  // legacy preflight. Preserve the caller's allocation failure by rethrowing.
  gStackDangerForecasts.erase(stored.first);
  throw;
 }
 gStackKeyPayloadBytes += payload;
 UpdateStackForecastPeaks();
}

'''
new = once(new, 'static void StoreStackDefenderForecast(', packet_store + 'static void StoreStackDefenderForecast(')

# Representation-only storage stage; key construction and scalar-hit wrapper
# changes are deliberately owned by the composing forecast stage.
for signature in ('static bool CanStoreStackForecast(', 'static void StoreStackDefenderForecast(',
                  'static void ClearStackForecastEntries(', 'static int GetCachedStackDanger(',
                  'static void AppendStackCandidates(', 'static void AppendStackDamageProjected('):
    assert function(old, signature) == function(new, signature), signature
hash_start = old.index('struct StackForecastKey\n')
hash_end = old.index(old_typedef)
assert old[hash_start:hash_end] == new[hash_start:new.index(value)]
restored = once(new, value + new_typedef, old_typedef)
restored = once(restored, payload_helper, '')
restored = once(restored, new_evict, old_evict)
restored = once(restored, new_estimate, old_estimate)
restored = once(restored, new_scalar, old_scalar)
restored = once(restored, packet_store, '')
assert restored == old

OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'control-CvTacticalAI.cpp').write_text(old, encoding='utf-8', newline='')
(OUT / 'CvTacticalAI.cpp').write_text(new, encoding='utf-8', newline='')
(OUT / 'storage.patch').write_text(''.join(difflib.unified_diff(
    old.splitlines(keepends=True), new.splitlines(keepends=True),
    fromfile='a/' + PATH, tofile='b/' + PATH)), encoding='utf-8', newline='')
proof = {'control': CONTROL, 'production_applied': False, 'cpp_restoration_byte_exact': True,
         'scalar_key_hash_scratch_and_wrapper_unchanged': True, 'limits_and_fifo_rule_unchanged': True,
         'compilation_performed': False, 'standalone_compile_ready': False,
         'composition_requirement': 'Forecast query stage changes cached->second to cached->second.scalar and supplies pending query/key/descriptor/wrapper.',
         'clear_paths': 'Existing danger clear/outer swap destroy score vectors before shared charge reset; no additional retained output counter or table.',
         'original_sha256': hashlib.sha256(old.encode()).hexdigest(),
         'candidate_sha256': hashlib.sha256(new.encode()).hexdigest(),
         'new_packet_store_exception_contract': 'Pending node rollback if FIFO push throws; earlier useful FIFO evictions remain; rethrow. No stronger legacy scalar exception contract claimed.'}
(OUT / 'staging-proof.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
print(json.dumps(proof))
