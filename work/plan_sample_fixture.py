"""Remove only marked diagnostic probes from standalone gameplay fixtures.

test-plan-sampled-timing.py independently compiles those probes and proves that
reverse-stripping every addition restores the pinned DLL58 production sources.
Gameplay/AI fixtures should continue compiling their complete original bodies;
they do not need to mock this diagnostic layer's TLS/session/clock services.
"""
def without_plan_sample_probes(text):
    return ''.join(line for line in text.splitlines(keepends=True)
                   if 'PLAN_SAMPLE_DIAGNOSTIC_ONLY' not in line)
