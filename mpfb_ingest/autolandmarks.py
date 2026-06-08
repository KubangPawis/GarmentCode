"""Per-mesh geometric landmark derivation (topology-agnostic).

Works on any Y-up human mesh in centimetres (feet grounded at 0). Produces a
``Landmarks``-compatible object so ``measurements.compute_all`` runs unchanged.
Clean-room: implemented from the published GarmentCode measurement definitions
(predecessor spec section 2.4), not from the GPLv3 GarmentMeasurements tool.
"""
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from . import geometry as geo
from .landmarks import Landmarks


def _girth(mesh, y, keep_x):
    try:
        return geo.torso_perimeter(mesh, float(y), keep_x)
    except Exception:
        return float("nan")


def _full_girth(mesh, y):
    try:
        return geo.slice_perimeter(mesh, float(y), pick="longest")
    except Exception:
        return float("nan")


def find_levels(mesh):
    """Anatomical girth scan -> {crotch,hips,waist,bust,underbust,neck,keep_x,
    _arm_merge} as cm Y. Arm-aware: uses an X-clipped torso girth for level
    values and the full/clipped girth ratio to find (and avoid) the arm zone,
    so it is correct under a true T-pose where arms merge into the torso loop.
    Feet at y=0.
    """
    top = float(mesh.bounds[1][1])
    keep_x = 1.6 * geo.torso_halfwidth(mesh)
    ys = np.arange(2.0, top, 1.0)
    gc = np.array([_girth(mesh, y, keep_x) for y in ys])   # clipped (arm-excluded)
    gf = np.array([_full_girth(mesh, y) for y in ys])      # full (arms included)

    def band(arr, lo, hi):
        m = (ys >= lo) & (ys <= hi) & np.isfinite(arr)
        return ys[m], arr[m]

    torso_max = float(np.nanmax(gc))
    thr = 0.7 * torso_max

    # crotch: legs merge into the pelvis -> first strong clipped-girth jump.
    crotch = None
    for y, gv in zip(ys, gc):
        if 40.0 <= y <= 0.6 * top and np.isfinite(gv) and gv > thr:
            crotch = float(y)
            break
    if crotch is None:
        crotch = 0.45 * top

    # arm zone: lowest height in the upper body where the FULL girth exceeds the
    # clipped girth by >50% (an arm has entered the slice). Cap torso bands below.
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = gf / np.where(gc > 1.0, gc, np.nan)
    arm_merge = None
    for y, r in zip(ys, ratio):
        if crotch + 30.0 <= y <= 0.9 * top and np.isfinite(r) and r > 1.5:
            arm_merge = float(y)
            break
    if arm_merge is None:
        arm_merge = 0.80 * top

    hy, hg = band(gc, crotch + 1.0, crotch + 18.0)
    hips = float(hy[np.argmax(hg)])
    # bust: widest clipped girth between the hips and just below the arm zone.
    by, bg = band(gc, hips + 10.0, arm_merge - 3.0)
    bust = float(by[np.argmax(bg)]) if len(by) else (hips + 0.25 * (arm_merge - hips))
    # waist: narrowest clipped girth between the hips and the bust.
    wy, wg = band(gc, hips + 5.0, bust - 3.0)
    waist = float(wy[np.argmin(wg)]) if len(wy) else (0.5 * (hips + bust))
    underbust = 0.5 * (waist + bust)
    # neck: narrowest clipped girth ABOVE the arm zone (true neck, no skull loop).
    ny, ng = band(gc, arm_merge + 3.0, 0.95 * top)
    neck = float(ny[np.argmin(ng)]) if len(ny) else (0.88 * top)

    return {"crotch": crotch, "hips": hips, "waist": waist,
            "bust": bust, "underbust": underbust, "neck": neck,
            "keep_x": keep_x, "_arm_merge": arm_merge}


def _nearest_vertex(mesh, point):
    d = np.asarray(mesh.vertices) - np.asarray(point, dtype=np.float64)
    return int(np.argmin(np.einsum("ij,ij->i", d, d)))


def _nearest_vertex_in_mask(V, point, mask):
    """Nearest vertex index among those indicated by boolean mask."""
    candidates = np.where(mask)[0]
    d = V[candidates] - np.asarray(point, dtype=np.float64)
    return int(candidates[np.argmin(np.einsum("ij,ij->i", d, d))])


def _body_component_mask(mesh):
    """Boolean mask: True for vertices on the largest Y-span mesh component.

    Multi-component meshes (MPFB base has 17 islands) need this so geodesic
    anchors (nape, neck_base) aren't snapped to interior skull cavities that
    happen to be spatially closer.
    """
    F = mesh.faces
    n = len(mesh.vertices)
    row = np.concatenate([F[:, 0], F[:, 1], F[:, 2],
                          F[:, 1], F[:, 2], F[:, 0]])
    col = np.concatenate([F[:, 1], F[:, 2], F[:, 0],
                          F[:, 0], F[:, 1], F[:, 2]])
    adj = csr_matrix((np.ones(len(row)), (row, col)), shape=(n, n))
    _, labels = connected_components(adj, directed=False)
    V = np.asarray(mesh.vertices)
    best_comp, best_span = 0, 0.0
    for c in np.unique(labels):
        cv = np.where(labels == c)[0]
        span = float(V[cv, 1].max() - V[cv, 1].min())
        if span > best_span:
            best_span = span
            best_comp = c
    return labels == best_comp, labels


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


def _back_point(loop):
    """Back-most (min Z) point of a loop."""
    return loop[int(np.argmin(loop[:, 2]))]


def _front_center_point(loop):
    """Front-most (max Z) point nearest the X axis of a loop."""
    fz = loop[:, 2].max()
    near = loop[loop[:, 2] >= fz - 1.0]
    return near[int(np.argmin(np.abs(near[:, 0])))]


def _arm_loops(mesh, y, x_min_abs):
    """Section loops whose |mean X| exceeds x_min_abs (the arms at height y)."""
    out = []
    for L in geo.slice_loops(mesh, y):
        if abs(float(np.mean(L[:, 0]))) >= x_min_abs:
            out.append(L)
    return out


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

    arm_merge = levels["_arm_merge"]
    V = np.asarray(mesh.vertices)
    top = float(mesh.bounds[1][1])

    # Compute connected component labels once; body_mask = largest Y-span island.
    # Used to anchor geodesic landmarks on the exterior body surface rather than
    # interior cavities (skull, mouth) that can be spatially closer.
    body_mask, comp_labels = _body_component_mask(mesh)

    # crown / nape / neck base ------------------------------------------------
    vtx["crown"] = int(np.argmax(V[:, 1]))
    neck_loop = geo.central_loop(mesh, levels["neck"])
    # Use body-surface-constrained nearest vertex to avoid interior skull verts.
    vtx["nape"] = _nearest_vertex_in_mask(V, _back_point(neck_loop), body_mask)
    vtx["neck_base"] = _nearest_vertex_in_mask(V, _front_center_point(neck_loop), body_mask)
    lvl["nape_lvl"] = vtx["nape"]

    # shoulders / collar (widest torso just below the arm merge) --------------
    sh_y = max(levels["bust"] + 2.0, arm_merge - 4.0)
    sh_loop = geo.central_loop(mesh, sh_y)
    _sl, sr = _loop_side_points(sh_loop)
    vtx["shoulder_r"] = _nearest_vertex(mesh, sr)   # broad shoulder tip (armscye/arm)

    # clavicle ends: front extreme-X at the collar level. Scan UP from the bust
    # for the highest torso level whose (arm-clipped) front-half X span is in the
    # clavicle band [35,48] cm, stopping when the span explodes (>55 -> deltoid /
    # merged arm zone) or collapses (<30 -> neck). This is robust to a true
    # T-pose where the neck-minus-offset heuristic would land in the thin neck.
    keep_x = levels["keep_x"]

    def _front_xspan(loop):
        front = loop[loop[:, 2] >= loop[:, 2].mean()]   # front half
        if len(front) < 2:
            front = loop
        fx = front[:, 0]
        fxc = fx[np.abs(fx) <= keep_x]                   # drop arm excursions
        if len(fxc) < 2:
            fxc = fx
        return float(fxc.max() - fxc.min())

    col_y = levels["neck"] - 6.0                         # heuristic fallback
    best_y = None
    for _cy in np.arange(levels["bust"] + 1.0, levels["neck"] + 1.0, 1.0):
        try:
            span = _front_xspan(geo.central_loop(mesh, float(_cy)))
        except Exception:
            continue
        if 35.0 <= span <= 48.0:
            best_y = float(_cy)                           # topmost good level wins
        elif span > 55.0 or span < 30.0:
            break
    if best_y is not None:
        col_y = best_y
    col_loop = geo.central_loop(mesh, col_y)
    _front = col_loop[col_loop[:, 2] >= col_loop[:, 2].mean()]   # front half
    if len(_front) < 2:
        _front = col_loop
    _front = _front[np.abs(_front[:, 0]) <= keep_x] if np.any(np.abs(_front[:, 0]) <= keep_x) else _front
    vtx["collar_l"] = _nearest_vertex(mesh, _front[int(np.argmin(_front[:, 0]))])
    vtx["collar_r"] = _nearest_vertex(mesh, _front[int(np.argmax(_front[:, 0]))])

    # armpit_r: inner edge of the RIGHT (+X) arm at the lowest height the arm is
    # still a distinct side loop (the underarm crease).
    half_w = abs(float(sh_loop[:, 0].max()))
    armpit_pt = sr
    for _ay in np.arange(arm_merge + 8.0, arm_merge - 16.0, -1.0):   # scan downward
        arms = [L for L in _arm_loops(mesh, float(_ay), 0.45 * half_w)
                if float(np.mean(L[:, 0])) > 0.0]                    # right side only
        if arms:
            arm = min(arms, key=lambda L: abs(float(np.mean(L[:, 0]))))  # nearest torso
            armpit_pt = arm[int(np.argmin(arm[:, 0]))]              # inner edge toward torso
    vtx["armpit_r"] = _nearest_vertex(mesh, armpit_pt)

    # wrist: anatomical wrist position on a T-pose (horizontal) arm.
    # The far-X vertex (fingertip) gives a ~3 cm Y-slice which is not a wrist
    # girth.  We instead find the arm component's "wrist zone" — the first Y
    # level above the fingertip where the arm's horizontal cross-section
    # broadens to a forearm-like perimeter (>= 12 cm).  That vertex is used
    # both as wrist_r (for pick="nearest") and as lvl["wrist"] (for level_y).
    # For geodesic arm_length the far-X fingertip index is what geometry.geodesic
    # uses after falling back to Euclidean across components.
    vtx["wrist_r"] = int(np.argmax(V[:, 0]))  # fingertip for arm_length geodesic

    # Find arm-component Y level where wrist-girth slice is plausible.
    arm_comp = int(comp_labels[vtx["wrist_r"]])
    arm_comp_verts = np.where(comp_labels == arm_comp)[0]
    wrist_lvl_idx = vtx["wrist_r"]  # fallback = fingertip
    wrist_min_y = float(V[arm_comp_verts, 1].min())
    for _wy in np.arange(wrist_min_y + 4.0,
                          float(V[arm_comp_verts, 1].max()) + 1.0, 1.0):
        loops_at_wy = [L for L in geo.slice_loops(mesh, _wy)
                       if abs(float(np.mean(L[:, 0]))) > 30.0]
        if loops_at_wy:
            best = max(loops_at_wy, key=lambda L: geo._loop_perimeter(L))
            if geo._loop_perimeter(best) >= 12.0:
                # Pick the arm-component vertex with Y nearest to this slice
                # height so level_y(mesh,"wrist") returns _wy, not a stray Y.
                wrist_lvl_idx = int(
                    arm_comp_verts[
                        np.argmin(np.abs(V[arm_comp_verts, 1] - _wy))])
                break
    lvl["wrist"] = wrist_lvl_idx

    # Thigh: scan just below the crotch to find a single-leg loop at upper-thigh
    # level.  crotch - 10 to crotch - 20 cm typically gives a 45-60 cm upper
    # thigh girth on a standard body.  Avoid crotch - 5 which can still be the
    # merged-legs blob; avoid 0.5*crotch which is mid-calf on a 170 cm body.
    thigh_y = None
    for _ty in np.arange(levels["crotch"] - 8.0, levels["crotch"] - 25.0, -1.0):
        loops_here = geo.slice_loops(mesh, float(_ty))
        off_axis = [L for L in loops_here
                    if abs(float(np.mean(L[:, 0]))) > 5.0]
        if off_axis:
            thigh_y = float(_ty)
            break
    if thigh_y is not None:
        all_thigh_loops = [L for L in geo.slice_loops(mesh, thigh_y)
                           if abs(float(np.mean(L[:, 0]))) > 5.0]
        if all_thigh_loops:
            thigh_loop = max(all_thigh_loops,
                             key=lambda L: geo._loop_perimeter(L))
            vtx["thigh_r"] = _nearest_vertex(mesh, thigh_loop[0])
            lvl["thigh"] = vtx["thigh_r"]

    # geodesic / angle anchors at the waist -----------------------------------
    waist_loop = geo.central_loop(mesh, levels["waist"])
    vtx["waist_back"] = _nearest_vertex(mesh, _back_point(waist_loop))
    vtx["waist_front"] = _nearest_vertex(mesh, _front_center_point(waist_loop))
    wl, wr = _loop_side_points(waist_loop)
    vtx["waist_side"] = _nearest_vertex(mesh, wr)
    hip_loop = geo.central_loop(mesh, levels["hips"])
    hp_l, hp_r = _loop_side_points(hip_loop)
    vtx["hip_side"] = _nearest_vertex(mesh, hp_r)

    return Landmarks({"n_vertices_expected": 0, "vertices": vtx, "levels": lvl})
