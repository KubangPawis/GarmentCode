"""Compute GarmentCode's 26 base measurements from a cm body mesh + landmarks.

Implemented from docs/Body Measurements GarmentCode.pdf (spec section 2.4).
"""
from . import geometry as geo


def circumferences(mesh, lm, level_y=None):
    """waist, bust, underbust, hips (longest loop) + wrist, leg_circ (nearest limb).

    Fields whose level is not available are skipped (a later task fills the gaps).
    """
    def ly(n):
        if level_y is not None:
            return level_y(n)
        return lm.level_y(mesh, n) if n in lm.levels else None

    out = {}
    for field in ["waist", "bust", "underbust", "hips"]:
        y = ly(field)
        if y is None:
            continue
        out[field] = geo.slice_perimeter(mesh, y, pick="longest")
    if "wrist_r" in lm.vertices and ly("wrist") is not None:
        p = lm.point(mesh, "wrist_r")
        out["wrist"] = geo.slice_perimeter(mesh, ly("wrist"), pick="nearest",
                                           point=(p[0], p[2]))
    if "thigh_r" in lm.vertices and ly("thigh") is not None:
        p = lm.point(mesh, "thigh_r")
        out["leg_circ"] = geo.slice_perimeter(mesh, ly("thigh"), pick="nearest",
                                              point=(p[0], p[2]))
    return out
