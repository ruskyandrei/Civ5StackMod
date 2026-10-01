# Sparse unit resource eligibility checks

VP's `CvPlayer::HasResourceForNewUnit` scanned every resource type for each
healing, production or upgrade eligibility query. Only positive requirements
or total-quantity rules enter the live checks. Each `CvUnitEntry` now builds an
ascending union of those resource IDs after both database sections are loaded.
The player function visits this list, retaining its original inner logic.

Current database evidence:57 resource types and215 unit types;135 units have no
positive rules,79 have one affected resource and one has two. This is not a
limit: arbitrary XML rules are included. Feature flags, player quantities,
shortages, upgrade refunds, Aluminum reserves, continuation and tooltip text
remain live and retain their original order. No player eligibility results
are cached.

Construction starts with unavailable derived metadata. Every `CacheResults`
attempt invalidates the list first, including failed/repeated loads. Successful
loading rebuilds it using the current getters without changing the existing
totals-map reload behavior. Incomplete metadata or a changed resource count
uses the original full scan. Future writers to the private quantity fields
must also invalidate/rebuild this derived list. No new save fields are added.

The production fixture passes577,586 checks using x86 VC9. It compiles complete
old/new player functions, unchanged quantity getters, the new builder/accessor
and actual resource-related loading sections. Source-delta guards bind all
three current files. Return values, live callback/getter order, resulting state
and complete tooltip bytes match across flag, upgrade, shortage, minor-player,
default/failure/reload and resource-count cases. Unrelated database-loading and
localization services are deterministic substitutes; this is not a whole-engine
proof. Fixture work fell from503,320 visited metadata rows to34,868. Native
speed and gameplay comparisons remain necessary.

To reproduce: run `work/prepare-sparse-unit-resources.py`, then
`work/test-sparse-unit-resources.py --production`. Stage files are generated
under ignored `work/sparse-unit-resources-staged`; production files are only
read by these helpers.
