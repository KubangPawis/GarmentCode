"""Asset-sanity gate over the generated MPFB test set (.temp/testset/*.glb).

Proves every body the headless generator wrote is a loadable, Y-up, NaN-free
human mesh of plausible stature, and that manifest.json describes exactly the
set on disk. Skips cleanly when the set has not been generated. The cross-body
measurement/property assertions live in test_stress_testset.py.
"""
import json
from pathlib import Path

import numpy as np
import pytest

from mpfb_ingest.mesh_io import load_body, normalize

TESTSET = Path(".temp/testset")
GLBS = sorted(TESTSET.glob("*.glb")) if TESTSET.is_dir() else []
pytestmark = pytest.mark.skipif(not GLBS, reason="no .temp/testset/*.glb (run scripts/run_mpfb_gen.sh)")


def test_manifest_covers_every_glb():
    manifest = json.loads((TESTSET / "manifest.json").read_text())
    on_disk = {p.stem for p in GLBS}
    in_manifest = set(manifest)
    assert on_disk == in_manifest, f"disk-only={on_disk - in_manifest} manifest-only={in_manifest - on_disk}"
    # every macro entry is a full slider dict in [0,1] + a race blend summing to 1
    for idn, m in manifest.items():
        for k in ("gender", "age", "muscle", "weight", "height", "cupsize"):
            assert 0.0 <= m[k] <= 1.0, f"{idn}.{k}={m[k]} out of [0,1]"
        assert abs(sum(m["race"].values()) - 1.0) < 1e-6, f"{idn} race blend != 1"


@pytest.mark.parametrize("glb", GLBS, ids=[p.stem for p in GLBS])
def test_glb_loads_yup_grounded_and_human_sized(glb):
    mesh = load_body(glb)
    assert len(mesh.vertices) > 1000, f"{glb.name}: only {len(mesh.vertices)} verts"
    assert np.isfinite(mesh.vertices).all(), f"{glb.name}: non-finite vertices"

    (x0, y0, z0), (x1, y1, z1) = mesh.bounds
    # Y-up: stature is the dominant extent (taller than wide or deep)
    assert (y1 - y0) > (x1 - x0) and (y1 - y0) > (z1 - z0), f"{glb.name}: not Y-up"

    norm, report = normalize(mesh)
    # plausible human stature once unit-detected (child .. tall adult)
    assert 1.0 <= report["height_m"] <= 2.2, f"{glb.name}: height {report['height_m']:.3f} m"
    # normalize grounds feet to Y=0 and centres X/Z on the bbox midpoint
    (nx0, ny0, nz0), (nx1, _, nz1) = norm.bounds
    assert abs(ny0) < 1e-6, f"{glb.name}: feet not grounded (minY={ny0})"
    assert abs(nx0 + nx1) < 1e-6 and abs(nz0 + nz1) < 1e-6, f"{glb.name}: not X/Z centred"
