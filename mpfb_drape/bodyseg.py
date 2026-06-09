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
import numpy as np

REGION_KEYS = ("body", "left_arm", "right_arm", "left_leg", "right_leg", "face_internal")


def segment_by_thresholds(vertices, arm_x, crotch_y):
    """Partition vertices into the six ggg regions using two thresholds.

    Args:
        vertices: (N, 3) array, Y-up, in the mesh's own units.
        arm_x:    |X| beyond which a vertex belongs to an arm.
        crotch_y: Y below which a non-arm vertex belongs to a leg.

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
