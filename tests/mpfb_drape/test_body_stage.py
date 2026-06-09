import json
from pathlib import Path
from mpfb_drape import body_stage


def _write_min_body_yaml(path):
    path.write_text("body:\n  height: 172.0\n  arm_pose_angle: 0.0\n")


def test_stage_body_copies_and_segments(tpose_m, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    obj = src / "avatar.obj"
    tpose_m.export(str(obj))
    yaml_path = src / "avatar.yaml"
    _write_min_body_yaml(yaml_path)

    bodies = tmp_path / "bodies"
    staged = body_stage.stage_body(yaml_path, obj, bodies, name="avatar")

    assert (bodies / "avatar.obj").exists()
    assert (bodies / "avatar.yaml").exists()
    seg_path = Path(staged["body_seg"])
    assert seg_path.exists()
    seg = json.loads(seg_path.read_text())
    assert set(seg) == {"body", "left_arm", "right_arm", "left_leg", "right_leg", "face_internal"}
    assert staged["body_name"] == "avatar"
    # Note: synthetic fixture arms are not laterally separable by the torso-width
    # heuristic; arm presence is tested against the real bundled T-pose in test_bodyseg.py
    assert all(isinstance(v, list) for v in seg.values())


def test_stage_body_defaults_name_from_yaml_stem(tpose_m, tmp_path):
    obj = tmp_path / "bob.obj"
    tpose_m.export(str(obj))
    y = tmp_path / "bob.yaml"
    _write_min_body_yaml(y)
    staged = body_stage.stage_body(y, obj, tmp_path / "bodies")
    assert staged["body_name"] == "bob"
