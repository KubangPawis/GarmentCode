import json
from mpfb_drape import manifest


def test_build_and_write_manifest(tmp_path):
    results = [
        {"design": "tee", "verdict": {"passed": True, "reasons": [], "metrics": {"body_collisions": 3}},
         "out_folder": "/x/tee", "sim_glb": "/x/tee/tee_sim.glb"},
        {"design": "dress", "verdict": {"passed": False, "reasons": ["static_equilibrium"], "metrics": {}},
         "out_folder": "/x/dress", "sim_glb": None},
    ]
    man = manifest.build("avatar", results)
    assert man["body"] == "avatar"
    assert man["summary"]["total"] == 2
    assert man["summary"]["passed"] == 1
    assert man["summary"]["failed"] == 1

    out = tmp_path / "wardrobe_manifest.json"
    manifest.write(man, out)
    loaded = json.loads(out.read_text())
    assert loaded["summary"]["passed"] == 1
    assert loaded["designs"][1]["verdict"]["reasons"] == ["static_equilibrium"]
