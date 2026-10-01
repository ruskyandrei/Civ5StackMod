# Reusing immediate key-loan validation

The danger and defender forecast wrappers now reuse the successful validation
already performed by their immediately preceding shared-key loan constructor.
Only clearing a vector of integers occurs between that validation and the
wrapper's decision. The change is two Boolean expressions; it adds no token,
result table, capacity or numerical calculation.

Private, busy, nested, foreign and unsupported paths still perform the original
full validation. The final check after key construction remains: obtaining
projected danger sources can rebuild danger and change the scene. Post-compute
admission and all callback safeguards also remain.

The production-bound fixture passes11,547 checks using complete current
wrapper/cache and strength-provider code plus original combat-math functions.
It covers actual missing-provider, lock/event/AIR/interceptor rejection and
an epoch change after borrowing. A supported scalar hit goes from five full
Context checks to four; a defender hit goes from four to three. This is a
work-count result. Native turn-time benefit has not yet been measured.

Reproduction: work/stage-immediate-forecast-borrow.py and
work/test-immediate-forecast-borrow.py --production.
