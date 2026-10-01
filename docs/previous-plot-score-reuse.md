# Reusing previous scores during destination scoring

A preferred-assignment call evaluates many destinations for one actor. Each
candidate previously repeated the same reverse assignment-history scan to find
that actor's previous plot score. A lazy local query now reuses that scalar
only for the same actor and exact history-container object.

Different actors or histories, unavailable forecast context, nested searches,
changed forecast revision and fresh scene changes use the original accessor.
The scene check also catches a yield before the forecast revision updates;
it does not clear or otherwise mutate forecast caches. No pointer escapes the
preferred call, no global result table is added and candidate order/search
budgets are unchanged. Default helper callers retain the original path.

The production fixture passes72,260 x86 VC9 checks. It binds the full source
delta and compiles complete old/new preferred-assignment bodies and move
dispatchers, the actual history accessor, assignments/CoW and six initializer
statements. Other scorer/engine services are deterministic substitutes; this
is not a complete combat-scorer proof. Scores, order and fallback behavior
agree, including a scene change without a revision change and zero scene
reads for ineligible queries. Fixture scans fell from40,535 calls/873,611 rows
to1,960 calls/43,004 rows. Native benefit remains unmeasured.

Reproduce with `work/prepare-previous-plot-score.py`, then
`work/test-previous-plot-score.py --production`.
