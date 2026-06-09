"""Slow, gated end-to-end: drive Blender headless to generate+normalize+export,
then verify the exported .glb is a TRUE T-pose AND ingests through mpfb_ingest.
Skips when the Windows Blender + MPFB is unavailable.

Run explicitly:
  PYTHONPATH=. ./.venv/bin/python -m pytest \
      tests/mpfb_tpose/test_normalize_integration.py -v -s
"""
import os
import subprocess

import numpy as np
import pytest

BLENDER = "/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
WRAPPER = "scripts/run_tpose_normalize.sh"
OUT_DIR = ".temp/tpose_it"

pytestmark = pytest.mark.skipif(
    not os.path.exists(BLENDER),
    reason="Windows Blender + MPFB not available")


def _run(preset):
    os.makedirs(OUT_DIR, exist_ok=True)
    glb = os.path.join(OUT_DIR, preset["name"] + ".glb")
    blend = os.path.join(OUT_DIR, preset["name"] + ".blend")
    cmd = ["bash", WRAPPER, "--out-glb", glb, "--out-blend", blend]
    for k in ("gender", "weight", "height", "cupsize", "muscle"):
        if k in preset:
            cmd += ["--" + k, str(preset[k])]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    print(res.stdout[-2500:])
    print(res.stderr[-800:])
    return glb, blend, res.stdout


def _tpose_info(stdout):
    """Parse 'TPOSE_INFO <pre_span> <post_span>' -> (pre, post)."""
    for line in stdout.splitlines():
        if line.startswith("TPOSE_INFO"):
            parts = line.split()
            return float(parts[1]), float(parts[2])
    raise AssertionError("no TPOSE_INFO line in output")


@pytest.mark.parametrize("preset", [
    {"name": "f_neutral", "gender": 0.0},
    {"name": "m_heavy", "gender": 1.0, "weight": 0.9, "cupsize": 0.0},
])
def test_generate_normalize_export_is_tpose(preset):
    glb, blend, stdout = _run(preset)
    assert "TPOSE_OK" in stdout, "normalizer did not report success"
    assert os.path.isfile(glb) and os.path.isfile(blend)
    assert os.path.getsize(glb) > 0 and os.path.getsize(blend) > 0

    # The normalizer logged a real outward lift (arms swung from droop to horizontal).
    pre, post = _tpose_info(stdout)
    assert post > pre * 1.2, "span did not widen (pre=%.3f post=%.3f)" % (pre, post)

    # Load the exported body through mpfb_ingest's OWN pipeline (proves downstream
    # compatibility) and verify the geometry is a true T-pose.
    from mpfb_ingest import mesh_io, autolandmarks, measurements
    raw = mesh_io.load_body(glb)
    mesh_m, _ = mesh_io.normalize(raw)
    cm = mesh_io.to_cm(mesh_m)
    assert len(cm.vertices) > 1000
    v = np.asarray(cm.vertices, dtype=float)        # mpfb_ingest space: Y up, X lateral
    ymin, ymax = float(v[:, 1].min()), float(v[:, 1].max())
    stature = ymax - ymin
    xmax = float(v[:, 0].max())
    xspan = xmax - float(v[:, 0].min())

    # (1) Arm span (X, fingertip-to-fingertip) ~ stature for a T-pose; drooped ~0.45.
    assert xspan / stature > 0.70, "arms not extended (span/stature=%.2f)" % (xspan / stature)

    # (2) The hands (lateral extremes) sit near shoulder height for a T-pose
    #     (~0.8 of stature); drooped arms hang to ~0.45.
    hand = v[v[:, 0] > 0.9 * xmax]
    hand_rel = (float(hand[:, 1].mean()) - ymin) / stature
    assert hand_rel > 0.65, "hands not near shoulder height (rel=%.2f)" % hand_rel

    # (3) The full mpfb_ingest measurement pipeline runs on the T-pose output and
    #     returns sane body measurements (this is the module's whole purpose).
    lm = autolandmarks.derive(cm)
    measured = measurements.compute_all(cm, lm, arm_pose_angle=0.0)
    assert measured["bust"] > 0 and measured["waist"] > 0, measured
