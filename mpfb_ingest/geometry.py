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


def torso_halfwidth(mesh):
    """Robust torso half-width (cm): the 97th-percentile |X| over the mid-lower
    body band, where a T-pose has no arms (arms sit at shoulder height)."""
    V = np.asarray(mesh.vertices)
    top = float(V[:, 1].max())
    band = (V[:, 1] > 0.30 * top) & (V[:, 1] < 0.52 * top)
    xs = np.abs(V[band, 0]) if band.any() else np.abs(V[:, 0])
    return float(np.percentile(xs, 97))


def central_loop(mesh, y, keep_x=None):
    """Section loop straddling the body axis at height y, with arm/leg excursions
    excluded. First pick the loop whose mean X is nearest the body axis (x~=0);
    then clip points with |X| > keep_x (the arms) and bridge the armpit gaps, so
    a T-pose arm that merges into the torso loop is excluded. keep_x defaults to
    1.6 * torso_halfwidth(mesh). Returns the ordered (N,3) polyline.
    """
    loops = slice_loops(mesh, y)
    if not loops:
        raise ValueError(f"No cross-section at y={y}")
    substantial = [L for L in loops if _loop_perimeter(L) >= 8.0]
    pool = substantial if substantial else loops
    abs_mx = [abs(float(np.mean(L[:, 0]))) for L in pool]
    mx_max = max(abs_mx) if abs_mx else 0.0
    threshold = max(0.5 * mx_max, 1e-6)
    central = [L for L, mx in zip(pool, abs_mx) if mx <= threshold] or pool
    loop = max(central, key=_loop_perimeter)

    if keep_x is None:
        keep_x = 1.6 * torso_halfwidth(mesh)
    mask = np.abs(loop[:, 0]) <= keep_x
    if mask.any() and not mask.all():
        loop = loop[mask]
    return loop


def central_perimeter(mesh, y):
    """Perimeter (cm) of the central torso loop at height y (arm-excluded)."""
    return _loop_perimeter(central_loop(mesh, y))


def torso_perimeter(mesh, y, keep_x):
    """Tape-measure torso girth (cm) at height y: the central loop with arm
    excursions (|X| > keep_x) clipped away and the armpit gaps bridged. Robust
    to T-pose arms that merge into the torso loop."""
    loop = central_loop(mesh, y)
    mask = np.abs(loop[:, 0]) <= keep_x
    if mask.all() or not mask.any():
        return _loop_perimeter(loop)
    return _loop_perimeter(loop[mask])


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
    """Exact surface geodesic distance between two vertex indices (cm).

    The mesh is welded (duplicate vertices merged) before the geodesic so that
    meshes loaded unprocessed -- which split shared edges into many spurious
    'components' -- are treated as the single connected surface they represent.
    Falls back to Euclidean only when the welded endpoints are genuinely on
    different connected components (igl then returns 0).
    """
    import trimesh
    v = np.ascontiguousarray(mesh.vertices, dtype=np.float64)
    f = np.asarray(mesh.faces)
    uniq, inv = trimesh.grouping.unique_rows(v)
    Vw = np.ascontiguousarray(v[uniq], dtype=np.float64)
    Fw = np.ascontiguousarray(inv[f], dtype=np.int64)
    s, t = int(inv[src_idx]), int(inv[dst_idx])
    d = igl.exact_geodesic(
        Vw, Fw,
        VS=np.array([s], dtype=np.int64), FS=np.array([], dtype=np.int64),
        VT=np.array([t], dtype=np.int64), FT=np.array([], dtype=np.int64),
    )
    result = float(np.atleast_1d(d)[0])
    if result < 1e-6 and s != t:
        result = euclidean(v[src_idx], v[dst_idx])
    return result


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
