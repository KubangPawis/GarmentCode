import numpy as np
import trimesh
from mpfb_ingest.landmarks import Landmarks
from mpfb_ingest import measurements


def test_euclidean_and_dy_and_geodesic(tiny_mesh):
    lm = Landmarks({
        "n_vertices_expected": 4,
        "vertices": {"collar_l": 0, "collar_r": 1,     # (0,0,0)-(30,0,0) -> 30
                     "nape": 0, "crown": 2,            # (0,0,0)-(0,40,0) -> 40 / dy 40
                     "shoulder_r": 0, "wrist_r": 3},   # geodesic 0->3 on flat = 50
        "levels": {"waist": 0, "hips": 2},
    })
    out = measurements.distances(tiny_mesh, lm)
    assert abs(out["shoulder_w"] - 30.0) < 1e-6
    assert abs(out["head_l"] - 40.0) < 1e-6
    assert abs(out["height"] - 40.0) < 1e-6                # total Y extent
    assert abs(out["hips_line"] - 40.0) < 1e-6             # |waist y0 - hips y40|
    assert abs(out["arm_length"] - 50.0) < 1e-4            # geodesic
