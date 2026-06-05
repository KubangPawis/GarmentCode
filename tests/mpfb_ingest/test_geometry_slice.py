import numpy as np
from mpfb_ingest import geometry


def test_perimeter_at_height_matches_circle(cylinder_cm):
    # cylinder radius 15 cm -> circumference 2*pi*15 ~= 94.248
    p = geometry.slice_perimeter(cylinder_cm, y=50.0)
    assert abs(p - 2 * np.pi * 15.0) < 0.5


def test_slice_loops_returns_ordered_polyline(cylinder_cm):
    loops = geometry.slice_loops(cylinder_cm, y=50.0)
    assert len(loops) == 1
    loop = loops[0]
    assert loop.shape[1] == 3
    assert len(loop) > 16
