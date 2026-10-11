"""Update checker for DroidDeck.

Fetches the latest-version manifest from the project's update server
(default https://droiddeck.top/latest.json) and compares it with the running
version.
"""

from __future__ import annotations

import json
import os
import platform
import urllib.request
from dataclasses import dataclass, field

from . import __version__

#: Update manifest endpoint. Overridable via the DROIDDECK_UPDATE_URL env var.
DEFAULT_UPDATE_URL = os.environ.get(
    "DROIDDECK_UPDATE_URL", "https://droiddeck.top/latest.json")


@dataclass
class UpdateInfo:
    version: str
    date: str = ""
    notes: str = ""
    page_url: str = ""
    assets: dict = field(default_factory=dict)
    error: str = ""

    def download_url(self) -> str:
        """Pick the best asset for the current platform."""
        if not self.assets:
            return self.page_url
        system = platform.system().lower()
        if system == "linux":
            for key in self.assets:
                if key.endswith(".deb"):
                    return self.assets[key]
            for key in self.assets:
                if key.endswith(".tar.gz"):
                    return self.assets[key]
        elif system == "windows":
            for key in self.assets:
                if key.endswith(".zip"):
                    return self.assets[key]
        elif system == "darwin":
            for key in self.assets:
                if key.endswith(".tar.gz"):
                    return self.assets[key]
        return next(iter(self.assets.values()))


def _key(v: str) -> list[int]:
    out = []
    for part in v.strip().lstrip("v").split("."):
        num = ""
        for ch in part:
            if ch.isdigit():
                num += ch
            else:
                break
        out.append(int(num) if num else 0)
    return out


def is_newer(candidate: str, current: str) -> bool:
    return _key(candidate) > _key(current)


def check(url: str = DEFAULT_UPDATE_URL, timeout: float = 10) -> UpdateInfo:
    """Fetch the latest manifest. Never raises — returns an UpdateInfo with
    `error` set on failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return UpdateInfo(version="", error=str(e))
    return UpdateInfo(
        version=str(data.get("version", "")),
        date=data.get("date", ""),
        notes=data.get("notes", ""),
        page_url=data.get("url", ""),
        assets=data.get("assets", {}) or {},
    )


def check_for_update(url: str = DEFAULT_UPDATE_URL) -> UpdateInfo | None:
    """Return an UpdateInfo if a newer version exists, else None."""
    info = check(url)
    if info.error or not info.version:
        return None
    if is_newer(info.version, __version__):
        return info
    return None
