"""Acceptance check for one drape: sanity + penetration + settle.

Penetration and settle are read from the stats run_sim already records; sanity
(finite, non-empty, in-bounds) is computed here from the draped OBJ. Pure and
GPU-free.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import trimesh

# The GarmentCode sim writes the draped garment in centimetres, while the body
# collider OBJ is in metres (the sim scales it by b_scale=100 internally). Bring
# the body bbox into the garment's cm units before comparing.
BODY_OBJ_SCALE_TO_CM = 100.0
BBOX_MARGIN_CM = 30.0  # slack (cm) around the body before declaring fly-away


def acceptance(stats, design_name, sim_obj_path, body_obj_path,
               max_body_collisions=35, max_self_collisions=300):
    """Return {passed: bool, reasons: list[str], metrics: dict}."""
    reasons, metrics = [], {}

    # --- settle + hard failures (from run_sim stats) ---
    fails = stats.get("fails", {}) or {}
    for ftype, names in fails.items():
        if design_name in (names or []):
            reasons.append(ftype)

    # --- penetration (from run_sim stats) ---
    body_pen = (stats.get("body_collisions", {}) or {}).get(design_name)
    self_pen = (stats.get("self_collisions", {}) or {}).get(design_name)
    metrics["body_collisions"] = body_pen
    metrics["self_collisions"] = self_pen
    if body_pen is not None and body_pen > max_body_collisions:
        reasons.append(f"body_penetration {body_pen} > {max_body_collisions}")
    if self_pen is not None and self_pen > max_self_collisions:
        reasons.append(f"self_penetration {self_pen} > {max_self_collisions}")

    # --- sanity on the draped mesh ---
    sim_obj_path = Path(sim_obj_path)
    if not sim_obj_path.exists():
        reasons.append("sim_obj_missing")
        return {"passed": False, "reasons": reasons, "metrics": metrics}

    mesh = trimesh.load(str(sim_obj_path), process=False, force="mesh")
    v = np.asarray(mesh.vertices, dtype=float)
    metrics["n_vertices"] = int(len(v))
    if len(v) == 0:
        reasons.append("sim_obj_empty")
    elif not np.isfinite(v).all():
        reasons.append("non_finite_vertices (nan/inf)")
    else:
        body = trimesh.load(str(body_obj_path), process=False, force="mesh")
        bmin = np.asarray(body.bounds[0]) * BODY_OBJ_SCALE_TO_CM
        bmax = np.asarray(body.bounds[1]) * BODY_OBJ_SCALE_TO_CM
        gmin, gmax = v.min(axis=0), v.max(axis=0)
        if (gmin < bmin - BBOX_MARGIN_CM).any() or (gmax > bmax + BBOX_MARGIN_CM).any():
            reasons.append("bbox_outside_body (fly-away/explosion)")

    return {"passed": len(reasons) == 0, "reasons": reasons, "metrics": metrics}
