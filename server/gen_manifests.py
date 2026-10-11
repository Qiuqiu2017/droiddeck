#!/usr/bin/env python3
"""Generate the update manifests (versions.json / latest.json) for the site.

It reads:
  server/meta/<version>.json      version metadata (date, notes, asset names)
  server/releases/<version>/*     the mirrored binaries
and writes:
  server/build/versions.json      full history (used by the website)
  server/build/latest.json        latest version (used by the app's updater)

Config via env:
  DL_BASE   base URL for binaries      (default https://dl.droiddeck.top)
  SITE_BASE base URL for the website   (default https://droiddeck.top)
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
META = HERE / "meta"
RELEASES = HERE / "releases"
SITE = HERE / "site"
BUILD = HERE / "build"

DL_BASE = os.environ.get("DL_BASE", "https://dl.droiddeck.top").rstrip("/")
SITE_BASE = os.environ.get("SITE_BASE", "https://droiddeck.top").rstrip("/")


def semver_key(v: str):
    parts = []
    for x in v.split("."):
        parts.append(int(x) if x.isdigit() else 0)
    return parts


def human(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def main() -> None:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)

    entries = []
    for meta_file in sorted(META.glob("*.json")):
        meta = json.loads(meta_file.read_text())
        version = meta["version"]
        ver_dir = RELEASES / version
        assets = []
        for name in meta.get("assets", []):
            f = ver_dir / name
            if not f.is_file():
                print(f"  ! 缺少文件: {ver_dir/name}")
                continue
            assets.append({
                "name": name,
                "url": f"{DL_BASE}/{version}/{name}",
                "size": human(f.stat().st_size),
            })
        entries.append({
            "version": version,
            "date": meta.get("date", ""),
            "notes": meta.get("notes", ""),
            "assets": assets,
        })

    entries.sort(key=lambda e: semver_key(e["version"]), reverse=True)
    latest = entries[0] if entries else None

    versions = {"latest": latest["version"] if latest else "", "versions": entries}
    (BUILD / "versions.json").write_text(json.dumps(versions, ensure_ascii=False, indent=2))

    if latest:
        latest_manifest = {
            "version": latest["version"],
            "date": latest["date"],
            "notes": latest["notes"],
            "url": f"{SITE_BASE}/",
            "assets": {a["name"]: a["url"] for a in latest["assets"]},
        }
        (BUILD / "latest.json").write_text(
            json.dumps(latest_manifest, ensure_ascii=False, indent=2))

    # Copy the static site into the publish root.
    for f in SITE.iterdir():
        if f.is_file():
            shutil.copy2(f, BUILD / f.name)

    print(f"生成完成：{len(entries)} 个版本 -> {BUILD}")
    if latest:
        print(f"最新版本：{latest['version']}")


if __name__ == "__main__":
    main()
