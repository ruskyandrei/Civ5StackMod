# Independent packet miss-outline review

Read-only review of DLL94 baseline3601cc10c and staged candidate
`b0975783336b020a92d856d1da46e28907ed5e176277316b188f28da7afd6e0a`.
Manifest reverses the complete source; original numerical miss tail
`e8cca5942fa6b269b4f69101c3f90b31da270522fb5f85165bc7a9c6aac265c9`
is byte-identical. Actual-source fixture reports23,557/0 with explicit engine
substitutes; reviewer ran no tests or compiler.

No concrete blocker. Query, referenced key, keySample and miss counter stay in
the caller. The original owned scratch loan therefore survives all helper work
and callbacks. Arguments are copies of immutable locals or const references to
the same original objects; there is no new getter evaluation or ordering.
Miss count still increments before PacketProbe construction. The helper keeps
the original leafSample/packetQuery/packetProbe construction and explicit Finish
order. Normal and exception cleanup is leafSample→packetQuery→packetProbe,
then caller keySample→query, matching the old combined scope. No table Slot
reference or payload pointer escapes a clearing Context call. Query-key object
lifetime and existing invalidation/admission checks are unchanged.

Assembly evidence: optimized native94 caller reserves2,272 bytes; fixture
baseline reserves2,208, candidate caller36 and noinline miss helper2,180.
Baseline/helper retain cookie setup and EH; the smaller caller naturally has
no cookie setup. /GS compilation is retained. The reader's
`gs_cookie_check=false` does not prove a missing runtime check: it means the
direct check symbol was not recognized, while EH epilog machinery can perform
the check. Stack trace/return PC and measured instruction time can differ;
these are representation effects, not a native speed result.
