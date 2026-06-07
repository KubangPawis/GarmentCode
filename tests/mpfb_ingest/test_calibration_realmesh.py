"""End-to-end validation of the quick-pass MakeHuman calibration.

Runs the full ingestion CLI on the committed body-only base mesh + calibrated
landmark JSON and checks the geometry-derived measurements land in anatomical
ranges and the right ordering. Self-contained -- the assets live in the repo,
so no external MPFB export is needed.
"""
from pathlib import Path

import yaml

from ingest_mpfb_body import run

BODY = Path("mpfb_ingest/data/mpfb_base_body.obj")
LANDMARKS = Path("mpfb_ingest/data/makehuman_landmarks.json")


def test_calibrated_base_body_measurements(tmp_path):
    out = run(str(BODY), out_dir=str(tmp_path), name="cal",
              landmarks_path=str(LANDMARKS), arm_pose_angle=0.0,
              height_m=1.7, fill_defaults=True)
    d = yaml.safe_load(out.read_text())["body"]

    # Geometry-derived fields in plausible anatomical ranges (cm).
    assert 150 <= d["height"] <= 200
    assert 70 <= d["bust"] <= 130
    assert 55 <= d["waist"] <= 120
    assert 80 <= d["hips"] <= 150

    # The girth-scan levels must be anatomically ordered.
    assert d["waist"] < d["underbust"] < d["bust"]
    assert d["waist"] < d["hips"]

    # The waist back arc is only part of the full waist girth.
    assert d["waist_back_width"] < d["waist"]
