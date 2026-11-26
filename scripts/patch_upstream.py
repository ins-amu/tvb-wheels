#!/usr/bin/env python3
"""Patch upstream tvb_library before wheel build.

1. Replaces -march=native in CMakeLists.txt with portable SSE4.2 on x86_64/AMD64
   (and baseline flags on ARM64) so built wheels do not SIGILL on older CPUs.
2. Applies a PEP 440 version suffix (or explicit tag version) in pyproject.toml
   so built wheels never collide with or get shadowed by PyPI's tvb-library==3.0.0a1.
3. With --cp311-only, switches an already-patched checkout from cp312-abi3 to
   non-stable-ABI cp311-cp311 so Python 3.11 wheels also bundle _cpp_hybrid.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


def patch_cmake_isa(cmake_path: Path) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    target = "target_compile_options(_cpp_hybrid PRIVATE -march=native)"
    replacement = (
        'if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64)$")\n'
        "        target_compile_options(_cpp_hybrid PRIVATE -msse4.2)\n"
        "      endif()"
    )
    count = text.count(target)
    if count != 2:
        raise RuntimeError(
            f"Expected 2 occurrences of {target!r} in {cmake_path}, found {count}"
        )
    cmake_path.write_text(text.replace(target, replacement), encoding="utf-8")
    print(f"Patched {count} -march=native entries in {cmake_path} -> -msse4.2 (x86_64/AMD64)")


def patch_pyproject_version(pyproject_path: Path, suffix: str, explicit_version: str) -> str:
    text = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'^(version\s*=\s*")([^"]+)(")', text, flags=re.MULTILINE)
    if not match:
        raise RuntimeError(f"Could not find project version in {pyproject_path}")

    base_version = match.group(2)
    if explicit_version:
        new_version = explicit_version
    elif suffix and not base_version.endswith(suffix):
        new_version = f"{base_version}{suffix}"
    else:
        new_version = base_version

    updated = (
        text[: match.start()]
        + f"{match.group(1)}{new_version}{match.group(3)}"
        + text[match.end() :]
    )
    pyproject_path.write_text(updated, encoding="utf-8")
    print(f"Patched version in {pyproject_path}: {base_version} -> {new_version}")
    return new_version


def patch_for_cp311(tvb_library_dir: Path) -> None:
    cmake_path = tvb_library_dir / "CMakeLists.txt"
    cmake_text = cmake_path.read_text(encoding="utf-8")

    guard_target = "if(Python_VERSION VERSION_LESS 3.12)"
    if guard_target not in cmake_text:
        raise RuntimeError(f"Expected {guard_target!r} in {cmake_path}")
    cmake_text = cmake_text.replace(guard_target, "if(Python_VERSION VERSION_LESS 3.11)", 1)

    abi_target = "STABLE_ABI NB_STATIC LTO NOMINSIZE"
    if abi_target not in cmake_text:
        raise RuntimeError(f"Expected {abi_target!r} in {cmake_path}")
    cmake_text = cmake_text.replace(abi_target, "NB_STATIC LTO NOMINSIZE", 1)
    cmake_path.write_text(cmake_text, encoding="utf-8")

    pyproject_path = tvb_library_dir / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    py_api_target = 'py-api = "cp312"'
    if py_api_target not in pyproject_text:
        raise RuntimeError(f"Expected {py_api_target!r} in {pyproject_path}")
    pyproject_text = pyproject_text.replace(py_api_target, '# py-api disabled for cp311-cp311 build', 1)
    pyproject_path.write_text(pyproject_text, encoding="utf-8")

    dfungen_path = tvb_library_dir / "tvb" / "simulator" / "backend" / "cpp_hybrid" / "dfungen.py"
    dfungen_text = dfungen_path.read_text(encoding="utf-8")
    fstring_target = '{" from the supported set" if args.only_supported else ""}'
    if fstring_target in dfungen_text:
        dfungen_text = dfungen_text.replace(
            fstring_target,
            "{' from the supported set' if args.only_supported else ''}",
            1,
        )
        dfungen_path.write_text(dfungen_text, encoding="utf-8")

    print(f"Patched {tvb_library_dir} for non-abi3 cp311-cp311 build")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tvb-library-dir", type=Path, required=True)
    parser.add_argument("--version-suffix", default=".post1")
    parser.add_argument("--explicit-version", default="")
    parser.add_argument("--cp311-only", action="store_true")
    args = parser.parse_args()

    if args.cp311_only:
        patch_for_cp311(args.tvb_library_dir)
        return

    patch_cmake_isa(args.tvb_library_dir / "CMakeLists.txt")
    new_version = patch_pyproject_version(
        args.tvb_library_dir / "pyproject.toml",
        suffix=args.version_suffix,
        explicit_version=args.explicit_version,
    )

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"version={new_version}\n")


if __name__ == "__main__":
    main()
