from mpfb_ingest.landmarks import Landmarks
from mpfb_ingest import measurements


def test_shoulder_incl_angle(tiny_mesh):
    # neck_base (0,40,0) -> collar_r (30,0,0): drop of 40 over 30 horiz -> 53.13 deg
    lm = Landmarks({
        "n_vertices_expected": 4,
        "vertices": {"neck_base": 2, "collar_r": 1, "waist_side": 0, "hip_side": 0},
        "levels": {},
    })
    out = measurements.angles(tiny_mesh, lm, arm_pose_angle=90.0)
    assert abs(out["shoulder_incl"] - 53.130102) < 1e-3
    assert out["arm_pose_angle"] == 90.0


def test_compute_all_returns_dict(cylinder_cm):
    lm = Landmarks({"n_vertices_expected": len(cylinder_cm.vertices),
                    "vertices": {}, "levels": {}})
    # with no landmarks, only height + (no) others; must not raise
    result = measurements.compute_all(cylinder_cm, lm, arm_pose_angle=90.0,
                                      level_y=lambda n: 50.0)
    assert "height" in result and "arm_pose_angle" in result
