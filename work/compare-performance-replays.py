"""Compare retained same-save decisions, capture scheduling and paused census.

Reads archived inputs only; --output explicitly writes the derived JSON result.
The existing PLAN/COMBAT_SUMMARY/CITY_CAPTURE and census comparisons retain their
selection and ordering. Early city opportunities/capture execution are compared
separately and together so a timing optimization cannot silently remove their
actions while preserving a final city/unit census.
"""
from pathlib import Path
import argparse
from collections import Counter
import importlib.util
import json
import re

spec = importlib.util.spec_from_file_location('diag', Path(__file__).with_name('summarize-stacking-diagnostics.py'))
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

DECISION_CATEGORIES = ('PLAN', 'COMBAT_SUMMARY', 'CITY_CAPTURE')
IMMEDIATE_CATEGORIES = ('IMMEDIATE_CITY',)
CAPTURE_CATEGORIES = ('CAPTURE_ORDER', 'CAPTURE_RESULT', 'CAPTURE_FALLBACK')
SEMANTIC_CATEGORIES = IMMEDIATE_CATEGORIES + CAPTURE_CATEGORIES
# DLL45's adjacent fallback shares CAPTURE_ORDER/RESULT with reserved captures;
# it has no dedicated CAPTURE_FALLBACK emitter. Recognize that name if a later
# branch adds it, and expose explicit zero counts instead of assuming coverage.


def read(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'replay-manifest.json').read_text(encoding='utf-8-sig'))
    run = manifest['NativeRun']
    segments, rows, semantic = {}, [], []
    for path in (folder / 'native-segments').glob('*.log'):
        lines = path.read_text(encoding='utf-8-sig').splitlines()
        match = diag.SESSION.fullmatch(lines[0]) if lines else None
        if match:
            header = diag.fields(match[1])
            number = header.get('segment')
            if header.get('run') == run and (number not in segments or len(lines) > len(segments[number])):
                segments[number] = lines
    for _, lines in sorted(segments.items()):
        for line in lines[1:]:
            match = diag.RECORD.fullmatch(line)
            if match and match[4] in DECISION_CATEGORIES + SEMANTIC_CATEGORIES:
                record = (int(match[2]), int(match[3]), match[4], re.sub(r' milliseconds=\d+', '', match[5]))
                if match[4] in DECISION_CATEGORIES:
                    rows.append(record)
                else:
                    semantic.append(record)
    census = []
    for line in (folder / 'Lua-end.log').read_text(encoding='utf-8-sig').splitlines():
        match = re.search(r'InGame: (PERF_UNIT|PERF_CITY)\s+(.*)', line)
        if match:
            census.append((match[1], tuple(int(number) for number in match[2].split())))
    return manifest, rows, sorted(census), semantic


def first_difference(baseline, cached):
    for index in range(max(len(baseline), len(cached))):
        before = baseline[index] if index < len(baseline) else None
        after = cached[index] if index < len(cached) else None
        if before != after:
            return dict(index=index, baseline=before, cached=after)
    return None


def semantic_comparison(baseline, cached, categories):
    before = [row for row in baseline if row[2] in categories]
    after = [row for row in cached if row[2] in categories]
    counts_before, counts_after = Counter(row[2] for row in before), Counter(row[2] for row in after)
    return dict(categories=list(categories), record_counts=[len(before), len(after)],
                category_counts=[{key: counts_before[key] for key in categories},
                                 {key: counts_after[key] for key in categories}],
                sequence_equal=before == after, first_difference=first_difference(before, after))


def compare(baseline, cached):
    b, br, bc, bs = read(baseline)
    c, cr, cc, cs = read(cached)
    immediate = semantic_comparison(bs, cs, IMMEDIATE_CATEGORIES)
    capture = semantic_comparison(bs, cs, CAPTURE_CATEGORIES)
    combined = semantic_comparison(bs, cs, SEMANTIC_CATEGORIES)
    return dict(baseline=b['NativeRun'], cached=c['NativeRun'], record_counts=[len(br), len(cr)],
                census_counts=[len(bc), len(cc)], planner_and_combat_sequence_equal=br == cr,
                paused_unit_city_census_equal=bc == cc, first_record_difference=first_difference(br, cr),
                baseline_only_census=list(set(bc) - set(cc))[:10], cached_only_census=list(set(cc) - set(bc))[:10],
                immediate_city_semantics=immediate, capture_execution_semantics=capture,
                city_action_semantics=combined,
                all_compared_semantics_equal=br == cr and bc == cc and combined['sequence_equal'],
                limits='Retained Summary decisions, early-city/capture execution markers and exact paused census only; '
                       'no verbose assignment trace or proof for other game states. Empty semantic categories do not '
                       'establish branch coverage. Turn275 is resumed/partial;277 switches to human.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('cached', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.baseline, args.cached)
    data = json.dumps(result, indent=2)
    args.output.write_text(data)
    print(data)


if __name__ == '__main__':
    main()
