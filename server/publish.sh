#!/usr/bin/env bash
# Publish releases to Aliyun OSS.
#
# Usage:
#   ./publish.sh add  <version>    把 dist/ 里的安装包镜像到 releases/<version>/
#   ./publish.sh gen               生成 versions.json / latest.json / 站点
#   ./publish.sh sync              上传到 OSS（需要 ossutil 已配置）
#   ./publish.sh all  <version>    add + gen + sync
#
# 需要环境变量（sync 时）：
#   DL_BUCKET    版本文件桶      例：oss://droiddeck-dl
#   SITE_BUCKET  站点桶          例：oss://droiddeck-site
#   DL_BASE / SITE_BASE   公网地址（生成清单用，默认见 gen_manifests.py）
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DIST="$ROOT/dist"
RELEASES="$HERE/releases"

cmd="${1:-}"; version="${2:-}"

add_release() {
  [ -n "$version" ] || { echo "用法: ./publish.sh add <version>"; exit 1; }
  mkdir -p "$RELEASES/$version"
  shopt -s nullglob
  local n=0
  for f in "$DIST"/*; do
    case "$f" in
      *"$version"*.deb|*droiddeck-linux-*.tar.gz|*droiddeck-windows-*.zip|*droiddeck-macos-*.tar.gz)
        cp -f "$f" "$RELEASES/$version/"; echo "  + $(basename "$f")"; n=$((n+1)) ;;
    esac
  done
  shopt -u nullglob
  [ "$n" -gt 0 ] || { echo "dist/ 里没找到 $version 的安装包"; exit 1; }
  echo "已镜像 $n 个文件到 releases/$version/"
}

gen() { python3 "$HERE/gen_manifests.py"; }

sync() {
  local ossutil="${OSSUTIL:-ossutil}"
  command -v "$ossutil" >/dev/null 2>&1 || { echo "未找到 ossutil，请先安装并 ossutil config"; exit 1; }
  [ -n "${DL_BUCKET:-}" ] && [ -n "${SITE_BUCKET:-}" ] || { echo "请设置 DL_BUCKET / SITE_BUCKET"; exit 1; }
  echo "上传版本文件 -> $DL_BUCKET"
  "$ossutil" cp -r -f --update "$RELEASES/" "$DL_BUCKET/"
  echo "上传站点+清单 -> $SITE_BUCKET"
  "$ossutil" cp -r -f --update "$HERE/build/" "$SITE_BUCKET/"
}

case "$cmd" in
  add)  add_release ;;
  gen)  gen ;;
  sync) sync ;;
  all)  add_release; gen; sync ;;
  *)    sed -n '2,20p' "$0" ;;
esac
