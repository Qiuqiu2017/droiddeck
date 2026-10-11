#!/usr/bin/env bash
# Build a .deb from the PyInstaller output. Run ./build.sh first.
set -euo pipefail

cd "$(dirname "$0")/.."

VERSION="$(python3 -c "import droiddeck; print(droiddeck.__version__)")"
ARCH="amd64"
PKG="droiddeck_${VERSION}_${ARCH}"
ROOT="build/${PKG}"

rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" "$ROOT/opt/droiddeck" "$ROOT/usr/bin" \
         "$ROOT/usr/share/applications" "$ROOT/usr/share/icons/hicolor/scalable/apps"

cp -r dist/droiddeck/. "$ROOT/opt/droiddeck/"

cat > "$ROOT/usr/bin/droiddeck" <<'EOF'
#!/bin/sh
exec /opt/droiddeck/droiddeck "$@"
EOF
chmod 755 "$ROOT/usr/bin/droiddeck"

cp packaging/droiddeck.desktop "$ROOT/usr/share/applications/droiddeck.desktop"
cp droiddeck/assets/icon.svg \
   "$ROOT/usr/share/icons/hicolor/scalable/apps/droiddeck.svg"

cat > "$ROOT/DEBIAN/control" <<EOF
Package: droiddeck
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: waydroid | waydroid-container, weston
Maintainer: DroidDeck contributors
Description: Android app runner front-end for Waydroid
 DroidDeck installs and runs Android apps (APK) on Linux through the
 Waydroid container, with an install UI and an optional Magisk root
 environment.
EOF

dpkg-deb --build --root-owner-group "$ROOT" "dist/${PKG}.deb"
echo "已生成 dist/${PKG}.deb"
