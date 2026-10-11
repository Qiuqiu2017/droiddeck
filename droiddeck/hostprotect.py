"""Host-machine protection for the Waydroid container.

Even if a wipe script ("格机") manages to run *inside* the container, the HOST
must stay safe.  Waydroid's LXC config does not restrict the device cgroup, so
a root process in the container can mknod the host's disk devices and dd/mkfs
them, wiping the host operating system.

This module adds an LXC **device allow-list** (cgroup v2):

    deny all devices, then allow
      - all character devices  (Android needs binder / graphics / input / ...)
      - loop block devices  (7:*)  (needed to mount system/vendor images)

Host disks (8:*, 259:*, ...) are therefore unreachable from the container.

It is written to the live LXC config and to the Waydroid config template so it
survives ``waydroid init`` / upgrades, and re-applied on every session start.
"""

from __future__ import annotations

import os
from pathlib import Path

MARKER = "# droiddeck host protection"
BLOCK = """# droiddeck host protection (device allow-list)
lxc.cgroup2.devices.deny = a
lxc.cgroup2.devices.allow = c *:* rwm
lxc.cgroup2.devices.allow = b 7:* rwm
"""

LIVE_CONFIG = Path("/var/lib/waydroid/lxc/waydroid/config")
TEMPLATES = [
    Path("/usr/lib/waydroid/data/configs/config_base"),
    Path("/usr/lib/waydroid/data/configs/config_3"),
    Path("/usr/lib/waydroid/data/configs/config_4"),
]


def is_enabled() -> bool:
    try:
        return MARKER in LIVE_CONFIG.read_text(errors="ignore")
    except OSError:
        return False


def _ensure_file(path: Path) -> bool:
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return False
    if MARKER in text:
        return False
    try:
        with path.open("a") as f:
            if not text.endswith("\n"):
                f.write("\n")
            f.write("\n" + BLOCK)
    except OSError:
        return False
    return True


def ensure() -> bool:
    """Make sure the device allow-list is present. Returns True if it changed
    anything. Safe to call repeatedly; each missing file is patched once."""
    if not LIVE_CONFIG.parent.is_dir():
        return False
    changed = False
    if _ensure_file(LIVE_CONFIG):
        changed = True
    for t in TEMPLATES:
        if t.is_file() and _ensure_file(t):
            changed = True
    return changed


def status() -> str:
    if is_enabled():
        return "enabled"
    if LIVE_CONFIG.parent.is_dir():
        return "disabled"
    return "unavailable"
