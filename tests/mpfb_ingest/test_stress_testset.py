"""Cross-body stress suite over the generated MPFB test set (.temp/testset/).

The real proof that the topology-agnostic, full-fidelity extractor "works
across all body types": every generated body emits a complete, in-range,
anatomically-ordered measurement set and drives GarmentCode pattern generation
without crashing, AND the measurements move in the right direction as the MPFB
macro sliders move (weight^=>waist^, height^=>stature^, cup^=>bust^,
male=>broader shoulders). Groups are derived from manifest.json so the suite
adapts to whatever bodies were generated; it skips cleanly when the set is
absent. See test_testset_assets.py for the per-file asset gate.
"""
import json
import tempfile
from pathlib import Path

import yaml
import pytest

from ingest_mpfb_body import run
from mpfb_ingest.emit import REQUIRED, RANGES

TESTSET = Path(".temp/testset")
MANIFEST = TESTSET / "manifest.json"
GLBS = sorted(TESTSET.glob("*.glb")) if TESTSET.is_dir() else []
pytestmark = pytest.mark.skipif(
    not GLBS or not MANIFEST.exists(),
    reason="no .temp/testset (run scripts/run_mpfb_gen.sh)")

_MACRO_AXES = ["gender", "age", "muscle", "weight", "height", "cupsize"]


@pytest.fixture(scope="module")
def measured():
    """{id: body-dict} for every generated body, ingested once via the auto path."""
    manifest = json.loads(MANIFEST.read_text())
    out = {}
    d = tempfile.mkdtemp()
    for glb in GLBS:
        idn = glb.stem
        y = run(str(glb), out_dir=d, name=idn, landmarks_path=None,
                arm_pose_angle=0.0, height_m=None, fill_defaults=False)
        out[idn] = (yaml.safe_load(Path(y).read_text())["body"], y)
    return manifest, out


def _race_key(m):
    return tuple(round(m["race"][k], 3) for k in ("asian", "caucasian", "african"))


def _key_excluding(macro, axis):
    """Macro identity with one axis dropped -> groups bodies that vary only on it."""
    return tuple(round(macro[a], 3) for a in _MACRO_AXES if a != axis) + (_race_key(macro),)


def _groups(manifest, axis):
    """Lists of ids that differ only in `axis`, each sorted ascending by it."""
    buckets = {}
    for idn, macro in manifest.items():
        buckets.setdefault(_key_excluding(macro, axis), []).append(idn)
    return [sorted(ids, key=lambda i: manifest[i][axis])
            for ids in buckets.values() if len(ids) >= 2]


# --- universal: every body is a complete, in-range, ordered measurement set ---

def test_every_body_complete_in_range_and_ordered(measured):
    _, bodies = measured
    for idn, (b, _) in bodies.items():
        assert not (set(REQUIRED) - set(b)), f"{idn} missing {set(REQUIRED) - set(b)}"
        for f, (lo, hi) in RANGES.items():
            assert lo <= b[f] <= hi, f"{idn}: {f}={b[f]:.1f} out of [{lo},{hi}]"
        assert b["waist"] < b["underbust"] < b["bust"], f"{idn}: bust order"
        assert b["waist"] < b["hips"], f"{idn}: hips order"
        assert b["waist_back_width"] < b["waist"], f"{idn}: waist_back_width"
        assert b["back_width"] < b["bust"], f"{idn}: back_width"


# --- monotonicity: measurements track the macro sliders -----------------------

def _assert_monotone(seq, tol, min_gain, label):
    """Non-decreasing within `tol`, with overall gain >= min_gain end-to-end."""
    assert len(seq) >= 2
    for a, b in zip(seq, seq[1:]):
        assert b >= a - tol, f"{label}: not monotone ({seq})"
    assert seq[-1] - seq[0] >= min_gain, f"{label}: gain {seq[-1]-seq[0]:.1f} < {min_gain} ({seq})"


def test_weight_increases_waist(measured):
    manifest, bodies = measured
    groups = _groups(manifest, "weight")
    assert groups, "no weight-sweep group in test set"
    for ids in groups:
        _assert_monotone([bodies[i][0]["waist"] for i in ids], tol=1.0, min_gain=3.0,
                         label="weight->waist " + ",".join(ids))


def test_height_slider_increases_stature(measured):
    manifest, bodies = measured
    groups = _groups(manifest, "height")
    assert groups, "no height-sweep group in test set"
    for ids in groups:
        _assert_monotone([bodies[i][0]["height"] for i in ids], tol=1.0, min_gain=10.0,
                         label="height->stature " + ",".join(ids))


def test_cupsize_increases_bust(measured):
    manifest, bodies = measured
    groups = _groups(manifest, "cupsize")
    assert groups, "no cupsize-sweep group in test set"
    for ids in groups:
        _assert_monotone([bodies[i][0]["bust"] for i in ids], tol=1.0, min_gain=3.0,
                         label="cupsize->bust " + ",".join(ids))


def test_male_has_broader_shoulders(measured):
    manifest, bodies = measured
    groups = _groups(manifest, "gender")
    assert groups, "no gender-pair group in test set"
    for ids in groups:                          # sorted ascending by gender (female first)
        sw = [bodies[i][0]["shoulder_w"] for i in ids]
        assert sw[-1] >= sw[0] - 0.5, f"gender->shoulder_w not broader for male ({ids}: {sw})"


# --- generation: extreme + neutral bodies drive a real pattern, no crash ------

def _extreme_ids(manifest):
    """A small representative subset: each slider extreme + neutral + a male."""
    picks = set()
    for axis in ("weight", "height", "cupsize"):
        vals = {i: manifest[i][axis] for i in manifest}
        picks.add(max(vals, key=vals.get))
        picks.add(min(vals, key=vals.get))
    picks.update(i for i in manifest if manifest[i]["gender"] >= 0.5)
    if "neutral" in manifest:
        picks.add("neutral")
    return sorted(picks)


@pytest.mark.parametrize("design_file", [
    "assets/design_params/default.yaml",
    "assets/design_params/t-shirt.yaml",
])
def test_extreme_bodies_generate_without_crash(measured, design_file):
    from assets.bodies.body_params import BodyParameters
    from assets.garment_programs.meta_garment import MetaGarment

    manifest, bodies = measured
    design = yaml.safe_load(open(design_file))["design"]
    for idn in _extreme_ids(manifest):
        _, ypath = bodies[idn]
        body = BodyParameters(str(ypath))
        pattern = MetaGarment(f"stress_{idn}", body, design).assembly()
        assert pattern is not None, f"{idn} failed to assemble {design_file}"
