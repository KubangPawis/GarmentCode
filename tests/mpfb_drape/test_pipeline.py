from pathlib import Path
import pytest
from mpfb_drape import pipeline

REPO = Path("/home/kubangpawis/dev/GarmentCode/.claude/worktrees/feat+mpfb-drape")
DEFAULT_SIM = REPO / "assets/Sim_props/default_sim_props.yaml"


def test_make_sim_props_has_stats_and_no_optimize():
    props = pipeline.make_sim_props(DEFAULT_SIM)
    cfg = props["sim"]["config"]
    assert cfg["optimize_storage"] is False          # forced off
    assert "material" in cfg and "options" in cfg     # kept from yaml
    stats = props["sim"]["stats"]
    for key in ("fails", "meshgen_time", "face_count", "body_collisions",
                "self_collisions", "sim_time", "fin_frame"):
        assert key in stats                            # init_sim_props structure
    assert "render" in props


import json
import trimesh
import yaml


def test_drape_one_injects_seg_and_returns_record(tmp_path):
    # Use the bundled, COMPLETE mean_all_tpose body so the real fit step has full
    # measurements AND arms are detected (T-pose contract); stub only the GPU sim.
    # drape_one stages the avatar into system.json's bodies_default_path under a
    # namespaced name (_mpfbdrape_<stem>) and cleans up afterward.
    bodies = REPO / "assets/bodies"
    body_yaml = bodies / "mean_all_tpose.yaml"
    body_obj = bodies / "mean_all_tpose.obj"
    with open(REPO / "assets/design_params/t-shirt.yaml") as f:
        design = yaml.safe_load(f)["design"]

    captured = {}

    def fake_run(paths, props, caching=False):
        # stand in for template_simulation: capture overrides + emit a clean draped obj + stats
        captured["body_seg"] = str(paths.body_seg)
        captured["body_obj"] = str(paths.in_body_obj)
        # read seg JSON while the staged file is still alive (cleanup runs in finally after return)
        captured["seg_content"] = json.loads(Path(captured["body_seg"]).read_text())
        m = trimesh.creation.box(extents=[0.4, 0.5, 0.2])
        m.apply_translation([0, 1.2, 0])  # in-bounds for the ~1.72 m tpose body
        m.export(str(paths.g_sim))
        props["sim"]["stats"]["body_collisions"][paths.sim_tag] = 2
        props["sim"]["stats"]["self_collisions"][paths.sim_tag] = 0

    res = pipeline.drape_one(
        body_yaml, body_obj, design, out_dir=tmp_path / "out",
        name="tee", sim_props_yaml=DEFAULT_SIM, run=fake_run)
    assert res["design"] == "tee"
    assert res["body_name"] == "mean_all_tpose"
    assert res["verdict"]["passed"] is True, res["verdict"]["reasons"]
    # body_seg + in_body_obj point at the NAMESPACED staged files:
    assert "_mpfbdrape_mean_all_tpose_bodyseg.json" in captured["body_seg"]
    assert captured["body_obj"].endswith("_mpfbdrape_mean_all_tpose.obj")
    assert captured["seg_content"]  # valid seg json was readable while staged file was alive
    # drape_one's finally cleaned up — no namespaced files should linger:
    assert not (bodies / "_mpfbdrape_mean_all_tpose.obj").exists()
    assert not (bodies / "_mpfbdrape_mean_all_tpose.yaml").exists()
    assert not (bodies / "_mpfbdrape_mean_all_tpose_bodyseg.json").exists()


def test_resolve_designs_accepts_list_and_dir(tmp_path):
    d = tmp_path / "d"; d.mkdir()
    (d / "a.yaml").write_text("design: {}")
    (d / "b.yaml").write_text("design: {}")
    assert len(pipeline.resolve_designs([d])) == 2
    assert len(pipeline.resolve_designs([d / "a.yaml"])) == 1


def test_drape_wardrobe_folder_and_manifest(tmp_path, monkeypatch):
    body_dir = tmp_path / "in"; body_dir.mkdir()
    obj = body_dir / "avatar.obj"
    import trimesh as _tm
    _tm.creation.box(extents=[0.4, 1.6, 0.2]).export(str(obj))
    yml = body_dir / "avatar.yaml"
    yml.write_text("body:\n  height: 172.0\n  arm_pose_angle: 0.0\n")

    designs_dir = tmp_path / "designs"; designs_dir.mkdir()
    (designs_dir / "t-shirt.yaml").write_text(
        (REPO / "assets/design_params" / "t-shirt.yaml").read_text())

    calls = []

    def fake_drape_one(*a, **k):
        calls.append(k.get("name"))
        return {"design": k.get("name"), "body_name": "avatar",
                "verdict": {"passed": True, "reasons": [], "metrics": {}},
                "out_folder": "x", "sim_obj": "x", "sim_glb": None}

    monkeypatch.setattr(pipeline, "drape_one", fake_drape_one)
    man = pipeline.drape_wardrobe(
        yml, obj, designs_dir, out_dir=tmp_path / "out",
        sim_props_yaml=DEFAULT_SIM)

    assert man["summary"]["total"] == 1
    assert man["summary"]["passed"] == 1
    assert (tmp_path / "out" / "wardrobe_manifest.json").exists()
    assert calls == ["t-shirt"]   # design name = file stem


def test_drape_one_rejects_arms_down_body(tmp_path):
    # mean_all is a neutral/arms-down body -> no lateral arms -> clear error,
    # NOT a cryptic deep Warp crash. Cleanup must run even on the error path.
    bodies = REPO / "assets/bodies"
    with open(REPO / "assets/design_params/t-shirt.yaml") as f:
        design = yaml.safe_load(f)["design"]
    with pytest.raises(ValueError, match="true T-pose"):
        pipeline.drape_one(
            bodies / "mean_all.yaml", bodies / "mean_all.obj", design,
            out_dir=tmp_path / "out", name="tee",
            sim_props_yaml=DEFAULT_SIM)
    # Verify cleanup ran — namespaced staging files must be gone:
    assert not (bodies / "_mpfbdrape_mean_all.obj").exists()
    assert not (bodies / "_mpfbdrape_mean_all.yaml").exists()
    assert not (bodies / "_mpfbdrape_mean_all_bodyseg.json").exists()
