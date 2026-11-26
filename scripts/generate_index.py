#!/usr/bin/env python3
"""Generate a PEP 503 static Python package index from GitHub Releases."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import urllib.request
from collections import defaultdict
from pathlib import Path


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def http_get(url: str, token: str | None = None, accept: str | None = None) -> tuple[bytes, dict[str, str]]:
    headers = {"User-Agent": "tvb-wheels-index-generator"}
    if accept:
        headers["Accept"] = accept
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return resp.read(), {k.lower(): v for k, v in resp.headers.items()}


def fetch_all_releases(repo: str, token: str | None) -> list[dict]:
    releases: list[dict] = []
    url: str | None = f"https://api.github.com/repos/{repo}/releases?per_page=100"
    while url:
        body, headers = http_get(url, token=token, accept="application/vnd.github+json")
        releases.extend(json.loads(body.decode("utf-8")))
        link = headers.get("link", "")
        next_match = re.search(r'<([^>]+)>;\s*rel="next"', link)
        url = next_match.group(1) if next_match else None
    return releases


def parse_sha256sums(release: dict, token: str | None) -> dict[str, str]:
    for asset in release.get("assets", []):
        if asset.get("name") == "SHA256SUMS":
            data, _ = http_get(asset["browser_download_url"], token=token)
            sums: dict[str, str] = {}
            for line in data.decode("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) == 2:
                    digest, fname = parts[0].lower(), parts[1].lstrip("*").strip()
                    sums[fname] = digest
            return sums
    return {}


def resolve_sha256(asset: dict, cached_sums: dict[str, str], token: str | None) -> str:
    api_digest = asset.get("digest") or ""
    if isinstance(api_digest, str) and api_digest.startswith("sha256:"):
        return api_digest.split(":", 1)[1].lower()
    name = asset["name"]
    if name in cached_sums:
        return cached_sums[name]
    data, _ = http_get(asset["browser_download_url"], token=token)
    return hashlib.sha256(data).hexdigest().lower()


def build_index(repo: str, out_dir: Path, token: str | None) -> None:
    releases = fetch_all_releases(repo, token)
    packages: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    seen_filenames: set[str] = set()

    for release in releases:
        if release.get("draft"):
            continue
        assets = release.get("assets", [])
        wheel_assets = [a for a in assets if a.get("name", "").endswith(".whl")]
        if not wheel_assets:
            continue
        sums = parse_sha256sums(release, token)
        for asset in sorted(wheel_assets, key=lambda a: a["name"]):
            filename = asset["name"]
            if filename in seen_filenames:
                continue
            seen_filenames.add(filename)
            dist_raw = filename.split("-", 1)[0]
            pkg = normalize_name(dist_raw)
            sha256 = resolve_sha256(asset, sums, token)
            url = asset["browser_download_url"]
            packages[pkg].append((filename, url, sha256))

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    simple_dir = out_dir / "simple"
    simple_dir.mkdir(parents=True, exist_ok=True)

    sorted_pkgs = sorted(packages)
    pkg_links = "\n".join(
        f'    <a href="{html.escape(pkg)}/">{html.escape(pkg)}</a><br/>'
        for pkg in sorted_pkgs
    )
    (simple_dir / "index.html").write_text(
        "<!DOCTYPE html>\n"
        "<html>\n"
        "  <head>\n"
        '    <meta charset="utf-8"/>\n'
        '    <meta name="pypi:repository-version" content="1.1"/>\n'
        "    <title>Simple Index</title>\n"
        "  </head>\n"
        "  <body>\n"
        f"{pkg_links}\n"
        "  </body>\n"
        "</html>\n",
        encoding="utf-8",
    )

    owner, repo_name = repo.split("/", 1)
    index_url = f"https://{owner}.github.io/{repo_name}/simple/"
    landing_items = "\n".join(
        f'      <li><a href="simple/{html.escape(pkg)}/">{html.escape(pkg)}</a> ({len(packages[pkg])} wheels)</li>'
        for pkg in sorted_pkgs
    )
    (out_dir / "index.html").write_text(
        "<!DOCTYPE html>\n"
        "<html>\n"
        "  <head>\n"
        '    <meta charset="utf-8"/>\n'
        f"    <title>{html.escape(repo)} Wheelhouse</title>\n"
        "  </head>\n"
        "  <body>\n"
        f"    <h1>{html.escape(repo)} Wheelhouse</h1>\n"
        f"    <p>PEP 503 simple index: <a href=\"simple/\"><code>{html.escape(index_url)}</code></a></p>\n"
        "    <ul>\n"
        f"{landing_items}\n"
        "    </ul>\n"
        "  </body>\n"
        "</html>\n",
        encoding="utf-8",
    )

    for pkg in sorted_pkgs:
        pkg_dir = simple_dir / pkg
        pkg_dir.mkdir(parents=True, exist_ok=True)
        links = "\n".join(
            f'    <a href="{html.escape(url)}#sha256={sha256}">{html.escape(filename)}</a><br/>'
            for filename, url, sha256 in sorted(packages[pkg], key=lambda item: item[0])
        )
        (pkg_dir / "index.html").write_text(
            "<!DOCTYPE html>\n"
            "<html>\n"
            "  <head>\n"
            '    <meta charset="utf-8"/>\n'
            '    <meta name="pypi:repository-version" content="1.1"/>\n'
            f"    <title>Links for {html.escape(pkg)}</title>\n"
            "  </head>\n"
            "  <body>\n"
            f"    <h1>Links for {html.escape(pkg)}</h1>\n"
            f"{links}\n"
            "  </body>\n"
            "</html>\n",
            encoding="utf-8",
        )

    total = sum(len(v) for v in packages.values())
    print(f"Generated PEP 503 index in {out_dir} for {len(sorted_pkgs)} package(s), {total} wheel(s).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    build_index(args.repo, args.out_dir, token)


if __name__ == "__main__":
    main()
