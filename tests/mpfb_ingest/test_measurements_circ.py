import numpy as np
from mpfb_ingest.landmarks import Landmarks
from mpfb_ingest import measurements


def test_circumferences_on_cylinder(cylinder_cm):
    lm = Landmarks({
        "n_vertices_expected": len(cylinder_cm.vertices),
        "vertices": {"wrist_r": 0, "thigh_r": 0},
        "levels": {"waist": 0, "bust": 0, "underbust": 0, "hips": 0,
                   "wrist": 0, "thigh": 0},
    })
    measured = measurements.circumferences(cylinder_cm, lm, level_y=lambda n: 50.0)
    expect = 2 * np.pi * 15.0
    for field in ["waist", "bust", "underbust", "hips"]:
        assert abs(measured[field] - expect) < 0.5
