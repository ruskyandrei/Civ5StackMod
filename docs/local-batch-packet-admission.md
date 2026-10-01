# Prefer existing local danger batches

A ready local outcome batch already serves subsequent member queries. Those
queries now retain the original batch lookup and scalar admission, avoiding
global packet preparation. A cold batch can still hit an existing global
packet. If it computes a new outcome, its result and queried scalar are kept
without seeding another global packet. Nonbatch queries retain global reuse.

This reduces duplicate retained entries without changing cache limits, math,
source/callback checks or the inexpensive scalar hit path. Invalidated or
released computed results are returned once; required work is never repeated
to populate a cache. Unsupported and mismatched batches keep existing fallbacks.

The actual-source fixture compares frozen77,79 and both trial policies with
complete original math, wrappers and storage. The adopted combined policy
passed14,546 checks, including strike traces, ready/cold/stale batches,
callbacks, scene/source changes, admission, allocation failure and release.
Strict production mode binds all three current Tactical/Danger files to the
reviewed variant and keeps original controls pinned to Git.

Synthetic batch loops with a two-entry limit reduced evictions158→98 and
descriptor reads560→100, with20 original simulations on both sides. These are
controlled fixture counts, not native turn-time predictions. A native replay
must compare actions, censuses, pressure and complete turn windows before
claiming a performance improvement.
