# Target-distance field timing

One existing TurnPhaseScope surrounds UpdatePlotDistanceToTarget, including
both original land/naval reach floods, output copies and target assignment.
The helper's original body and query order are unchanged. The existing Summary
filter, interval, row budget, rotation and generation guards apply; this adds
one bounded phase row per attempted rebuild without enabling Verbose.

The phase reader classifies target_distance_fields as tactical work. Its
inclusive span is a child of operation or zone processing, so use interval
unions rather than adding it to enclosing spans. TURN_PHASE records do not move
the comparable native turn anchors. The reader's48 regression checks pass.

The guarded composition reverses the entire two-file change exactly to DLL93.
Native behavior and complete archive coverage still need comparison. This
measurement neither reuses fields nor changes pathfinder/search behavior.
Equal field values alone would not justify skipping the queries: world
dependencies and retained StepFinder state require a separate proof. See
`work/target-distance-field/dependency-review.md`.

The complete DLL94 replay matches DLL93's699 semantic records, both censuses,
and all34 recorded non-timing cache fields in455 searches. The rebased
production timer checks pass32/0, binding both full candidate files and seven
unchanged dependencies. Source/query order and entire-function reversal remain
exact. Native archive coverage is complete for the compared records.

Interior252 took31.515s (PLAN8.997s),253 took58.047s (PLAN33.331s). This is a
diagnostic build, not a clean optimization speed result. The new phase records
72 rebuilds on252 with79ms summed inclusive time, and100 rebuilds on253 with
218ms. Its estimated outside-PLAN spans are69/205ms; small overlap arises from
the approximate PLAN boundary. GetTickCount has coarse resolution, so zero rows
are not zero work and these sums are not exact CPU cost. The observations do not
support a large saving from redesigning this field calculation in this replay.

Evidence: `work/test-runs/perf-d94-distance-field-timing-251-255`, native
`Stacking-20261001T105227-071-p22752-r1`, phases252/253 and
`distance-field-summary.json`. Game/service closed normally10:55:13UTC and the
guards stayed within thresholds. Further work prioritizes resident-key reuse
and the verified large miss-only packet frame on cache hits.
