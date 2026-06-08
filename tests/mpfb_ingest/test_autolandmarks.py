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


def test_derive_full_field_set_on_base():
    cm = _base_cm()
    lm = al.derive(cm)
    out = measurements.compute_all(cm, lm, arm_pose_angle=0.0)
    required = {
        "height", "bust", "waist", "hips", "underbust",
        "waist_back_width", "back_width", "hip_back_width", "neck_w",
        "shoulder_w", "head_l", "bust_points", "bum_points", "armscye_depth",
        "arm_length", "waist_line", "bust_line", "waist_over_bust_line",
        "hips_line", "crotch_hip_diff", "vert_bust_line",
        "leg_circ", "wrist", "shoulder_incl", "hip_inclination", "arm_pose_angle",
    }
    missing = required - set(out)
    assert not missing, f"missing geometric fields: {sorted(missing)}"
    # sane ranges for a ~170 cm body
    assert 30 <= out["shoulder_w"] <= 45       # clavicle span, not deltoid
    assert 8 <= out["armscye_depth"] <= 20      # right-side underarm
    assert 25 <= out["waist_line"] <= 45        # welded surface geodesic
    assert 20 <= out["head_l"] <= 32
    assert 40 <= out["arm_length"] <= 75
    assert 0 <= out["shoulder_incl"] <= 45
    assert 0 <= out["hip_inclination"] <= 45
    assert 40 <= out["leg_circ"] <= 80
    assert 10 <= out["wrist"] <= 25
    assert 10 <= out["neck_w"] <= 25     # PART A fix: no longer the ~1.0 artifact; base body neck_w ~11.7


import pytest
from pathlib import Path as _Path

_GLB = _Path(".temp/avatar_base.glb")


@pytest.mark.skipif(not _GLB.exists(), reason="avatar_base.glb absent")
def test_glb_full_body_in_range_and_ordered():
    raw = mesh_io.load_body(str(_GLB))
    mm, _ = mesh_io.normalize(raw)          # auto units -> ~1.729 m
    cm = mesh_io.to_cm(mm)
    out = measurements.compute_all(cm, al.derive(cm), arm_pose_angle=0.0)
    out["height"] = float(cm.bounds[1][1] - cm.bounds[0][1])
    # the bug was bust=252; assert the whole set is anatomically sane
    from mpfb_ingest.emit import RANGES
    for f, (lo, hi) in RANGES.items():
        assert lo <= out[f] <= hi, f"{f}={out[f]:.1f} out of [{lo},{hi}]"
    assert out["waist"] < out["underbust"] < out["bust"], \
        f"ordering: w={out['waist']:.0f} ub={out['underbust']:.0f} b={out['bust']:.0f}"
    assert out["waist"] < out["hips"]
    assert out["back_width"] < out["bust"]
    assert out["waist_back_width"] < out["waist"]
    assert 165 <= out["height"] <= 178       # measured true glb height (~172.9)
