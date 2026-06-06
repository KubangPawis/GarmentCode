import numpy as np
import trimesh
import yaml
from ingest_mpfb_body import run


def _proxy_obj(tmp_path):
    cyl = trimesh.creation.cylinder(radius=0.15, height=1.7, sections=64)
    R = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0])
    cyl.apply_transform(R)
    p = tmp_path / "avatar.obj"
    cyl.export(str(p))
    return p


def test_cli_run_smoke(tmp_path, monkeypatch):
    obj = _proxy_obj(tmp_path)
    # Minimal landmarks JSON that only enables height (cylinder has no anatomy).
    lm = tmp_path / "lm.json"
    lm.write_text('{"n_vertices_expected": 0, "vertices": {}, "levels": {}}')
    # Force-fill missing fields so emit.validate passes (gross proxy values).
    out = run(str(obj), out_dir=str(tmp_path), name="avatar",
              landmarks_path=str(lm), arm_pose_angle=90.0, height_m=1.7,
              fill_defaults=True)
    data = yaml.safe_load((tmp_path / "avatar.yaml").read_text())["body"]
    assert abs(data["height"] - 170.0) < 3.0
    assert data["arm_pose_angle"] == 90.0
