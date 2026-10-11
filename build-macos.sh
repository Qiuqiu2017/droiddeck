#!/usr/bin/env bash
# DroidDeck - build a macOS package (run on macOS)
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pip install --upgrade pip
python3 -m pip install "PySide6>=6.5" pyinstaller

rm -rf build dist
python3 -m PyInstaller --noconfirm --clean packaging/droiddeck.spec

ARCH="$(uname -m)"
tar -C dist -czf "droiddeck-macos-${ARCH}.tar.gz" droiddeck

echo "构建完成：dist/droiddeck-macos-${ARCH}.tar.gz"
