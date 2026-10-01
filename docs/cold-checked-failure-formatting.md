# Checked failure formatting outside successful accessor frames

DLL87 moves assertion and precondition message formatting into out-of-line
failure helpers. It retains the checked expressions, per-callsite ignore flags,
original diagnostic expression/file/line, formatting, dialog, break/trap and
global `/GS` setting. No AI limits, numerical calculations or game data change.

The old failure branch creates a local `CvString` inside many otherwise tiny
checked getters. VC9 consequently generates exception-handling and stack-cookie
frames even on successful reads. The new helpers own the string only after a
check fails. Actual VC9 disassembly confirms seven tested getter/map functions
lose those successful frames; the cold helpers and formatter remain protected.
This is a broad legacy overhead candidate, not proof of a native speed gain.

The production-bound fixture passed 192,028 checks in release, debug, explicitly
disabled-assert and quiet release configurations. It uses the actual formatter,
EnumMap header and selected getter bodies, with explicit player/map services and
recording dialog/break/trap substitutes. Successful values, failed-check metadata,
argument evaluation, static ignore handling and recorded break/trap outcomes
match. These tests cannot establish game performance or exhaustive engine safety.

Failure-side behavior has two documented diagnostic differences. The breakpoint
or fatal instruction now resides in a helper, adding a failure stack frame.
Formatting-argument temporaries remain alive through the handler instead of
being destroyed immediately after the original formatting statement. Audited
existing examples are plain `CvString`/`std::string` temporaries whose destruction
releases storage without gameplay callbacks. Arbitrary future user-defined
destructor timing is not claimed equivalent. The original reported caller
expression, file and line remain intact.

Reproducible tools in `work/` are `stage-cold-assertion-formatting.py`,
`apply-cold-assertion-formatting.py`, `test-cold-assertion-formatting.py` and
`analyze-cold-assertion-assembly.py`. The stage is pinned to DLL86 commit
`ef274591d0f4f32e193959524faf953cf964bd86`. It verifies complete original and
candidate files; application verifies every input before writing and preserves
BOM/newlines. Run the fixture with `--production` after application. Its engine
substitutes and failure-only lifetime limits are explicit.

The matched native replay result will be recorded in
`performance-progress-20260930.md`. Until that completes, benefit is unmeasured.
