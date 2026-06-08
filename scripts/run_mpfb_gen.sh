#!/usr/bin/env bash
# Generate the MPFB body-type test set into a WSL dir via the Windows Blender +
# the MPFB extension (which only runs under the GUI Blender install, driven
# headless). MPFB output is CC0.
#
# Usage: scripts/run_mpfb_gen.sh [out_dir] [limit]
#   out_dir  WSL path for the .glb set + manifest.json   (default .temp/testset)
#   limit    cap the number of bodies (default: full grid ~80-150)
set -euo pipefail

BL="/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
OUT_WSL="${1:-.temp/testset}"
LIMIT="${2:-}"

mkdir -p "$OUT_WSL"
OUT_WIN="$(wslpath -w "$(realpath "$OUT_WSL")")"
SCRIPT_WIN="$(wslpath -w "$(realpath scripts/gen_mpfb_testset.py)")"

ARGS=(--out "$OUT_WIN")
[ -n "$LIMIT" ] && ARGS+=(--limit "$LIMIT")

# The on-exit EXCEPTION_ACCESS_VIOLATION from an unrelated Blender addon is
# harmless (files are written before exit), so tolerate a nonzero exit code.
"$BL" --background -noaudio --python "$SCRIPT_WIN" -- "${ARGS[@]}" || true

echo "----"
echo "Generated $(ls -1 "$OUT_WSL"/*.glb 2>/dev/null | wc -l) bodies in $OUT_WSL"
