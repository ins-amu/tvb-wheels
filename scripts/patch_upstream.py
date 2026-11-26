#!/usr/bin/env python3
"""Patch upstream tvb_library before wheel build.

1. Replaces -march=native in CMakeLists.txt with portable SSE4.2 on x86_64/AMD64
   (and baseline flags on ARM64) so built wheels do not SIGILL on older CPUs.
2. Applies a PEP 440 version suffix (or explicit tag version) in pyproject.toml
   so built wheels never collide with or get shadowed by PyPI's tvb-library==3.0.0a1.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


def patch_cmake(cmake_path: Path) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    target = "target_compile_options(_cpp_hybrid PRIVATE -march=native)"
    replacement = (
        "if(CMAKE_SYSTEM_PROCESSOR MATCHES \"^(x86_64|AMD64)$\")\n"
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


def patch_pyproject(pyproject_path: Path, suffix: str, explicit_version: str) -> str:
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tvb-library-dir", type=Path, required=True)
    parser.add_argument("--version-suffix", default=".post1")
    parser.add_argument("--explicit-version", default="")
    args = parser.parse_args()

    patch_cmake(args.tvb_library_dir / "CMakeLists.txt")
    new_version = patch_pyproject(
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
