"""Quick-pass landmark calibration for the MakeHuman/MPFB base topology.

Clean-room: derives landmark vertex indices purely from the mesh geometry and
MakeHuman's own CC0 measurement morph-target regions (``measure-*.target``).
Does not use the GPLv3 GarmentMeasurements tool.

What it produces (run once, committed as data):
  * ``mpfb_ingest/data/mpfb_base_body.obj`` -- the body-only mesh (MakeHuman
    helper geometry stripped: eyes, teeth, joint cubes...). The generic
    ingestion CLI runs on THIS file, so no pipeline change is needed.
  * ``mpfb_ingest/data/makehuman_landmarks.json`` -- vertex indices in the
    body-only mesh's compact numbering.

Quick-pass scope: the four torso circumference LEVELS (waist/bust/underbust/
hips) are found by an anatomical girth scan; the side-landmark PAIRS come from
the CC0 measure rings. Everything else (geodesic anchors, bust points, limb
circumferences, angles) is left to the CLI's ``--fill-defaults`` for now and
refined in a later full-fidelity pass.

Usage:
  MPFB_BASE_OBJ=/path/to/base.obj .venv/bin/python scripts/calibrate_landmarks.py
  # default path: the MPFB Blender-extension data dir on this machine.
"""
import os
import json
import gzip
from pathlib import Path

import numpy as np
import trimesh

from mpfb_ingest import mesh_io, geometry as geo

# --- MakeHuman hm08 base-mesh constants -------------------------------------
# Body proper occupies vertex indices [0, BODY_SPLIT); everything at or above
# is helper geometry (eyes/teeth/tongue/genitals/joint cubes) that must not
# take part in slicing or bounds.
BODY_SPLIT = 13380

_DEF_DATA = ("/mnt/c/Users/KubangPawis/AppData/Roaming/Blender Foundation/"
             "Blender/5.1/extensions/blender_org/mpfb/data")

_OUT_DIR = Path("mpfb_ingest/data")
_BODY_OBJ = _OUT_DIR / "mpfb_base_body.obj"
_JSON = _OUT_DIR / "makehuman_landmarks.json"

# CC0 measure-target rings used for side-landmark pairs and the neck level.
_RINGS = {
    "neck":      "neck/measure-neck-circ-incr.target.gz",
    "bust":      "torso/measure-bust-circ-incr.target.gz",
    "underbust": "torso/measure-underbust-circ-incr.target.gz",
    "waist":     "torso/measure-waist-circ-incr.target.gz",
    "hips":      "torso/measure-hips-circ-incr.target.gz",
}


def _body_only(raw):
    """Return (compact_body_mesh, orig_to_compact_index_map).

    Keep only faces whose vertices all lie in the body range, then compact the
    referenced vertices into a fresh 0..N-1 numbering (deterministic: ascending
    original index). Helper geometry and its stray slice loops are gone.
    """
    V = np.asarray(raw.vertices)
    F = np.asarray(raw.faces)
    keep = (F < BODY_SPLIT).all(axis=1)
    Fb = F[keep]
    used = np.unique(Fb)
    remap = -np.ones(len(V), dtype=np.int64)
    remap[used] = np.arange(len(used))
    body = trimesh.Trimesh(vertices=V[used], faces=remap[Fb], process=False)
    return body, remap


def _read_target_indices(path):
    """Vertex indices touched by a MakeHuman .target.gz morph (CC0)."""
    idx = []
    with gzip.open(path, "rt") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            idx.append(int(line.split()[0]))
    return np.asarray(idx, dtype=np.int64)


def _girth(cm, y):
    try:
        return geo.slice_perimeter(cm, float(y), pick="longest")
    except Exception:
        return float("nan")


def _find_levels(cm):
    """Anatomical girth scan -> {field: y_cm} for hips/waist/bust/underbust.

    Profile landmarks (feet at y=0): legs merge into the pelvis at a sharp girth
    jump (crotch); the arms merge into the shoulders at a second jump higher up.
    hips = max girth just above the crotch jump; waist = min girth between hips
    and the chest; bust = max girth between the waist and the arm jump;
    underbust = min girth between bust and waist.
    """
    top = float(cm.bounds[1][1])
    ys = np.arange(2.0, top, 1.0)
    g = np.array([_girth(cm, y) for y in ys])

    def jump_up(lo, hi, thresh):
        """First y in [lo,hi] where girth crosses above thresh."""
        for y, gv in zip(ys, g):
            if lo <= y <= hi and np.isfinite(gv) and gv > thresh:
                return y
        return None

    # Torso girths sit ~100+ cm; legs/neck are far smaller. Use a fraction of
    # the max torso girth as the merge threshold so it scales with body size.
    torso_max = float(np.nanmax(g))
    thr = 0.7 * torso_max

    crotch_y = jump_up(40, top * 0.6, thr) or (top * 0.45)
    # arm/shoulder merge: the next strong jump well above the waist region.
    arm_y = jump_up(crotch_y + 30, top * 0.85, thr) or (top * 0.78)

    def in_band(lo, hi):
        m = (ys >= lo) & (ys <= hi) & np.isfinite(g)
        return ys[m], g[m]

    hy, hg = in_band(crotch_y, crotch_y + 18)
    hips_y = float(hy[np.argmax(hg)])
    wy, wg = in_band(hips_y + 5, arm_y - 5)
    waist_y = float(wy[np.argmin(wg)])
    by, bg = in_band(waist_y + 5, arm_y - 2)
    bust_y = float(by[np.argmax(bg)])
    # Underbust sits between the bust apex and the waist; take the midpoint
    # level (a girth between the two) rather than the band minimum, which would
    # otherwise collapse onto the waist on a slim torso.
    underbust_y = (waist_y + bust_y) / 2.0

    return {"hips": hips_y, "waist": waist_y,
            "bust": bust_y, "underbust": underbust_y}


def _vertex_at_level(V, y, prefer_front=True):
    """Body vertex index whose Y is nearest `y` (ties broken toward front
    centre so the stored level sits on the torso, not a fingertip)."""
    cost = np.abs(V[:, 1] - y) + 0.02 * np.abs(V[:, 0])
    if prefer_front:
        cost += 0.02 * (V[:, 2].max() - V[:, 2])
    return int(np.argmin(cost))


def _ring_sides(V, ring_compact, level_y):
    """(left index, right index) = extreme-X vertices of a measure ring,
    restricted to the slab near the given level so we don't grab a far-away
    part of a broad deform region."""
    P = V[ring_compact]
    band = np.abs(P[:, 1] - level_y) <= 6.0
    sub = ring_compact[band] if band.any() else ring_compact
    Ps = V[sub]
    return int(sub[np.argmin(Ps[:, 0])]), int(sub[np.argmax(Ps[:, 0])])


def main():
    data_dir = os.environ.get("MPFB_BASE_OBJ_DATA", _DEF_DATA)
    base_obj = os.environ.get("MPFB_BASE_OBJ",
                              os.path.join(data_dir, "3dobjs", "base.obj"))
    targets_dir = os.path.join(os.path.dirname(os.path.dirname(base_obj)),
                               "targets")

    raw = mesh_io.load_body(base_obj)
    body, remap = _body_only(raw)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    body.export(str(_BODY_OBJ))

    # Calibrate in the same normalized cm frame the CLI will use.
    mm, report = mesh_io.normalize(body, expected_height_m=1.7)
    cm = mesh_io.to_cm(mm)
    V = np.asarray(cm.vertices)

    levels_y = _find_levels(cm)

    # Neck level from the CC0 neck ring (median Y of its body verts).
    def ring_compact(name):
        orig = _read_target_indices(os.path.join(targets_dir, _RINGS[name]))
        c = remap[orig]
        return c[c >= 0]
    neck_ring = ring_compact("neck")
    levels_y["neck"] = float(np.median(V[neck_ring][:, 1]))

    levels_idx, vertices_idx = {}, {}
    for field, y in levels_y.items():
        levels_idx[field] = _vertex_at_level(V, y)

    # Side-landmark pairs from the measure rings, at each level.
    # Quick pass keeps only the WAIST pair: validated against the reference body
    # (waist_back_width 39.9 vs 39.14). The bust/hips/neck rings are broad deform
    # regions whose extreme-X verts land near the armpits and mis-size the back
    # arc (e.g. back_width 24.8 vs 47.68, which degenerates the armscye), so
    # those back-section widths are left to the CLI's --fill-defaults for now.
    side_map = {"waist": "side_{}_waist"}
    for field, tmpl in side_map.items():
        rc = ring_compact(field)
        li, ri = _ring_sides(V, rc, levels_y[field])
        vertices_idx[tmpl.format("l")] = li
        vertices_idx[tmpl.format("r")] = ri

    lm = {
        "_provenance": "clean-room girth-scan + CC0 MakeHuman measure rings; "
                       "quick pass, anchors via CLI --fill-defaults",
        "n_vertices_expected": int(len(V)),
        "vertices": vertices_idx,
        "levels": levels_idx,
    }
    _JSON.write_text(json.dumps(lm, indent=2))

    # --- report -----------------------------------------------------------
    print(f"body-only mesh : {_BODY_OBJ}  ({len(V)} verts)")
    print(f"landmarks json : {_JSON}")
    print(f"scale_to_m={report['scale_to_m']:.4f}  height_cm={V[:,1].max():.1f}")
    print("levels (cm Y / girth):")
    for f, y in levels_y.items():
        print(f"  {f:10s} y={y:6.1f}  girth={_girth(cm, y):6.1f}")
    print(f"side pairs: {sorted(vertices_idx)}")


if __name__ == "__main__":
    main()
