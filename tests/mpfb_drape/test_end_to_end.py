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


# Production input is an mpfb_ingest'd mpfb_tpose export; the bundled
# mean_all_tpose body is used here as a true-T-pose stand-in because generating
# an MPFB T-pose requires Blender (gated elsewhere). This test's sole job is to
# prove the real Warp drape + verify path works end-to-end on a contract-valid
# T-pose body.
def test_end_to_end_drape_tshirt(tmp_path):
    from mpfb_drape import pipeline

    bodies = REPO / "assets/bodies"
    body_yaml = bodies / "mean_all_tpose.yaml"   # a genuine T-pose body
    body_obj = bodies / "mean_all_tpose.obj"
    seg_extra = bodies / "mean_all_tpose_bodyseg.json"
    with open(REPO / "assets/design_params/t-shirt.yaml") as f:
        design = yaml.safe_load(f)["design"]

    try:
        res = pipeline.drape_one(
            body_yaml, body_obj, design, out_dir=tmp_path / "out",
            bodies_dir=bodies, name="tee",
            sim_props_yaml=REPO / "assets/Sim_props/mpfb_drape_sim_props.yaml")
        assert Path(res["sim_obj"]).exists()
        assert res["verdict"]["passed"], res["verdict"]["reasons"]
    finally:
        seg_extra.unlink(missing_ok=True)
