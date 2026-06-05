import numpy as np
from mpfb_ingest import geometry


def test_euclidean(tiny_mesh):
    p = tiny_mesh.vertices[0]   # (0,0,0)
    q = tiny_mesh.vertices[3]   # (30,40,0) -> 50
    assert abs(geometry.euclidean(p, q) - 50.0) < 1e-9


def test_delta_y(tiny_mesh):
    p = tiny_mesh.vertices[0]   # y=0
    q = tiny_mesh.vertices[2]   # y=40
    assert abs(geometry.delta_y(p, q) - 40.0) < 1e-9


def test_angle_to_horizontal(tiny_mesh):
    # vector (30,40) -> angle above horizontal = atan2(40,30) ~ 53.13 deg
    p = tiny_mesh.vertices[0]
    q = tiny_mesh.vertices[3]
    assert abs(geometry.angle_to_horizontal(p, q) - 53.130102) < 1e-3


def test_geodesic_on_flat_quad_equals_euclidean(tiny_mesh):
    # flat sheet: surface geodesic from v0 to v3 == straight line 50
    d = geometry.geodesic(tiny_mesh, 0, 3)
    assert abs(d - 50.0) < 1e-6


def test_back_arc_half_circle(cylinder_cm):
    # two opposite points on a radius-15 cylinder slice -> half perimeter = pi*15
    loops = geometry.slice_loops(cylinder_cm, y=50.0)
    loop = loops[0]
    left = loop[np.argmin(loop[:, 0])]
    right = loop[np.argmax(loop[:, 0])]
    arc = geometry.arc_between(loop, left, right, side="back")
    assert abs(arc - np.pi * 15.0) < 0.1


def test_angle_to_vertical(tiny_mesh):
    p = tiny_mesh.vertices[0]
    q = tiny_mesh.vertices[3]
    assert abs(geometry.angle_to_vertical(p, q)
               - (90.0 - geometry.angle_to_horizontal(p, q))) < 1e-9
