# Reusing immutable enemy-damage key fragments

One preferred-assignment call scores many destinations for the same tactical
position. Its enemy-damage ledger stays unchanged during that call, but danger
cache queries repeatedly sorted its contents. A lexical holder now sorts the
nonzero entries once and filters them against each query's freshly obtained
source IDs. It emits the same complete key, preserving raw IDs, signed damage,
duplicate entries and ordering.

Only the exact borrowed ledger object can use the fragment. Nested borrowers,
foreign threads, changed scene/revision and oversized data take the original
path. A dedicated scratch loan keeps membership sorting independent. It adds
no forecast result entries and changes no cache capacity, admission, eviction,
unit/candidate order or search budget. Scope exit returns the loan; outer search
exit frees retained storage. Fresh source metadata calls remain in their
original position, including dirty-state refresh behavior.

The current production fixture passed29,938 actual-source VC9 checks. Complete
old/new context/storage/key builders and the unchanged scalar wrapper are
compiled with the actual value container and deterministic danger services.
It verifies keys/results, hits/misses, capacity/admission/eviction, nested and
foreign contexts, source changes, invalidation, overflow and warm allocation
behavior. The whole source restores to DLL71 after the four reviewed edits
are reversed. Fixture repeated-query sort calls fell2,200→1,101 for1,100 queries;
this is work evidence, not a native speed prediction.

Reproduce with `work/prepare-immutable-enemy-key.py`, followed by
`work/test-immutable-enemy-key.py --production`. Native action/census and timing
comparison remains necessary.
