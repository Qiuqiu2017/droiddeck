"""Tiny JSON settings store for DroidDeck."""

from __future__ import annotations

import json
from pathlib import Path


class Settings:
    DEFAULTS = {
        "root_enabled": True,   # ask on start-up, checked by default
        "armor_enabled": True,  # anti-wipe module
        "asked_root": False,    # only ask once
        "compat_apps": [],      # apps with fake-touch / fake-wifi enabled
    }

    def __init__(self) -> None:
        base = Path.home() / ".config" / "droiddeck"
        self.path = base / "config.json"
        self._data = dict(self.DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            self._data.update(json.loads(self.path.read_text()))
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False))

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self.save()
