import json
import numpy as np
import pytest
from mpfb_ingest.landmarks import Landmarks


def _write(tmp_path, data):
    p = tmp_path / "lm.json"
    p.write_text(json.dumps(data))
    return p


def test_load_and_lookup(tmp_path, tiny_mesh):
    p = _write(tmp_path, {
        "n_vertices_expected": 4,
        "vertices": {"nape": 2, "wrist_r": 1},
        "levels": {"waist": 0},
    })
    lm = Landmarks.load(p)
    assert lm.vertex_index("nape") == 2
    assert np.allclose(lm.point(tiny_mesh, "wrist_r"), [30, 0, 0])
    assert lm.level_y(tiny_mesh, "waist") == 0.0


def test_validate_rejects_wrong_vertex_count(tmp_path, tiny_mesh):
    p = _write(tmp_path, {"n_vertices_expected": 9999, "vertices": {}, "levels": {}})
    lm = Landmarks.load(p)
    with pytest.raises(ValueError, match="vertex count"):
        lm.validate(tiny_mesh)


def test_validate_rejects_out_of_range_index(tmp_path, tiny_mesh):
    p = _write(tmp_path, {"n_vertices_expected": 4, "vertices": {"x": 10}, "levels": {}})
    lm = Landmarks.load(p)
    with pytest.raises(ValueError, match="out of range"):
        lm.validate(tiny_mesh)
