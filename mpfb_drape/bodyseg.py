"""Topology-matched body segmentation for an arbitrary (MPFB) body mesh.

GarmentCode's bundled ggg_body_segmentation.json is a dict of region ->
vertex-index lists bound to mean_all's 23752-vertex topology. An MPFB body has
different topology, so the Warp sim needs a segmentation expressed in the
avatar's own vertex indices, with the same six region keys:
    body, left_arm, right_arm, left_leg, right_leg, face_internal

Approach: geometric, topology-agnostic. The avatar is a known true T-pose
(Y-up, feet at Y=0, centred X/Z). Convention: left = -X, right = +X. The Warp
collision filters union both sides, so the sim is insensitive to that choice.
"""
from __future__ import annotations
import json as _json
from pathlib import Path as _Path
import numpy as np

REGION_KEYS = ("body", "left_arm", "right_arm", "left_leg", "right_leg", "face_internal")


def segment_by_thresholds(vertices, arm_x, crotch_y):
    """Partition vertices into the six ggg regions using two thresholds.

    Args:
        vertices: (N, 3) array, Y-up, in the mesh's own units.
        arm_x:    |X| beyond which a vertex belongs to an arm.
        crotch_y: Y strictly below which a non-arm vertex belongs to a leg.

    Returns dict {region_key: sorted list[int]}; complete + disjoint over
    range(N); face_internal is empty (the exported MPFB body has helpers
    stripped, and an empty filter is harmless).
    """
    v = np.asarray(vertices, dtype=float)
    x, y = v[:, 0], v[:, 1]

    is_arm = np.abs(x) > arm_x
    is_leg = (~is_arm) & (y < crotch_y)
    is_body = ~is_arm & ~is_leg
    right = x > 0.0  # +X

    def idx(mask):
        return [int(i) for i in np.nonzero(mask)[0]]

    return {
        "body": idx(is_body),
        "left_arm": idx(is_arm & ~right),
        "right_arm": idx(is_arm & right),
        "left_leg": idx(is_leg & ~right),
        "right_leg": idx(is_leg & right),
        "face_internal": [],
    }


def derive_thresholds(vertices, arm_margin=1.6):
    """Estimate (arm_x, crotch_y) geometrically from a true T-pose mesh.

    arm_x: torso half-width (P97 of |X| in a band BELOW the armpit, where a
        T-pose has no lateral arms) times a margin. Vertices with |X| beyond
        this are arms. On an arms-down / non-T-pose body the band already
        spans the arms, so torso_hw ~= max|X| and arm_x exceeds it -> no arms
        detected (correct: such a body has no laterally separable arms).
    crotch_y: half the stature above the ground.

    Note: this is the topology-agnostic geometric heuristic; it relies on the
    mpfb_drape contract that the body is a true T-pose (arm_pose_angle ~= 0).
    """
    v = np.asarray(vertices, dtype=float)
    y = v[:, 1]
    ymin, ymax = float(y.min()), float(y.max())
    height = ymax - ymin

    band = v[(y >= ymin + 0.50 * height) & (y <= ymin + 0.68 * height)]
    if len(band):
        torso_hw = float(np.percentile(np.abs(band[:, 0]), 97))
    else:
        torso_hw = float(np.abs(v[:, 0]).max())

    arm_x = torso_hw * arm_margin
    crotch_y = ymin + 0.5 * height
    return arm_x, crotch_y


def build_segmentation(vertices):
    """Full pipeline: derive thresholds, then partition into ggg regions."""
    arm_x, crotch_y = derive_thresholds(vertices)
    return segment_by_thresholds(vertices, arm_x, crotch_y)


def arms_detected(seg):
    """True if the segmentation found lateral arms (a true-T-pose property)."""
    return bool(seg.get("left_arm")) or bool(seg.get("right_arm"))


def write_segmentation(seg, path):
    """Write the segmentation dict as ggg-shaped JSON ({region: [int,...]})."""
    path = _Path(path)
    path.write_text(_json.dumps({k: list(map(int, v)) for k, v in seg.items()}))
    return path
