import numpy as np
from mpfb_drape import bodyseg

GGG_KEYS = {"body", "left_arm", "right_arm", "left_leg", "right_leg", "face_internal"}


def test_segment_partition_complete_and_disjoint(tpose_cm):
    v = np.asarray(tpose_cm.vertices)
    seg = bodyseg.segment_by_thresholds(v, arm_x=16.5, crotch_y=80.0)
    assert set(seg) == GGG_KEYS
    all_idx = [i for k in GGG_KEYS for i in seg[k]]
    assert sorted(all_idx) == list(range(len(v)))          # complete
    assert len(all_idx) == len(set(all_idx))                # disjoint


def test_arms_are_lateral_split_by_sign(tpose_cm):
    v = np.asarray(tpose_cm.vertices)
    seg = bodyseg.segment_by_thresholds(v, arm_x=16.5, crotch_y=80.0)
    assert seg["right_arm"] and seg["left_arm"]
    assert all(v[i, 0] > 16.5 for i in seg["right_arm"])
    assert all(v[i, 0] < -16.5 for i in seg["left_arm"])


def test_legs_are_low_and_central(tpose_cm):
    v = np.asarray(tpose_cm.vertices)
    seg = bodyseg.segment_by_thresholds(v, arm_x=16.5, crotch_y=80.0)
    assert seg["right_leg"] and seg["left_leg"]
    for i in seg["right_leg"] + seg["left_leg"]:
        assert v[i, 1] < 80.0 and abs(v[i, 0]) <= 16.5


def test_indices_in_range_and_face_internal_empty(tpose_cm):
    v = np.asarray(tpose_cm.vertices)
    seg = bodyseg.segment_by_thresholds(v, arm_x=16.5, crotch_y=80.0)
    assert seg["face_internal"] == []
    for k in GGG_KEYS:
        assert all(0 <= i < len(v) for i in seg[k])
        assert all(isinstance(i, int) for i in seg[k])
