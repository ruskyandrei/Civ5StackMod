"""Stage handle-lifetime metadata/API only inside the actual DLL91 IndexedStore.

No parent view, active key elision, source application, build or game calls.
"""
from pathlib import Path
import argparse
import difflib
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = 'e8b5bd3e6'
SOURCE = 'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
OUT = ROOT / 'work/resident-scalar-handles'
OUT.mkdir(exist_ok=True)


def function(source, signature):
    first = source.index(signature)
    last = source.index('{', first) + 1
    depth = 1
    while depth:
        depth += (source[last] == '{') - (source[last] == '}')
        last += 1
    return source[first:last]


old = subprocess.check_output(['git', 'show', BASE + ':' + SOURCE], cwd=ROOT).decode('utf-8-sig').replace('\r\n', '\n')
live = (ROOT / SOURCE).read_text(encoding='utf-8-sig')
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pinned',action='store_true',help='emit only the immutable pinned component even when live Tactical has advanced');options=parser.parse_args()
if not options.pinned:assert live == old, 'Whole current Tactical must equal pinned91 source'
first = old.index('class IndexedStore\n')
last = old.index('static IndexedStore gIndexed;', first)
original = old[first:last]
candidate = original
changes = []


def once(before, after):
    global candidate
    assert candidate.count(before) == 1, before[:100]
    candidate = candidate.replace(before, after, 1)
    changes.append((before, after))


api = ''' // Residence certificates are valid only within this IndexedStore object's
 // C++ lifetime. The production store is one process-lifetime static object.
 // Callers must also hold the original owning, callback-safe Context and bind
 // their exact input proof. These APIs certify residency, not dependencies.
 struct ScalarHandle
 {
  const IndexedStore* table;int slot;unsigned long lifetime,generation;
  ScalarHandle():table(NULL),slot(-1),lifetime(0),generation(0){}
 };
 bool CaptureScalarHandle(int handle,ScalarHandle& result)const
 {
  if(!scalarHandlesEnabled||scalarLifetimeExhausted||!slots||handle<0||static_cast<size_t>(handle)>=slotCapacity)return false;
  const Slot& value=slots[handle];
  if(!value.used||value.kind!=DANGER||value.keyWords%2!=0||value.members!=0||value.scalarGeneration==0)return false;
  ScalarHandle captured;captured.table=this;captured.slot=handle;
  captured.lifetime=scalarLifetime;captured.generation=value.scalarGeneration;
  result=captured;return true;
 }
 bool TryReadScalarHandle(const ScalarHandle& handle,int& result)const
 {
  // Check lifetime and bounds BEFORE any possibly released/recycled slot read.
  if(handle.table!=this||!scalarHandlesEnabled||scalarLifetimeExhausted||handle.lifetime!=scalarLifetime||
   !slots||handle.slot<0||static_cast<size_t>(handle.slot)>=slotCapacity||handle.generation==0)return false;
  const Slot& value=slots[handle.slot];
  if(!value.used||value.kind!=DANGER||value.keyWords%2!=0||value.members!=0||value.scalarGeneration!=handle.generation)return false;
  result=value.scalar;return true; // Only the copied integer escapes.
 }
'''
lifecycle = ''' // No serial is reset by Clear/Release/reInitialize. Exhaustion rejects
 // certificates while ordinary storage continues with the existing policy.
 unsigned long scalarLifetime,nextScalarGeneration;
 bool scalarHandlesEnabled,scalarLifetimeExhausted;
 void AdvanceScalarLifetime()
 {
  if(scalarLifetimeExhausted){scalarHandlesEnabled=false;return;}
  if(scalarLifetime==static_cast<unsigned long>(-1))
  {scalarHandlesEnabled=false;scalarLifetimeExhausted=true;return;}
  ++scalarLifetime;nextScalarGeneration=0;scalarHandlesEnabled=true;
 }
 unsigned long PublishScalarGeneration()
 {
  if(!scalarHandlesEnabled||scalarLifetimeExhausted)return 0;
  if(nextScalarGeneration==static_cast<unsigned long>(-1))
  {scalarHandlesEnabled=false;return 0;}
  return ++nextScalarGeneration;
 }
'''

# Pending's inline layout is unchanged. Only retained Slot gains a four-byte tag.
slot = function(candidate, 'struct Slot\n') + ';'
updated_slot = slot.replace('int words[INLINE_WORDS];', 'unsigned long scalarGeneration;\n  int words[INLINE_WORDS];', 1)
updated_slot = updated_slot.replace('kind(0),used(0){}', 'kind(0),used(0),scalarGeneration(0){}', 1)
once(slot, updated_slot)
once('nextUnused(0),overflowBytes(0)\n', 'nextUnused(0),overflowBytes(0),scalarLifetime(1),nextScalarGeneration(0),scalarHandlesEnabled(true),scalarLifetimeExhausted(false)\n')
once(' void Clear()\n {\n', ' void Clear()\n {\n  AdvanceScalarLifetime();\n')
once(' void Release()\n {\n', ' void Release()\n {\n  AdvanceScalarLifetime();\n')
once('s.hashPrev=s.queueNext=s.hashNext=-1;\n', 's.hashPrev=s.queueNext=s.hashNext=-1;s.scalarGeneration=0;\n')
once('s.used=1;\n', 's.used=1;s.scalarGeneration=0;\n')
once('--counts[s.kind];s.used=0;s.keyWords=s.members=0;\n', '--counts[s.kind];s.used=0;s.keyWords=s.members=0;s.scalarGeneration=0;\n')
once(' void QueuePush(int handle){Push(handle);++queued[slots[handle].kind];}',
     ' void QueuePush(int handle){Push(handle);++queued[slots[handle].kind];slots[handle].scalarGeneration=PublishScalarGeneration();}')
once('slots[handle].queueNext=-1;--queued[kind];', 'slots[handle].queueNext=-1;--queued[kind];slots[handle].scalarGeneration=0;')
once(' // Stable handle. The caller copies scalar/pointer/member data before Context.\n', api + ' // Stable handle. The caller copies scalar/pointer/member data before Context.\n')
once(' IndexedStore(const IndexedStore&);', lifecycle + ' IndexedStore(const IndexedStore&);')

restored = candidate
for before, after in reversed(changes):
    assert restored.count(after) == 1
    restored = restored.replace(after, before, 1)
assert restored == original
new = old[:first] + candidate + old[last:]
assert new.replace(candidate, original, 1) == old
(OUT / 'control-CvTacticalAI.cpp').write_text(old, encoding='utf-8')
(OUT / 'CvTacticalAI.cpp').write_text(new, encoding='utf-8')
(OUT / 'control-IndexedStore.h').write_text(original, encoding='utf-8')
(OUT / 'IndexedStore.h').write_text(candidate, encoding='utf-8')
(OUT / 'api.txt').write_text(api + '\n' + lifecycle, encoding='utf-8')
(OUT / 'handles.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='a/' + SOURCE, tofile='b/' + SOURCE)), encoding='utf-8')
proof = dict(control=BASE, original_whole_sha256=hashlib.sha256(old.encode()).hexdigest(),
    candidate_whole_sha256=hashlib.sha256(new.encode()).hexdigest(), old_class_sha256=hashlib.sha256(original.encode()).hexdigest(),
    candidate_class_sha256=hashlib.sha256(candidate.encode()).hexdigest(), whole_reverse_exact=True, production_untouched=True,
    active_reuse_implemented=False, scope='Queued resident even-scalar handle lifecycle only. Owner C++ lifetime contract; no parent view/callback/key/lookup/budget/policy changes.')
(OUT / 'manifest.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
print(json.dumps(proof))
