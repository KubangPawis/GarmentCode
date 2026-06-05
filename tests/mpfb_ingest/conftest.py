import numpy as np
import trimesh
import pytest


@pytest.fixture
def cylinder_cm():
    """Upright cylinder as a torso proxy, already in cm.
    radius=15 cm, height=100 cm, axis = Y. Perimeter at any slice = 2*pi*15.
    """
    # trimesh cylinder is built along Z; rotate so axis is +Y.
    cyl = trimesh.creation.cylinder(radius=15.0, height=100.0, sections=256)
    R = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0])
    cyl.apply_transform(R)
    # ground it: min Y -> 0
    cyl.apply_translation([0, -cyl.bounds[0][1], 0])
    return cyl


@pytest.fixture
def tiny_mesh():
    """A 4-vertex tri-pair with known coordinates (cm) for euclidean/angle tests.

    v0 = (0,0,0)   v1 = (30,0,0)   v2 = (0,40,0)   v3 = (30,40,0)
    """
    v = np.array([[0, 0, 0], [30, 0, 0], [0, 40, 0], [30, 40, 0]], dtype=np.float64)
    f = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int64)
    return trimesh.Trimesh(vertices=v, faces=f, process=False)
