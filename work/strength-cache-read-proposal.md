# Strength cache acquire-read proposal (research only)

2026-09-30. Production files, game state, compiler flags and entry limits were not changed for this experiment.

Subsequent approval: root authorized the narrow production edit after reviewing this experiment. `CvStackingStrengthCache.cpp` now has the proposed aligned globals and guarded read. The updated isolated fixture tests actual production without transforming its read helper; separate control/fallback/Intel-guard variants and artifacts are under `work/strength-cache-read-production`. All five variants passed after the native-control CPU hold was released; details follow below.

## Proposed change and its boundary

The current strength-cache `Read(volatile LONG&)` uses `InterlockedCompareExchange(&value, 0, 0)`. A successful public-wrapper cache hit calls `Context` and then `Lookup`'s `Context`, so it normally performs four owner/epoch read-modify-write operations. The genuine Visual C++ 2008 x86 build can instead use the Microsoft extension's acquire read, `return value`, while preserving every existing owner, epoch, depth and generation check and every existing Interlocked write.

Use a narrow genuine VC9/x86 compiler guard (`_MSC_VER == 1500`, `_M_IX86`, excluding Clang and Intel compatibility compilers), explicit `__declspec(align(4))` owner/epoch globals, and the original Interlocked implementation for every other compiler/architecture. No compiler-flag change is proposed. This is not a portable ISO C++ volatile implementation.

The proposed production spelling is:

```cpp
__declspec(align(4)) volatile LONG owner = 0;
__declspec(align(4)) volatile LONG epoch = 0;
LONG Read(volatile LONG& value)
{
#if defined(_MSC_VER) && _MSC_VER == 1500 && defined(_M_IX86) && \
    !defined(__clang__) && !defined(__INTEL_COMPILER) && !defined(__ICL)
    return value;
#else
    return InterlockedCompareExchange(&value, 0, 0);
#endif
}
```

The isolated fixture has the VC9/x86/Clang guard and a test-only forced-fallback guard. The additional Intel exclusions above are inactive for the verified genuine compiler and protect compatibility configurations that were not tested. No claim is made for alternative compilers' plain volatile semantics.

## Primary documentation

Microsoft's historical article explicitly describes acquire reads/release writes from Visual Studio 2005 onward, including replacing a compare-exchange acquire-read with a volatile read under `_MSC_VER >= 1400`. The example establishes applicability to VC9 rather than relying solely on current compiler documentation. [Visual Studio 2005 gives you acquire and release semantics for free on volatile memory access](https://devblogs.microsoft.com/oldnewthing/20110419-00/?p=10893).

Windows documents that properly aligned 32-bit simple reads/writes are atomic; ordering requires additional guarantees. Interlocked operations ordinarily supply a full memory barrier. [Interlocked Variable Access](https://learn.microsoft.com/en-us/windows/win32/sync/interlocked-variable-access).

Microsoft also documents the VS2005-era volatile acquire/release extension and its ordering purpose. [Synchronization and Multiprocessor Issues](https://learn.microsoft.com/en-us/windows/win32/sync/synchronization-and-multiprocessor-issues).

The modern Microsoft-specific volatile description states that references following an acquire read remain after it, and preceding references remain before a release write. `/volatile:iso` does not provide these guarantees; the non-ARM default is Microsoft semantics. These modern pages corroborate the historical source; they do not justify changing flags on VC9. [volatile (C++)](https://learn.microsoft.com/en-us/cpp/cpp/volatile-cpp?view=msvc-170), [/volatile](https://learn.microsoft.com/en-us/cpp/build/reference/volatile-volatile-keyword-interpretation?view=msvc-170).

## Local toolchain evidence

The inspected native response file was `work/msvc-build/Release/20260930-214752/compile.rsp`: `/Ox`, `/MD`, `/EHsc`, `/Gd`, and the existing Win32/final-release defines. It contains no `/volatile:iso` or `/Zp` override. The link response targets `/MACHINE:X86`.

The actual-module isolated build reported `_MSC_VER=1500`, `_M_IX86=600`, 4-byte pointers, 4-byte LONGs, and 4-byte-aligned owner/epoch addresses. Its separately inspectable optimized `InspectRead` assembly is:

```asm
; Acquire prototype:
mov eax, DWORD PTR _value$[esp-4]
mov eax, DWORD PTR [eax]
ret 0

; Unchanged control and forced fallback:
mov eax, DWORD PTR _value$[esp-4]
push 0
push 0
push eax
call DWORD PTR __imp__InterlockedCompareExchange@12
ret 0
```

The control is an imported Win32 API call in this build, not an inline `lock cmpxchg` instruction. Both remain read-modify-write operations semantically.

## Protocol argument

This is a code-audit inference using Microsoft's compiler guarantees:

- Ownership is still claimed with `InterlockedCompareExchange` and released with `InterlockedExchange` after table/order destruction. Acquire owner reads precede all ordinary owner-only state reads; a foreign thread still exits before accessing the map.
- Epoch changes still use `InterlockedIncrement`. Acquire epoch reads precede cache access. Existing generation rechecks after key construction and before admission remain intact.
- Nested scopes still increase depth and invalidate on entry/exit; they cannot use the outer table at depth other than one.
- All clearing, lookup, admission, FIFO eviction and statistics access remain confined to the owner. No table access becomes concurrent.
- The read helper does not publish previously written table data. Removing its unused release/full-fence component does not replace the ownership release, atomic claim, or engine GameCore lock.
- The epoch remains an invalidation mechanism, not an independent lock for publishing arbitrary game-world mutations. Existing scene assumptions, mutation hooks and unlock/relock invalidations remain necessary.

A concurrent epoch increment occurring just after the final read is possible with either implementation. This proposal does not broaden the existing scene/lock protocol or remove any recheck. Finite stress tests below are supporting evidence, not proof of every interleaving.

## Actual-module fixture and measurements

`work/test-strength-cache-read-prototype.py` compiles the current cache source into three isolated variants under `work/strength-cache-read-prototype`: unchanged control, guarded acquire-read prototype, and a test-forced fallback. The prototype changes only the read helper and owner/epoch alignment in its generated source; no production source is written. It uses genuine VC9/x86 with real Win32 Interlocked APIs, threads and events.

All variants passed owner/foreign access, nested scopes, epoch invalidation, all 22 key words, FIFO bounds, completed foreign invalidation, 100,000 concurrent foreign queries/periodic invalidations, and a 20,000-publication acquire-read payload handshake. Check counts vary with benign concurrent misses:

| Variant | Checks | Failures | Median of five 1M-query samples |
| --- | ---: | ---: | ---: |
| Unchanged control | 118,272 | 0 | 41.448 ms |
| Acquire prototype | 118,126 | 0 | 32.573 ms |
| Forced fallback | 118,144 | 0 | 42.198 ms |

The candidate/control median ratio is 0.78588, a 21.4% reduction in this isolated prebuilt-key `Context` + `Lookup` hit loop. This is not a measured whole-game improvement: key construction, strength misses, scene checks outside this module, search, rendering and engine work are excluded. Runs are short and sequential; system noise can affect timings. The matching fallback is useful evidence that the change is in the read path.

Raw source module SHA256: `83f055674f422b7eb97b5d25612fb8e84a45ed434cd6f6afca1aa578cccb123f`. Full timing, compiler output and assembly artifacts are in `work/strength-cache-read-prototype/result.json` and the sibling files.

The subsequent actual-production regression retained the original prototype artifacts and used `work/strength-cache-read-production/result.json`. The original-control variant restores only the old read helper; forced fallback disables only the actual guard; Intel and ICL variants independently define each compatibility macro around the unchanged actual read. SDK/STL headers are not parsed under fake compiler macros. Every variant passed automated assembly checks (MOV for production, imported InterlockedCompareExchange for all fallback cases), and the test asserted that it never changed production source.

| Actual-production variant | Checks | Failures | Median of five 1M-query samples |
| --- | ---: | ---: | ---: |
| Original-read control | 118,112 | 0 | 41.567 ms |
| Actual production acquire | 118,241 | 0 | 32.579 ms |
| Actual guard forced off | 118,102 | 0 | 42.304 ms |
| `__INTEL_COMPILER` fallback | 118,163 | 0 | 42.493 ms |
| `__ICL` fallback | 118,079 | 0 | 41.953 ms |

The actual-production ratio was 0.78377, again an isolated result. Existing actual-source strength regression passed 96,078 checks and the whole original-body melee-strength regression passed 140,042 checks, both with zero failures. The normalized-text source module SHA256 for this approved version is `b36d5d56112dbb1821f4996c234459d4cfa60c6a4fdd308bba29d00802e4b48c`.

## Suggested next validation

If root elects to implement the narrow guarded read, rerun the existing actual-source cache/whole-strength/virtual-stack regressions, this thread fixture against the production implementation, and the identical preserved manual T251→253 native replay. Require the current semantic sequence and nonempty unit/city census comparisons to match. Compare interior T252 full time and PLAN time separately, retaining all existing owner/epoch guards. Do not increase entry budgets or conflate this change with additional key canonicalization.
