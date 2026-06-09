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


def derive_thresholds(vertices):
    """Estimate (arm_x, crotch_y) geometrically from a T-pose mesh.

    arm_x: largest gap in sorted |X| over the upper half (torso vs arms).
    crotch_y: half the stature above the ground.
    """
    v = np.asarray(vertices, dtype=float)
    y = v[:, 1]
    ymin, ymax = float(y.min()), float(y.max())
    height = ymax - ymin

    upper = v[y > ymin + 0.5 * height]
    ax = np.sort(np.abs(upper[:, 0]))
    if ax.size >= 2:
        gaps = np.diff(ax)
        gi = int(np.argmax(gaps))

        # The largest gap may be INTERIOR to an arm cylinder (arm end-caps sit at
        # both extremes of |X|, leaving a hollow span in the sorted distribution).
        # If so, the true torso/arm boundary gap is just to the LEFT of ax[gi].
        # Find the last strictly smaller value before ax[gi]:
        left_val = ax[gi]
        lo = gi
        while lo > 0 and ax[lo] >= left_val:
            lo -= 1
        prev_gap = left_val - ax[lo]

        # 0.5% of height = a gap large enough to be a real anatomical separation
        small_thresh = 0.005 * height
        if prev_gap > small_thresh:
            # Largest gap is arm-interior; the real boundary is this preceding gap
            arm_x = float(0.5 * (ax[lo] + left_val))
        elif gaps[gi] > 0.05 * height:
            # No preceding gap; the largest gap IS the torso/arm boundary
            arm_x = float(0.5 * (ax[gi] + ax[gi + 1]))
        else:
            arm_x = float(ax[-1]) * 1.5  # no separated arms found laterally
    else:
        arm_x = float(np.abs(v[:, 0]).max()) * 1.5

    crotch_y = ymin + 0.5 * height
    return arm_x, crotch_y
