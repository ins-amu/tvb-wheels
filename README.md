# ins-amu/tvb-wheels

Prebuilt cross-platform binary wheels (`cp311-cp311` and `cp312-abi3`) for [`tvb-library`](https://github.com/the-virtual-brain/tvb-root/tree/tvbkh/tvb_library) (specifically the `tvbkh` branch containing the nanobind `_cpp_hybrid` C++ simulator extension), served via a static PEP 503 index on GitHub Pages backed by GitHub Releases.

## Supported Platforms & Python Versions

| OS | Architecture | Runner | ISA / Notes |
|---|---|---|---|
| Linux (`manylinux_2_28`) | `x86_64` | `ubuntu-latest` | `-msse4.2` (replaces `-march=native` for portability) |
| Linux (`manylinux_2_28`) | `aarch64` | `ubuntu-24.04-arm` | Baseline ARM64 |
| macOS | `arm64` | `macos-15` | Apple Silicon |
| macOS | `x86_64` | `macos-15-intel` | `-msse4.2` (Intel macOS; uses `numba<0.63` / `llvmlite<0.46` wheels at build time) |
| Windows | `AMD64` | `windows-latest` | Baseline x64 (MSVC `/O2`, SSE2 baseline — safe on all SSE4.2/x64 CPUs) |

- **CPython ≥ 3.12 (`3.12`, `3.13`, `3.14+`):** served by `cp312-abi3` stable-ABI wheels.
- **CPython 3.11:** served by `cp311-cp311` wheels (patched at build time to disable `STABLE_ABI` and bypass upstream's `< 3.12` CMake guard).

## Consuming the Wheelhouse

Point `pip` or `uv` at the PEP 503 index:

```bash
pip install --extra-index-url https://ins-amu.github.io/tvb-wheels/simple/ tvb-library==3.0.0a1.post2
```

Or in a `requirements.txt`:

```text
--extra-index-url https://ins-amu.github.io/tvb-wheels/simple/
tvb-library==3.0.0a1.post2
```

> **Why `.postN`?** PyPI already hosts an older `tvb-library==3.0.0a1` sdist/wheel without the `tvbkh` C++ extension. Publishing as `3.0.0a1.postN` (and avoiding `+local` labels, which GitHub Releases rewrites to `.`) prevents PyPI shadowing while preserving PEP 440 compatibility and exact asset filenames.

## Building Wheels for a New Upstream Commit

Trigger [`.github/workflows/build-wheels.yml`](.github/workflows/build-wheels.yml) manually via GitHub Actions UI or CLI:

```bash
gh workflow run build-wheels.yml \
  --repo ins-amu/tvb-wheels \
  -f ref=<tvb-root-commit-or-branch> \
  -f version_suffix=.post3 \
  -f release_tag=v3.0.0a1.post3
```

Or push a tag matching `v*` (e.g. `v3.0.0a1.post3`) after updating the default `ref` in `build-wheels.yml`. Every run builds all 5 platforms × `{cp311, cp312-abi3}`, publishes a GitHub Release with `SHA256SUMS`, and regenerates the PEP 503 index across **all** existing releases so older versions remain installable.
