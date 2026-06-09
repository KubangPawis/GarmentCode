import numpy as np
import trimesh
import pytest


def _ycyl(radius, y0, y1, sections=48, xz=(0.0, 0.0)):
    """Solid cylinder along +Y from y0..y1 centred at (x,z)=xz."""
    h = y1 - y0
    c = trimesh.creation.cylinder(radius=radius, height=h, sections=sections)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0]))
    c.apply_translation([xz[0], y0 + h / 2.0, xz[1]])
    return c


def _xcyl(radius, x0, x1, y, sections=24):
    """Solid cylinder along +X from x0..x1 at height y (a T-pose arm)."""
    w = x1 - x0
    c = trimesh.creation.cylinder(radius=radius, height=w, sections=sections)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0]))
    c.apply_translation([x0 + w / 2.0, y, 0.0])
    return c


def _tpose_parts():
    """Crude T-pose humanoid parts (centimetre scale).

    torso  : X in [-16, 16], Y in [80, 150]
    R arm  : X in [17, 55] at Y=142   (clear of the torso radius 16)
    L arm  : X in [-55, -17] at Y=142
    R leg  : centred x=+8, Y in [0, 80]
    L leg  : centred x=-8, Y in [0, 80]
    head   : centred Y=161 (so the mesh top is ~172)
    """
    head = trimesh.creation.icosphere(radius=11.0)
    head.apply_translation([0, 161, 0])
    return [
        _ycyl(16.0, 80.0, 150.0),
        _xcyl(5.0, 17.0, 55.0, 142.0),
        _xcyl(5.0, -55.0, -17.0, 142.0),
        _ycyl(9.0, 0.0, 80.0, xz=(8.0, 0.0)),
        _ycyl(9.0, 0.0, 80.0, xz=(-8.0, 0.0)),
        head,
    ]


@pytest.fixture
def tpose_cm():
    """T-pose humanoid in centimetres (concatenated, not unioned)."""
    return trimesh.util.concatenate(_tpose_parts())


@pytest.fixture
def tpose_m(tpose_cm):
    """Same humanoid scaled to metres, feet grounded at Y=0, centred X/Z."""
    m = tpose_cm.copy()
    m.apply_scale(0.01)
    (x0, _, z0), (x1, _, z1) = m.bounds
    m.apply_translation([-0.5 * (x0 + x1), -m.bounds[0][1], -0.5 * (z0 + z1)])
    return m


@pytest.fixture
def tiny_obj(tmp_path):
    """A 4-vertex draped-garment stand-in saved as OBJ, returns its path."""
    v = np.array([[0, 100, 0], [10, 100, 0], [0, 110, 0], [10, 110, 0]], dtype=float)
    f = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int64)
    p = tmp_path / "tiny_sim.obj"
    trimesh.Trimesh(vertices=v, faces=f, process=False).export(str(p))
    return p
