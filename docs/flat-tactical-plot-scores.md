# Contiguous tactical plot scores

`CvBasePosition::plotScores` now uses `SCoWField<STacticalPlotScores>` instead
of `SCoWField<map<int, short>>`. Tactical branches frequently copy this small
score table. The former tree allocated a node for each scored actor on a
child's first write. The new table copies contiguous `pair<int, short>` records
and can reuse its allocation when a storage slot is recycled.

The change is confined to this protected field, its container implementation
in `CvTacticalAI.h`, and four explicit type declarations in `CvTacticalAI.cpp`.
It does not change scores, unit recruitment, candidate creation/order, search
budgets, tie handling or saved-game data. Other maps and CoW fields retain
their existing behavior.

## Container contract

Keys remain signed integers in ascending order. `operator[]` inserts a missing
key with a zero `short` value and returns a `short&`, preserving the existing
assignment/narrowing and `+=` conversion behavior. Const iteration, copy,
assignment, clear, swap, size and empty are supported. There is no actor count
cap: the 13 retained active-unit search limit does not bound initial, dropped
or support-unit score entries.

Vector insertion can invalidate element references and iterators. The current
field's callers are safe under that contract:

- `operator[]` references are consumed in an immediate assignment or `+=`.
- `UpdateScore` writes during iteration only after finding an existing key;
  that operation does not insert or grow the vector. A dirty local table's
  iterator stays valid. A first write to a borrowed table clones into the child
  while the loop continues reading the unchanged parent.
- `UpdateScore` inserts a missing key after its iteration has ended.
- Finish bonuses are inserted before the final score-summation iteration.
- CoW borrows the container object's address, not an element address. The
  container object stays stable when its vector grows.

Future callers must preserve these conditions. Do not retain an element
reference or iterator across insertion, and do not substitute this table for
the latest assignment's plot score; finish adjustments can make those differ.

## Memory and lifecycle

The existing CoW implementation is unchanged. `inheritFrom` clears the child's
local table and then borrows the parent until first write. `clear` removes
score entries while retaining vector capacity. The existing hard reset/wipe
releases it through an empty-container swap. No history, tactical-plot payload
or unit object is retained by a new generic CoW policy.

Contiguous records reduce allocation/node overhead for the same key count.
Capacity can remain larger than a later smaller roster in a reused slot, so
isolated fixed-size allocation results do not prove lower RSS in every state.
Guarded native replay should still check peak memory, especially in the x86
game.

## Verification

`work/test-plot-score-container.py` compiles current production methods with
the project's VC9 x86 compiler. It checks the whole container-only source delta
against pre-container DLL64 commit `fb45e447e`. The header/wrapper and actual
score/finish extracts must exactly match the independently reviewed staging;
restoring the four type names must restore the original methods. Concurrent
zero-AoE and diagnostic cadence changes are outside this comparison.

The differential fixture passes **49,687 checks**. It compiles complete actual
original/current `UpdateScore` and `addFinishMovesIfAcceptable` methods, plus
the actual CoW, assignment/equality and damage/healing definitions. Engine
unit, plot and forecast services are deterministic stubs. Cases cover stacking
on/off, more than 1,000 keys, extreme/negative/zero IDs, default insertion,
short narrowing and finish overflow conversion, dirty/borrowed writes,
parent/child/grandchild isolation, insertion after iteration, clear/wipe,
self-inherit, copy/swap, finish return/bad-unit results, negative safeguards,
loss budgets and emitted assignment payloads.

A fixed-size experiment recycles one child 3,000 times:

| Score keys | Tree allocations | Contiguous allocations | Tree requested bytes | Contiguous requested bytes |
| --- | ---: | ---: | ---: | ---: |
| 1 | 3,000 | 1 | 72,000 | 8 |
| 13 | 39,000 | 1 | 936,000 | 104 |
| 40 | 120,000 | 1 | 2,880,000 | 320 |
| 127 | 381,000 | 1 | 9,144,000 | 1,016 |

These allocation requests are asserted, and live requested bytes return to
their previous value after destruction. They are helper-level results, not
native turn-speed or RSS measurements. Full saved-game semantic/census
comparison and guarded turn timing remain the acceptance test. No native
speedup is claimed by this implementation note.
