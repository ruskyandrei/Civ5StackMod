#!/usr/bin/env python3
"""Build the checked-out gamecore DLL with clang, the way upstream builds its releases.

Upstream releases come from build_vp_clang.py run inside a VS2008 command prompt (scripts/release.py). This
wrapper reproduces that build with the portable toolchain in work/toolchain (clang/lld 19, VC9 SP1 headers and
libraries, Windows SDK 7) and no Visual Studio install:

- The source list, defines, compiler and linker flags come from build_vp_clang_sdk.py, loaded without running
  its entry point.
- The VC9 and SDK headers are searched after clang's own headers, through INCLUDE, as in the VS2008 prompt.
  build_vp_clang_sdk.py passes them as -external:I, which puts them first: VC9's <stdarg.h> then defines
  va_start as "address of the last named parameter + 4" instead of __builtin_va_start. Clang 19 inlines
  variadic functions that do not use the builtin (CvString::format among them) and so drops their variable
  arguments; the DLL then crashes in its first CUSTOMLOG call while loading (error 1114).
- -fms-compatibility-version is VC9 SP1's (15.00.30729.1), which clang detects from cl.exe in the VS2008 prompt.
  C++14 parsing, no sized deallocation and no thread-safe statics keep clang 19 on the VC9 runtime ABI.
- At most --jobs compiler processes and linker threads run at once.

Each build goes to a new work/clang-output/<Config>/<timestamp> folder of the source checkout, with the DLL, PDB,
build log, every command run (commands.jsonl) and build-result.json.
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

MSVC_COMPATIBILITY_VERSION = "15.00.30729.1"  # cl.exe of VS2008 SP1


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def default_toolchain(work):
    """work/toolchain next to this script, else the main checkout's (worktrees share it)."""
    local = work / "toolchain"
    if local.is_dir():
        return local
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=work,
                                capture_output=True, text=True, check=True).stdout.strip()
        return Path(common).parent / "work" / "toolchain"
    except (OSError, subprocess.CalledProcessError):
        return local


def arguments():
    work = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=work.parent,
                        help="checkout to build (default: parent of this script's work directory)")
    parser.add_argument("--config", choices=("release", "debug"), default="release")
    parser.add_argument("--jobs", type=positive_int, default=6,
                        help="maximum simultaneous compiler processes and linker threads (default: 6)")
    parser.add_argument("--toolchain", type=Path, default=None,
                        help="folder with llvm/ and sdk/ (default: work/toolchain, or the main checkout's)")
    parser.add_argument("--no-lto", action="store_true", help="compile without -flto (faster link, slower DLL)")
    parser.add_argument("--keep-commit-id", action="store_true",
                        help="use the existing commit_id.inc instead of running update_commit_id.bat")
    parser.add_argument("--check", action="store_true",
                        help="validate tool/header/library paths without compiling")
    args = parser.parse_args()
    toolchain = (args.toolchain or default_toolchain(work)).resolve()
    args.source = args.source.resolve()
    args.llvm_bin = toolchain / "llvm/bin"
    args.sdk_include = toolchain / "sdk/windows/Include"
    args.sdk_lib = toolchain / "sdk/windows/Lib"
    args.vc_include = toolchain / "sdk/vc9/include"
    args.vc_lib = toolchain / "sdk/vc9/lib"
    args.toolchain = toolchain
    return args


def validate(args):
    if os.name != "nt":
        raise RuntimeError("This wrapper requires Windows and the 32-bit VC9/Windows SDK 7 libraries.")
    required = {
        "upstream build script": args.source / "build_vp_clang_sdk.py",
        "Clang compiler": args.llvm_bin / "clang-cl.exe",
        "LLVM linker": args.llvm_bin / "lld-link.exe",
        "Windows SDK header": args.sdk_include / "Windows.h",
        "Windows SDK x86 library": args.sdk_lib / "kernel32.lib",
        "VC9 C runtime header": args.vc_include / "stdio.h",
        "VC9 x86 runtime library": args.vc_lib / "msvcrt.lib",
    }
    if args.keep_commit_id:
        required["existing commit_id.inc"] = args.source / "commit_id.inc"
    missing = [f"{label}: {path}" for label, path in required.items() if not path.is_file()]
    if missing:
        raise RuntimeError("Missing build prerequisites:\n  " + "\n  ".join(missing))
    return required


def load_upstream(path):
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))
    entry_index = None
    for index, node in enumerate(tree.body):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "set_environment"):
            entry_index = index
            break
    if entry_index is None:
        raise RuntimeError("Upstream build entry point changed; review this wrapper before building.")
    tree.body = tree.body[:entry_index]
    namespace = {"__name__": "vp_upstream_build_definitions", "__file__": str(path)}
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace


class CommandRecorder:
    """Record each actual subprocess command without changing upstream invocation semantics."""
    def __init__(self, path):
        self.file = path.open("w", encoding="utf-8")
        self.lock = threading.Lock()
        self.counter = 0

    def write(self, event):
        with self.lock:
            self.file.write(json.dumps(event, ensure_ascii=False) + "\n")
            self.file.flush()

    def run(self, command, *positional, **kwargs):
        with self.lock:
            self.counter += 1
            number = self.counter
        started = time.monotonic()
        self.write({"id": number, "event": "start", "at": utc_now(),
                    "cwd": str(kwargs.get("cwd", Path.cwd())), "command": command,
                    "shell": kwargs.get("shell", False)})
        try:
            result = subprocess.run(command, *positional, **kwargs)
        except BaseException as exc:
            self.write({"id": number, "event": "error", "at": utc_now(),
                        "elapsed_seconds": time.monotonic() - started, "error": repr(exc)})
            raise
        self.write({"id": number, "event": "finish", "at": utc_now(),
                    "elapsed_seconds": time.monotonic() - started, "returncode": result.returncode})
        return result

    def close(self):
        self.file.close()


def update_commit_id(recorder, source, keep, log):
    """Upstream's step, through cmd.exe: Python will not start a .bat file directly."""
    if keep:
        log.write(b"==== update_commit_id.bat ====\nskipped (--keep-commit-id)\n")
        return
    result = recorder.run(["cmd", "/c", str(source / "update_commit_id.bat")], cwd=source, capture_output=True)
    log.write(b"==== update_commit_id.bat ====\n" + result.stdout + result.stderr)
    log.flush()
    if result.returncode:
        raise RuntimeError("update_commit_id.bat failed; see the build log")


def build_cpps_bounded(upstream, recorder, jobs, cl, cl_args, pch_path, build_dir, log):
    sources = upstream["CPP"]
    print(f"Building {len(sources)} C++ files with at most {jobs} compiler processes...", flush=True)
    start = time.monotonic()
    log_dir = build_dir / "compile-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    def compile_one(index, relative):
        source = upstream["PROJECT_DIR"] / relative
        output = (build_dir / relative).with_suffix(".obj")
        command = (f'{cl} "{source}" /Fo"{output}" /Yu"{upstream["PCH_H"]}" '
                   f'/Fp"{pch_path}" {cl_args}')
        source_log = log_dir / f"{index:03d}-{Path(relative).stem}.log"
        with source_log.open("wb") as handle:
            result = recorder.run(command, stdout=handle, stderr=subprocess.STDOUT)
        return source, source_log, result.returncode

    failures = []
    with ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="vp-compile") as executor:
        futures = [executor.submit(compile_one, index, relative)
                   for index, relative in enumerate(sources)]
        for completed, future in enumerate(as_completed(futures), 1):
            source, source_log, code = future.result()
            log.write(f"==== {source} ====\n".encode())
            log.write(source_log.read_bytes())
            log.flush()
            if code:
                failures.append(str(source))
            print(f"[{completed}/{len(sources)}] {'FAILED' if code else 'OK'} {source.name}", flush=True)
    print(f"C++ compilation finished after {time.monotonic() - start:.1f} seconds.", flush=True)
    if failures:
        raise RuntimeError(f"{len(failures)} C++ files failed. See {log.name} and {log_dir}.")


def main():
    args = arguments()
    prerequisites = validate(args)
    if args.check:
        for label, path in prerequisites.items():
            print(f"OK {label}: {path}")
        print(f"Configuration: {args.config}; maximum compiler processes: {args.jobs}")
        return 0

    os.chdir(args.source)
    upstream_path = args.source / "build_vp_clang_sdk.py"
    upstream = load_upstream(upstream_path)
    upstream["PROJECT_DIR"] = args.source
    # Headers through INCLUDE only (after clang's own), never -external:I; see the module docstring.
    upstream["INCLUDE_PATHS"] = []
    upstream["LIB_PATHS"] = [str(args.sdk_lib), str(args.vc_lib)]
    os.environ["INCLUDE"] = ";".join([str(args.sdk_include), str(args.vc_include)])
    os.environ["LIB"] = ";".join(upstream["LIB_PATHS"])
    os.environ["PATH"] = str(args.llvm_bin) + os.pathsep + os.environ.get("PATH", "")
    config = upstream["Config"].Release if args.config == "release" else upstream["Config"].Debug
    config_name = "Release" if args.config == "release" else "Debug"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    build_dir = args.source / "work" / "clang-build" / config_name
    out_dir = args.source / "work" / "clang-output" / config_name / stamp
    upstream["prepare_dirs"](build_dir, out_dir)
    cl_path, link_path = args.llvm_bin / "clang-cl.exe", args.llvm_bin / "lld-link.exe"
    cl, link = f'"{cl_path}"', f'"{link_path}"'
    # LLVM 19 rejects VP's legacy out-of-range PlayerTypes constexpr cast; build_vp_clang.py suppresses it too.
    if "enum-constexpr-conversion" not in upstream["CL_SUPPRESS"]:
        upstream["CL_SUPPRESS"].append("enum-constexpr-conversion")
    compatibility_args = [f"-fms-compatibility-version={MSVC_COMPATIBILITY_VERSION}", "/std:c++14",
                          "/Zc:sizedDealloc-", "/Zc:threadSafeInit-"]
    cl_config_args = upstream["build_cl_config_args"](config)
    if args.no_lto:
        cl_config_args = [arg for arg in cl_config_args if arg != "-flto"]
    cl_args = " ".join(cl_config_args + compatibility_args)
    link_args = upstream["build_link_config_args"](config) + [f"/threads:{args.jobs}"]
    pch_path = build_dir / upstream["PCH"]
    recorder = CommandRecorder(out_dir / "commands.jsonl")
    # Only the imported script's subprocess binding is replaced; Python's module
    # and the wrapper's subprocess calls are unaffected.
    upstream["subprocess"] = SimpleNamespace(run=recorder.run)
    metadata = {
        "started_at": utc_now(), "source": str(args.source), "config": args.config, "lto": not args.no_lto,
        "jobs": args.jobs, "python": sys.version, "python_executable": sys.executable,
        "wrapper": str(Path(__file__).resolve()),
        "wrapper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "upstream_script_sha256": hashlib.sha256(upstream_path.read_bytes()).hexdigest(),
        "arguments": {name: str(value) if isinstance(value, Path) else value for name, value in vars(args).items()},
        "environment": {name: os.environ.get(name, "") for name in ("INCLUDE", "LIB", "PATH")},
        "compiler_args": cl_args, "linker_args": link_args,
        "source_count": len(upstream["CPP"]),
    }
    start = time.monotonic()
    code = 1
    try:
        for name, command in (
                ("clang_version", [str(cl_path), "--version"]),
                ("linker_version", [str(link_path), "--version"]),
                ("git_head", ["git", "rev-parse", "HEAD"]),
                ("git_describe", ["git", "describe", "--tags", "--long", "HEAD"]),
                ("git_status", ["git", "status", "--untracked-files=no", "--porcelain"])):
            result = recorder.run(command, capture_output=True, text=True)
            metadata[name] = {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
            if result.returncode and name in ("clang_version", "linker_version", "git_head"):
                raise RuntimeError(f"Prerequisite command failed: {command}: {result.stderr}")
        (out_dir / "environment.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        print(f"Building {args.config} DLL from {args.source}", flush=True)
        print(f"Build log: {out_dir / 'build.log'}", flush=True)
        with (out_dir / "build.log").open("w+b") as log:
            update_commit_id(recorder, args.source, args.keep_commit_id, log)
            metadata["commit_id"] = (args.source / "commit_id.inc").read_text(encoding="utf-8", errors="replace")
            upstream["build_clang_cpp"](cl, cl_args, build_dir, log)
            upstream["build_pch"](cl, cl_args, pch_path, build_dir, log)
            build_cpps_bounded(upstream, recorder, args.jobs, cl, cl_args, pch_path, build_dir, log)
            upstream["link_dll"](link, link_args, build_dir, out_dir, log)
        dll = out_dir / f"{upstream['CORE_DLL']}.dll"
        metadata["dll"] = {"path": str(dll), "size": dll.stat().st_size,
                           "sha256": hashlib.sha256(dll.read_bytes()).hexdigest()}
        code = 0
        (args.source / "work" / "latest-clang-build-path.txt").write_text(str(out_dir) + "\n", encoding="utf-8")
        print(f"Built: {dll}", flush=True)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        metadata["error"] = str(exc)
    except Exception as exc:
        metadata["error"] = repr(exc)
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
    finally:
        metadata["finished_at"] = utc_now()
        metadata["elapsed_seconds"] = time.monotonic() - start
        metadata["exit_code"] = code
        metadata["status"] = "success" if code == 0 else "failed"
        (out_dir / "build-result.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        recorder.close()
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
