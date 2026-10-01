"""Stack-scanning CPU sampler for the Civ V gamecore thread.

capture: suspend the thread, read EIP/ESP and the top of its stack, resume.
Nothing is called inside the game; the pause covers only the context read and
one ReadProcessMemory. Each sample stores GetTickCount (the clock used by the
native STACKDIAG log), the thread CPU delta and stack words that fall inside
the gamecore DLL.

report: validate stack words as return addresses (the preceding bytes in the
DLL image must be a call instruction), symbolize with DbgHelp using the
matching PDB, and print flat (self) and inclusive (on-stack) function shares.
Inclusive shares are approximate: stale return addresses left on the stack
can be counted. Use --start-tick/--end-tick to restrict the window.
"""
from __future__ import annotations
import argparse, collections, ctypes as C, json, os, struct, sys, time
from ctypes import wintypes as W
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILED = 0xFFFFFFFF


class FloatingSave(C.Structure):
    _fields_ = [(n, W.DWORD) for n in ('ControlWord', 'StatusWord', 'TagWord', 'ErrorOffset', 'ErrorSelector', 'DataOffset', 'DataSelector')] + \
        [('RegisterArea', W.BYTE * 80), ('Cr0NpxState', W.DWORD)]


class Context32(C.Structure):
    _fields_ = [('ContextFlags', W.DWORD)] + [(n, W.DWORD) for n in ('Dr0', 'Dr1', 'Dr2', 'Dr3', 'Dr6', 'Dr7')] + \
        [('FloatSave', FloatingSave)] + \
        [(n, W.DWORD) for n in ('SegGs', 'SegFs', 'SegEs', 'SegDs', 'Edi', 'Esi', 'Ebx', 'Edx', 'Ecx', 'Eax', 'Ebp', 'Eip', 'SegCs', 'EFlags', 'Esp', 'SegSs')] + \
        [('ExtendedRegisters', W.BYTE * 512)]


class Module32(C.Structure):
    _fields_ = [(n, W.DWORD) for n in ('dwSize', 'th32ModuleID', 'th32ProcessID', 'GlblcntUsage', 'ProccntUsage')] + \
        [('modBaseAddr', C.POINTER(W.BYTE)), ('modBaseSize', W.DWORD), ('hModule', W.HMODULE), ('szModule', W.WCHAR * 256), ('szExePath', W.WCHAR * 260)]


class Thread32(C.Structure):
    _fields_ = [(n, W.DWORD) for n in ('dwSize', 'cntUsage', 'th32ThreadID', 'th32OwnerProcessID')] + [('tpBasePri', W.LONG), ('tpDeltaPri', W.LONG), ('dwFlags', W.DWORD)]


def kernel():
    k = C.WinDLL('kernel32', use_last_error=True)
    sig = {
        'OpenProcess': (W.HANDLE, [W.DWORD, W.BOOL, W.DWORD]), 'OpenThread': (W.HANDLE, [W.DWORD, W.BOOL, W.DWORD]),
        'CloseHandle': (W.BOOL, [W.HANDLE]), 'GetThreadTimes': (W.BOOL, [W.HANDLE] + [C.POINTER(C.c_ulonglong)] * 4),
        'Wow64SuspendThread': (W.DWORD, [W.HANDLE]), 'ResumeThread': (W.DWORD, [W.HANDLE]),
        'Wow64GetThreadContext': (W.BOOL, [W.HANDLE, C.POINTER(Context32)]), 'GetTickCount': (W.DWORD, []),
        'CreateToolhelp32Snapshot': (W.HANDLE, [W.DWORD, W.DWORD]),
        'Module32FirstW': (W.BOOL, [W.HANDLE, C.POINTER(Module32)]), 'Module32NextW': (W.BOOL, [W.HANDLE, C.POINTER(Module32)]),
        'Thread32First': (W.BOOL, [W.HANDLE, C.POINTER(Thread32)]), 'Thread32Next': (W.BOOL, [W.HANDLE, C.POINTER(Thread32)]),
        'ReadProcessMemory': (W.BOOL, [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]),
        'WaitForSingleObject': (W.DWORD, [W.HANDLE, W.DWORD]),
        'QueryThreadCycleTime': (W.BOOL, [W.HANDLE, C.POINTER(C.c_ulonglong)]),
    }
    for name, (res, args) in sig.items():
        f = getattr(k, name); f.restype = res; f.argtypes = args
    return k


def thread_cycles(k, h):
    value = C.c_ulonglong()
    return value.value if k.QueryThreadCycleTime(h, C.byref(value)) else None


def thread_cpu(k, h):
    a, b, c, d = (C.c_ulonglong() for _ in range(4))
    if not k.GetThreadTimes(h, C.byref(a), C.byref(b), C.byref(c), C.byref(d)):
        return None
    return c.value + d.value


def find_module(k, pid, name):
    snap = k.CreateToolhelp32Snapshot(0x8 | 0x10, pid)
    entry = Module32(); entry.dwSize = C.sizeof(entry)
    try:
        ok = k.Module32FirstW(snap, C.byref(entry))
        while ok:
            if entry.szModule.lower() == name.lower():
                return C.cast(entry.modBaseAddr, C.c_void_p).value, int(entry.modBaseSize), entry.szExePath
            ok = k.Module32NextW(snap, C.byref(entry))
    finally:
        k.CloseHandle(snap)
    raise RuntimeError('module not loaded: ' + name)


def all_modules(k, pid):
    snap = k.CreateToolhelp32Snapshot(0x8 | 0x10, pid)
    entry = Module32(); entry.dwSize = C.sizeof(entry); out = []
    try:
        ok = k.Module32FirstW(snap, C.byref(entry))
        while ok:
            out.append((entry.szModule, C.cast(entry.modBaseAddr, C.c_void_p).value, int(entry.modBaseSize)))
            ok = k.Module32NextW(snap, C.byref(entry))
    finally:
        k.CloseHandle(snap)
    return out


def threads(k, pid):
    snap = k.CreateToolhelp32Snapshot(0x4, 0)
    entry = Thread32(); entry.dwSize = C.sizeof(entry); out = []
    try:
        ok = k.Thread32First(snap, C.byref(entry))
        while ok:
            if entry.th32OwnerProcessID == pid:
                out.append(entry.th32ThreadID)
            ok = k.Thread32Next(snap, C.byref(entry))
    finally:
        k.CloseHandle(snap)
    return out


def busiest_thread(k, pid, seconds=3.0):
    handles = {}
    for tid in threads(k, pid):
        h = k.OpenThread(0x0040 | 0x0800, False, tid)  # QUERY_INFORMATION | QUERY_LIMITED
        if h:
            handles[tid] = (h, thread_cpu(k, h) or 0)
    time.sleep(seconds)
    best = max(handles, key=lambda t: (thread_cpu(k, handles[t][0]) or 0) - handles[t][1])
    for h, _ in handles.values():
        k.CloseHandle(h)
    return best


def capture(args):
    k = kernel()
    base, size, path = find_module(k, args.pid, 'CvGameCore_Expansion2.dll')
    tid = args.thread or busiest_thread(k, args.pid)
    process = k.OpenProcess(0x0010 | 0x0400 | 0x00100000, False, args.pid)  # VM_READ | QUERY_INFORMATION | SYNCHRONIZE
    thread = k.OpenThread(0x0002 | 0x0008 | 0x0040, False, tid)  # SUSPEND_RESUME | GET_CONTEXT | QUERY_INFORMATION
    if not process or not thread:
        raise OSError(C.get_last_error(), 'OpenProcess/OpenThread')
    out = Path(args.output)
    meta = dict(pid=args.pid, thread=tid, deltaUnit='kilocycles', dllBase=base, dllSize=size, dllPath=path, hz=args.hz, stackBytes=args.stack_bytes,
                startedTick=k.GetTickCount(), modules=all_modules(k, args.pid))
    out.with_suffix('.meta.json').write_text(json.dumps(meta, indent=1))
    ctx = Context32(); ctx.ContextFlags = 0x10001  # CONTEXT_i386 | CONTEXT_CONTROL
    buf = C.create_string_buffer(args.stack_bytes); got = C.c_size_t()
    period = 1.0 / args.hz; deadline = time.time() + args.seconds
    last_cpu = thread_cycles(k, thread); n = 0; lo, hi = base, base + size
    stop_file = Path(args.stop_file) if args.stop_file else None
    with out.open('wb') as stream:
        next_time = time.perf_counter()
        while time.time() < deadline:
            if k.WaitForSingleObject(process, 0) == 0:
                break  # process exited
            if stop_file and stop_file.exists():
                break
            tick = k.GetTickCount()
            previous = k.Wow64SuspendThread(thread)
            eip = esp = 0; nread = 0
            if previous != FAILED:
                try:
                    if previous == 0 and k.Wow64GetThreadContext(thread, C.byref(ctx)):
                        eip, esp = ctx.Eip, ctx.Esp
                        if k.ReadProcessMemory(process, esp, buf, args.stack_bytes, C.byref(got)) or got.value:
                            nread = got.value
                        else:
                            # Near the stack base a full read can fail; retry smaller.
                            for size_try in (args.stack_bytes // 4, 4096, 1024):
                                if k.ReadProcessMemory(process, esp, buf, size_try, C.byref(got)):
                                    nread = got.value; break
                finally:
                    for _ in range(3):
                        if k.ResumeThread(thread) != FAILED:
                            break
            cpu = thread_cycles(k, thread)
            # Kilocycles since the previous sample (cycle counters are exact,
            # unlike the 15.6ms thread-time quantum).
            delta = (cpu - last_cpu) // 1000 if (cpu is not None and last_cpu is not None) else -1
            last_cpu = cpu
            words = memoryview(buf.raw[:nread - nread % 4]).cast('I') if nread else []
            frames = [w for w in words if lo <= w < hi]
            stream.write(struct.pack('<IIiH', tick, eip, max(-1, min(delta, 0x7FFFFFFF)), len(frames)))
            if frames:
                stream.write(struct.pack('<%dI' % len(frames), *frames))
            n += 1
            next_time += period
            sleep = next_time - time.perf_counter()
            if sleep > 0:
                time.sleep(sleep)
            else:
                next_time = time.perf_counter()
    meta.update(samples=n, endedTick=k.GetTickCount())
    out.with_suffix('.meta.json').write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta))


def read_samples(path):
    data = Path(path).read_bytes(); i = 0; rows = []
    while i + 14 <= len(data):
        tick, eip, delta, count = struct.unpack_from('<IIiH', data, i); i += 14
        if i + 4 * count > len(data):
            break  # partial record from a file still being written
        frames = struct.unpack_from('<%dI' % count, data, i) if count else (); i += 4 * count
        rows.append((tick, eip, delta, frames))
    return rows


class SymbolInfo(C.Structure):
    _fields_ = [('SizeOfStruct', W.ULONG), ('TypeIndex', W.ULONG), ('Reserved', C.c_ulonglong * 2), ('Index', W.ULONG), ('Size', W.ULONG),
                ('ModBase', C.c_ulonglong), ('Flags', W.ULONG), ('Value', C.c_ulonglong), ('Address', C.c_ulonglong), ('Register', W.ULONG),
                ('Scope', W.ULONG), ('Tag', W.ULONG), ('NameLen', W.ULONG), ('MaxNameLen', W.ULONG), ('Name', C.c_char * 1)]


class Symbols:
    def __init__(self, dll, pdb, base, size):
        k = C.WinDLL('kernel32'); k.GetCurrentProcess.restype = W.HANDLE
        self.h = k.GetCurrentProcess()
        self.d = C.WinDLL('dbghelp', use_last_error=True)
        self.d.SymSetOptions.argtypes = [W.DWORD]
        self.d.SymInitializeW.argtypes = [W.HANDLE, W.LPCWSTR, W.BOOL]
        self.d.SymLoadModuleExW.restype = C.c_ulonglong
        self.d.SymLoadModuleExW.argtypes = [W.HANDLE, W.HANDLE, W.LPCWSTR, W.LPCWSTR, C.c_ulonglong, W.DWORD, C.c_void_p, W.DWORD]
        self.d.SymFromAddr.argtypes = [W.HANDLE, C.c_ulonglong, C.POINTER(C.c_ulonglong), C.POINTER(SymbolInfo)]
        self.d.SymSetOptions(0x2 | 0x4 | 0x10 | 0x400 | 0x80000 | 0x200000)
        if not self.d.SymInitializeW(self.h, str(Path(pdb).resolve().parent), False):
            raise OSError(C.get_last_error(), 'SymInitializeW')
        if self.d.SymLoadModuleExW(self.h, None, str(Path(dll).resolve()), None, base, size, None, 0) != base:
            raise OSError(C.get_last_error(), 'SymLoadModuleExW')
        self.cache = {}

    def __call__(self, address):
        if address in self.cache:
            return self.cache[address]
        b = C.create_string_buffer(C.sizeof(SymbolInfo) + 1024); info = C.cast(b, C.POINTER(SymbolInfo))
        info.contents.SizeOfStruct = C.sizeof(SymbolInfo); info.contents.MaxNameLen = 1024; disp = C.c_ulonglong()
        if self.d.SymFromAddr(self.h, address, C.byref(disp), info):
            name = C.string_at(C.addressof(info.contents) + SymbolInfo.Name.offset, info.contents.NameLen).decode('utf-8', 'replace')
            result = (name, info.contents.Address)
        else:
            result = ('?%08X' % address, address)
        self.cache[address] = result
        return result


def text_section(image):
    pe = struct.unpack_from('<I', image, 60)[0]; count = struct.unpack_from('<H', image, pe + 6)[0]
    opt_size = struct.unpack_from('<H', image, pe + 20)[0]; sections = []
    for i in range(count):
        o = pe + 24 + opt_size + i * 40
        name = image[o:o + 8].rstrip(b'\0'); vsize, va, rsize, raw = struct.unpack_from('<4I', image, o + 8)
        characteristics = struct.unpack_from('<I', image, o + 36)[0]
        sections.append((name, va, vsize, raw, rsize, characteristics))
    return sections


def file_offset(rva, sections):
    for name, va, vsize, raw, rsize, ch in sections:
        if va <= rva < va + min(vsize, rsize) and ch & 0x20000000:  # executable
            return raw + rva - va
    return None


def call_site(rva, sections, image):
    """None if no call precedes rva; ('direct', target_rva) or ('indirect', None)."""
    off = file_offset(rva, sections)
    if off is None or off < 7:
        return None
    b = image
    if b[off - 5] == 0xE8:
        return ('direct', (rva + struct.unpack_from('<i', b, off - 4)[0]) & 0xFFFFFFFF)
    modrm_checks = ((2, lambda m: m >> 6 == 3), (3, lambda m: m >> 6 == 1 and m & 7 != 4), (6, lambda m: m >> 6 == 2 and m & 7 != 4 or (m >> 6 == 0 and m & 7 == 5)),
                    (4, lambda m: m >> 6 == 1 and m & 7 == 4), (7, lambda m: m >> 6 == 2 and m & 7 == 4), (3, lambda m: m >> 6 == 0 and m & 7 == 4),
                    (2, lambda m: m >> 6 == 0 and m & 7 not in (4, 5)))
    for back, test in modrm_checks:
        m = b[off - back + 1]
        if b[off - back] == 0xFF and (m >> 3) & 7 == 2 and test(m):
            return ('indirect', None)
    return None


def is_return_address(rva, sections, image):
    return call_site(rva, sections, image) is not None


def walk(eip, frames, base, size, sections, image, sym, cache):
    """Leaf first. Direct calls must target the function we are currently in."""
    inside = base <= eip < base + size
    chain = [sym(eip)[0] if inside else '<outside gamecore>']
    current = sym(eip)[1] - base if inside else None
    for w in frames:
        site = cache.get(w)
        if site is None:
            site = cache[w] = call_site(w - base, sections, image) or False
        if not site:
            continue
        kind, target = site
        if kind == 'direct' and (current is None or target != current):
            continue  # stale, or (outside gamecore) not the import call into the CRT/OS
        if kind == 'indirect' and current is not None:
            continue  # unverifiable mid-chain; virtual calls are rare in this code
        name, start = sym(w)
        chain.append(name); current = start - base
    return chain


def module_of(address, modules):
    for name, start, length in modules:
        if start <= address < start + length:
            return name
    return 'unknown'


def report(args):
    meta = json.loads(Path(args.samples).with_suffix('.meta.json').read_text())
    base, size = meta['dllBase'], meta['dllSize']
    image = Path(args.dll).read_bytes(); sections = text_section(image)
    sym = Symbols(args.dll, args.pdb, base, size)
    rows = read_samples(args.samples)
    if args.start_tick is not None:
        rows = [r for r in rows if (r[0] - args.start_tick) & 0xFFFFFFFF < 0x80000000]
    if args.end_tick is not None:
        rows = [r for r in rows if (args.end_tick - r[0]) & 0xFFFFFFFF < 0x80000000]
    # Busy: at least ~0.3ms of CPU (1000 kilocycles) since the previous sample.
    threshold = 1000 if meta.get('deltaUnit') == 'kilocycles' else 0.25 * 1e7 / meta['hz']
    total = len(rows); busy = [r for r in rows if r[2] > threshold]
    flat = collections.Counter(); inclusive = collections.Counter(); outside = 0; cache = {}
    callers = collections.defaultdict(collections.Counter); stacks = collections.Counter()
    for tick, eip, delta, frames in busy:
        chain = walk(eip, frames, base, size, sections, image, sym, cache)
        leaf = chain[0]
        outside += leaf == '<outside gamecore>'
        flat[leaf] += 1
        for name in set(chain):
            inclusive[name] += 1
        if len(chain) > 1:
            callers[leaf][chain[1]] += 1
        stacks[' <- '.join(x.split('(')[0][:60] for x in chain[:args.stack_depth])] += 1
    n = max(1, len(busy))
    modules = collections.Counter(module_of(r[1], meta.get('modules', [])) for r in busy)
    print('modules (busy samples):', ', '.join('%s %.1f%%' % (m, 100.0 * c / n) for m, c in modules.most_common(12)))
    result = dict(samples=total, busySamples=len(busy), outsideGamecore=outside,
                  seconds=total / meta['hz'],
                  flat=[(name, c, round(100.0 * c / n, 2)) for name, c in flat.most_common(args.top)],
                  inclusive=[(name, c, round(100.0 * c / n, 2)) for name, c in inclusive.most_common(args.top)],
                  leafCallers={name: callers[name].most_common(4) for name, _ in flat.most_common(25)},
                  stacks=[(k, c, round(100.0 * c / n, 2)) for k, c in stacks.most_common(args.top)])
    text = json.dumps(result, indent=1)
    if args.output:
        Path(args.output).write_text(text)
    print('samples %d, busy %d (%.1f%%), outside gamecore %d' % (total, len(busy), 100.0 * len(busy) / max(1, total), outside))
    print('\n== flat (self) ==')
    for name, c, p in result['flat'][:args.print_top]:
        print('%6.2f%% %6d  %s' % (p, c, name[:160]))
    print('\n== inclusive (approximate) ==')
    for name, c, p in result['inclusive'][:args.print_top]:
        print('%6.2f%% %6d  %s' % (p, c, name[:160]))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('capture'); c.add_argument('--pid', type=int, required=True); c.add_argument('--thread', type=int)
    c.add_argument('--hz', type=float, default=200); c.add_argument('--seconds', type=float, default=1800)
    c.add_argument('--stack-bytes', type=int, default=32768); c.add_argument('--output', required=True); c.add_argument('--stop-file')
    r = sub.add_parser('report'); r.add_argument('samples'); r.add_argument('--dll', required=True); r.add_argument('--pdb', required=True)
    r.add_argument('--start-tick', type=int); r.add_argument('--end-tick', type=int); r.add_argument('--top', type=int, default=300)
    r.add_argument('--print-top', type=int, default=60); r.add_argument('--output')
    r.add_argument('--stack-depth', type=int, default=6)
    a = p.parse_args()
    if C.sizeof(C.c_void_p) != 8:
        sys.exit('64-bit Python required')
    capture(a) if a.cmd == 'capture' else report(a)


if __name__ == '__main__':
    main()
