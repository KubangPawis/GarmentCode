from pathlib import Path
import numpy as np
from mpfb_ingest import mesh_io, autolandmarks as al, measurements

BASE = Path("mpfb_ingest/data/mpfb_base_body.obj")


def _base_cm():
    raw = mesh_io.load_body(str(BASE))
    mm, _ = mesh_io.normalize(raw, expected_height_m=1.7)
    return mesh_io.to_cm(mm)


def test_find_levels_ordered_on_real_base():
    cm = _base_cm()
    lv = al.find_levels(cm)
    # anatomical ordering by height (cm, feet at 0)
    assert lv["crotch"] < lv["hips"] < lv["waist"] < lv["underbust"] < lv["bust"] < lv["neck"]
    # plausible bands for a ~170 cm body
    assert 70 <= lv["hips"] <= 100
    assert 95 <= lv["waist"] <= 120
    assert 120 <= lv["bust"] <= 145


def test_derive_circumferences_and_backwidths():
    cm = _base_cm()
    lm = al.derive(cm)
    out = measurements.compute_all(cm, lm, arm_pose_angle=0.0)
    # torso circumferences present and ordered
    assert out["waist"] < out["underbust"] < out["bust"]
    assert out["waist"] < out["hips"]
    # back-section widths are real (not the 39.14 default for every body) and
    # smaller than the full girth they sit inside
    assert out["waist_back_width"] < out["waist"]
    assert out["back_width"] < out["bust"]
    assert out["hip_back_width"] < out["hips"]
    # bust/bum point spreads are plausible peak-to-peak distances
    assert 10.0 <= out["bust_points"] <= 30.0
    assert 10.0 <= out["bum_points"] <= 35.0
