import numpy as np
import trimesh
from mpfb_ingest import mesh_io


def _person(height_units):
    # a 1.7-proportioned box scaled to the given Y extent (any unit)
    b = trimesh.creation.box(extents=[0.5, 1.0, 0.25])
    b.apply_translation([0, 0.5, 0])          # ground it
    b.apply_scale(height_units / 1.0)
    return b


def test_detects_metres_and_measures_height():
    m, rep = mesh_io.normalize(_person(1.73))   # already metres
    assert abs(rep["height_m"] - 1.73) < 0.02   # measured, NOT forced to 1.70
    assert abs(m.bounds[0][1]) < 1e-6           # grounded


def test_detects_decimetres():
    m, rep = mesh_io.normalize(_person(17.3))    # decimetres
    assert abs(rep["height_m"] - 1.73) < 0.02


def test_detects_makehuman_units():
    m, rep = mesh_io.normalize(_person(173.0))   # cm / MakeHuman raw
    assert abs(rep["height_m"] - 1.73) < 0.05


def test_explicit_override_still_forces():
    m, rep = mesh_io.normalize(_person(1.50), expected_height_m=1.80)
    assert abs(rep["height_m"] - 1.80) < 0.02
