"""Verify existing VC9 listings for cold formatting; no compilation/game calls."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/cold-assertion-formatting-regression'
PROC = re.compile(r'^([^\r\n]*?\bPROC[^\r\n]*)\r?\n([\s\S]*?)^[^\r\n]*?\bENDP[^\r\n]*$', re.M)
INSTRUCTION = re.compile(r'^\s*([0-9a-f]{5,8})\s+((?:[0-9a-f]{2}\s+)+)([a-z][^\r\n]*)$', re.I | re.M)


def functions(path):
    result = {}
    for match in PROC.finditer(path.read_text(errors='replace')):
        title, body = match.groups()
        name = title.split()[0]
        handler = re.search(r'^__ehhandler\$[^\n]+:', body, re.M)
        primary = body[:handler.start()] if handler else body
        instructions = list(INSTRUCTION.finditer(primary))
        extent = max((int(m.group(1), 16) + len(m.group(2).split()) for m in instructions), default=0)
        result[name] = dict(symbol=title, primaryCodeExtent=extent,
            successfulPathCookieCalls=len(re.findall(r'\bcall\s+@__security_check_cookie', primary)),
            cookieSetup='___security_cookie' in primary,
            exceptionFrame='push\t __ehhandler$' in primary or 'push\t__ehhandler$' in primary,
            firstInstructions=[m.group(3).strip() for m in instructions[:12]])
    return result


old = functions(OUT / 'release/old.cod')
new = functions(OUT / 'release/new.cod')
patterns = ('?getDamage@CvUnit@', '?GetMaxHitPoints@CvUnit@',
            '?GetCurrHitPoints@CvUnit@', '?getDomainType@CvUnit@',
            '?plot@CvUnit@', '?getPlayer@CvPlayerAI@')
names = []
for pattern in patterns:
    hits = [name for name in old if name.startswith(pattern)]
    assert len(hits) == 1, pattern
    names.extend(hits)
maps = [name for name in old if name.startswith('?checkValidAccess@?$CvEnumMap@') and 'CvPlayerAI' in name]
assert len(maps) == 1
names.extend(maps)
comparisons = []
for name in names:
    assert name in new
    left, right = old[name], new[name]
    assert left['successfulPathCookieCalls'] > 0 and left['cookieSetup'] and left['exceptionFrame'], name
    assert right['successfulPathCookieCalls'] == 0 and not right['cookieSetup'] and not right['exceptionFrame'], name
    comparisons.append(dict(symbol=name, old=left, new=right))
helpers = [value for name, value in new.items() if name.startswith(('?CvAssertFailedFormat@', '?CvPreconditionFailedFormat@'))]
assert len(helpers) == 4
assert all(value['cookieSetup'] and value['exceptionFrame'] for value in helpers)
formatters = [value for name, value in new.items() if name.startswith('?formatv@CvString@')]
assert formatters and any(value['cookieSetup'] for value in formatters)
result = json.loads((OUT / 'result.json').read_text())
report = dict(control=result['control'], numericChecks=result['total_checks'],
    checkedFunctions=len(comparisons), comparisons=comparisons,
    coldHelpersProtected=helpers, actualStringFormatters=formatters,
    compiler='VC9 x86 /O2 /EHsc /GS; same controls, fake recording failure handlers',
    sourceProof='source-proof.json',
    limitations='Actual getter/map/macro/string bodies against explicit engine services. These sizes describe the isolated fixture, not a full-game DLL. /GS remains enabled. No native timing or speedup extrapolation.')
with (OUT / 'assembly-proof.json').open('x', encoding='utf-8') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps(dict(numericChecks=report['numericChecks'], checkedFunctions=report['checkedFunctions'],
    coldHelpersProtected=len(helpers), getterCodeBytes=[dict(symbol=c['symbol'],old=c['old']['primaryCodeExtent'],new=c['new']['primaryCodeExtent']) for c in comparisons]), indent=2))
