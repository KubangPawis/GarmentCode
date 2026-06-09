from pathlib import Path
import yaml
import pytest

REPO = Path("/home/kubangpawis/dev/GarmentCode/.claude/worktrees/feat+mpfb-drape")


def _cuda_available():
    try:
        import warp as wp
        wp.init()
        return wp.get_device().is_cuda
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _cuda_available(),
                                reason="Warp/CUDA not available for full drape")


def test_end_to_end_drape_tshirt(tmp_path):
    import ingest_mpfb_body as ingest
    from mpfb_drape import pipeline

    # 1) ingest the committed MPFB base body (auto path, T-pose angle 0)
    src_obj = REPO / "mpfb_ingest/data/mpfb_base_body.obj"
    out_bodies = REPO / "assets/bodies"
    name = "e2e_avatar"
    ingest.run(str(src_obj), str(out_bodies), name, landmarks_path=None,
               arm_pose_angle=0.0, save_obj=True, fill_defaults=True)
    body_yaml = out_bodies / f"{name}.yaml"
    body_obj = out_bodies / f"{name}.obj"
    seg_extra = out_bodies / f"{name}_bodyseg.json"

    try:
        with open(REPO / "assets/design_params/t-shirt.yaml") as f:
            design = yaml.safe_load(f)["design"]
        res = pipeline.drape_one(
            body_yaml, body_obj, design, out_dir=tmp_path / "out",
            bodies_dir=out_bodies, name="tee",
            sim_props_yaml=REPO / "assets/Sim_props/default_sim_props.yaml")

        assert Path(res["sim_obj"]).exists()
        assert res["verdict"]["passed"], res["verdict"]["reasons"]
    finally:
        for p in (body_yaml, body_obj, seg_extra):
            p.unlink(missing_ok=True)
