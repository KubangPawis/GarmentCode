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


def _ycyl(radius, y0, y1, sections=48, xz=(0.0, 0.0)):
    """Solid cylinder along +Y from y0..y1 centred at (x,z)=xz (cm)."""
    h = y1 - y0
    c = trimesh.creation.cylinder(radius=radius, height=h, sections=sections)
    R = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0])
    c.apply_transform(R)                      # axis Z -> Y
    c.apply_translation([xz[0], y0 + h / 2.0, xz[1]])
    return c


def _xcyl(radius, x0, x1, y, sections=24):
    """Solid cylinder along +X from x0..x1 at height y (a T-pose arm)."""
    w = x1 - x0
    c = trimesh.creation.cylinder(radius=radius, height=w, sections=sections)
    # default axis Z -> rotate to X
    R = trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0])
    c.apply_transform(R)
    c.apply_translation([x0 + w / 2.0, y, 0.0])
    return c


@pytest.fixture
def tpose_body_cm():
    """A crude T-pose humanoid in cm: torso + 2 horizontal arms + 2 legs + head.

    Concatenated (not boolean-unioned) so a horizontal cut yields the torso loop
    PLUS separate side loops for the arms -- exactly the arm-exclusion case.
    Arms start at x=±17 (just outside the torso radius=16) and are centred at
    y=142 so a cut at y=140 crosses the lateral cylinder wall cleanly (not caps).
    A section at y=140 yields 3 loops:
      - torso: X in [-16, 16], perimeter ~100.5 cm (2*pi*16)
      - right arm: X in [17, 55], perimeter ~94 cm (2*(38+10))
      - left  arm: X in [-55,-17], perimeter ~94 cm
    """
    head = trimesh.creation.icosphere(radius=11.0)
    head.apply_translation([0, 161, 0])
    parts = [
        _ycyl(16.0, 80.0, 150.0),                 # torso
        _xcyl(5.0, 17.0, 55.0, 142.0),            # right arm (+X), clear of torso
        _xcyl(5.0, -55.0, -17.0, 142.0),          # left arm (-X), clear of torso
        _ycyl(9.0, 0.0, 80.0, xz=(8.0, 0.0)),     # right leg
        _ycyl(9.0, 0.0, 80.0, xz=(-8.0, 0.0)),    # left leg
        head,                                       # head
    ]
    return trimesh.util.concatenate(parts)
