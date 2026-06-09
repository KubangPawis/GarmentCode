#!/usr/bin/env bash
# Run a repo python script inside the Windows Blender (headless) with the repo on
# sys.path. Usage: scripts/run_blender.sh <repo-relative-script.py> [-- ARGS...]
# Tolerates the harmless on-exit EXCEPTION_ACCESS_VIOLATION (cats-blender addon).
set -uo pipefail
BL="/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
REPO_WSL="$(realpath .)"
SCRIPT_WSL="$(realpath "$1")"; shift
REPO_WIN="$(wslpath -w "$REPO_WSL")"
SCRIPT_WIN="$(wslpath -w "$SCRIPT_WSL")"
"$BL" --background -noaudio --python "$SCRIPT_WIN" -- --repo "$REPO_WIN" "$@" || true
