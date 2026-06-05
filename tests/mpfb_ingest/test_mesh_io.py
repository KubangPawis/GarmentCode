import numpy as np
import trimesh
from mpfb_ingest import mesh_io


def _raw_human_proxy(scale):
    """Cylinder 'human' 1.7 units tall at the given unit scale, off-ground/off-centre."""
    cyl = trimesh.creation.cylinder(radius=0.15 * scale, height=1.7 * scale, sections=64)
    R = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0])
    cyl.apply_transform(R)
    cyl.apply_translation([5.0 * scale, 10.0 * scale, -3.0 * scale])
    return cyl


def test_normalize_metres_from_metre_input():
    mesh = _raw_human_proxy(scale=1.0)          # already metres
    out, report = mesh_io.normalize(mesh, expected_height_m=1.7)
    assert abs(report["height_m"] - 1.7) < 0.02
    assert abs(report["scale_to_m"] - 1.0) < 1e-6
    assert abs(out.bounds[0][1]) < 1e-6          # feet grounded at Y=0
    cx, _, cz = out.centroid
    assert abs(cx) < 1e-6 and abs(cz) < 1e-6     # centred X/Z


def test_normalize_metres_from_decimetre_input():
    mesh = _raw_human_proxy(scale=10.0)         # decimetres (MakeHuman quirk)
    out, report = mesh_io.normalize(mesh, expected_height_m=1.7)
    assert abs(report["scale_to_m"] - 0.1) < 1e-6
    assert abs(report["height_m"] - 1.7) < 0.02


def test_to_cm_scales_by_100():
    mesh = _raw_human_proxy(scale=1.0)
    out_m, _ = mesh_io.normalize(mesh, expected_height_m=1.7)
    cm = mesh_io.to_cm(out_m)
    assert abs(cm.bounds[1][1] - 170.0) < 2.0    # ~170 cm tall
