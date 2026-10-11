#!/usr/bin/env bash
# DroidDeck - run on macOS
set -e
cd "$(dirname "$0")"
exec python3 -m droiddeck "$@"
