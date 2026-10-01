# Sharing enemy rosters across tactical branches

Tactical plot copies previously allocated and copied their enemy-unit vectors
even when a branch changed only movement or damage. The private roster value
now shares ordered raw unit pointers until membership changes. Empty copies
own no payload or control block. Constructor membership rules remain unchanged.

Removal searches the read-only roster first. An absent ID does not detach;
the first matching raw ID obtains writable storage and erases that same index.
Parent and sibling rosters remain intact, including duplicate ID/pointer order.
Distance fields are recomputed in their original order. Capture and final
removal release the child's empty payload. Unit state itself remains live and
is neither copied nor owned by the roster.

Each retained payload has at least one plot-field owner, so distinct payloads
cannot exceed retained fields, plus one transient detach. No ancestor position
or assignment history is retained. Shared ownership/control blocks can cost
more than plain vectors when many small rosters are unique. Current callers
consume borrowed const views before mutation; those references must not be
retained across detach, clear or reinitialization. No save-game fields change.

The production fixture passes154,342 x86 VC9 checks, binding both entire current
tactical files and the complete source delta. It compiles actual plot classes,
constructors, removal/capture/volatile/count methods and CoW, with deterministic
engine services. It covers duplicate membership, first-match callback counts,
siblings, recycling, empty/default plots, live unit flags, complete memory
release and three injected detach allocation failures. A synthetic3,000-copy
experiment with32 nonempty plots reduced nested clone allocations96,001→1;
this is not native speed or RSS evidence. Timing and action/census comparisons
remain required.

Reproduce with `work/prepare-enemy-roster-cow.py`, then
`work/test-enemy-roster-cow.py --production`. The fixture's standalone service
data is hash-checked; no other generated scaffold is required.
