"""Stage checked failure formatting outside hot legacy accessors; no core edits."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CONTROL = 'ef274591d0f4f32e193959524faf953cf964bd86'
OUT = ROOT / 'work/cold-assertion-formatting-staged'
FILES = ('CvGameCoreDLLUtil/include/CvAssert.h',
         'CvGameCoreDLL_Expansion2/CvGameCoreDLLPCH.h',
         'CvGameCoreDLL_Expansion2/CvGameCoreUtils.cpp')

DECLARATIONS = '''
// Failure-only formatting stays out of successful checked accessor frames.
// The per-callsite ignore flag and expression evaluation remain in ASSERT.
void CvAssertFailedFormat(const char* expr, const char* file, unsigned int line, bool& ignore);
void CvAssertFailedFormat(const char* expr, const char* file, unsigned int line, bool& ignore, const char* format, ...);
#if defined(_MSC_VER)
#define CV_PRECONDITION_NORETURN __declspec(noreturn)
#elif defined(__clang__)
#define CV_PRECONDITION_NORETURN __attribute__((noreturn))
#else
#define CV_PRECONDITION_NORETURN
#endif
CV_PRECONDITION_NORETURN void CvPreconditionFailedFormat(const char* expr, const char* file, unsigned int line);
CV_PRECONDITION_NORETURN void CvPreconditionFailedFormat(const char* expr, const char* file, unsigned int line, const char* format, ...);
#undef CV_PRECONDITION_NORETURN
'''

HELPERS = '''
// Cold failure paths retain the message through the original handler/break or
// fatal trap. Keep /GS on these helpers; successful callers hold no CvString.
#if defined(_MSC_VER)
#define CV_FAILURE_NOINLINE __declspec(noinline)
#elif defined(__clang__)
#define CV_FAILURE_NOINLINE __attribute__((noinline))
#else
#define CV_FAILURE_NOINLINE
#endif

#ifdef CVASSERT_ENABLE
CV_FAILURE_NOINLINE void CvAssertFailedFormat(const char* expr, const char* file, unsigned int line, bool& ignore)
{
    CvString message;
    // A no-message ASSERT formerly called format(message) through CvString's
    // implicit const char* conversion, producing a discarded empty result.
    CvString::format(message);
    if (CvAssertDlg(expr, file, line, ignore, message.c_str()))
        { CVASSERT_BREAKPOINT; }
}
CV_FAILURE_NOINLINE void CvAssertFailedFormat(const char* expr, const char* file, unsigned int line, bool& ignore, const char* format, ...)
{
    CvString message;
    va_list args;
    va_start(args, format);
    CvString::formatv(message, format, args);
    va_end(args);
    if (CvAssertDlg(expr, file, line, ignore, message.c_str()))
        { CVASSERT_BREAKPOINT; }
}
#endif

CV_FAILURE_NOINLINE void CvPreconditionFailedFormat(const char* expr, const char* file, unsigned int line)
{
    CvString message;
    CvString::format(message);
    CvPreconditionDlg(expr, file, line, message.c_str());
    BUILTIN_TRAP();
}
CV_FAILURE_NOINLINE void CvPreconditionFailedFormat(const char* expr, const char* file, unsigned int line, const char* format, ...)
{
    CvString message;
    va_list args;
    va_start(args, format);
    CvString::formatv(message, format, args);
    va_end(args);
    CvPreconditionDlg(expr, file, line, message.c_str());
    BUILTIN_TRAP();
}
#undef CV_FAILURE_NOINLINE
'''


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def read_control(name):
    return subprocess.check_output(['git', 'show', CONTROL + ':' + name], cwd=ROOT).decode('utf-8-sig').replace('\r\n', '\n')


def transform(original):
    result = dict(original)
    assert_header = original[FILES[0]]
    anchor = 'bool CvAssertDlg(const char* expr, const char* szFile, unsigned int uiLine, bool& bIgnoreAlways, const char* msg);\n'
    assert assert_header.count(anchor) == 1
    assert_header = assert_header.replace(anchor, anchor + DECLARATIONS, 1)
    start = assert_header.index('\t\tCvString str;')
    end = assert_header.index('\n\t}', start)
    old_failure = assert_header[start:end]
    assert 'CvString::format(str, __VA_ARGS__);' in old_failure
    assert 'if(CvAssertDlg(#expr, __FILE__, __LINE__, bIgnoreAlways, str.c_str()))' in old_failure
    assert_header = assert_header[:start] + '\t\tCvAssertFailedFormat(#expr, __FILE__, __LINE__, bIgnoreAlways, __VA_ARGS__);\\' + assert_header[end:]
    result[FILES[0]] = assert_header
    old_precondition = '#define PRECONDITION(expr, ...) if (!(expr)) {CvString str; CvString::format(str, __VA_ARGS__); CvPreconditionDlg(#expr, __FILE__, __LINE__, str.c_str()); BUILTIN_TRAP();}'
    new_precondition = '#define PRECONDITION(expr, ...) if (!(expr)) {CvPreconditionFailedFormat(#expr, __FILE__, __LINE__, __VA_ARGS__);}'
    assert original[FILES[1]].count(old_precondition) == 1
    result[FILES[1]] = original[FILES[1]].replace(old_precondition, new_precondition, 1)
    anchor = '\nint RING_PLOTS[6] = '
    assert original[FILES[2]].count(anchor) == 1
    result[FILES[2]] = original[FILES[2]].replace(anchor, '\n' + HELPERS + anchor, 1)
    assert result[FILES[0]].replace(DECLARATIONS, '', 1).replace('\t\tCvAssertFailedFormat(#expr, __FILE__, __LINE__, bIgnoreAlways, __VA_ARGS__);\\', old_failure, 1) == original[FILES[0]]
    assert result[FILES[1]].replace(new_precondition, old_precondition, 1) == original[FILES[1]]
    assert result[FILES[2]].replace('\n' + HELPERS, '', 1) == original[FILES[2]]
    return result


def main():
    original = {name: read_control(name) for name in FILES}
    for name in FILES:
        assert (ROOT / name).read_text(encoding='utf-8-sig') == original[name], 'Current control drift: ' + name
    candidate = transform(original)
    OUT.mkdir(exist_ok=True)
    patch = []
    for name in FILES:
        target = OUT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(candidate[name], encoding='utf-8')
        patch.extend(difflib.unified_diff(original[name].splitlines(True), candidate[name].splitlines(True), 'a/' + name, 'b/' + name))
    (OUT / 'cold-format.patch').write_text(''.join(patch), encoding='utf-8')
    (OUT / 'manifest.json').write_text(json.dumps(dict(control=CONTROL,
        original_sha256={n: sha(s) for n, s in original.items()},
        candidate_sha256={n: sha(s) for n, s in candidate.items()},
        production_untouched=True, original_bodies_reversible=True,
        assertions_enabled_unchanged=True, global_buffer_security_unchanged=True,
        save_math_search_unchanged=True), indent=2) + '\n')
    print('Three-file cold-failure stage prepared; production untouched; no compile or game calls.')


if __name__ == '__main__':
    main()
