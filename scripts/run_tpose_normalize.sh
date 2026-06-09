#!/usr/bin/env bash
# Generate an MPFB human from macro params and normalize it to a true T-pose via
# the Windows Blender + MPFB extension, headless. MPFB output is CC0.
#
# Usage: scripts/run_tpose_normalize.sh --out-glb PATH --out-blend PATH \
#          [--gender 0.0] [--weight 0.5] [--height 0.5] [--cupsize 0.5] [--muscle 0.5]
# All flags take a value. Output paths are WSL paths (auto-translated to Windows).
set -uo pipefail

BL="/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
REPO_WSL="$(realpath .)"
REPO_WIN="$(wslpath -w "$REPO_WSL")"
SCRIPT_WIN="$(wslpath -w "$REPO_WSL/tpose_normalize_mpfb.py")"

ARGS=(--repo "$REPO_WIN")
while [ $# -gt 0 ]; do
  case "$1" in
    --out-glb|--out-blend)
      [ $# -lt 2 ] && { echo "ERROR: $1 requires a value" >&2; exit 1; }
      mkdir -p "$(dirname "$2")"
      ARGS+=("$1" "$(wslpath -w "$(realpath -m "$2")")"); shift 2;;
    *) [ $# -lt 2 ] && { echo "ERROR: flag $1 requires a value" >&2; exit 1; }
       ARGS+=("$1" "$2"); shift 2;;
  esac
done

# Tolerate the harmless on-exit EXCEPTION_ACCESS_VIOLATION (cats-blender addon);
# success is verified by the caller via output-file existence + the TPOSE_OK line.
"$BL" --background -noaudio --python "$SCRIPT_WIN" -- "${ARGS[@]}" || true
