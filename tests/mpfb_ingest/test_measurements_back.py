import numpy as np
from mpfb_ingest.landmarks import Landmarks
from mpfb_ingest import measurements


def test_back_widths_on_cylinder(cylinder_cm):
    loop = measurements.geo.slice_loops(cylinder_cm, 50.0)[0]
    li = int(np.argmin(loop[:, 0]))
    ri = int(np.argmax(loop[:, 0]))
    # map those loop points to nearest mesh vertices for landmark indices
    vi = lambda pt: int(np.argmin(np.linalg.norm(cylinder_cm.vertices - pt, axis=1)))
    lm = Landmarks({
        "n_vertices_expected": len(cylinder_cm.vertices),
        "vertices": {"side_l_waist": vi(loop[li]), "side_r_waist": vi(loop[ri])},
        "levels": {"waist": 0},
    })
    out = measurements.back_widths(cylinder_cm, lm, level_y=lambda n: 50.0)
    assert abs(out["waist_back_width"] - np.pi * 15.0) < 1.0
