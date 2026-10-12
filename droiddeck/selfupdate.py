"""Silent self-update.

Flow (triggered from the "更新" button):
  1. write a small helper script
  2. the app quits
  3. the helper (detached) downloads the new package, installs it,
     writes a "done" marker and relaunches DroidDeck
  4. on the next start the app reads the marker and shows 更新完成
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

CONF = Path.home() / ".config" / "droiddeck"
MARKER = CONF / "update_done.json"


def take_completed() -> str | None:
    """If a silent update just finished, return its version and clear it."""
    try:
        data = json.loads(MARKER.read_text())
    except (OSError, ValueError):
        return None
    try:
        MARKER.unlink()
    except OSError:
        pass
    ver = data.get("version")
    return str(ver) if ver else None


def start(info) -> Path:
    """Write and launch the detached update helper. Returns the script path."""
    url = info.download_url()
    assets = getattr(info, "assets", {}) or {}
    for u in assets.values():
        if u.endswith(".deb"):
            url = u
            break
    app = shutil.which("droiddeck") or "/opt/droiddeck/droiddeck"
    CONF.mkdir(parents=True, exist_ok=True)
    deb = "/tmp/droiddeck-update-" + info.version + ".deb"
    script = CONF / "update.sh"

    lines = [
        "#!/bin/sh",
        "# DroidDeck silent self-update to " + info.version,
        'LOG="' + str(CONF / "update.log") + '"',
        'exec >>"$LOG" 2>&1',
        'echo "=== update to ' + info.version + ' at $(date) ==="',
        "",
        "# wait for the running app to exit (match the app binary, not this script)",
        "sleep 2",
        "for i in $(seq 1 60); do",
        '  pgrep -f "/opt/droiddeck/droiddeck" >/dev/null 2>&1 || break',
        "  sleep 1",
        "done",
        "",
        "# download",
        "if command -v curl >/dev/null 2>&1; then",
        '  curl -L -f -o "' + deb + '" "' + url + '"',
        "elif command -v wget >/dev/null 2>&1; then",
        '  wget -O "' + deb + '" "' + url + '"',
        "fi",
        'if [ ! -s "' + deb + '" ]; then',
        '  echo "download failed"',
        '  [ -x "' + app + '" ] && "' + app + '" >/dev/null 2>&1 &',
        "  exit 1",
        "fi",
        "",
        "# install (root directly, otherwise passwordless sudo)",
        "install_deb() {",
        '  if [ "$(id -u)" = "0" ]; then',
        '    apt-get install -y "$1"',
        "  else",
        '    sudo -n apt-get install -y "$1"',
        "  fi",
        "}",
        'if install_deb "' + deb + '"; then',
        '  echo ' + repr(info.version) + ' > "' + str(MARKER) + '"',
        '  echo "installed ' + info.version + '"',
        "else",
        '  echo "install failed (need root or passwordless sudo)"',
        "fi",
        "",
        "# relaunch",
        '[ -x "' + app + '" ] && "' + app + '" >/dev/null 2>&1 &',
        'echo "done"',
        "",
    ]
    script.write_text("\n".join(lines))
    script.chmod(0o755)
    subprocess.Popen(
        ["setsid", str(script)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, start_new_session=True,
    )
    return script
