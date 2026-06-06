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


_BACK = {
    "waist_back_width": ("waist", "side_l_waist", "side_r_waist"),
    "back_width":       ("bust",  "side_l_bust",  "side_r_bust"),
    "hip_back_width":   ("hips",  "side_l_hips",  "side_r_hips"),
    "neck_w":           ("neck",  "side_l_neck",  "side_r_neck"),
}


def back_widths(mesh, lm, level_y=None, back_sign=-1.0):
    ly = level_y if level_y is not None else (lambda n: lm.level_y(mesh, n))
    out = {}
    for field, (level, lname, rname) in _BACK.items():
        if lname not in lm.vertices or rname not in lm.vertices:
            continue
        loops = geo.slice_loops(mesh, ly(level))
        loop = max(loops, key=lambda L: len(L))
        out[field] = geo.arc_between(loop, lm.point(mesh, lname),
                                     lm.point(mesh, rname),
                                     side="back", back_sign=back_sign)
    return out
