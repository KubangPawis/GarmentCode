import importlib.util
from pathlib import Path
import pytest

REPO = Path("/home/kubangpawis/dev/GarmentCode/.claude/worktrees/feat+mpfb-drape")


def _load_cli():
    spec = importlib.util.spec_from_file_location("drape_cli", REPO / "drape_mpfb_garment.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_missing_body_obj_errors(tmp_path):
    cli = _load_cli()
    y = tmp_path / "avatar.yaml"; y.write_text("body:\n  height: 172.0\n")
    # no sibling avatar.obj
    with pytest.raises(SystemExit) as e:
        cli.main(["--body", str(y), "--designs", str(tmp_path), "--out", str(tmp_path / "o")])
    assert e.value.code != 0


def test_no_designs_errors(tmp_path):
    cli = _load_cli()
    y = tmp_path / "avatar.yaml"; y.write_text("body:\n  height: 172.0\n")
    (tmp_path / "avatar.obj").write_text("")
    empty = tmp_path / "empty"; empty.mkdir()
    with pytest.raises(SystemExit) as e:
        cli.main(["--body", str(y), "--designs", str(empty), "--out", str(tmp_path / "o")])
    assert e.value.code != 0
