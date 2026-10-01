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
