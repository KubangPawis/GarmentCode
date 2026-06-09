from pathlib import Path
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
