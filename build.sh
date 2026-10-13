#!/usr/bin/env bash
# Build a DroidDeck package for the CURRENT platform.
# Usage: ./build.sh
set -euo pipefail

cd "$(dirname "$0")"

if ! python3 -c "import PyInstaller" 2>/dev/null; then
  echo "安装 PyInstaller…"
  python3 -m pip install --upgrade pyinstaller
fi

rm -rf build dist
python3 -m PyInstaller --noconfirm --clean packaging/droiddeck.spec

OS="$(uname -s)"
case "$OS" in
  Linux*)  ARCH="$(uname -m)"; tar -C dist -czf "dist/droiddeck-linux-$ARCH.tar.gz" droiddeck ;;
  Darwin*) ARCH="$(uname -m)"; tar -C dist -czf "dist/droiddeck-macos-$ARCH.tar.gz" droiddeck ;;
  *)       echo "请在 Windows 上使用: Compress-Archive dist/droiddeck droiddeck-windows.zip" ;;
esac

echo "构建完成，产物在 dist/"
ls -lh dist/*.tar.gz 2>/dev/null || true
