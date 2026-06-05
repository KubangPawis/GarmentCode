"""Pure geometry primitives. All inputs/outputs in centimetres (mesh pre-scaled)."""
import numpy as np
import igl

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
    pick='nearest'  -> loop whose centroid is nearest `point` (x,z) (one limb);
                       `point` is required for this mode.
    """
    loops = slice_loops(mesh, y)
    if not loops:
        raise ValueError(f"No cross-section at y={y}")
    if pick == "nearest":
        if point is None:
            raise ValueError("pick='nearest' requires a point=(x, z)")
        px, pz = point
        nearest = min(loops, key=lambda L: (L[:, 0].mean() - px) ** 2
                                            + (L[:, 2].mean() - pz) ** 2)
        return _loop_perimeter(nearest)
    return max(_loop_perimeter(L) for L in loops)


def euclidean(p, q):
    return float(np.linalg.norm(np.asarray(p, float) - np.asarray(q, float)))


def delta_y(p, q):
    return float(abs(float(p[1]) - float(q[1])))


def angle_to_horizontal(p, q):
    """Degrees between vector p->q and the horizontal (XZ) plane."""
    v = np.asarray(q, float) - np.asarray(p, float)
    horiz = float(np.linalg.norm([v[0], v[2]]))
    # Degenerate p == q gives horiz == 0 -> arctan2(0, 0) == 0.0 (returns 0 degrees).
    return float(np.degrees(np.arctan2(abs(v[1]), horiz)))


def angle_to_vertical(p, q):
    """Degrees between vector p->q and vertical (Y). 0 = perfectly vertical."""
    return 90.0 - angle_to_horizontal(p, q)


def geodesic(mesh, src_idx, dst_idx):
    """Exact surface geodesic distance between two vertex indices (cm)."""
    v = np.ascontiguousarray(mesh.vertices, dtype=np.float64)
    f = np.ascontiguousarray(mesh.faces, dtype=np.int64)
    d = igl.exact_geodesic(
        v, f,
        VS=np.array([src_idx], dtype=np.int64),
        VT=np.array([dst_idx], dtype=np.int64),
    )
    return float(np.atleast_1d(d)[0])


def arc_between(loop, a, b, side="back", back_sign=-1.0):
    """Length along an ordered closed loop polyline between the loop points
    nearest to a and b, taking the branch on the requested side.

    side='back' selects the branch whose mean Z has sign == back_sign
    (facing convention: front = +Z, back = -Z by default).
    """
    ia = int(np.argmin(np.linalg.norm(loop - np.asarray(a, float), axis=1)))
    ib = int(np.argmin(np.linalg.norm(loop - np.asarray(b, float), axis=1)))
    lo, hi = sorted((ia, ib))
    branch1 = loop[lo:hi + 1]
    branch2 = np.vstack([loop[hi:], loop[:lo + 1]])

    def _len(poly):
        return float(np.sum(np.linalg.norm(np.diff(poly, axis=0), axis=1)))

    if side == "back":
        z1, z2 = branch1[:, 2].mean(), branch2[:, 2].mean()
        if np.sign(z1) == np.sign(z2):
            # Branches not distinguishable front/back (symmetric or off-centre
            # cut) -> proxy to branch1; halves are equal in the symmetric case.
            chosen = branch1
        elif np.sign(z1) == np.sign(back_sign):
            chosen = branch1
        else:
            chosen = branch2
    else:
        chosen = branch1
    return _len(chosen)
