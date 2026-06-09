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


def test_pass_when_clean(tiny_obj, tmp_path):
    body = _body_obj(tmp_path)
    # tiny_obj is in cm (Y~100..110); shrink to sit inside the metre body bbox
    m = trimesh.load(str(tiny_obj), process=False, force="mesh")
    m.apply_scale(0.01)
    m.export(str(tiny_obj))
    v = verify.acceptance(_stats("g"), "g", tiny_obj, body,
                          max_body_collisions=35, max_self_collisions=300)
    assert v["passed"] is True
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


def test_fail_on_flyaway_bbox(tiny_obj, tmp_path):
    body = _body_obj(tmp_path)
    # tiny_obj at Y~100 m relative to a 1.7 m body -> way outside -> fly-away
    v = verify.acceptance(_stats("g"), "g", tiny_obj, body, 35, 300)
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
