import json
from pathlib import Path
import numpy as np
import trimesh
from mpfb_drape import bodyseg

REPO = Path(__file__).resolve().parents[2]

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


def test_region_keys_match_output(tpose_cm):
    import numpy as np
    seg = bodyseg.segment_by_thresholds(np.asarray(tpose_cm.vertices), arm_x=16.5, crotch_y=80.0)
    assert set(seg) == set(bodyseg.REGION_KEYS)


def test_indices_in_range_and_face_internal_empty(tpose_cm):
    v = np.asarray(tpose_cm.vertices)
    seg = bodyseg.segment_by_thresholds(v, arm_x=16.5, crotch_y=80.0)
    assert seg["face_internal"] == []
    for k in GGG_KEYS:
        assert all(0 <= i < len(v) for i in seg[k])
        assert all(isinstance(i, int) for i in seg[k])


def test_build_segmentation_from_mesh():
    m = trimesh.load(str(REPO / "assets/bodies/mean_all_tpose.obj"),
                     process=False, force="mesh")
    seg = bodyseg.build_segmentation(np.asarray(m.vertices))
    assert set(seg) == GGG_KEYS
    assert seg["right_arm"] and seg["left_arm"] and seg["left_leg"]


def test_write_segmentation_json_shape(tpose_cm, tmp_path):
    seg = bodyseg.build_segmentation(np.asarray(tpose_cm.vertices))
    out = tmp_path / "avatar_bodyseg.json"
    bodyseg.write_segmentation(seg, out)
    loaded = json.loads(out.read_text())
    assert set(loaded) == GGG_KEYS
    assert all(isinstance(i, int) for i in loaded["body"])


def test_derive_detects_arms_on_real_tpose():
    v = np.asarray(trimesh.load(str(REPO / "assets/bodies/mean_all_tpose.obj"),
                                process=False, force="mesh").vertices)
    arm_x, crotch_y = bodyseg.derive_thresholds(v)
    assert arm_x < np.abs(v[:, 0]).max()       # arms ARE laterally separable
    seg = bodyseg.segment_by_thresholds(v, arm_x, crotch_y)
    assert seg["left_arm"] and seg["right_arm"]
    assert bodyseg.arms_detected(seg)


def test_arms_empty_on_arms_down_body():
    # mean_all.obj is a neutral/arms-down body: arms are not laterally separable
    v = np.asarray(trimesh.load(str(REPO / "assets/bodies/mean_all.obj"),
                                process=False, force="mesh").vertices)
    seg = bodyseg.build_segmentation(v)
    assert seg["left_arm"] == [] and seg["right_arm"] == []
    assert not bodyseg.arms_detected(seg)


def test_tpose_regions_form_complete_faces():
    # every non-empty region must form >=1 complete face, else Warp's
    # extract_submesh hits np.vectorize size-0 and crashes
    m = trimesh.load(str(REPO / "assets/bodies/mean_all_tpose.obj"),
                     process=False, force="mesh")
    v = np.asarray(m.vertices); faces = np.asarray(m.faces)
    seg = bodyseg.build_segmentation(v)
    for k in ("body", "left_arm", "right_arm", "left_leg", "right_leg"):
        if seg[k]:
            s = set(seg[k])
            assert any(all(int(i) in s for i in f) for f in faces), f"{k}: no complete face"
