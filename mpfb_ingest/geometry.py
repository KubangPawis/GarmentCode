"""Pure geometry primitives. All inputs/outputs in centimetres (mesh pre-scaled)."""
import numpy as np

_Y = np.array([0.0, 1.0, 0.0])


def slice_loops(mesh, y):
    """Return a list of ordered (N,3) polylines where the mesh crosses plane Y=y."""
    section = mesh.section(plane_origin=[0.0, y, 0.0], plane_normal=_Y)
    if section is None:
        return []
    return [np.asarray(d, dtype=np.float64) for d in section.discrete]


def _loop_perimeter(loop):
    d = np.diff(np.vstack([loop, loop[0]]), axis=0)   # close the loop
    return float(np.sum(np.linalg.norm(d, axis=1)))


def slice_perimeter(mesh, y, pick="longest", point=None):
    """Perimeter of one closed loop at height y.

    pick='longest'  -> the longest loop (torso girth, ignores stray loops)
    pick='nearest'  -> loop whose centroid is nearest `point` (x,z) (one limb)
    """
    loops = slice_loops(mesh, y)
    if not loops:
        raise ValueError(f"No cross-section at y={y}")
    if pick == "nearest" and point is not None:
        px, pz = point
        loops.sort(key=lambda L: (L[:, 0].mean() - px) ** 2 + (L[:, 2].mean() - pz) ** 2)
        return _loop_perimeter(loops[0])
    return max(_loop_perimeter(L) for L in loops)
