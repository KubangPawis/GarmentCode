"""Per-mesh geometric landmark derivation (topology-agnostic).

Works on any Y-up human mesh in centimetres (feet grounded at 0). Produces a
``Landmarks``-compatible object so ``measurements.compute_all`` runs unchanged.
Clean-room: implemented from the published GarmentCode measurement definitions
(predecessor spec section 2.4), not from the GPLv3 GarmentMeasurements tool.
"""
import numpy as np

from . import geometry as geo
from .landmarks import Landmarks


def _girth(mesh, y):
    try:
        return geo.central_perimeter(mesh, float(y))
    except Exception:
        return float("nan")


def find_levels(mesh):
    """Anatomical girth scan -> {crotch,hips,waist,bust,underbust,neck} as cm Y.

    Mirrors the validated calibrator scan (predecessor section 8.3) but on the
    arm-excluded central girth, so it is correct under a T-pose. Feet at y=0.

    One literal differs from the offline calibrator: the hips band starts at
    ``crotch + 1`` (not ``crotch``) so that hips > crotch is guaranteed when the
    crotch jump lands exactly on the pelvis maximum (as on the MakeHuman base).
    """
    top = float(mesh.bounds[1][1])
    ys = np.arange(2.0, top, 1.0)
    g = np.array([_girth(mesh, y) for y in ys])
    torso_max = float(np.nanmax(g))
    thr = 0.7 * torso_max

    def jump_up(lo, hi):
        for y, gv in zip(ys, g):
            if lo <= y <= hi and np.isfinite(gv) and gv > thr:
                return float(y)
        return None

    crotch = jump_up(40.0, top * 0.6) or (top * 0.45)
    arm = jump_up(crotch + 30.0, top * 0.85) or (top * 0.78)

    def band(lo, hi):
        m = (ys >= lo) & (ys <= hi) & np.isfinite(g)
        return ys[m], g[m]

    # hips band starts at crotch+1 to guarantee hips > crotch (the pelvis girth
    # maximum often coincides with the crotch jump y on a T-pose mesh).
    hy, hg = band(crotch + 1.0, crotch + 18.0)
    hips = float(hy[np.argmax(hg)])
    wy, wg = band(hips + 5.0, arm - 5.0)
    waist = float(wy[np.argmin(wg)])
    by, bg = band(waist + 5.0, arm - 2.0)
    bust = float(by[np.argmax(bg)])
    underbust = 0.5 * (waist + bust)
    ny, ng = band(arm, top * 0.95)
    neck = float(ny[np.argmin(ng)]) if len(ny) else (top * 0.9)

    return {"crotch": crotch, "hips": hips, "waist": waist,
            "bust": bust, "underbust": underbust, "neck": neck,
            "_arm_merge": arm}


def _nearest_vertex(mesh, point):
    d = np.asarray(mesh.vertices) - np.asarray(point, dtype=np.float64)
    return int(np.argmin(np.einsum("ij,ij->i", d, d)))


def _vertex_at_level(mesh, y, prefer_front=True):
    V = np.asarray(mesh.vertices)
    cost = np.abs(V[:, 1] - y) + 0.02 * np.abs(V[:, 0])
    if prefer_front:
        cost += 0.02 * (V[:, 2].max() - V[:, 2])
    return int(np.argmin(cost))


def _loop_side_points(loop):
    """(left_point, right_point) = extreme -X / +X points of a loop."""
    li = int(np.argmin(loop[:, 0]))
    ri = int(np.argmax(loop[:, 0]))
    return loop[li], loop[ri]


def _loop_peak_points(loop, axis=2, sign=1.0):
    """(left_peak, right_peak) split by X<0 / X>0, extreme along ``axis``*sign.

    sign=+1 picks the front-most (max +Z) per side -> bust peaks;
    sign=-1 picks the back-most (min Z)  per side -> bum peaks.
    """
    leftm = loop[loop[:, 0] < 0.0]
    rightm = loop[loop[:, 0] >= 0.0]

    def pick(half):
        if len(half) == 0:
            return None
        i = int(np.argmax(sign * half[:, axis]))
        return half[i]

    return pick(leftm), pick(rightm)


def derive(mesh, *, arm_pose="tpose"):
    """Return a Landmarks-compatible object with geometric landmark indices."""
    levels = find_levels(mesh)
    vtx, lvl = {}, {}

    # --- circumference level vertices (drive level_y for waist/bust/...) ------
    for name in ("waist", "bust", "underbust", "hips", "neck", "crotch"):
        lvl_name = "crotch_lvl" if name == "crotch" else name
        lvl[lvl_name] = _vertex_at_level(mesh, levels[name])

    # --- side-balance pairs at each level (back-section widths) ---------------
    for level, l_name, r_name in [
        ("waist", "side_l_waist", "side_r_waist"),
        ("bust",  "side_l_bust",  "side_r_bust"),
        ("hips",  "side_l_hips",  "side_r_hips"),
        ("neck",  "side_l_neck",  "side_r_neck"),
    ]:
        loop = geo.central_loop(mesh, levels[level])
        lp, rp = _loop_side_points(loop)
        vtx[l_name] = _nearest_vertex(mesh, lp)
        vtx[r_name] = _nearest_vertex(mesh, rp)

    # --- bust / bum peaks -----------------------------------------------------
    bust_loop = geo.central_loop(mesh, levels["bust"])
    bl, br = _loop_peak_points(bust_loop, axis=2, sign=1.0)
    if bl is not None and br is not None:
        vtx["bust_l"] = _nearest_vertex(mesh, bl)
        vtx["bust_r"] = _nearest_vertex(mesh, br)
    hip_loop = geo.central_loop(mesh, levels["hips"])
    ml, mr = _loop_peak_points(hip_loop, axis=2, sign=-1.0)
    if ml is not None and mr is not None:
        vtx["bum_l"] = _nearest_vertex(mesh, ml)
        vtx["bum_r"] = _nearest_vertex(mesh, mr)

    return Landmarks({"n_vertices_expected": 0, "vertices": vtx, "levels": lvl})
