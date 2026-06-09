import numpy as np
import trimesh
from mpfb_drape import verify


def _stats(name, body=0, self_=0, fails=None):
    return {
        "fails": fails or {},
        "body_collisions": {name: body},
        "self_collisions": {name: self_},
    }


def _body_obj(tmp_path):
    # a 1 m tall box body collider
    b = trimesh.creation.box(extents=[0.6, 1.7, 0.3])
    b.apply_translation([0, 0.85, 0])
    p = tmp_path / "body.obj"
    b.export(str(p))
    return p


def test_pass_when_clean(tmp_path):
    body = _body_obj(tmp_path)              # ~1.7 m box body (metres)
    import trimesh, numpy as np
    # a small garment in CENTIMETRES sitting on the chest (inside body x100 cm bbox)
    g = trimesh.creation.box(extents=[40.0, 50.0, 25.0])
    g.apply_translation([0, 120.0, 0])      # y=120 cm, within body 0..170 cm
    p = tmp_path / "clean_sim.obj"; g.export(str(p))
    v = verify.acceptance(_stats("g"), "g", p, body,
                          max_body_collisions=35, max_self_collisions=300)
    assert v["passed"] is True, v["reasons"]
    assert v["reasons"] == []


def test_fail_on_static_equilibrium(tiny_obj, tmp_path):
    body = _body_obj(tmp_path)
    s = _stats("g", fails={"static_equilibrium": ["g"]})
    v = verify.acceptance(s, "g", tiny_obj, body, 35, 300)
    assert v["passed"] is False
    assert "static_equilibrium" in v["reasons"]


def test_fail_on_body_penetration(tiny_obj, tmp_path):
    body = _body_obj(tmp_path)
    v = verify.acceptance(_stats("g", body=999), "g", tiny_obj, body, 35, 300)
    assert v["passed"] is False
    assert any("body" in r for r in v["reasons"])


def test_fail_on_nan(tmp_path):
    body = _body_obj(tmp_path)
    p = tmp_path / "nan.obj"
    # export raw so NaN survives the round-trip
    p.write_text("v 0 0 0\nv nan 0 0\nv 0 1 0\nf 1 2 3\n")
    res = verify.acceptance(_stats("g"), "g", p, body, 35, 300)
    assert res["passed"] is False
    assert any("nan" in r.lower() or "finite" in r.lower() or "unreadable" in r.lower()
               for r in res["reasons"])


def test_fail_on_flyaway_bbox(tmp_path):
    body = _body_obj(tmp_path)              # body x ~[-0.3,0.3] m -> [-30,30] cm
    import trimesh
    g = trimesh.creation.box(extents=[10.0, 10.0, 10.0])
    g.apply_translation([500.0, 120.0, 0])  # x=500 cm, far outside body cm bbox+margin
    p = tmp_path / "fly_sim.obj"; g.export(str(p))
    v = verify.acceptance(_stats("g"), "g", p, body, 35, 300)
    assert v["passed"] is False
    assert any("bbox" in r or "outside" in r for r in v["reasons"])


def test_fail_on_self_penetration(tiny_obj, tmp_path):
    body = _body_obj(tmp_path)
    v = verify.acceptance(_stats("g", self_=999), "g", tiny_obj, body, 35, 300)
    assert v["passed"] is False
    assert any("self" in r for r in v["reasons"])


def test_fail_on_missing_obj(tmp_path):
    body = _body_obj(tmp_path)
    v = verify.acceptance(_stats("g"), "g", tmp_path / "nonexistent.obj", body, 35, 300)
    assert v["passed"] is False
    assert "sim_obj_missing" in v["reasons"]
