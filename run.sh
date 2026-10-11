#!/usr/bin/env bash
# 便捷启动脚本
set -e
cd "$(dirname "$0")"
exec python3 -m droiddeck "$@"
