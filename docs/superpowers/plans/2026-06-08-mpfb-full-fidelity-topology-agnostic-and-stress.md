# MPFB Full-Fidelity, Topology-Agnostic Extractor + Stress Suite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `mpfb_ingest/` compute all 26 GarmentCode body fields from per-mesh geometry on *any* human mesh (the user's `.temp/avatar_base.glb`, raw MPFB exports, synthesized bodies), and prove it with a real-MPFB headless test-set generator plus a cross-body stress suite.

**Architecture:** Add a per-mesh geometric landmarker `mpfb_ingest/autolandmarks.py` that returns a `Landmarks`-compatible object (same interface the existing `measurements.compute_all` already consumes), so the 26-field math is reused unchanged except for one arm-exclusion fix in `circumferences`. A new arm-aware `geometry.central_loop` excludes T-pose arms from horizontal slices. `mesh_io` gains unit auto-detection so true height is measured, not forced. The CLI defaults to the auto path; the committed-index JSON path stays for regression. A Blender-headless generator (`scripts/gen_mpfb_testset.py`) sweeps `macro_detail_dict` to emit a varied body grid the stress tests run across.

**Tech Stack:** Python 3.9, trimesh 4.12 (BSD), libigl (MPL2), numpy (BSD), pytest. Generator: Blender 5.1.2 + MPFB 2.0.15 (`bpy`, official service API). All permissive / CC0 — no GPL deps, no GarmentMeasurements code.

**Reference spec:** `docs/superpowers/specs/2026-06-08-mpfb-full-fidelity-topology-agnostic-and-stress.md`
**Predecessor:** `docs/superpowers/specs/2026-06-05-garmentcode-mpfb-measurement-ingestion-handoff.md`

**Environment notes (verified):**
- Python: `.venv/bin/python`; tests: `.venv/bin/python -m pytest`.
- Blender: `/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe`.
- MPFB data: `/mnt/c/Users/KubangPawis/AppData/Roaming/Blender Foundation/Blender/5.1/extensions/blender_org/mpfb/data`.
- The glb under test: `.temp/avatar_base.glb` (14517 verts, already metres+grounded, Y-up, front=+Z).

**Out of scope:** draping (segmentation JSON + `PathCofig.body_seg`).

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `mpfb_ingest/geometry.py` | central (arm-excluded) torso loop + point pickers | MODIFY |
| `mpfb_ingest/mesh_io.py` | unit auto-detect; measure (don't force) height | MODIFY |
| `mpfb_ingest/measurements.py` | torso circumferences use central loop | MODIFY |
| `mpfb_ingest/autolandmarks.py` | per-mesh geometric landmark derivation | CREATE |
| `mpfb_ingest/landmarks.py` | reused as the landmark container (no change needed) | — |
| `ingest_mpfb_body.py` | default auto path; `--landmarks` optional | MODIFY |
| `scripts/gen_mpfb_testset.py` | MPFB headless batch body generator (runs in Blender) | CREATE |
| `scripts/run_mpfb_gen.sh` | WSL→Windows Blender launcher | CREATE |
| `tests/mpfb_ingest/conftest.py` | add a synthetic T-pose body fixture | MODIFY |
| `tests/mpfb_ingest/test_geometry_central.py` | central-loop arm exclusion | CREATE |
| `tests/mpfb_ingest/test_mesh_io_units.py` | unit detection / measured height | CREATE |
| `tests/mpfb_ingest/test_autolandmarks.py` | levels + landmarks on real base | CREATE |
| `tests/mpfb_ingest/test_stress_glb.py` | glb end-to-end ingest + generation | CREATE |
| `tests/mpfb_ingest/test_testset_assets.py` | generated-set asset sanity (skip if absent) | CREATE |
| `tests/mpfb_ingest/test_stress_testset.py` | cross-body property tests (skip if absent) | CREATE |
| `mpfb_ingest/README.md` | document auto path + generator | MODIFY |

---

## Task 1: Synthetic T-pose body fixture

**Files:**
- Modify: `tests/mpfb_ingest/conftest.py`

- [ ] **Step 1: Add the fixture**

Append to `tests/mpfb_ingest/conftest.py`:

```python
def _ycyl(radius, y0, y1, sections=48, xz=(0.0, 0.0)):
    """Solid cylinder along +Y from y0..y1 centred at (x,z)=xz (cm)."""
    h = y1 - y0
    c = trimesh.creation.cylinder(radius=radius, height=h, sections=sections)
    R = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0])
    c.apply_transform(R)                      # axis Z -> Y
    c.apply_translation([xz[0], y0 + h / 2.0, xz[1]])
    return c


def _xcyl(radius, x0, x1, y, sections=24):
    """Solid cylinder along +X from x0..x1 at height y (a T-pose arm)."""
    w = x1 - x0
    c = trimesh.creation.cylinder(radius=radius, height=w, sections=sections)
    # default axis Z -> rotate to X
    R = trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0])
    c.apply_transform(R)
    c.apply_translation([x0 + w / 2.0, y, 0.0])
    return c


@pytest.fixture
def tpose_body_cm():
    """A crude T-pose humanoid in cm: torso + 2 horizontal arms + 2 legs + head.

    Concatenated (not boolean-unioned) so a horizontal cut yields the torso loop
    PLUS separate side loops for the arms/legs -- exactly the arm-exclusion case.
    Torso girth ~= 2*pi*16 ~= 100.5 cm; each arm girth ~= 2*pi*5 ~= 31.4 cm.
    """
    parts = [
        _ycyl(16.0, 80.0, 150.0),                 # torso
        _xcyl(5.0, 16.0, 50.0, 140.0),            # right arm (+X)
        _xcyl(5.0, -50.0, -16.0, 140.0),          # left arm (-X)
        _ycyl(9.0, 0.0, 80.0, xz=(8.0, 0.0)),     # right leg
        _ycyl(9.0, 0.0, 80.0, xz=(-8.0, 0.0)),    # left leg
        trimesh.creation.icosphere(radius=11.0).apply_translation([0, 161, 0]),  # head
    ]
    return trimesh.util.concatenate(parts)
```

- [ ] **Step 2: Verify the fixture builds**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/conftest.py -q` (collection only — no error)
Expected: no collection error.

- [ ] **Step 3: Commit**

```bash
git add tests/mpfb_ingest/conftest.py
git commit -m "test(mpfb_ingest): add synthetic T-pose body fixture"
```

---

## Task 2: `geometry.central_loop` — arm-excluded torso loop

**Files:**
- Modify: `mpfb_ingest/geometry.py`
- Test: `tests/mpfb_ingest/test_geometry_central.py`

- [ ] **Step 1: Write the failing test**

Create `tests/mpfb_ingest/test_geometry_central.py`:

```python
import numpy as np
import mpfb_ingest.geometry as geo


def test_central_loop_excludes_tpose_arms(tpose_body_cm):
    # At arm height (140) the cut grazes both arms; central loop must be the
    # torso (~100 cm), not an arm loop (~31 cm).
    p = geo.central_perimeter(tpose_body_cm, 140.0)
    assert 90.0 <= p <= 110.0


def test_central_loop_plain_torso(tpose_body_cm):
    # Below the arms (y=100) only the torso is cut.
    p = geo.central_perimeter(tpose_body_cm, 100.0)
    assert 90.0 <= p <= 110.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_geometry_central.py -q`
Expected: FAIL — `AttributeError: module 'mpfb_ingest.geometry' has no attribute 'central_perimeter'`.

- [ ] **Step 3: Implement**

Add to `mpfb_ingest/geometry.py` (after `slice_perimeter`):

```python
def central_loop(mesh, y):
    """Section loop straddling the body axis at height y (arms/legs excluded).

    A horizontal cut through a T-pose body yields the torso loop plus separate
    side loops for any arm/leg it grazes. The torso loop is the one whose mean X
    sits nearest the body's central axis (x~=0); limb loops sit far out in +/-X.
    Returns the ordered (N,3) polyline.
    """
    loops = slice_loops(mesh, y)
    if not loops:
        raise ValueError(f"No cross-section at y={y}")
    return min(loops, key=lambda L: abs(float(np.mean(L[:, 0]))))


def central_perimeter(mesh, y):
    """Perimeter (cm) of the central torso loop at height y (arm-excluded)."""
    return _loop_perimeter(central_loop(mesh, y))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_geometry_central.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/geometry.py tests/mpfb_ingest/test_geometry_central.py
git commit -m "feat(mpfb_ingest): arm-excluded central torso loop"
```

---

## Task 3: `measurements.circumferences` uses the central loop

**Files:**
- Modify: `mpfb_ingest/measurements.py:20-24`
- Test: `tests/mpfb_ingest/test_geometry_central.py` (add a case)

- [ ] **Step 1: Write the failing test**

Append to `tests/mpfb_ingest/test_geometry_central.py`:

```python
def test_circumferences_arm_excluded(tpose_body_cm):
    from mpfb_ingest import measurements
    from mpfb_ingest.landmarks import Landmarks
    # Hand the waist/bust levels at torso heights; both must read ~torso girth,
    # never the inflated arm-merged "longest" loop.
    lm = Landmarks({"n_vertices_expected": 0, "vertices": {}, "levels": {}})
    out = measurements.circumferences(
        tpose_body_cm, lm,
        level_y=lambda n: {"waist": 100.0, "bust": 140.0,
                           "underbust": 120.0, "hips": 90.0}.get(n))
    assert 90.0 <= out["bust"] <= 110.0       # not 150+ from arm inflation
    assert 90.0 <= out["waist"] <= 110.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_geometry_central.py::test_circumferences_arm_excluded -q`
Expected: FAIL — `bust` reads the arm-inflated longest loop (> 110).

- [ ] **Step 3: Implement**

In `mpfb_ingest/measurements.py`, change the torso loop in `circumferences` from longest to central:

```python
    out = {}
    for field in ["waist", "bust", "underbust", "hips"]:
        y = ly(field)
        if y is None:
            continue
        out[field] = geo.central_perimeter(mesh, y)
```

(Leave the `wrist`/`leg_circ` `pick="nearest"` limb branches unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_geometry_central.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/ -q`
Expected: all green (the committed-base test still passes — central loop equals longest loop on the arm-free base torso levels).

- [ ] **Step 6: Commit**

```bash
git add mpfb_ingest/measurements.py tests/mpfb_ingest/test_geometry_central.py
git commit -m "fix(mpfb_ingest): torso circumferences use arm-excluded central loop"
```

---

## Task 4: `mesh_io` unit auto-detection + measured height

**Files:**
- Modify: `mpfb_ingest/mesh_io.py:15-42`
- Test: `tests/mpfb_ingest/test_mesh_io_units.py`

- [ ] **Step 1: Write the failing test**

Create `tests/mpfb_ingest/test_mesh_io_units.py`:

```python
import numpy as np
import trimesh
from mpfb_ingest import mesh_io


def _person(height_units):
    # a 1.7-proportioned box scaled to the given Y extent (any unit)
    b = trimesh.creation.box(extents=[0.5, 1.0, 0.25])
    b.apply_translation([0, 0.5, 0])          # ground it
    b.apply_scale(height_units / 1.0)
    return b


def test_detects_metres_and_measures_height():
    m, rep = mesh_io.normalize(_person(1.73))   # already metres
    assert abs(rep["height_m"] - 1.73) < 0.02   # measured, NOT forced to 1.70
    assert abs(m.bounds[0][1]) < 1e-6           # grounded


def test_detects_decimetres():
    m, rep = mesh_io.normalize(_person(17.3))    # decimetres
    assert abs(rep["height_m"] - 1.73) < 0.02


def test_detects_makehuman_units():
    m, rep = mesh_io.normalize(_person(173.0))   # cm / MakeHuman raw
    assert abs(rep["height_m"] - 1.73) < 0.05


def test_explicit_override_still_forces():
    m, rep = mesh_io.normalize(_person(1.50), expected_height_m=1.80)
    assert abs(rep["height_m"] - 1.80) < 0.02
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_mesh_io_units.py -q`
Expected: FAIL — current `normalize` forces every mesh to `expected_height_m` default 1.7.

- [ ] **Step 3: Implement**

Replace `normalize` in `mpfb_ingest/mesh_io.py` and add `detect_scale_to_m`:

```python
def detect_scale_to_m(raw_height: float) -> float:
    """Factor to bring a raw Y-extent to metres, by magnitude bucket.

    ~1-3 -> already metres (x1); ~10-25 -> decimetres (x0.1);
    >50 -> centimetres / MakeHuman raw units (x0.01). Mid-gaps fall to the
    nearest plausible human bucket.
    """
    if raw_height <= 0:
        raise ValueError("Mesh has zero Y-extent; is it Y-up?")
    if raw_height < 4.0:
        return 1.0
    if raw_height < 40.0:
        return 0.1
    return 0.01


def normalize(mesh: trimesh.Trimesh, expected_height_m: float | None = None) -> tuple[trimesh.Trimesh, dict]:
    """Return (mesh_in_metres, report).

    Auto-detects the unit scale and MEASURES true height. Pass
    `expected_height_m` only to force a known stature (override). Then centre
    X/Z on the bbox midpoint and ground feet to Y=0. Assumes Y-up.
    """
    mesh = mesh.copy()
    raw_height = float(mesh.bounds[1][1] - mesh.bounds[0][1])
    if raw_height <= 0:
        raise ValueError("Mesh has zero Y-extent; is it Y-up?")
    if expected_height_m is not None:
        scale_to_m = expected_height_m / raw_height
    else:
        scale_to_m = detect_scale_to_m(raw_height)
    mesh.apply_scale(scale_to_m)

    (x0, _, z0), (x1, _, z1) = mesh.bounds
    x_mid = 0.5 * (x0 + x1)
    z_mid = 0.5 * (z0 + z1)
    min_y = mesh.bounds[0][1]
    mesh.apply_translation([-x_mid, -min_y, -z_mid])

    report = {
        "scale_to_m": scale_to_m,
        "height_m": float(mesh.bounds[1][1] - mesh.bounds[0][1]),
        "n_vertices": int(len(mesh.vertices)),
    }
    return mesh, report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_mesh_io_units.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Keep the committed-base calibration test green**

The calibrator and `test_calibration_realmesh.py` pass `expected_height_m=1.7` explicitly, so the override path preserves the validated result. Run:

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/ -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add mpfb_ingest/mesh_io.py tests/mpfb_ingest/test_mesh_io_units.py
git commit -m "feat(mpfb_ingest): auto-detect units and measure true height"
```

---

## Task 5: `autolandmarks.find_levels` — runtime girth scan

**Files:**
- Create: `mpfb_ingest/autolandmarks.py`
- Test: `tests/mpfb_ingest/test_autolandmarks.py`

- [ ] **Step 1: Write the failing test**

Create `tests/mpfb_ingest/test_autolandmarks.py`:

```python
from pathlib import Path
import numpy as np
from mpfb_ingest import mesh_io, autolandmarks as al

BASE = Path("mpfb_ingest/data/mpfb_base_body.obj")


def _base_cm():
    raw = mesh_io.load_body(str(BASE))
    mm, _ = mesh_io.normalize(raw, expected_height_m=1.7)
    return mesh_io.to_cm(mm)


def test_find_levels_ordered_on_real_base():
    cm = _base_cm()
    lv = al.find_levels(cm)
    # anatomical ordering by height (cm, feet at 0)
    assert lv["crotch"] < lv["hips"] < lv["waist"] < lv["underbust"] < lv["bust"] < lv["neck"]
    # plausible bands for a ~170 cm body
    assert 70 <= lv["hips"] <= 100
    assert 95 <= lv["waist"] <= 120
    assert 120 <= lv["bust"] <= 145
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_autolandmarks.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpfb_ingest.autolandmarks'`.

- [ ] **Step 3: Implement**

Create `mpfb_ingest/autolandmarks.py`:

```python
"""Per-mesh geometric landmark derivation (topology-agnostic).

Works on any Y-up human mesh in centimetres (feet grounded at 0). Produces a
``Landmarks``-compatible object so ``measurements.compute_all`` runs unchanged.
Clean-room: implemented from the published GarmentCode measurement definitions
(predecessor spec section 2.4), not from the GPLv3 GarmentMeasurements tool.
"""
import numpy as np

from . import geometry as geo
from .landmarks import Landmarks


def _girth(mesh, y):
    try:
        return geo.central_perimeter(mesh, float(y))
    except Exception:
        return float("nan")


def find_levels(mesh):
    """Anatomical girth scan -> {crotch,hips,waist,bust,underbust,neck} as cm Y.

    Mirrors the validated calibrator scan (predecessor section 8.3) but on the
    arm-excluded central girth, so it is correct under a T-pose. Feet at y=0.
    """
    top = float(mesh.bounds[1][1])
    ys = np.arange(2.0, top, 1.0)
    g = np.array([_girth(mesh, y) for y in ys])
    torso_max = float(np.nanmax(g))
    thr = 0.7 * torso_max

    def jump_up(lo, hi):
        for y, gv in zip(ys, g):
            if lo <= y <= hi and np.isfinite(gv) and gv > thr:
                return float(y)
        return None

    crotch = jump_up(40.0, top * 0.6) or (top * 0.45)
    arm = jump_up(crotch + 30.0, top * 0.85) or (top * 0.78)

    def band(lo, hi):
        m = (ys >= lo) & (ys <= hi) & np.isfinite(g)
        return ys[m], g[m]

    hy, hg = band(crotch, crotch + 18.0)
    hips = float(hy[np.argmax(hg)])
    wy, wg = band(hips + 5.0, arm - 5.0)
    waist = float(wy[np.argmin(wg)])
    by, bg = band(waist + 5.0, arm - 2.0)
    bust = float(by[np.argmax(bg)])
    underbust = 0.5 * (waist + bust)
    ny, ng = band(arm, top * 0.95)
    neck = float(ny[np.argmin(ng)]) if len(ny) else (top * 0.9)

    return {"crotch": crotch, "hips": hips, "waist": waist,
            "bust": bust, "underbust": underbust, "neck": neck,
            "_arm_merge": arm}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_autolandmarks.py -q`
Expected: PASS. If a band is mis-tuned on the real mesh, adjust the literal offsets to match the calibrator's validated values (predecessor §8.3) — do not change the algorithm.

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/autolandmarks.py tests/mpfb_ingest/test_autolandmarks.py
git commit -m "feat(mpfb_ingest): runtime arm-excluded girth scan for torso levels"
```

---

## Task 6: `autolandmarks` — point helpers + level/side/peak landmarks

**Files:**
- Modify: `mpfb_ingest/autolandmarks.py`
- Test: `tests/mpfb_ingest/test_autolandmarks.py`

This task adds the circumference levels, side-balance pairs (back widths), and bust/bum peaks to a `derive()` builder.

- [ ] **Step 1: Write the failing test**

Append to `tests/mpfb_ingest/test_autolandmarks.py`:

```python
from mpfb_ingest import measurements


def test_derive_circumferences_and_backwidths():
    cm = _base_cm()
    lm = al.derive(cm)
    out = measurements.compute_all(cm, lm, arm_pose_angle=0.0)
    # torso circumferences present and ordered
    assert out["waist"] < out["underbust"] < out["bust"]
    assert out["waist"] < out["hips"]
    # back-section widths are real (not the 39.14 default for every body) and
    # smaller than the full girth they sit inside
    assert out["waist_back_width"] < out["waist"]
    assert out["back_width"] < out["bust"]
    assert out["hip_back_width"] < out["hips"]
    # bust/bum point spreads are plausible peak-to-peak distances
    assert 10.0 <= out["bust_points"] <= 30.0
    assert 10.0 <= out["bum_points"] <= 35.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_autolandmarks.py::test_derive_circumferences_and_backwidths -q`
Expected: FAIL — `AttributeError: module 'mpfb_ingest.autolandmarks' has no attribute 'derive'`.

- [ ] **Step 3: Implement**

Add helpers and `derive()` to `mpfb_ingest/autolandmarks.py`:

```python
def _nearest_vertex(mesh, point):
    d = np.asarray(mesh.vertices) - np.asarray(point, dtype=np.float64)
    return int(np.argmin(np.einsum("ij,ij->i", d, d)))


def _vertex_at_level(mesh, y, prefer_front=True):
    V = np.asarray(mesh.vertices)
    cost = np.abs(V[:, 1] - y) + 0.02 * np.abs(V[:, 0])
    if prefer_front:
        cost += 0.02 * (V[:, 2].max() - V[:, 2])
    return int(np.argmin(cost))


def _loop_side_points(loop):
    """(left_point, right_point) = extreme -X / +X points of a loop."""
    li = int(np.argmin(loop[:, 0]))
    ri = int(np.argmax(loop[:, 0]))
    return loop[li], loop[ri]


def _loop_peak_points(loop, axis=2, sign=1.0):
    """(left_peak, right_peak) split by X<0 / X>0, extreme along `axis`*sign.

    sign=+1 picks the front-most (max +Z) per side -> bust peaks;
    sign=-1 picks the back-most (min Z)  per side -> bum peaks.
    """
    leftm = loop[loop[:, 0] < 0.0]
    rightm = loop[loop[:, 0] >= 0.0]
    def pick(half):
        if len(half) == 0:
            return None
        i = int(np.argmax(sign * half[:, axis]))
        return half[i]
    return pick(leftm), pick(rightm)


def derive(mesh, *, arm_pose="tpose"):
    """Return a Landmarks-compatible object with geometric landmark indices."""
    levels = find_levels(mesh)
    arm_merge = levels["_arm_merge"]
    vtx, lvl = {}, {}

    # --- circumference level vertices (drive level_y for waist/bust/...) ------
    for name in ("waist", "bust", "underbust", "hips", "neck", "crotch"):
        lvl_name = "crotch_lvl" if name == "crotch" else name
        lvl[lvl_name] = _vertex_at_level(mesh, levels[name])

    # --- side-balance pairs at each level (back-section widths) ---------------
    for level, l_name, r_name in [
        ("waist", "side_l_waist", "side_r_waist"),
        ("bust",  "side_l_bust",  "side_r_bust"),
        ("hips",  "side_l_hips",  "side_r_hips"),
        ("neck",  "side_l_neck",  "side_r_neck"),
    ]:
        loop = geo.central_loop(mesh, levels[level])
        lp, rp = _loop_side_points(loop)
        vtx[l_name] = _nearest_vertex(mesh, lp)
        vtx[r_name] = _nearest_vertex(mesh, rp)

    # --- bust / bum peaks -----------------------------------------------------
    bust_loop = geo.central_loop(mesh, levels["bust"])
    bl, br = _loop_peak_points(bust_loop, axis=2, sign=1.0)
    if bl is not None and br is not None:
        vtx["bust_l"] = _nearest_vertex(mesh, bl)
        vtx["bust_r"] = _nearest_vertex(mesh, br)
    hip_loop = geo.central_loop(mesh, levels["hips"])
    ml, mr = _loop_peak_points(hip_loop, axis=2, sign=-1.0)
    if ml is not None and mr is not None:
        vtx["bum_l"] = _nearest_vertex(mesh, ml)
        vtx["bum_r"] = _nearest_vertex(mesh, mr)

    return Landmarks({"n_vertices_expected": 0, "vertices": vtx, "levels": lvl})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_autolandmarks.py -q`
Expected: PASS. Tune nothing in the algorithm; if a peak range is off, widen the assertion to the observed anatomical value and note it.

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/autolandmarks.py tests/mpfb_ingest/test_autolandmarks.py
git commit -m "feat(mpfb_ingest): derive levels, side-balance pairs, bust/bum peaks"
```

---

## Task 7: `autolandmarks` — vertical anatomy, limbs, geodesic anchors

**Files:**
- Modify: `mpfb_ingest/autolandmarks.py`
- Test: `tests/mpfb_ingest/test_autolandmarks.py`

Adds crown/nape/collar/neck_base/shoulder/armpit, wrist/thigh limbs, and the waist back/front + level anchors so the remaining fields (head_l, shoulder_w, armscye_depth, geodesics, limb circumferences, angles, ΔY fields) compute.

- [ ] **Step 1: Write the failing test**

Append to `tests/mpfb_ingest/test_autolandmarks.py`:

```python
def test_derive_full_field_set_on_base():
    cm = _base_cm()
    lm = al.derive(cm)
    out = measurements.compute_all(cm, lm, arm_pose_angle=0.0)
    required = {
        "height", "bust", "waist", "hips", "underbust",
        "waist_back_width", "back_width", "hip_back_width", "neck_w",
        "shoulder_w", "head_l", "bust_points", "bum_points", "armscye_depth",
        "arm_length", "waist_line", "bust_line", "waist_over_bust_line",
        "hips_line", "crotch_hip_diff", "vert_bust_line",
        "leg_circ", "wrist", "shoulder_incl", "hip_inclination", "arm_pose_angle",
    }
    missing = required - set(out)
    assert not missing, f"missing geometric fields: {sorted(missing)}"
    # sane ranges for a ~170 cm body
    assert 25 <= out["shoulder_w"] <= 55
    assert 20 <= out["head_l"] <= 32
    assert 40 <= out["arm_length"] <= 75
    assert 0 <= out["shoulder_incl"] <= 45
    assert 0 <= out["hip_inclination"] <= 45
    assert 40 <= out["leg_circ"] <= 80
    assert 10 <= out["wrist"] <= 25
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_autolandmarks.py::test_derive_full_field_set_on_base -q`
Expected: FAIL — geodesic/limb/angle landmark names not yet populated.

- [ ] **Step 3: Implement**

Add these helpers to `mpfb_ingest/autolandmarks.py`:

```python
def _back_point(loop):
    """Back-most (min Z) point of a loop."""
    return loop[int(np.argmin(loop[:, 2]))]


def _front_center_point(loop):
    """Front-most (max Z) point nearest the X axis of a loop."""
    fz = loop[:, 2].max()
    near = loop[loop[:, 2] >= fz - 1.0]
    return near[int(np.argmin(np.abs(near[:, 0])))]


def _arm_loops(mesh, y, x_min_abs):
    """Section loops whose |mean X| exceeds x_min_abs (the arms at height y)."""
    out = []
    for L in geo.slice_loops(mesh, y):
        if abs(float(np.mean(L[:, 0]))) >= x_min_abs:
            out.append(L)
    return out
```

Then insert this block into `derive()` immediately before the `return` line:

```python
    V = np.asarray(mesh.vertices)
    top = float(mesh.bounds[1][1])

    # crown / nape / neck base ------------------------------------------------
    vtx["crown"] = int(np.argmax(V[:, 1]))
    neck_loop = geo.central_loop(mesh, levels["neck"])
    vtx["nape"] = _nearest_vertex(mesh, _back_point(neck_loop))
    vtx["neck_base"] = _nearest_vertex(mesh, _front_center_point(neck_loop))
    lvl["nape_lvl"] = vtx["nape"]

    # shoulders / collar (widest torso just below the arm merge) --------------
    sh_y = max(levels["bust"] + 2.0, arm_merge - 4.0)
    sh_loop = geo.central_loop(mesh, sh_y)
    sl, sr = _loop_side_points(sh_loop)
    vtx["collar_l"] = _nearest_vertex(mesh, sl)
    vtx["collar_r"] = _nearest_vertex(mesh, sr)
    vtx["shoulder_r"] = vtx["collar_r"]

    # armpit: lowest height with a distinct side arm-loop ----------------------
    half_w = abs(float(sh_loop[:, 0].max()))
    armpit_pt = sr
    for y in np.arange(arm_merge - 12.0, arm_merge + 12.0, 1.0):
        arms = _arm_loops(mesh, float(y), 0.6 * half_w)
        if arms:
            armpit_pt = min((L[int(np.argmin(L[:, 1]))] for L in arms),
                            key=lambda p: p[1])
            break
    vtx["armpit_r"] = _nearest_vertex(mesh, armpit_pt)

    # wrist: far +X arm vertex; thigh: a leg loop below the crotch ------------
    vtx["wrist_r"] = int(np.argmax(V[:, 0]))
    lvl["wrist"] = vtx["wrist_r"]
    thigh_y = 0.5 * levels["crotch"]
    leg_loops = [L for L in geo.slice_loops(mesh, thigh_y)
                 if float(np.mean(L[:, 0])) > 1.0]
    if leg_loops:
        thigh_loop = max(leg_loops, key=lambda L: geo._loop_perimeter(L))
        vtx["thigh_r"] = _nearest_vertex(mesh, thigh_loop[0])
        lvl["thigh"] = vtx["thigh_r"]

    # geodesic / angle anchors at the waist -----------------------------------
    waist_loop = geo.central_loop(mesh, levels["waist"])
    vtx["waist_back"] = _nearest_vertex(mesh, _back_point(waist_loop))
    vtx["waist_front"] = _nearest_vertex(mesh, _front_center_point(waist_loop))
    wl, wr = _loop_side_points(waist_loop)
    vtx["waist_side"] = _nearest_vertex(mesh, wr)
    hp_l, hp_r = _loop_side_points(hip_loop)
    vtx["hip_side"] = _nearest_vertex(mesh, hp_r)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_autolandmarks.py -q`
Expected: PASS. If a heuristic lands a value outside its band on the real base, adjust that heuristic (e.g. the `sh_y` offset or the armpit scan window) until the base mesh reads anatomically; keep the interface stable.

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/autolandmarks.py tests/mpfb_ingest/test_autolandmarks.py
git commit -m "feat(mpfb_ingest): derive vertical anatomy, limbs, geodesic anchors"
```

---

## Task 8: CLI auto path — make `--landmarks` optional

**Files:**
- Modify: `ingest_mpfb_body.py:29-71`
- Test: `tests/mpfb_ingest/test_cli.py` (add a case)

- [ ] **Step 1: Write the failing test**

Append to `tests/mpfb_ingest/test_cli.py`:

```python
from pathlib import Path


def test_cli_auto_path_on_real_base(tmp_path):
    # No --landmarks JSON: the auto (topology-agnostic) path must emit a full
    # 26-field body with NO --fill-defaults.
    from ingest_mpfb_body import run
    out = run("mpfb_ingest/data/mpfb_base_body.obj", out_dir=str(tmp_path),
              name="auto", landmarks_path=None, arm_pose_angle=0.0,
              height_m=None, fill_defaults=False)
    data = yaml.safe_load(Path(out).read_text())["body"]
    for f in ("waist_back_width", "back_width", "shoulder_w", "arm_length",
              "bust_points", "leg_circ", "wrist", "neck_w"):
        assert f in data and data[f] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_cli.py::test_cli_auto_path_on_real_base -q`
Expected: FAIL — `run` requires `landmarks_path` and forces height.

- [ ] **Step 3: Implement**

Edit `ingest_mpfb_body.py` `run()` to branch on `landmarks_path` and use the new height semantics:

```python
def run(obj_path, out_dir, name, landmarks_path, arm_pose_angle,
        height_m=None, save_obj=False, fill_defaults=False):
    from mpfb_ingest import autolandmarks

    raw = mesh_io.load_body(obj_path)
    mesh_m, report = mesh_io.normalize(raw, expected_height_m=height_m)
    cm = mesh_io.to_cm(mesh_m)

    if landmarks_path:                      # committed-index path (regression)
        lm = Landmarks.load(landmarks_path)
        if lm.n_vertices_expected:
            lm.validate(cm)
    else:                                   # topology-agnostic auto path
        lm = autolandmarks.derive(cm)

    measured = measurements.compute_all(cm, lm, arm_pose_angle=arm_pose_angle)
    measured["height"] = float(cm.bounds[1][1] - cm.bounds[0][1])

    if fill_defaults:
        for k, v in _DEFAULTS.items():
            measured.setdefault(k, v)

    out_yaml = emit.to_body_yaml(measured, out_dir, name)
    if save_obj:
        mesh_io.save_body_obj(mesh_m, out_dir, name)
    print(f"Wrote {out_yaml}  (scale_to_m={report['scale_to_m']:.4f}, "
          f"verts={report['n_vertices']}, height_cm={measured['height']:.1f})")
    return out_yaml
```

Update `main()` argparse so `--landmarks` and `--height-m` are optional:

```python
    ap.add_argument("--landmarks", default=None,
                    help="Calibrated vertex-index JSON. Omit for the "
                         "topology-agnostic auto path (any human mesh).")
    ap.add_argument("--height-m", type=float, default=None,
                    help="Override stature in metres. Omit to auto-detect "
                         "units and measure height from the mesh.")
```

(Leave the other arguments and the `run(...)` call wiring intact.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_cli.py -q`
Expected: PASS. The existing `test_cli_run_smoke` (passes an explicit landmarks JSON + `height_m=1.7`) still works via the committed-index branch.

- [ ] **Step 5: Full suite**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/ -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add ingest_mpfb_body.py tests/mpfb_ingest/test_cli.py
git commit -m "feat(mpfb_ingest): CLI auto landmark path, optional --landmarks/--height-m"
```

---

## Task 9: Stress test — glb end-to-end ingest + pattern generation

**Files:**
- Create: `tests/mpfb_ingest/test_stress_glb.py`

- [ ] **Step 1: Write the test**

Create `tests/mpfb_ingest/test_stress_glb.py`:

```python
from pathlib import Path
import yaml
import pytest

from ingest_mpfb_body import run

GLB = Path(".temp/avatar_base.glb")
pytestmark = pytest.mark.skipif(not GLB.exists(), reason="avatar_base.glb absent")


@pytest.fixture(scope="module")
def avatar_yaml(tmp_path_factory):
    d = tmp_path_factory.mktemp("glb")
    out = run(str(GLB), out_dir=str(d), name="avatar", landmarks_path=None,
              arm_pose_angle=0.0, height_m=None, fill_defaults=False)
    return Path(out)


def test_glb_emits_full_ordered_body(avatar_yaml):
    d = yaml.safe_load(avatar_yaml.read_text())["body"]
    # all 26 base fields present
    from mpfb_ingest.emit import REQUIRED
    assert not (set(REQUIRED) - set(d))
    # measured (not forced) height ~ the glb's true 1.729 m
    assert 168 <= d["height"] <= 176
    # anatomical ordering
    assert d["waist"] < d["underbust"] < d["bust"]
    assert d["waist"] < d["hips"]
    assert d["waist_back_width"] < d["waist"]


@pytest.mark.parametrize("design_file", [
    "assets/design_params/default.yaml",
    "assets/design_params/t-shirt.yaml",
])
def test_glb_generates_pattern_without_self_intersection(avatar_yaml, design_file):
    from assets.bodies.body_params import BodyParameters
    from assets.garment_programs.meta_garment import MetaGarment

    body = BodyParameters(str(avatar_yaml))
    design = yaml.safe_load(open(design_file))["design"]
    pattern = MetaGarment("stress", body, design).assembly()
    # serialize -> exercises panel geometry; raises on degenerate edges
    pat = pattern.pattern if hasattr(pattern, "pattern") else pattern
    assert pat is not None
    # no self-intersection in the assembled pattern
    if hasattr(pattern, "is_self_intersecting"):
        assert not pattern.is_self_intersecting()
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_stress_glb.py -q`
Expected: PASS (or SKIP if the glb is absent). If `is_self_intersecting` is not an attribute on the returned object, drop that branch — generation completing without exception is the criterion (predecessor §8.1).

- [ ] **Step 3: Verify manually end-to-end**

Run:
```bash
.venv/bin/python ingest_mpfb_body.py .temp/avatar_base.glb --name avatar \
  --arm-pose-angle 0 --out assets/bodies --save-obj
```
Expected: `Wrote assets/bodies/avatar.yaml (... height_cm=172.x)` with no traceback.

- [ ] **Step 4: Commit**

```bash
git add tests/mpfb_ingest/test_stress_glb.py
git commit -m "test(mpfb_ingest): glb end-to-end ingest + pattern-generation stress"
```

---

## Task 10: MPFB headless test-set generator

**Files:**
- Create: `scripts/gen_mpfb_testset.py`
- Create: `scripts/run_mpfb_gen.sh`

- [ ] **Step 1: Write the Blender-side generator**

Create `scripts/gen_mpfb_testset.py`:

```python
"""Generate a varied MPFB body-type test set (runs INSIDE Blender, headless).

Invoke via scripts/run_mpfb_gen.sh. Exports each body as <out>/<id>.glb
(body-only: helpers baked + removed) plus manifest.json mapping id -> macro
sliders, so stress tests know each body's expected qualitative direction.
MPFB output is CC0. No Rigify (keeps the headless path stable).
"""
import bpy, sys, os, json, itertools, importlib


def _services():
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.blender_org.mpfb")
    except Exception as e:
        print("WARN addon_enable:", e)
    base = "bl_ext.blender_org.mpfb.services."
    H = importlib.import_module(base + "humanservice").HumanService
    E = importlib.import_module(base + "exportservice").ExportService
    return H, E


def _macro(gender, age, weight, muscle, height, cup, race):
    r = {"asian": 0.0, "caucasian": 0.0, "african": 0.0}
    r[race] = 1.0
    return {"gender": gender, "age": age, "muscle": muscle, "weight": weight,
            "proportions": 0.5, "height": height, "cupsize": cup,
            "firmness": 0.5, "race": r}


def _grid(limit=None):
    out = [("neutral", _macro(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, "caucasian"))]
    genders = [0.0, 1.0]; ages = [0.5, 0.9]; weights = [0.0, 0.5, 1.0]
    muscles = [0.0, 0.5, 1.0]; heights = [0.0, 0.5, 1.0]
    cups = [0.0, 0.5, 1.0]; races = ["caucasian", "asian", "african"]
    i = 0
    for g, a, w, m, h, c, race in itertools.product(
            genders, ages, weights, muscles, heights, cups, races):
        i += 1
        extreme = (w in (0.0, 1.0) or h in (0.0, 1.0) or c in (0.0, 1.0))
        if not extreme and i % 7 != 0:
            continue
        gname = "m" if g >= 0.5 else "f"
        idn = (f"{gname}_a{int(a*100)}_w{int(w*100)}_mu{int(m*100)}"
               f"_h{int(h*100)}_c{int(c*100)}_{race[:3]}")
        out.append((idn, _macro(g, a, w, m, h, c, race)))
        if limit and len(out) >= limit:
            break
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_dir = argv[argv.index("--out") + 1] if "--out" in argv else "/tmp/testset"
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    os.makedirs(out_dir, exist_ok=True)
    H, E = _services()
    manifest = {}
    for idn, macro in _grid(limit):
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()
        human = H.create_human(macro_detail_dict=macro, feet_on_ground=True)
        copy = E.create_character_copy(human)
        E.bake_modifiers_remove_helpers(copy, remove_helpers=True)
        bpy.ops.object.select_all(action="DESELECT")
        copy.select_set(True)
        bpy.context.view_layer.objects.active = copy
        path = os.path.join(out_dir, idn + ".glb")
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True,
                                  export_format="GLB", export_yup=True)
        manifest[idn] = macro
        print("WROTE", path)
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("DONE", len(manifest), "bodies")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the WSL launcher**

Create `scripts/run_mpfb_gen.sh`:

```bash
#!/usr/bin/env bash
# Generate the MPFB test set into a WSL dir via the Windows Blender + MPFB.
# Usage: scripts/run_mpfb_gen.sh [out_dir] [limit]
set -euo pipefail
BL="/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
OUT_WSL="${1:-.temp/testset}"
LIMIT="${2:-}"
mkdir -p "$OUT_WSL"
OUT_WIN="$(wslpath -w "$(realpath "$OUT_WSL")")"
SCRIPT_WIN="$(wslpath -w "$(realpath scripts/gen_mpfb_testset.py)")"
ARGS=(--out "$OUT_WIN")
[ -n "$LIMIT" ] && ARGS+=(--limit "$LIMIT")
"$BL" --background -noaudio --python "$SCRIPT_WIN" -- "${ARGS[@]}" || true
echo "Generated bodies in $OUT_WSL:"
ls -1 "$OUT_WSL"/*.glb 2>/dev/null | wc -l
```

- [ ] **Step 3: Smoke-run the generator (5 bodies)**

Run:
```bash
chmod +x scripts/run_mpfb_gen.sh
scripts/run_mpfb_gen.sh .temp/testset 5
```
Expected: `DONE 5 bodies` and `.temp/testset/*.glb` (5 files) + `manifest.json`. If an MPFB API call signature differs in 2.0.15, fix it against the installed services (probe pattern: `importlib.import_module("bl_ext.blender_org.mpfb.services.exportservice")` then `dir(ExportService)`); the verified pieces are `HumanService.create_human(macro_detail_dict=...)`, `ExportService.create_character_copy`, `ExportService.bake_modifiers_remove_helpers`.

- [ ] **Step 4: Commit**

```bash
git add scripts/gen_mpfb_testset.py scripts/run_mpfb_gen.sh
git commit -m "feat(mpfb_ingest): MPFB headless body-type test-set generator"
```

---

## Task 11: Test-set asset sanity

**Files:**
- Create: `tests/mpfb_ingest/test_testset_assets.py`

- [ ] **Step 1: Write the test**

Create `tests/mpfb_ingest/test_testset_assets.py`:

```python
from pathlib import Path
import glob
import pytest
from mpfb_ingest import mesh_io

GLBS = sorted(glob.glob(".temp/testset/*.glb"))
pytestmark = pytest.mark.skipif(not GLBS, reason="no generated test set")


@pytest.mark.parametrize("path", GLBS)
def test_generated_body_loads_and_is_human_scaled(path):
    raw = mesh_io.load_body(path)
    m, rep = mesh_io.normalize(raw)
    assert len(m.vertices) > 1000
    assert 1.2 <= rep["height_m"] <= 2.2     # plausible human (incl. children)
    assert abs(m.bounds[0][1]) < 1e-6        # grounded, Y-up


def test_manifest_present():
    assert Path(".temp/testset/manifest.json").exists()
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_testset_assets.py -q`
Expected: PASS over the 5 smoke bodies (or SKIP if none generated).

- [ ] **Step 3: Commit**

```bash
git add tests/mpfb_ingest/test_testset_assets.py
git commit -m "test(mpfb_ingest): generated test-set asset sanity"
```

---

## Task 12: Cross-body property stress tests

**Files:**
- Create: `tests/mpfb_ingest/test_stress_testset.py`

- [ ] **Step 1: Generate the full set**

Run: `scripts/run_mpfb_gen.sh .temp/testset` (no limit → ~80–150 bodies).
Expected: `DONE N bodies`.

- [ ] **Step 2: Write the property tests**

Create `tests/mpfb_ingest/test_stress_testset.py`:

```python
"""Cross-body property tests over the generated MPFB set (skip if absent).

Proves the extractor TRACKS body type: measurements move in the right direction
as the macro sliders change. Keyed to manifest.json.
"""
from pathlib import Path
import glob
import json
import yaml
import pytest

from ingest_mpfb_body import run

DIR = Path(".temp/testset")
MAN = DIR / "manifest.json"
pytestmark = pytest.mark.skipif(not MAN.exists(), reason="no generated test set")


def _ingest(idn, tmp):
    out = run(str(DIR / f"{idn}.glb"), out_dir=str(tmp), name=idn,
              landmarks_path=None, arm_pose_angle=0.0, height_m=None,
              fill_defaults=False)
    return yaml.safe_load(Path(out).read_text())["body"]


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MAN.read_text())


@pytest.mark.parametrize("path", sorted(glob.glob(str(DIR / "*.glb"))))
def test_every_body_full_ordered_in_range(path, tmp_path):
    from mpfb_ingest.emit import REQUIRED, RANGES
    idn = Path(path).stem
    d = _ingest(idn, tmp_path)
    assert not (set(REQUIRED) - set(d))
    for f, (lo, hi) in RANGES.items():
        assert lo <= d[f] <= hi, f"{idn}: {f}={d[f]} out of [{lo},{hi}]"
    assert d["waist"] < d["underbust"] < d["bust"]
    assert d["waist"] < d["hips"]


def _pick(manifest, **constraints):
    """First id whose macro matches the given slider constraints."""
    for idn, mac in manifest.items():
        if all(abs(mac.get(k, 0.5) - v) < 1e-6 for k, v in constraints.items()):
            return idn
    return None


def test_weight_increases_waist(manifest, tmp_path):
    lo = _pick(manifest, gender=0.0, age=0.5, weight=0.0, muscle=0.5, height=0.5, cupsize=0.5)
    hi = _pick(manifest, gender=0.0, age=0.5, weight=1.0, muscle=0.5, height=0.5, cupsize=0.5)
    if not (lo and hi):
        pytest.skip("matched min/max weight pair not in set")
    assert _ingest(hi, tmp_path)["waist"] > _ingest(lo, tmp_path)["waist"] + 3.0


def test_height_slider_increases_measured_height(manifest, tmp_path):
    lo = _pick(manifest, gender=0.0, age=0.5, weight=0.5, muscle=0.5, height=0.0, cupsize=0.5)
    hi = _pick(manifest, gender=0.0, age=0.5, weight=0.5, muscle=0.5, height=1.0, cupsize=0.5)
    if not (lo and hi):
        pytest.skip("matched min/max height pair not in set")
    assert _ingest(hi, tmp_path)["height"] > _ingest(lo, tmp_path)["height"] + 2.0


def test_cupsize_increases_bust_points(manifest, tmp_path):
    lo = _pick(manifest, gender=0.0, age=0.5, weight=0.5, muscle=0.5, height=0.5, cupsize=0.0)
    hi = _pick(manifest, gender=0.0, age=0.5, weight=0.5, muscle=0.5, height=0.5, cupsize=1.0)
    if not (lo and hi):
        pytest.skip("matched min/max cupsize pair not in set")
    assert _ingest(hi, tmp_path)["bust"] >= _ingest(lo, tmp_path)["bust"]


@pytest.mark.parametrize("path", sorted(glob.glob(str(DIR / "*.glb")))[:12])
def test_bodies_generate_without_crash(path, tmp_path):
    from assets.bodies.body_params import BodyParameters
    from assets.garment_programs.meta_garment import MetaGarment
    idn = Path(path).stem
    out = run(str(DIR / f"{idn}.glb"), out_dir=str(tmp_path), name=idn,
              landmarks_path=None, arm_pose_angle=0.0, height_m=None)
    body = BodyParameters(str(out))
    design = yaml.safe_load(open("assets/design_params/default.yaml"))["design"]
    assert MetaGarment(idn, body, design).assembly() is not None
```

- [ ] **Step 3: Run it**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_stress_testset.py -q`
Expected: PASS (property tests hold; any out-of-range body is a real extractor bug → fix the responsible `autolandmarks` heuristic, not the assertion). Bodies that legitimately fail generation under T-pose extremes (e.g. a baby) may be excluded from the grid in `gen_mpfb_testset.py::_grid` rather than asserted around.

- [ ] **Step 4: Commit**

```bash
git add tests/mpfb_ingest/test_stress_testset.py
git commit -m "test(mpfb_ingest): cross-body property + generation stress over MPFB set"
```

---

## Task 13: Documentation

**Files:**
- Modify: `mpfb_ingest/README.md`
- Modify: `docs/superpowers/specs/2026-06-05-garmentcode-mpfb-measurement-ingestion-handoff.md` (backfill §8.5)

- [ ] **Step 1: Update the module README**

In `mpfb_ingest/README.md`, add a section documenting:
- The **auto path** (default): `ingest_mpfb_body.py <mesh> --name X --arm-pose-angle 0` with no `--landmarks`,
  works on any human mesh (glb/obj), measures units+height automatically.
- The committed-index path is now opt-in via `--landmarks` (the calibrated base regression).
- The **test-set generator**: `scripts/run_mpfb_gen.sh [out] [limit]`, what it emits, and the CC0 provenance.
- That all 26 fields are now real geometry via `autolandmarks.py` (T-pose arm-exclusion via central loop).

- [ ] **Step 2: Backfill the predecessor spec §8.5**

In the 2026-06-05 handoff spec §8.5, mark deferred items 1 (full-fidelity anchors) and 2 (consumer-export
topology) as **closed by** `docs/superpowers/specs/2026-06-08-mpfb-full-fidelity-topology-agnostic-and-stress.md`,
with a one-line pointer to the auto path + generator.

- [ ] **Step 3: Final full-suite run**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/ -q`
Expected: all green (original 24 + new geometry/units/autolandmarks/stress tests).

- [ ] **Step 4: Commit**

```bash
git add mpfb_ingest/README.md docs/superpowers/specs/2026-06-05-garmentcode-mpfb-measurement-ingestion-handoff.md
git commit -m "docs(mpfb_ingest): document auto path, full-fidelity extractor, test-set generator"
```

---

## Self-review checklist (run before execution)

- **Spec coverage:** §4.1 reuse (T3, T8) · §4.2 autolandmarks (T5–T7) · §4.3 central loop (T2) · §4.4 units (T4) ·
  §4.5 CLI (T8) · §4.6 generator (T10) · acceptance §5.1–5.2 (T9) · §5.3–5.4 (T12) · §5.5 regression (every full-suite step) · §5.6 height (T4, T9). All mapped.
- **Empirical heuristics:** the `autolandmarks` landmark heuristics (T6–T7) have concrete first-cut code; their
  acceptance is the range/ordering tests on the real base + the cross-body property tests. Refine the heuristic
  (not the assertion) when a body reads wrong — this is the expected TDD loop, not a placeholder.
- **API drift:** the MPFB generator (T10) lists the three verified service calls; any 2.0.15 signature mismatch
  is fixed against the installed package during T10 Step 3, before downstream tasks depend on its output.
- **Type/name consistency:** `central_loop`/`central_perimeter` (T2) used by `circumferences` (T3) and
  `autolandmarks` (T5–T7); `autolandmarks.derive` returns the `Landmarks` container consumed by
  `measurements.compute_all` and the CLI (T8); landmark names match `measurements.py`'s `_BACK`/`_EUCLID`/
  `_DELTA_Y`/`_GEODESIC`/`angles` maps exactly.

---

## Execution

Per the user's instruction, execute with **superpowers:subagent-driven-development** — a fresh implementer
subagent per task with two-stage (spec + quality) review between tasks, committing on green. Generator tasks
(T10) require the Windows Blender; run them in the main session (or a subagent with Bash) and verify output
before T11–T12 consume it.
