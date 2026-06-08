"""Compute GarmentCode's 26 base measurements from a cm body mesh + landmarks.

Implemented from docs/Body Measurements GarmentCode.pdf (spec section 2.4).
"""
from collections import OrderedDict
from . import geometry as geo


def circumferences(mesh, lm, level_y=None):
    """waist, bust, underbust, hips (arm-excluded central loop) + wrist, leg_circ (nearest limb).

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
        out[field] = geo.central_perimeter(mesh, y)
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


_EUCLID = {
    "shoulder_w":    ("collar_l", "collar_r"),
    "head_l":        ("nape", "crown"),
    "bust_points":   ("bust_l", "bust_r"),
    "bum_points":    ("bum_l", "bum_r"),
    "armscye_depth": ("shoulder_r", "armpit_r"),
    "arm_length":    ("shoulder_r", "wrist_r"),   # geodesic (see below) overrides
}
_DELTA_Y = {
    "hips_line":       ("waist", "hips"),
    "crotch_hip_diff": ("hips", "crotch_lvl"),
    "vert_bust_line":  ("nape_lvl", "bust"),
}
_GEODESIC = {
    "waist_line":           ("nape", "waist_back"),
    "bust_line":            ("shoulder_r", "bust_r"),
    "waist_over_bust_line": ("neck_base", "waist_front"),
    "arm_length":           ("shoulder_r", "wrist_r"),
}


def distances(mesh, lm, level_y=None):
    ly = level_y if level_y is not None else (lambda n: lm.level_y(mesh, n))
    out = {}
    out["height"] = float(mesh.bounds[1][1] - mesh.bounds[0][1])

    for field, (a, b) in _EUCLID.items():
        if field == "arm_length":
            continue   # prefer geodesic version below
        if a in lm.vertices and b in lm.vertices:
            out[field] = geo.euclidean(lm.point(mesh, a), lm.point(mesh, b))

    for field, (a, b) in _DELTA_Y.items():
        if a in lm.levels and b in lm.levels:
            out[field] = abs(ly(a) - ly(b))

    for field, (a, b) in _GEODESIC.items():
        if a in lm.vertices and b in lm.vertices:
            out[field] = geo.geodesic(mesh, lm.vertex_index(a), lm.vertex_index(b))
    return out


def angles(mesh, lm, arm_pose_angle):
    out = {"arm_pose_angle": float(arm_pose_angle)}
    if "neck_base" in lm.vertices and "collar_r" in lm.vertices:
        out["shoulder_incl"] = geo.angle_to_horizontal(
            lm.point(mesh, "neck_base"), lm.point(mesh, "collar_r"))
    if "waist_side" in lm.vertices and "hip_side" in lm.vertices:
        out["hip_inclination"] = geo.angle_to_vertical(
            lm.point(mesh, "waist_side"), lm.point(mesh, "hip_side"))
    return out


def compute_all(mesh, lm, arm_pose_angle, level_y=None):
    """Run every group; return an OrderedDict of all available base fields."""
    result = OrderedDict()
    result.update(circumferences(mesh, lm, level_y=level_y))
    result.update(back_widths(mesh, lm, level_y=level_y))
    result.update(distances(mesh, lm, level_y=level_y))
    result.update(angles(mesh, lm, arm_pose_angle=arm_pose_angle))
    return result
