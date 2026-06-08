"""End-to-end stress test on the real MPFB T-pose avatar (.temp/avatar_base.glb).

Proves the topology-agnostic auto path ingests a true T-pose mesh whose vertex
count (14517) does NOT match the calibrated base (13345), emits a full 26-field
body in anatomical range, and that body drives GarmentCode pattern generation
without crashing. Skips cleanly when the glb asset is absent.
"""
from pathlib import Path

import yaml
import pytest

from ingest_mpfb_body import run

GLB = Path(".temp/avatar_base.glb")
pytestmark = pytest.mark.skipif(not GLB.exists(), reason="avatar_base.glb absent")


@pytest.fixture(scope="module")
def avatar_yaml(tmp_path_factory):
    d = tmp_path_factory.mktemp("glb")
    out = run(str(GLB), out_dir=str(d), name="avatar", landmarks_path=None,
              arm_pose_angle=0.0, height_m=None, fill_defaults=False)
    return Path(out)


def test_glb_emits_full_ordered_in_range_body(avatar_yaml):
    from mpfb_ingest.emit import REQUIRED, RANGES
    d = yaml.safe_load(avatar_yaml.read_text())["body"]

    # all 26 base fields present (auto path, no --fill-defaults)
    assert not (set(REQUIRED) - set(d)), f"missing: {set(REQUIRED) - set(d)}"
    # every range-guarded field in its sane band
    for f, (lo, hi) in RANGES.items():
        assert lo <= d[f] <= hi, f"{f}={d[f]} out of [{lo},{hi}]"
    # measured (not forced) height ~ the glb's true 1.729 m
    assert 165 <= d["height"] <= 178
    # anatomical ordering
    assert d["waist"] < d["underbust"] < d["bust"]
    assert d["waist"] < d["hips"]
    assert d["waist_back_width"] < d["waist"]
    assert d["back_width"] < d["bust"]


@pytest.mark.parametrize("design_file", [
    "assets/design_params/default.yaml",
    "assets/design_params/t-shirt.yaml",
])
def test_glb_generates_pattern_without_crash(avatar_yaml, design_file):
    from assets.bodies.body_params import BodyParameters
    from assets.garment_programs.meta_garment import MetaGarment

    body = BodyParameters(str(avatar_yaml))
    design = yaml.safe_load(open(design_file))["design"]
    # assembly() raises on degenerate panel geometry (the failure mode a bad
    # armscye/back_width produced in the quick pass); reaching a pattern is the
    # success criterion.
    pattern = MetaGarment("stress", body, design).assembly()
    assert pattern is not None
