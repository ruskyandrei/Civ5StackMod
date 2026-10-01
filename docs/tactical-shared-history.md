# Shared history in tactical uniqueness checks

Normal tactical expansion now avoids repeatedly scanning the identical
assignment prefix inherited from its selected ancestor. The change uses a
protected `CvTacticalPosition::isUniqueWithSharedHistory` path called only by
the main tactical `makeNextAssignments` loop. The public/default `isUnique`,
shared default comparator and support uniqueness paths remain unchanged.

This reduces history work inside an existing check. It does not reduce the
number/order of descendants visited, permutation cases, branches, choices,
completed states, recruited units or search budgets. It stores no persistent
cache or serialized state.

## The invariant

The existing check climbs up to three ancestors and then traverses every
descendant beneath that ancestor. Every normal descendant inherits the
ancestor's complete assignment history and appends its own records. The
ancestor's prefix is therefore identical in the reference and each compared
descendant.

The traversal-local context begins at:

```text
max(reference.firstInterestingAssignment, ancestor.assignmentCount)
```

Comparison still ends at the reference's assignment count; extra FINISH records
in the other history remain ignored. Object self-comparison and reference-
longer-than-other guards run before any reference score sum is computed. The
context computes the reference suffix score lazily once, then reuses it only
during that immutable recursive traversal.

The original score sums include the same prefix, so that prefix cancels from
their equality comparison. The original backward permutation loop would
observe equal prefix records and continue without changing its A/B/C/D state.
Skipping them therefore preserves unfinished suffix mismatch and 2/3/4-element
permutation results. Sums remain `int` values built from actual saturated
assignment `Score()` values; total position score has a different meaning and
is not substituted.

## Mutation and lifetime rules

The current main expansion preserves the invariant:

- Initial assignment scores are rewritten during root preprocessing, before
  main children are created. The first-interesting boundary is then set once
  and inherited by children.
- Main assignment, visibility RESTART and final FINISH operations append
  records. Finish score adjustments modify plotScores rather than rewriting
  previous assignment records.
- Inconsistent partial combos are excluded before the protected check.
  Accepted children consume their storage slots. Rejected uncommitted slots
  are unlinked before reuse and receive a fresh context.
- Preview positions used by scoring do not enter this tree or use this path.
- Full support interleaving replaces only the selected winner's history after
  main expansion has finished. Early support feasibility returns before that
  replacement. New searches reset storage before checking another tree.
- The recursive traversal performs no game callbacks, yields or history
  mutations. Its borrowed records remain valid until the call returns.

The exposed mutable latest/history accessors currently have no production
callers; the initial mutable accessor is used only in preprocessing. A future
in-place mutation of an ancestor prefix during expansion would invalidate this
optimization. Such work must retain the legacy check or revise the invariant.
Arbitrary manually supplied unrelated histories already retain the unchanged
public/default path.

The three-ancestor parameter does not limit descendant depth. Old sibling
branches may contain long completed chains, so the existing traversal can
visit many nodes for each candidate. This change removes repeated prefix sums
and detailed prefix equality checks, including damage/healing payload work; it
does not address that traversal cardinality itself.

## Verification and interpretation

`work/test-uniqueness-history.py --compile` binds to current production. It
requires full normalized source equality to the independently reviewed stage
and reverses the helper/declaration/one-callsite delta back to compiled DLL65
commit `1715cd68f`. Default and support methods must be byte-identical. The
fixture defaults to source emission without compilation so it can be prepared
while a guarded replay is running.

The VC9 x86 differential fixture passes **111,472 checks**. It compiles actual
legacy and specialized comparators/recursive methods, plus actual assignment,
equality, damage/healing and CoW definitions. Deterministic inherited trees
exercise short-score extremes, long prefixes, 2/3/4-cycles, duplicate values,
trailing FINISH, root/zero-level checks, lazy no-read guards, randomized deep
branches, payload/primary identity differences, and reused rejected slots.
Deliberately inconsistent manual prefixes are checked on the legacy path.

For each case it compares uniqueness results, equivalent/different counter
deltas, node-entry sequence, actual comparison postorder and first match. It
also asserts that specialized assignment-record reads never exceed the
original work. These are helper-level work checks, not full-game timing or
memory measurements.

Denser DLL65 diagnostics estimated overlapping nextAssignments/preferred
envelopes around 51/47 seconds on the slow saved turn. They come from different
systematic samples; their difference is not a measured four-second uniqueness
budget. A modest gain is plausible, but no native speedup is claimed here.
The acceptance test remains a guarded saved-game replay with complete semantic
and census comparison, turn timing and peak memory. Diagnostic estimates must
not be summed or treated as CPU shares.
