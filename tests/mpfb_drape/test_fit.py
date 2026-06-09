from pathlib import Path
import yaml
import pytest
from mpfb_drape import fit

REPO = Path("/home/kubangpawis/dev/GarmentCode/.claude/worktrees/feat+mpfb-drape")


@pytest.fixture
def tshirt_design():
    with open(REPO / "assets/design_params/t-shirt.yaml") as f:
        return yaml.safe_load(f)["design"]


def test_fit_pattern_writes_specification(tshirt_design, tmp_path):
    body_yaml = REPO / "assets/bodies/mean_all.yaml"
    spec_dir, name = fit.fit_pattern(body_yaml, tshirt_design, tmp_path, name="tee_mean")
    spec = Path(spec_dir) / f"{name}_specification.json"
    assert spec.exists()
    data = yaml.safe_load(spec.read_text())  # json is valid yaml
    assert "pattern" in data
