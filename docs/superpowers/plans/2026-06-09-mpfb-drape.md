# mpfb_drape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Programmatically fit + drape GarmentCode garments onto a normalized true-T-pose MPFB body (from `mpfb_tpose` → `mpfb_ingest`) using GarmentCode's native Warp cloth sim — many designs × one body, with a per-drape acceptance verdict and a wardrobe manifest.

**Architecture:** A focused `mpfb_drape/` package + a root CLI `drape_mpfb_garment.py`. The drape primitive reuses the engine: `MetaGarment` (fit) → `pygarment.meshgen.datasim_utils.template_simulation` (BoxMesh → load → serialize → `run_sim`). The one piece that does not exist upstream is a **topology-matched body segmentation** (the bundled `ggg_body_segmentation.json` is vertex-index-bound to `mean_all`'s 23752 verts and invalid for an MPFB body), so `bodyseg.py` derives it from the avatar mesh and the pipeline injects it via `paths.body_seg`. Acceptance is mostly read back from `run_sim`'s own recorded stats.

**Tech Stack:** Python 3.9 (root `.venv`), `pygarment` (editable), NVIDIA Warp (editable, CUDA), `trimesh`, `numpy`, `pyyaml`, `pytest`.

---

## Conventions for every task

- **Working dir:** the worktree root `/home/kubangpawis/dev/GarmentCode/.claude/worktrees/feat+mpfb-drape`. Run everything from here.
- **Python:** always `/home/kubangpawis/dev/GarmentCode/.venv/bin/python` (call it `$PY`). Define once per shell: `PY=/home/kubangpawis/dev/GarmentCode/.venv/bin/python`.
- **Run a test:** `$PY -m pytest <path>::<name> -v`.
- **Commit** after each green task (frequent commits). Use the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Verified upstream facts (do not re-derive): body collider is read from `bodies_path/<body_name>.obj` and scaled ×100 (m→cm) in `pygarment/meshgen/garment.py:39,102`; `paths.body_seg` is a plain attribute (`pygarment/meshgen/sim_config.py:68`) safe to overwrite; `template_simulation(paths, props)` is `pygarment/meshgen/datasim_utils.py:289`; `run_sim` records `body_collisions`, `self_collisions`, and a `static_equilibrium` fail into `props['sim']['stats']` (`pygarment/meshgen/simulation.py`).

---

## File Structure

```
mpfb_drape/
  __init__.py        # package marker + version string
  bodyseg.py         # topology-matched body segmentation (the core new algorithm)
  body_stage.py      # stage avatar obj/yaml into a bodies dir + write the seg json
  fit.py             # BodyParameters + design -> MetaGarment -> serialize spec.json
  verify.py          # acceptance verdict from sim stats + the draped obj
  manifest.py        # aggregate per-design results into wardrobe_manifest.json
  pipeline.py        # drape_one + drape_wardrobe orchestration (calls template_simulation)
  README.md          # as-built usage + pose conventions
drape_mpfb_garment.py            # root CLI
tests/mpfb_drape/
  __init__.py
  conftest.py        # fixtures: tpose body (cm + metres), tiny sim obj, fake stats
  test_bodyseg.py
  test_body_stage.py
  test_fit.py
  test_verify.py
  test_manifest.py
  test_pipeline.py
  test_cli.py
  test_end_to_end.py # gated (CUDA) full drape
```

---

## Task 1: package scaffold + shared test fixtures

**Files:**
- Create: `mpfb_drape/__init__.py`
- Create: `tests/mpfb_drape/__init__.py`
- Create: `tests/mpfb_drape/conftest.py`

- [ ] **Step 1: Create the package marker**

`mpfb_drape/__init__.py`:
```python
"""Auto-fit + auto-drape GarmentCode garments onto normalized MPFB bodies.

Pipeline: mpfb_tpose -> mpfb_ingest -> mpfb_drape. See
docs/superpowers/specs/2026-06-09-mpfb-drape-fitting-design.md.
"""
__version__ = "0.1.0"
```

- [ ] **Step 2: Create the test package marker**

`tests/mpfb_drape/__init__.py`:
```python
```
(empty file)

- [ ] **Step 3: Create shared fixtures**

`tests/mpfb_drape/conftest.py`:
```python
import numpy as np
import trimesh
import pytest


def _ycyl(radius, y0, y1, sections=48, xz=(0.0, 0.0)):
    """Solid cylinder along +Y from y0..y1 centred at (x,z)=xz."""
    h = y1 - y0
    c = trimesh.creation.cylinder(radius=radius, height=h, sections=sections)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0]))
    c.apply_translation([xz[0], y0 + h / 2.0, xz[1]])
    return c


def _xcyl(radius, x0, x1, y, sections=24):
    """Solid cylinder along +X from x0..x1 at height y (a T-pose arm)."""
    w = x1 - x0
    c = trimesh.creation.cylinder(radius=radius, height=w, sections=sections)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0]))
    c.apply_translation([x0 + w / 2.0, y, 0.0])
    return c


def _tpose_parts():
    """Crude T-pose humanoid parts (centimetre scale).

    torso  : X in [-16, 16], Y in [80, 150]
    R arm  : X in [17, 55] at Y=142   (clear of the torso radius 16)
    L arm  : X in [-55, -17] at Y=142
    R leg  : centred x=+8, Y in [0, 80]
    L leg  : centred x=-8, Y in [0, 80]
    head   : centred Y=161 (so the mesh top is ~172)
    """
    head = trimesh.creation.icosphere(radius=11.0)
    head.apply_translation([0, 161, 0])
    return [
        _ycyl(16.0, 80.0, 150.0),
        _xcyl(5.0, 17.0, 55.0, 142.0),
        _xcyl(5.0, -55.0, -17.0, 142.0),
        _ycyl(9.0, 0.0, 80.0, xz=(8.0, 0.0)),
        _ycyl(9.0, 0.0, 80.0, xz=(-8.0, 0.0)),
        head,
    ]


@pytest.fixture
def tpose_cm():
    """T-pose humanoid in centimetres (concatenated, not unioned)."""
    return trimesh.util.concatenate(_tpose_parts())


@pytest.fixture
def tpose_m(tpose_cm):
    """Same humanoid scaled to metres, feet grounded at Y=0, centred X/Z."""
    m = tpose_cm.copy()
    m.apply_scale(0.01)
    (x0, _, z0), (x1, _, z1) = m.bounds
    m.apply_translation([-0.5 * (x0 + x1), -m.bounds[0][1], -0.5 * (z0 + z1)])
    return m


@pytest.fixture
def tiny_obj(tmp_path):
    """A 4-vertex draped-garment stand-in saved as OBJ, returns its path."""
    v = np.array([[0, 100, 0], [10, 100, 0], [0, 110, 0], [10, 110, 0]], dtype=float)
    f = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int64)
    p = tmp_path / "tiny_sim.obj"
    trimesh.Trimesh(vertices=v, faces=f, process=False).export(str(p))
    return p
```

- [ ] **Step 4: Verify fixtures import cleanly**

Run: `$PY -m pytest tests/mpfb_drape/conftest.py -q` (collects nothing, must not error)
Expected: `no tests ran` with exit 0 (import succeeds).

- [ ] **Step 5: Commit**

```bash
PY=/home/kubangpawis/dev/GarmentCode/.venv/bin/python
git add mpfb_drape/__init__.py tests/mpfb_drape/__init__.py tests/mpfb_drape/conftest.py
git commit -m "chore(mpfb_drape): package scaffold + shared test fixtures

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `bodyseg.segment_by_thresholds` (core partition)

**Files:**
- Create: `mpfb_drape/bodyseg.py`
- Test: `tests/mpfb_drape/test_bodyseg.py`

The six region keys must match `ggg_body_segmentation.json` exactly:
`body, left_arm, right_arm, left_leg, right_leg, face_internal`. Left = −X, right = +X (arbitrary but documented; the Warp filters union both sides so the sim is sign-agnostic). Arm test takes precedence over leg.

- [ ] **Step 1: Write the failing test**

`tests/mpfb_drape/test_bodyseg.py`:
```python
import numpy as np
from mpfb_drape import bodyseg

GGG_KEYS = {"body", "left_arm", "right_arm", "left_leg", "right_leg", "face_internal"}


def test_segment_partition_complete_and_disjoint(tpose_cm):
    v = np.asarray(tpose_cm.vertices)
    seg = bodyseg.segment_by_thresholds(v, arm_x=16.5, crotch_y=80.0)
    assert set(seg) == GGG_KEYS
    all_idx = [i for k in GGG_KEYS for i in seg[k]]
    assert sorted(all_idx) == list(range(len(v)))          # complete
    assert len(all_idx) == len(set(all_idx))                # disjoint


def test_arms_are_lateral_split_by_sign(tpose_cm):
    v = np.asarray(tpose_cm.vertices)
    seg = bodyseg.segment_by_thresholds(v, arm_x=16.5, crotch_y=80.0)
    assert seg["right_arm"] and seg["left_arm"]
    assert all(v[i, 0] > 16.5 for i in seg["right_arm"])
    assert all(v[i, 0] < -16.5 for i in seg["left_arm"])


def test_legs_are_low_and_central(tpose_cm):
    v = np.asarray(tpose_cm.vertices)
    seg = bodyseg.segment_by_thresholds(v, arm_x=16.5, crotch_y=80.0)
    assert seg["right_leg"] and seg["left_leg"]
    for i in seg["right_leg"] + seg["left_leg"]:
        assert v[i, 1] < 80.0 and abs(v[i, 0]) <= 16.5


def test_indices_in_range_and_face_internal_empty(tpose_cm):
    v = np.asarray(tpose_cm.vertices)
    seg = bodyseg.segment_by_thresholds(v, arm_x=16.5, crotch_y=80.0)
    assert seg["face_internal"] == []
    for k in GGG_KEYS:
        assert all(0 <= i < len(v) for i in seg[k])
        assert all(isinstance(i, int) for i in seg[k])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest tests/mpfb_drape/test_bodyseg.py -v`
Expected: FAIL — `AttributeError: module 'mpfb_drape.bodyseg' has no attribute 'segment_by_thresholds'`.

- [ ] **Step 3: Write minimal implementation**

`mpfb_drape/bodyseg.py`:
```python
"""Topology-matched body segmentation for an arbitrary (MPFB) body mesh.

GarmentCode's bundled ggg_body_segmentation.json is a dict of region ->
vertex-index lists bound to mean_all's 23752-vertex topology. An MPFB body has
different topology, so the Warp sim needs a segmentation expressed in the
avatar's own vertex indices, with the same six region keys:
    body, left_arm, right_arm, left_leg, right_leg, face_internal

Approach: geometric, topology-agnostic. The avatar is a known true T-pose
(Y-up, feet at Y=0, centred X/Z). Convention: left = -X, right = +X. The Warp
collision filters union both sides, so the sim is insensitive to that choice.
"""
from __future__ import annotations
import numpy as np

REGION_KEYS = ("body", "left_arm", "right_arm", "left_leg", "right_leg", "face_internal")


def segment_by_thresholds(vertices, arm_x, crotch_y):
    """Partition vertices into the six ggg regions using two thresholds.

    Args:
        vertices: (N, 3) array, Y-up, in the mesh's own units.
        arm_x:    |X| beyond which a vertex belongs to an arm.
        crotch_y: Y below which a non-arm vertex belongs to a leg.

    Returns dict {region_key: sorted list[int]}; complete + disjoint over
    range(N); face_internal is empty (the exported MPFB body has helpers
    stripped, and an empty filter is harmless).
    """
    v = np.asarray(vertices, dtype=float)
    x, y = v[:, 0], v[:, 1]

    is_arm = np.abs(x) > arm_x
    is_leg = (~is_arm) & (y < crotch_y)
    is_body = ~is_arm & ~is_leg
    right = x > 0.0  # +X

    def idx(mask):
        return [int(i) for i in np.nonzero(mask)[0]]

    return {
        "body": idx(is_body),
        "left_arm": idx(is_arm & ~right),
        "right_arm": idx(is_arm & right),
        "left_leg": idx(is_leg & ~right),
        "right_leg": idx(is_leg & right),
        "face_internal": [],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY -m pytest tests/mpfb_drape/test_bodyseg.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add mpfb_drape/bodyseg.py tests/mpfb_drape/test_bodyseg.py
git commit -m "feat(mpfb_drape): core body segmentation partition by thresholds

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `bodyseg.derive_thresholds` (geometric threshold estimation)

**Files:**
- Modify: `mpfb_drape/bodyseg.py`
- Test: `tests/mpfb_drape/test_bodyseg.py`

`arm_x`: in the upper half of the mesh, sort `|X|`; a T-pose puts a clear gap between the torso band (small `|X|`) and the arm cylinders (large `|X|`). Split at the largest gap if it is significant (> 5 % of height); otherwise (no lateral arms found) set `arm_x` above the max so no arm region is produced. `crotch_y`: default to 0.5 × height from the ground — sufficient to separate leg vertices for the (skirt/pants) leg filter; refinable from measurements later.

- [ ] **Step 1: Write the failing test (append)**

Append to `tests/mpfb_drape/test_bodyseg.py`:
```python
def test_derive_thresholds_finds_arm_gap(tpose_cm):
    v = np.asarray(tpose_cm.vertices)
    arm_x, crotch_y = bodyseg.derive_thresholds(v)
    # torso half-width is 16, arms start at 17 -> the cut sits in (16, 17)
    assert 16.0 <= arm_x <= 17.0
    # crotch at half height (~86 cm for this ~172 cm humanoid)
    assert 70.0 < crotch_y < 100.0


def test_derive_then_segment_matches_geometry(tpose_cm):
    v = np.asarray(tpose_cm.vertices)
    arm_x, crotch_y = bodyseg.derive_thresholds(v)
    seg = bodyseg.segment_by_thresholds(v, arm_x, crotch_y)
    assert seg["right_arm"] and seg["left_arm"]
    assert all(v[i, 0] > arm_x for i in seg["right_arm"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest tests/mpfb_drape/test_bodyseg.py::test_derive_thresholds_finds_arm_gap -v`
Expected: FAIL — `AttributeError: ... has no attribute 'derive_thresholds'`.

- [ ] **Step 3: Write minimal implementation (append to `bodyseg.py`)**

```python
def derive_thresholds(vertices):
    """Estimate (arm_x, crotch_y) geometrically from a T-pose mesh.

    arm_x: largest gap in sorted |X| over the upper half (torso vs arms).
    crotch_y: half the stature above the ground.
    """
    v = np.asarray(vertices, dtype=float)
    y = v[:, 1]
    ymin, ymax = float(y.min()), float(y.max())
    height = ymax - ymin

    upper = v[y > ymin + 0.5 * height]
    ax = np.sort(np.abs(upper[:, 0]))
    if ax.size >= 2:
        gaps = np.diff(ax)
        gi = int(np.argmax(gaps))
        if gaps[gi] > 0.05 * height:
            arm_x = float(0.5 * (ax[gi] + ax[gi + 1]))
        else:
            arm_x = float(ax[-1]) * 1.5  # no separated arms found laterally
    else:
        arm_x = float(np.abs(v[:, 0]).max()) * 1.5

    crotch_y = ymin + 0.5 * height
    return arm_x, crotch_y
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$PY -m pytest tests/mpfb_drape/test_bodyseg.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add mpfb_drape/bodyseg.py tests/mpfb_drape/test_bodyseg.py
git commit -m "feat(mpfb_drape): geometric arm/crotch threshold derivation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `bodyseg.build_segmentation` + JSON writer

**Files:**
- Modify: `mpfb_drape/bodyseg.py`
- Test: `tests/mpfb_drape/test_bodyseg.py`

One call from a mesh to the ggg-shaped dict, plus a writer that emits the exact JSON shape (`{region: [int, ...]}`).

- [ ] **Step 1: Write the failing test (append)**

```python
import json


def test_build_segmentation_from_mesh(tpose_cm):
    seg = bodyseg.build_segmentation(np.asarray(tpose_cm.vertices))
    assert set(seg) == GGG_KEYS
    assert seg["right_arm"] and seg["left_leg"]


def test_write_segmentation_json_shape(tpose_cm, tmp_path):
    seg = bodyseg.build_segmentation(np.asarray(tpose_cm.vertices))
    out = tmp_path / "avatar_bodyseg.json"
    bodyseg.write_segmentation(seg, out)
    loaded = json.loads(out.read_text())
    assert set(loaded) == GGG_KEYS
    assert all(isinstance(i, int) for i in loaded["body"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest tests/mpfb_drape/test_bodyseg.py::test_build_segmentation_from_mesh -v`
Expected: FAIL — no attribute `build_segmentation`.

- [ ] **Step 3: Write minimal implementation (append to `bodyseg.py`)**

```python
import json as _json
from pathlib import Path as _Path


def build_segmentation(vertices):
    """Full pipeline: derive thresholds, then partition into ggg regions."""
    arm_x, crotch_y = derive_thresholds(vertices)
    return segment_by_thresholds(vertices, arm_x, crotch_y)


def write_segmentation(seg, path):
    """Write the segmentation dict as ggg-shaped JSON ({region: [int,...]})."""
    path = _Path(path)
    path.write_text(_json.dumps({k: list(map(int, v)) for k, v in seg.items()}))
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$PY -m pytest tests/mpfb_drape/test_bodyseg.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add mpfb_drape/bodyseg.py tests/mpfb_drape/test_bodyseg.py
git commit -m "feat(mpfb_drape): build + write ggg-shaped body segmentation json

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `body_stage.stage_body`

**Files:**
- Create: `mpfb_drape/body_stage.py`
- Test: `tests/mpfb_drape/test_body_stage.py`

Stage the avatar so `PathCofig` can find it: ensure `<bodies_dir>/<name>.obj` (metres) and `<name>.yaml` exist (copy if the source is elsewhere), then build + write `<name>_bodyseg.json` from the staged obj. Return a small record.

- [ ] **Step 1: Write the failing test**

`tests/mpfb_drape/test_body_stage.py`:
```python
import json
from pathlib import Path
from mpfb_drape import body_stage


def _write_min_body_yaml(path):
    path.write_text("body:\n  height: 172.0\n  arm_pose_angle: 0.0\n")


def test_stage_body_copies_and_segments(tpose_m, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    obj = src / "avatar.obj"
    tpose_m.export(str(obj))
    yaml_path = src / "avatar.yaml"
    _write_min_body_yaml(yaml_path)

    bodies = tmp_path / "bodies"
    staged = body_stage.stage_body(yaml_path, obj, bodies, name="avatar")

    assert (bodies / "avatar.obj").exists()
    assert (bodies / "avatar.yaml").exists()
    seg_path = Path(staged["body_seg"])
    assert seg_path.exists()
    seg = json.loads(seg_path.read_text())
    assert set(seg) == {"body", "left_arm", "right_arm", "left_leg", "right_leg", "face_internal"}
    assert staged["body_name"] == "avatar"
    assert seg["right_arm"]  # arms detected on the metres mesh


def test_stage_body_defaults_name_from_yaml_stem(tpose_m, tmp_path):
    obj = tmp_path / "bob.obj"
    tpose_m.export(str(obj))
    y = tmp_path / "bob.yaml"
    _write_min_body_yaml(y)
    staged = body_stage.stage_body(y, obj, tmp_path / "bodies")
    assert staged["body_name"] == "bob"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest tests/mpfb_drape/test_body_stage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpfb_drape.body_stage'`.

- [ ] **Step 3: Write minimal implementation**

`mpfb_drape/body_stage.py`:
```python
"""Stage an ingested MPFB avatar so the GarmentCode sim can collide against it.

PathCofig resolves the body collider as <bodies_dir>/<name>.obj (metres) and
measurements as <name>.yaml. The bundled ggg segmentation is topology-bound to
mean_all, so we also write <name>_bodyseg.json for THIS avatar's topology; the
pipeline injects it via paths.body_seg.
"""
from __future__ import annotations
import shutil
from pathlib import Path

import trimesh

from mpfb_drape import bodyseg


def stage_body(body_yaml, body_obj, bodies_dir, name=None):
    """Copy avatar obj+yaml into bodies_dir and write its body segmentation.

    Returns {body_name, bodies_dir, obj, yaml, body_seg} as str paths.
    """
    body_yaml, body_obj, bodies_dir = Path(body_yaml), Path(body_obj), Path(bodies_dir)
    if name is None:
        name = body_yaml.stem
    bodies_dir.mkdir(parents=True, exist_ok=True)

    dst_obj = bodies_dir / f"{name}.obj"
    dst_yaml = bodies_dir / f"{name}.yaml"
    if dst_obj.resolve() != body_obj.resolve():
        shutil.copyfile(body_obj, dst_obj)
    if dst_yaml.resolve() != body_yaml.resolve():
        shutil.copyfile(body_yaml, dst_yaml)

    mesh = trimesh.load(str(dst_obj), process=False, force="mesh")
    seg = bodyseg.build_segmentation(mesh.vertices)
    seg_path = bodyseg.write_segmentation(seg, bodies_dir / f"{name}_bodyseg.json")

    return {
        "body_name": name,
        "bodies_dir": str(bodies_dir),
        "obj": str(dst_obj),
        "yaml": str(dst_yaml),
        "body_seg": str(seg_path),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$PY -m pytest tests/mpfb_drape/test_body_stage.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add mpfb_drape/body_stage.py tests/mpfb_drape/test_body_stage.py
git commit -m "feat(mpfb_drape): stage avatar + write topology-matched body seg

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `fit.fit_pattern`

**Files:**
- Create: `mpfb_drape/fit.py`
- Test: `tests/mpfb_drape/test_fit.py`

Build a `BodyParameters` from the avatar yaml + a design dict, assemble the `MetaGarment`, and serialize the 2-D pattern (no 3-D) into a spec subfolder. Mirror `pattern_fitter._save_sample`: `pattern = piece.assembly(); folder = pattern.serialize(folder, tag='', to_subfolder=True, with_3d=False, with_text=False, view_ids=False)` — `serialize` returns the subfolder containing `<name>_specification.json`. Uses a bundled body yaml + the bundled `t-shirt.yaml` design (CPU only, no GPU).

- [ ] **Step 1: Write the failing test**

`tests/mpfb_drape/test_fit.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest tests/mpfb_drape/test_fit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpfb_drape.fit'`.

- [ ] **Step 3: Write minimal implementation**

`mpfb_drape/fit.py`:
```python
"""Fit a garment design to body measurements -> a serialized sewing pattern.

Mirrors pattern_fitter._save_sample: MetaGarment(name, body, design) ->
piece.assembly() -> pattern.serialize(...). The serialized folder contains
<name>_specification.json, which PathCofig consumes for the box-mesh + sim.
"""
from __future__ import annotations
from pathlib import Path

from assets.bodies.body_params import BodyParameters
from assets.garment_programs.meta_garment import MetaGarment


def fit_pattern(body_yaml, design, out_dir, name):
    """Return (spec_folder, name). Writes <spec_folder>/<name>_specification.json."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    body = BodyParameters(str(body_yaml))
    piece = MetaGarment(name, body, design)
    pattern = piece.assembly()
    spec_folder = pattern.serialize(
        str(out_dir),
        tag="",
        to_subfolder=True,
        with_3d=False,
        with_text=False,
        view_ids=False,
    )
    return str(spec_folder), name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY -m pytest tests/mpfb_drape/test_fit.py -v`
Expected: 1 passed. (If `serialize` rejects an unknown kwarg, drop only that kwarg — keep `to_subfolder=True, with_3d=False`. Verify against `pygarment/pattern/wrappers.py:55`.)

- [ ] **Step 5: Commit**

```bash
git add mpfb_drape/fit.py tests/mpfb_drape/test_fit.py
git commit -m "feat(mpfb_drape): fit design+body into a serialized sewing pattern

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `verify.acceptance`

**Files:**
- Create: `mpfb_drape/verify.py`
- Test: `tests/mpfb_drape/test_verify.py`

Pure function over `(stats, design_name, sim_obj_path, body_obj_path)`. `stats` is `props['sim']['stats']` after a run. PASS requires: design not in any `fails[...]` list; `body_collisions[name] <= max_body_collisions`; `self_collisions[name] <= max_self_collisions`; sim obj finite, non-empty, and its bbox within the body bbox grown by a margin (catches fly-away/explosion). Returns a verdict dict.

- [ ] **Step 1: Write the failing test**

`tests/mpfb_drape/test_verify.py`:
```python
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
    v = np.array([[0, 0, 0], [np.nan, 0, 0], [0, 1, 0]], dtype=float)
    f = np.array([[0, 1, 2]], dtype=np.int64)
    p = tmp_path / "nan.obj"
    # export raw so NaN survives
    p.write_text("v 0 0 0\nv nan 0 0\nv 0 1 0\nf 1 2 3\n")
    res = verify.acceptance(_stats("g"), "g", p, body, 35, 300)
    assert res["passed"] is False
    assert any("nan" in r.lower() or "finite" in r.lower() for r in res["reasons"])


def test_fail_on_flyaway_bbox(tiny_obj, tmp_path):
    body = _body_obj(tmp_path)
    # tiny_obj at Y~100 m relative to a 1.7 m body -> way outside -> fly-away
    v = verify.acceptance(_stats("g"), "g", tiny_obj, body, 35, 300)
    assert v["passed"] is False
    assert any("bbox" in r or "outside" in r for r in v["reasons"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest tests/mpfb_drape/test_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpfb_drape.verify'`.

- [ ] **Step 3: Write minimal implementation**

`mpfb_drape/verify.py`:
```python
"""Acceptance check for one drape: sanity + penetration + settle.

Penetration and settle are read from the stats run_sim already records; sanity
(finite, non-empty, in-bounds) is computed here from the draped OBJ. Pure and
GPU-free.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import trimesh

BBOX_MARGIN = 0.30  # metres of slack around the body bbox before "fly-away"


def acceptance(stats, design_name, sim_obj_path, body_obj_path,
               max_body_collisions=35, max_self_collisions=300):
    """Return {passed: bool, reasons: list[str], metrics: dict}."""
    reasons, metrics = [], {}

    # --- settle + hard failures (from run_sim stats) ---
    fails = stats.get("fails", {}) or {}
    for ftype, names in fails.items():
        if design_name in (names or []):
            reasons.append(ftype)

    # --- penetration (from run_sim stats) ---
    body_pen = (stats.get("body_collisions", {}) or {}).get(design_name)
    self_pen = (stats.get("self_collisions", {}) or {}).get(design_name)
    metrics["body_collisions"] = body_pen
    metrics["self_collisions"] = self_pen
    if body_pen is not None and body_pen > max_body_collisions:
        reasons.append(f"body_penetration {body_pen} > {max_body_collisions}")
    if self_pen is not None and self_pen > max_self_collisions:
        reasons.append(f"self_penetration {self_pen} > {max_self_collisions}")

    # --- sanity on the draped mesh ---
    sim_obj_path = Path(sim_obj_path)
    if not sim_obj_path.exists():
        reasons.append("sim_obj_missing")
        return {"passed": False, "reasons": reasons, "metrics": metrics}

    mesh = trimesh.load(str(sim_obj_path), process=False, force="mesh")
    v = np.asarray(mesh.vertices, dtype=float)
    metrics["n_vertices"] = int(len(v))
    if len(v) == 0:
        reasons.append("sim_obj_empty")
    elif not np.isfinite(v).all():
        reasons.append("non_finite_vertices (nan/inf)")
    else:
        body = trimesh.load(str(body_obj_path), process=False, force="mesh")
        bmin, bmax = np.asarray(body.bounds[0]), np.asarray(body.bounds[1])
        gmin, gmax = v.min(axis=0), v.max(axis=0)
        if (gmin < bmin - BBOX_MARGIN).any() or (gmax > bmax + BBOX_MARGIN).any():
            reasons.append("bbox_outside_body (fly-away/explosion)")

    return {"passed": len(reasons) == 0, "reasons": reasons, "metrics": metrics}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$PY -m pytest tests/mpfb_drape/test_verify.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add mpfb_drape/verify.py tests/mpfb_drape/test_verify.py
git commit -m "feat(mpfb_drape): drape acceptance (sanity + penetration + settle)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: `manifest`

**Files:**
- Create: `mpfb_drape/manifest.py`
- Test: `tests/mpfb_drape/test_manifest.py`

Aggregate per-design result records into one manifest dict + write JSON.

- [ ] **Step 1: Write the failing test**

`tests/mpfb_drape/test_manifest.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest tests/mpfb_drape/test_manifest.py -v`
Expected: FAIL — no module `mpfb_drape.manifest`.

- [ ] **Step 3: Write minimal implementation**

`mpfb_drape/manifest.py`:
```python
"""Aggregate per-design drape results into one wardrobe manifest."""
from __future__ import annotations
import json
from pathlib import Path


def build(body_name, results):
    passed = sum(1 for r in results if r["verdict"]["passed"])
    return {
        "body": body_name,
        "designs": results,
        "summary": {"total": len(results), "passed": passed,
                    "failed": len(results) - passed},
    }


def write(man, path):
    path = Path(path)
    path.write_text(json.dumps(man, indent=2))
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY -m pytest tests/mpfb_drape/test_manifest.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add mpfb_drape/manifest.py tests/mpfb_drape/test_manifest.py
git commit -m "feat(mpfb_drape): wardrobe manifest aggregation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: `pipeline.make_sim_props` (props builder)

**Files:**
- Create: `mpfb_drape/pipeline.py`
- Test: `tests/mpfb_drape/test_pipeline.py`

Build the `Properties` object `template_simulation` needs: load `default_sim_props.yaml`, run `init_sim_props` (which adds the full stats structure `template_simulation` writes — `meshgen_time`, `face_count`, etc.), and **force `optimize_storage=False`** (the yaml sets it `true`, which deletes the `.obj` + texture after sim and would break verify + the standard export).

- [ ] **Step 1: Write the failing test**

`tests/mpfb_drape/test_pipeline.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest tests/mpfb_drape/test_pipeline.py::test_make_sim_props_has_stats_and_no_optimize -v`
Expected: FAIL — no module `mpfb_drape.pipeline`.

- [ ] **Step 3: Write minimal implementation**

`mpfb_drape/pipeline.py`:
```python
"""Orchestrate a single drape and a wardrobe of drapes onto one MPFB body.

drape_one: fit -> stage -> PathCofig (+ body_seg injection) ->
template_simulation (BoxMesh -> load -> serialize -> run_sim) -> verify.
"""
from __future__ import annotations
from pathlib import Path

from pygarment.data_config import Properties
import pygarment.meshgen.datasim_utils as sim
from pygarment.meshgen.sim_config import PathCofig


def make_sim_props(sim_props_yaml):
    """Build the Properties object template_simulation expects.

    Loads the sim/render config, ensures the full stats structure via
    init_sim_props, and forces optimize_storage off so the .obj/.glb/texture
    are preserved for verification and export.
    """
    props = Properties(str(sim_props_yaml))
    sim.init_sim_props(props)                 # adds meshgen_time/face_count/etc.
    props["sim"]["config"]["optimize_storage"] = False
    return props
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY -m pytest tests/mpfb_drape/test_pipeline.py::test_make_sim_props_has_stats_and_no_optimize -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add mpfb_drape/pipeline.py tests/mpfb_drape/test_pipeline.py
git commit -m "feat(mpfb_drape): sim Properties builder (stats + optimize_storage off)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: `pipeline.drape_one` (with injectable sim runner)

**Files:**
- Modify: `mpfb_drape/pipeline.py`
- Test: `tests/mpfb_drape/test_pipeline.py`

Wire fit → stage → `PathCofig` → inject `paths.body_seg` → run the sim → verify → result record. The actual sim call is taken as a parameter (`run=sim.template_simulation` by default) so unit tests can stub it; the gated test uses the real one. The stub asserts the body-seg override happened and writes a fake draped obj so verify runs.

- [ ] **Step 1: Write the failing test (append)**

```python
import json
import trimesh
import yaml


def _min_body_yaml(p):
    p.write_text("body:\n  height: 172.0\n  arm_pose_angle: 0.0\n")


def test_drape_one_injects_seg_and_returns_record(tpose_m, tmp_path, monkeypatch):
    # avatar
    body_dir = tmp_path / "in"; body_dir.mkdir()
    obj = body_dir / "avatar.obj"; tpose_m.export(str(obj))
    yml = body_dir / "avatar.yaml"; _min_body_yaml(yml)
    with open(REPO / "assets/design_params/t-shirt.yaml") as f:
        design = yaml.safe_load(f)["design"]

    captured = {}

    def fake_run(paths, props, caching=False):
        captured["body_seg"] = str(paths.body_seg)
        captured["body_obj"] = str(paths.in_body_obj)
        # write a small in-bounds draped obj where run_sim would (paths.g_sim)
        m = trimesh.creation.box(extents=[0.4, 0.5, 0.2]); m.apply_translation([0, 1.2, 0])
        m.export(str(paths.g_sim))
        props["sim"]["stats"]["body_collisions"][paths.sim_tag] = 2
        props["sim"]["stats"]["self_collisions"][paths.sim_tag] = 0

    res = pipeline.drape_one(
        yml, obj, design, out_dir=tmp_path / "out",
        bodies_dir=tmp_path / "bodies", name="tee",
        sim_props_yaml=DEFAULT_SIM, run=fake_run)

    assert res["design"] == "tee"
    assert res["verdict"]["passed"] is True
    # body_seg points at OUR generated avatar seg, not the bundled ggg
    assert res["body_name"] == "avatar"
    assert "avatar_bodyseg.json" in captured["body_seg"]
    assert json.loads(Path(captured["body_seg"]).read_text())  # valid seg json
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest tests/mpfb_drape/test_pipeline.py::test_drape_one_injects_seg_and_returns_record -v`
Expected: FAIL — `AttributeError: module 'mpfb_drape.pipeline' has no attribute 'drape_one'`.

- [ ] **Step 3: Write minimal implementation (append to `pipeline.py`)**

```python
from mpfb_drape import fit as _fit
from mpfb_drape import body_stage as _stage
from mpfb_drape import verify as _verify


def drape_one(body_yaml, body_obj, design, out_dir, bodies_dir, name,
              sim_props_yaml, run=None, render=False):
    """Fit + drape one design onto one staged avatar; return a result record."""
    run = run if run is not None else sim.template_simulation
    out_dir, bodies_dir = Path(out_dir), Path(bodies_dir)

    # 1) fit -> spec folder containing <name>_specification.json
    spec_dir, name = _fit.fit_pattern(body_yaml, design, out_dir / "_specs", name=name)

    # 2) stage avatar + topology-matched body segmentation
    staged = _stage.stage_body(body_yaml, body_obj, bodies_dir)

    # 3) paths, with body_seg overridden to OUR avatar segmentation
    props = make_sim_props(sim_props_yaml)
    paths = PathCofig(
        in_element_path=spec_dir,
        out_path=str(out_dir),
        in_name=name,
        body_name=staged["body_name"],
        default_body=True,
    )
    paths.in_body_obj = Path(staged["obj"])   # use the staged avatar obj
    paths.body_seg = Path(staged["body_seg"])  # topology-matched override

    # 4) drape (BoxMesh -> load -> serialize -> run_sim) — never raises
    run(paths, props)

    # 5) verify
    cfg = props["sim"]["config"]
    verdict = _verify.acceptance(
        props["sim"]["stats"], name, paths.g_sim, paths.in_body_obj,
        max_body_collisions=cfg.get("max_body_collisions", 35),
        max_self_collisions=cfg.get("max_self_collisions", 300),
    )

    sim_glb = Path(paths.g_sim_glb)
    return {
        "design": name,
        "body_name": staged["body_name"],
        "verdict": verdict,
        "out_folder": str(paths.out_el),
        "sim_obj": str(paths.g_sim),
        "sim_glb": str(sim_glb) if sim_glb.exists() else None,
    }
```

Note: `PathCofig.__init__` reads `bodies_path/<body_name>.yaml`; because we stage `avatar.yaml` into `bodies_dir`, point `system.json`'s `bodies_default_path` at it OR keep `bodies_dir = assets/bodies` (default). The default path in `system.json` is `./assets/bodies`; staging there (default `bodies_dir`) keeps `PathCofig` happy with no system.json edit. The test passes an explicit `bodies_dir` and overrides `paths.in_body_obj`, so construction must not fail — if `PathCofig` raises on a missing `bodies_path/<name>.yaml`, set `bodies_dir` default to `assets/bodies` in `drape_wardrobe` (Task 11) and ensure the avatar yaml is staged there before constructing `PathCofig`. (Staging happens at step 2, before step 3, so the yaml is present.)

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY -m pytest tests/mpfb_drape/test_pipeline.py -v`
Expected: 2 passed. (If `PathCofig` reads `system.json` `bodies_default_path` and cannot find `<name>.yaml`, the staged copy must live in that dir — adjust the test's `bodies_dir` to `REPO/'assets/bodies'` and clean up the staged files in a fixture teardown. Prefer keeping `bodies_dir` under the system bodies path.)

- [ ] **Step 5: Commit**

```bash
git add mpfb_drape/pipeline.py tests/mpfb_drape/test_pipeline.py
git commit -m "feat(mpfb_drape): drape_one orchestration with body_seg injection

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: `pipeline.drape_wardrobe` (many designs × one body)

**Files:**
- Modify: `mpfb_drape/pipeline.py`
- Test: `tests/mpfb_drape/test_pipeline.py`

Resolve designs (a directory → every `*.yaml`, or an explicit list of files), drape each onto the one avatar, aggregate into a manifest. Each design's `design` block is read with `yaml.safe_load(...)['design']`. Continues past a failed design (records its verdict).

- [ ] **Step 1: Write the failing test (append)**

```python
def test_drape_wardrobe_folder_and_manifest(tpose_m, tmp_path, monkeypatch):
    body_dir = tmp_path / "in"; body_dir.mkdir()
    obj = body_dir / "avatar.obj"; tpose_m.export(str(obj))
    yml = body_dir / "avatar.yaml"; _min_body_yaml(yml)

    designs_dir = tmp_path / "designs"; designs_dir.mkdir()
    for src in ("t-shirt.yaml",):
        (designs_dir / src).write_text((REPO / "assets/design_params" / src).read_text())

    calls = []

    def fake_drape_one(*a, **k):
        calls.append(k.get("name"))
        return {"design": k.get("name"), "body_name": "avatar",
                "verdict": {"passed": True, "reasons": [], "metrics": {}},
                "out_folder": "x", "sim_obj": "x", "sim_glb": None}

    monkeypatch.setattr(pipeline, "drape_one", fake_drape_one)
    man = pipeline.drape_wardrobe(
        yml, obj, designs_dir, out_dir=tmp_path / "out",
        bodies_dir=tmp_path / "bodies", sim_props_yaml=DEFAULT_SIM)

    assert man["summary"]["total"] == 1
    assert (tmp_path / "out" / "wardrobe_manifest.json").exists()


def test_resolve_designs_accepts_list_and_dir(tmp_path):
    d = tmp_path / "d"; d.mkdir()
    (d / "a.yaml").write_text("design: {}")
    (d / "b.yaml").write_text("design: {}")
    assert len(pipeline.resolve_designs([d])) == 2
    assert len(pipeline.resolve_designs([d / "a.yaml"])) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest tests/mpfb_drape/test_pipeline.py::test_resolve_designs_accepts_list_and_dir -v`
Expected: FAIL — no attribute `resolve_designs`.

- [ ] **Step 3: Write minimal implementation (append to `pipeline.py`)**

```python
import yaml as _yaml
from mpfb_drape import manifest as _manifest

DEFAULT_BODIES_DIR = "assets/bodies"


def resolve_designs(designs):
    """Accept a dir (every *.yaml) or explicit file paths -> sorted file list."""
    out = []
    for d in designs:
        d = Path(d)
        if d.is_dir():
            out.extend(sorted(d.glob("*.yaml")))
        else:
            out.append(d)
    return out


def drape_wardrobe(body_yaml, body_obj, designs, out_dir, sim_props_yaml,
                   bodies_dir=DEFAULT_BODIES_DIR, render=False):
    """Drape many designs onto one avatar; write + return the manifest."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    results, body_name = [], None
    for design_file in resolve_designs(designs):
        design = _yaml.safe_load(Path(design_file).read_text())["design"]
        name = Path(design_file).stem
        res = drape_one(body_yaml, body_obj, design, out_dir=out_dir,
                        bodies_dir=bodies_dir, name=name,
                        sim_props_yaml=sim_props_yaml, render=render)
        body_name = res["body_name"]
        results.append(res)
    man = _manifest.build(body_name, results)
    _manifest.write(man, out_dir / "wardrobe_manifest.json")
    return man
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$PY -m pytest tests/mpfb_drape/test_pipeline.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add mpfb_drape/pipeline.py tests/mpfb_drape/test_pipeline.py
git commit -m "feat(mpfb_drape): drape_wardrobe (folder|list) + manifest

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: root CLI `drape_mpfb_garment.py`

**Files:**
- Create: `drape_mpfb_garment.py`
- Test: `tests/mpfb_drape/test_cli.py`

`main(argv)` returns an exit code; errors are clear (mirrors the `mpfb_tpose` CLI error-clarity style). `--body` is the measurements yaml; the sibling `.obj` (same stem) is the collider unless `--body-obj` is given. `--designs` accepts a folder or explicit files (nargs="+").

- [ ] **Step 1: Write the failing test**

`tests/mpfb_drape/test_cli.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest tests/mpfb_drape/test_cli.py -v`
Expected: FAIL — file `drape_mpfb_garment.py` does not exist (spec load error).

- [ ] **Step 3: Write minimal implementation**

`drape_mpfb_garment.py`:
```python
"""CLI: fit + drape GarmentCode garments onto a normalized MPFB body.

Usage:
  .venv/bin/python drape_mpfb_garment.py \
      --body assets/bodies/avatar.yaml \
      --designs assets/design_params/ \
      --out .temp/wardrobe [--body-obj path] [--sim-props ...] [--render]

--designs accepts a directory (every *.yaml) or explicit file paths.
Pass a true-T-pose avatar ingested with `--arm-pose-angle 0`.
"""
import argparse
import sys
from pathlib import Path

DEFAULT_SIM_PROPS = "assets/Sim_props/default_sim_props.yaml"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", required=True, help="body-measurements YAML (mpfb_ingest output)")
    ap.add_argument("--body-obj", default=None, help="collider OBJ (default: sibling <body>.obj)")
    ap.add_argument("--designs", nargs="+", required=True, help="design YAML dir or files")
    ap.add_argument("--out", required=True, help="output dir for the wardrobe run")
    ap.add_argument("--bodies-dir", default="assets/bodies", help="where to stage the avatar")
    ap.add_argument("--sim-props", default=DEFAULT_SIM_PROPS)
    ap.add_argument("--render", action="store_true")
    a = ap.parse_args(argv)

    from mpfb_drape import pipeline

    body_yaml = Path(a.body)
    if not body_yaml.is_file():
        ap.error(f"--body not found: {body_yaml}")
    body_obj = Path(a.body_obj) if a.body_obj else body_yaml.with_suffix(".obj")
    if not body_obj.is_file():
        ap.error(f"body OBJ not found: {body_obj} (pass --body-obj or place <body>.obj beside the yaml)")

    designs = pipeline.resolve_designs(a.designs)
    if not designs:
        ap.error(f"no design YAMLs found in: {a.designs}")

    man = pipeline.drape_wardrobe(
        body_yaml, body_obj, a.designs, out_dir=a.out,
        sim_props_yaml=a.sim_props, bodies_dir=a.bodies_dir, render=a.render)

    s = man["summary"]
    print(f"DRAPE_DONE total={s['total']} passed={s['passed']} failed={s['failed']} "
          f"manifest={Path(a.out) / 'wardrobe_manifest.json'}")
    return 0 if s["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$PY -m pytest tests/mpfb_drape/test_cli.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add drape_mpfb_garment.py tests/mpfb_drape/test_cli.py
git commit -m "feat(mpfb_drape): root CLI drape_mpfb_garment.py

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: gated end-to-end drape (real Warp sim)

**Files:**
- Create: `tests/mpfb_drape/test_end_to_end.py`

Real ingest → drape, gated on CUDA/Warp (skip otherwise — mirrors the existing gated tests in `mpfb_ingest` / `mpfb_tpose`). Uses the committed MPFB base mesh `mpfb_ingest/data/mpfb_base_body.obj` via the auto path, then drapes the bundled `t-shirt.yaml`. The body is staged under `assets/bodies` (the `system.json` default) so `PathCofig` resolves it; the test cleans up the staged files.

- [ ] **Step 1: Write the gated test**

`tests/mpfb_drape/test_end_to_end.py`:
```python
from pathlib import Path
import shutil
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


def test_end_to_end_drape_tshirt(tmp_path):
    import ingest_mpfb_body as ingest
    from mpfb_drape import pipeline

    # 1) ingest the committed MPFB base body (auto path, T-pose angle 0)
    src_obj = REPO / "mpfb_ingest/data/mpfb_base_body.obj"
    out_bodies = REPO / "assets/bodies"
    name = "e2e_avatar"
    ingest.run(str(src_obj), str(out_bodies), name, landmarks_path=None,
               arm_pose_angle=0.0, save_obj=True, fill_defaults=True)
    body_yaml = out_bodies / f"{name}.yaml"
    body_obj = out_bodies / f"{name}.obj"
    seg_extra = out_bodies / f"{name}_bodyseg.json"

    try:
        with open(REPO / "assets/design_params/t-shirt.yaml") as f:
            design = yaml.safe_load(f)["design"]
        res = pipeline.drape_one(
            body_yaml, body_obj, design, out_dir=tmp_path / "out",
            bodies_dir=out_bodies, name="tee",
            sim_props_yaml=REPO / "assets/Sim_props/default_sim_props.yaml")

        assert Path(res["sim_obj"]).exists()
        assert res["verdict"]["passed"], res["verdict"]["reasons"]
    finally:
        for p in (body_yaml, body_obj, seg_extra):
            p.unlink(missing_ok=True)
```

- [ ] **Step 2: Run the test**

Run: `$PY -m pytest tests/mpfb_drape/test_end_to_end.py -v`
Expected: PASS (if CUDA present) or SKIPPED. If it FAILS on penetration/fly-away, that is the real-drape signal the spec's risk section anticipates — tune via a dedicated `assets/Sim_props/` preset or refine `bodyseg` thresholds, then re-run. Do **not** weaken `verify` to force a pass.

- [ ] **Step 3: Commit**

```bash
git add tests/mpfb_drape/test_end_to_end.py
git commit -m "test(mpfb_drape): gated end-to-end ingest->drape on real MPFB body

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: README + spec status

**Files:**
- Create: `mpfb_drape/README.md`
- Modify: `docs/superpowers/specs/2026-06-09-mpfb-drape-fitting-design.md` (status line)

- [ ] **Step 1: Write the README (as-built)**

`mpfb_drape/README.md` — cover: purpose (third stage of mpfb_tpose → mpfb_ingest → mpfb_drape); the CLI usage block from `drape_mpfb_garment.py`; pose convention (ingest the avatar with `--arm-pose-angle 0`); why a topology-matched body segmentation is generated (ggg is index-bound to `mean_all`); outputs (per-design GarmentCode export folders + `wardrobe_manifest.json`); the acceptance bar (sanity + penetration + settle); how to run the fast tests vs the gated drape test; known limitations (combined dressed-avatar GLB and rig-based segmentation are future work, per the spec §11).

- [ ] **Step 2: Flip the spec status**

In `docs/superpowers/specs/2026-06-09-mpfb-drape-fitting-design.md`, change
`**Status:** Design approved (brainstorming). Pending plan.` to
`**Status:** Implemented (as-built). See mpfb_drape/README.md.`

- [ ] **Step 3: Run the full fast suite (regression gate)**

Run: `$PY -m pytest tests/mpfb_drape tests/mpfb_ingest tests/mpfb_tpose/test_geometry.py -q`
Expected: all green (gated CUDA test skipped if no GPU); no regressions vs the pre-work baseline (57 passed, 13 skipped).

- [ ] **Step 4: Commit**

```bash
git add mpfb_drape/README.md docs/superpowers/specs/2026-06-09-mpfb-drape-fitting-design.md
git commit -m "docs(mpfb_drape): README (as-built) + spec status

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (author checklist — completed)

**Spec coverage:** §2 data flow → Tasks 6/9/10/11; §4 module layout → Tasks 1–12; §5 segmentation (approach A) → Tasks 2–5; §6 pipeline (reuse `template_simulation`, `paths.body_seg` override, props from `default_sim_props.yaml`, units) → Tasks 9/10; §7 verify (settle+penetration from stats, sanity here) → Task 7; §8 CLI + manifest (folder|list, standard export, manifest) → Tasks 8/11/12; §9 testing (fast units + gated e2e) → Tasks 2–13; §10 risks (seg accuracy, facing, T-pose stability) → surfaced in Task 13. §11 out-of-scope explicitly deferred (no tasks — correct).

**Placeholder scan:** no TBD/TODO; every code step shows complete code; commands have expected output.

**Type consistency:** `segment_by_thresholds(vertices, arm_x, crotch_y)` and `build_segmentation`/`write_segmentation` used identically across Tasks 2–5; `stage_body(...)` returns the `{body_name, obj, yaml, body_seg, bodies_dir}` dict consumed verbatim in Task 10; `acceptance(stats, design_name, sim_obj_path, body_obj_path, max_body_collisions, max_self_collisions)` signature matches its callsite in `drape_one`; `drape_one`/`drape_wardrobe`/`resolve_designs`/`make_sim_props` names match the CLI and tests; manifest `build(body_name, results)`/`write(man, path)` match Task 11 + 8.

**Known soft spots flagged for the executor (not placeholders):** `pattern.serialize` kwargs (verify against `pygarment/pattern/wrappers.py:55`); `PathCofig` requiring the staged `<name>.yaml` under `system.json`'s `bodies_default_path` (stage into `assets/bodies`); real-drape tuning in Task 13.
