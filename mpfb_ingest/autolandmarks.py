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
