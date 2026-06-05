# MPFB Body-Measurement Ingestion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A clean-room Python module that reads an MPFB/MakeHuman body mesh (OBJ) and emits a GarmentCode body-measurements YAML (the 26 base fields), so GarmentCode can fit/drape garments on custom MPFB avatars.

**Architecture:** New MIT-fork package `mpfb_ingest/` (no dependency on the GPLv3 `GarmentMeasurements` tool — see spec §5). Geometry-driven extraction: MakeHuman's fixed topology lets us pin anatomical **landmarks to constant vertex indices** (calibrated once into a JSON), then compute each measurement with mesh slicing (trimesh), surface geodesics (libigl `exact_geodesic`), and euclidean/Δ/angle primitives. A thin emit layer hands the measurement dict to GarmentCode's own `BodyParameters` so the derived `_`-fields and YAML format come for free. A root CLI `ingest_mpfb_body.py` orchestrates.

**Tech Stack:** Python 3.9, trimesh 4.x (BSD), libigl (MPL2, already a dep), numpy/scipy (BSD), pytest (dev). All permissive — no GPL geometry deps.

**Reference spec:** `docs/superpowers/specs/2026-06-05-garmentcode-mpfb-measurement-ingestion-handoff.md`

**Out of scope (separate future plan):** the body-segmentation JSON needed for *draping* and the `PathCofig.body_seg` extension (spec §4.5). This plan produces the measurements YAML only — which is the sole input pattern generation needs (spec §1).

---

## File structure

| File | Responsibility |
|---|---|
| `mpfb_ingest/__init__.py` | Package marker + public exports |
| `mpfb_ingest/mesh_io.py` | Load OBJ; normalize units→metres, Y-up, ground; produce a cm working copy |
| `mpfb_ingest/geometry.py` | Pure geometry primitives: slice loops/perimeter, geodesic, euclidean, ΔY, back-arc, angles |
| `mpfb_ingest/landmarks.py` | `Landmarks` loader/validator over the vertex-index JSON |
| `mpfb_ingest/data/makehuman_landmarks.json` | Calibrated constant vertex indices (Task 13, asset-gated) |
| `mpfb_ingest/measurements.py` | The 26 field computations → ordered dict |
| `mpfb_ingest/emit.py` | Range validation + hand-off to `BodyParameters` → YAML |
| `ingest_mpfb_body.py` (repo root) | CLI orchestration |
| `tests/mpfb_ingest/conftest.py` | Synthetic fixtures (cylinder torso, tiny hand-built meshes, fixture landmarks) |
| `tests/mpfb_ingest/test_*.py` | One test module per source module |
| `mpfb_ingest/README.md` | Usage + clean-room provenance note |

**Working-units convention (decided once, applies everywhere):**
- `mesh_io.normalize()` returns the mesh in **metres** (height ≈ 1.72), Y-up, feet at Y=0, centred in X/Z. This is the mesh you save as the GarmentCode body OBJ (GarmentCode scales it ×100 via `b_scale`).
- `mesh_io.to_cm()` returns a **×100 copy (centimetres)**. **All measurement math runs on the cm mesh**, so outputs are cm directly and match the YAML (angles are unitless degrees).

---

## Task 1: Package scaffolding + pytest

**Files:**
- Create: `mpfb_ingest/__init__.py`
- Create: `tests/mpfb_ingest/__init__.py`
- Create: `tests/mpfb_ingest/conftest.py`

- [ ] **Step 1: Install pytest into the project venv**

Run: `.venv/bin/python -m pip install pytest`
Expected: `Successfully installed pytest-...`

- [ ] **Step 2: Create the package marker**

`mpfb_ingest/__init__.py`:

```python
"""Clean-room MPFB/MakeHuman -> GarmentCode body-measurement ingestion.

Implemented from the published GarmentCode measurement definitions
(docs/Body Measurements GarmentCode.pdf). Does NOT use, link, or derive
from the GPLv3 mbotsch/GarmentMeasurements tool.
"""

__all__ = ["mesh_io", "geometry", "landmarks", "measurements", "emit"]
```

- [ ] **Step 3: Create the test package marker**

`tests/mpfb_ingest/__init__.py`:

```python
```

(empty file)

- [ ] **Step 4: Create shared synthetic fixtures**

`tests/mpfb_ingest/conftest.py`:

```python
import numpy as np
import trimesh
import pytest


@pytest.fixture
def cylinder_cm():
    """Upright cylinder as a torso proxy, already in cm.
    radius=15 cm, height=100 cm, axis = Y. Perimeter at any slice = 2*pi*15.
    """
    # trimesh cylinder is built along Z; rotate so axis is +Y.
    cyl = trimesh.creation.cylinder(radius=15.0, height=100.0, sections=256)
    R = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0])
    cyl.apply_transform(R)
    # ground it: min Y -> 0
    cyl.apply_translation([0, -cyl.bounds[0][1], 0])
    return cyl


@pytest.fixture
def tiny_mesh():
    """A 4-vertex tri-pair with known coordinates (cm) for euclidean/angle tests.

    v0 = (0,0,0)   v1 = (30,0,0)   v2 = (0,40,0)   v3 = (30,40,0)
    """
    v = np.array([[0, 0, 0], [30, 0, 0], [0, 40, 0], [30, 40, 0]], dtype=np.float64)
    f = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int64)
    return trimesh.Trimesh(vertices=v, faces=f, process=False)
```

- [ ] **Step 5: Verify pytest collects**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest -q`
Expected: `no tests ran` (0 collected, exit code 5) — confirms discovery works.

- [ ] **Step 6: Commit**

```bash
git add mpfb_ingest/__init__.py tests/mpfb_ingest/
git commit -m "feat(mpfb_ingest): package scaffolding + pytest fixtures"
```

---

## Task 2: Mesh IO — load, normalize, to_cm

**Files:**
- Create: `mpfb_ingest/mesh_io.py`
- Test: `tests/mpfb_ingest/test_mesh_io.py`

- [ ] **Step 1: Write the failing test**

`tests/mpfb_ingest/test_mesh_io.py`:

```python
import numpy as np
import trimesh
from mpfb_ingest import mesh_io


def _raw_human_proxy(scale):
    """Cylinder 'human' 1.7 units tall at the given unit scale, off-ground/off-centre."""
    cyl = trimesh.creation.cylinder(radius=0.15 * scale, height=1.7 * scale, sections=64)
    R = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0])
    cyl.apply_transform(R)
    cyl.apply_translation([5.0 * scale, 10.0 * scale, -3.0 * scale])
    return cyl


def test_normalize_metres_from_metre_input():
    mesh = _raw_human_proxy(scale=1.0)          # already metres
    out, report = mesh_io.normalize(mesh, expected_height_m=1.7)
    assert abs(report["height_m"] - 1.7) < 0.02
    assert abs(report["scale_to_m"] - 1.0) < 1e-6
    assert abs(out.bounds[0][1]) < 1e-6          # feet grounded at Y=0
    cx, _, cz = out.centroid
    assert abs(cx) < 1e-6 and abs(cz) < 1e-6     # centred X/Z


def test_normalize_metres_from_decimetre_input():
    mesh = _raw_human_proxy(scale=10.0)         # decimetres (MakeHuman quirk)
    out, report = mesh_io.normalize(mesh, expected_height_m=1.7)
    assert abs(report["scale_to_m"] - 0.1) < 1e-6
    assert abs(report["height_m"] - 1.7) < 0.02


def test_to_cm_scales_by_100():
    mesh = _raw_human_proxy(scale=1.0)
    out_m, _ = mesh_io.normalize(mesh, expected_height_m=1.7)
    cm = mesh_io.to_cm(out_m)
    assert abs(cm.bounds[1][1] - 170.0) < 2.0    # ~170 cm tall
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_mesh_io.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpfb_ingest.mesh_io'`

- [ ] **Step 3: Write minimal implementation**

`mpfb_ingest/mesh_io.py`:

```python
"""Load and normalize an MPFB-exported body mesh into GarmentCode's space."""
from pathlib import Path
import numpy as np
import trimesh


def load_body(path) -> trimesh.Trimesh:
    """Load an OBJ as a single Trimesh (concatenate scene geometry if needed)."""
    obj = trimesh.load(str(path), process=False, force="mesh")
    if not isinstance(obj, trimesh.Trimesh):
        obj = trimesh.util.concatenate(tuple(obj.geometry.values()))
    return obj


def normalize(mesh: trimesh.Trimesh, expected_height_m: float = 1.7):
    """Return (mesh_in_metres, report).

    Steps: detect unit scale from total Y-extent vs expected human height,
    scale to metres, centre X/Z on the centroid, ground feet to Y=0.
    Assumes the mesh is already Y-up (MakeHuman default).
    """
    mesh = mesh.copy()
    raw_height = float(mesh.bounds[1][1] - mesh.bounds[0][1])
    if raw_height <= 0:
        raise ValueError("Mesh has zero Y-extent; is it Y-up?")
    scale_to_m = expected_height_m / raw_height
    mesh.apply_scale(scale_to_m)

    cx, _, cz = mesh.centroid
    min_y = mesh.bounds[0][1]
    mesh.apply_translation([-cx, -min_y, -cz])

    report = {
        "scale_to_m": scale_to_m,
        "height_m": float(mesh.bounds[1][1] - mesh.bounds[0][1]),
        "n_vertices": int(len(mesh.vertices)),
    }
    return mesh, report


def to_cm(mesh_m: trimesh.Trimesh) -> trimesh.Trimesh:
    """Return a centimetre copy (x100) for measurement math."""
    cm = mesh_m.copy()
    cm.apply_scale(100.0)
    return cm


def save_body_obj(mesh_m: trimesh.Trimesh, out_dir, name: str) -> Path:
    """Save the metres mesh as <name>.obj for GarmentCode draping."""
    out = Path(out_dir) / f"{name}.obj"
    mesh_m.export(str(out))
    return out
```

> **Note on `scale_to_m`:** detecting scale from height is a heuristic. The CLI lets the user override `--height-m` per the model's known stature; the calibration task (13) confirms it on a real export.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_mesh_io.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/mesh_io.py tests/mpfb_ingest/test_mesh_io.py
git commit -m "feat(mpfb_ingest): mesh load + unit/pose normalization"
```

---

## Task 3: Geometry primitive — slice loops & perimeter

**Files:**
- Create: `mpfb_ingest/geometry.py`
- Test: `tests/mpfb_ingest/test_geometry_slice.py`

- [ ] **Step 1: Write the failing test**

`tests/mpfb_ingest/test_geometry_slice.py`:

```python
import numpy as np
from mpfb_ingest import geometry


def test_perimeter_at_height_matches_circle(cylinder_cm):
    # cylinder radius 15 cm -> circumference 2*pi*15 ~= 94.248
    p = geometry.slice_perimeter(cylinder_cm, y=50.0)
    assert abs(p - 2 * np.pi * 15.0) < 0.5


def test_slice_loops_returns_ordered_polyline(cylinder_cm):
    loops = geometry.slice_loops(cylinder_cm, y=50.0)
    assert len(loops) == 1
    loop = loops[0]
    assert loop.shape[1] == 3
    assert len(loop) > 16
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_geometry_slice.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpfb_ingest.geometry'`

- [ ] **Step 3: Write minimal implementation**

Create `mpfb_ingest/geometry.py` with the slicing primitives:

```python
"""Pure geometry primitives. All inputs/outputs in centimetres (mesh pre-scaled)."""
import numpy as np
import igl

_Y = np.array([0.0, 1.0, 0.0])


def slice_loops(mesh, y):
    """Return a list of ordered (N,3) polylines where the mesh crosses plane Y=y."""
    section = mesh.section(plane_origin=[0.0, y, 0.0], plane_normal=_Y)
    if section is None:
        return []
    return [np.asarray(d, dtype=np.float64) for d in section.discrete]


def _loop_perimeter(loop):
    d = np.diff(np.vstack([loop, loop[0]]), axis=0)   # close the loop
    return float(np.sum(np.linalg.norm(d, axis=1)))


def slice_perimeter(mesh, y, pick="longest", point=None):
    """Perimeter of one closed loop at height y.

    pick='longest'  -> the longest loop (torso girth, ignores stray loops)
    pick='nearest'  -> loop whose centroid is nearest `point` (x,z) (one limb)
    """
    loops = slice_loops(mesh, y)
    if not loops:
        raise ValueError(f"No cross-section at y={y}")
    if pick == "nearest" and point is not None:
        px, pz = point
        loops.sort(key=lambda L: (L[:, 0].mean() - px) ** 2 + (L[:, 2].mean() - pz) ** 2)
        return _loop_perimeter(loops[0])
    return max(_loop_perimeter(L) for L in loops)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_geometry_slice.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/geometry.py tests/mpfb_ingest/test_geometry_slice.py
git commit -m "feat(mpfb_ingest): mesh slicing + perimeter primitive"
```

---

## Task 4: Geometry primitives — geodesic, euclidean, ΔY, back-arc, angles

**Files:**
- Modify: `mpfb_ingest/geometry.py` (append)
- Test: `tests/mpfb_ingest/test_geometry_prims.py`

- [ ] **Step 1: Write the failing test**

`tests/mpfb_ingest/test_geometry_prims.py`:

```python
import numpy as np
from mpfb_ingest import geometry


def test_euclidean(tiny_mesh):
    p = tiny_mesh.vertices[0]   # (0,0,0)
    q = tiny_mesh.vertices[3]   # (30,40,0) -> 50
    assert abs(geometry.euclidean(p, q) - 50.0) < 1e-9


def test_delta_y(tiny_mesh):
    p = tiny_mesh.vertices[0]   # y=0
    q = tiny_mesh.vertices[2]   # y=40
    assert abs(geometry.delta_y(p, q) - 40.0) < 1e-9


def test_angle_to_horizontal(tiny_mesh):
    # vector (30,40) -> angle above horizontal = atan2(40,30) ~ 53.13 deg
    p = tiny_mesh.vertices[0]
    q = tiny_mesh.vertices[3]
    assert abs(geometry.angle_to_horizontal(p, q) - 53.130102) < 1e-3


def test_geodesic_on_flat_quad_equals_euclidean(tiny_mesh):
    # flat sheet: surface geodesic from v0 to v3 == straight line 50
    d = geometry.geodesic(tiny_mesh, 0, 3)
    assert abs(d - 50.0) < 1e-6


def test_back_arc_half_circle(cylinder_cm):
    # two opposite points on a radius-15 cylinder slice -> half perimeter = pi*15
    loops = geometry.slice_loops(cylinder_cm, y=50.0)
    loop = loops[0]
    # pick the two extreme-x points as 'side landmarks'
    left = loop[np.argmin(loop[:, 0])]
    right = loop[np.argmax(loop[:, 0])]
    arc = geometry.arc_between(loop, left, right, side="back")
    assert abs(arc - np.pi * 15.0) < 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_geometry_prims.py -q`
Expected: FAIL — `AttributeError: module 'mpfb_ingest.geometry' has no attribute 'euclidean'`

- [ ] **Step 3: Write minimal implementation (append to `geometry.py`)**

```python
def euclidean(p, q):
    return float(np.linalg.norm(np.asarray(p, float) - np.asarray(q, float)))


def delta_y(p, q):
    return float(abs(float(p[1]) - float(q[1])))


def angle_to_horizontal(p, q):
    """Degrees between vector p->q and the horizontal (XZ) plane."""
    v = np.asarray(q, float) - np.asarray(p, float)
    horiz = float(np.linalg.norm([v[0], v[2]]))
    return float(np.degrees(np.arctan2(abs(v[1]), horiz)))


def angle_to_vertical(p, q):
    """Degrees between vector p->q and vertical (Y). 0 = perfectly vertical."""
    return 90.0 - angle_to_horizontal(p, q)


def geodesic(mesh, src_idx, dst_idx):
    """Exact surface geodesic distance between two vertex indices (cm)."""
    v = np.asarray(mesh.vertices, dtype=np.float64)
    f = np.asarray(mesh.faces, dtype=np.int32)
    d = igl.exact_geodesic(
        v, f, np.array([src_idx], dtype=np.int32), np.array([dst_idx], dtype=np.int32)
    )
    return float(np.atleast_1d(d)[0])


def arc_between(loop, a, b, side="back", back_sign=-1.0):
    """Length along an ordered closed loop polyline between the loop points
    nearest to a and b, taking the branch on the requested side.

    side='back' selects the branch whose mean Z has sign == back_sign
    (facing convention: front = +Z, back = -Z by default).
    """
    ia = int(np.argmin(np.linalg.norm(loop - np.asarray(a, float), axis=1)))
    ib = int(np.argmin(np.linalg.norm(loop - np.asarray(b, float), axis=1)))
    lo, hi = sorted((ia, ib))
    branch1 = loop[lo:hi + 1]
    branch2 = np.vstack([loop[hi:], loop[:lo + 1]])

    def _len(poly):
        return float(np.sum(np.linalg.norm(np.diff(poly, axis=0), axis=1)))

    if side == "back":
        z1, z2 = branch1[:, 2].mean(), branch2[:, 2].mean()
        chosen = branch1 if (np.sign(z1) == np.sign(back_sign)) else branch2
        # if both ambiguous (symmetric), fall through to the longer/shorter as needed
        if np.sign(z1) == np.sign(z2):
            chosen = branch1   # symmetric proxy: either half is equal
    else:
        chosen = branch1
    return _len(chosen)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_geometry_prims.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/geometry.py tests/mpfb_ingest/test_geometry_prims.py
git commit -m "feat(mpfb_ingest): geodesic, euclidean, angle, back-arc primitives"
```

---

## Task 5: Landmarks loader + schema validation

**Files:**
- Create: `mpfb_ingest/landmarks.py`
- Create: `tests/mpfb_ingest/fixtures_landmarks.json`
- Test: `tests/mpfb_ingest/test_landmarks.py`

The landmark JSON maps semantic names to **vertex indices** (single ints) or **named levels** (a Y-height taken from a vertex). Schema:

```json
{
  "n_vertices_expected": 4,
  "vertices": { "nape": 2, "crown": 3, "wrist_r": 1 },
  "levels":   { "waist": 0 }
}
```

- [ ] **Step 1: Write the failing test**

`tests/mpfb_ingest/test_landmarks.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_landmarks.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpfb_ingest.landmarks'`

- [ ] **Step 3: Write minimal implementation**

`mpfb_ingest/landmarks.py`:

```python
"""Constant-vertex-index landmark registry for the fixed MakeHuman topology."""
import json
from pathlib import Path
import numpy as np


class Landmarks:
    def __init__(self, data: dict):
        self.n_vertices_expected = int(data.get("n_vertices_expected", 0))
        self.vertices = {k: int(v) for k, v in data.get("vertices", {}).items()}
        self.levels = {k: int(v) for k, v in data.get("levels", {}).items()}

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text()))

    def vertex_index(self, name: str) -> int:
        return self.vertices[name]

    def point(self, mesh, name: str):
        return np.asarray(mesh.vertices[self.vertices[name]], dtype=np.float64)

    def level_y(self, mesh, name: str) -> float:
        return float(mesh.vertices[self.levels[name]][1])

    def validate(self, mesh):
        n = len(mesh.vertices)
        if self.n_vertices_expected and n != self.n_vertices_expected:
            raise ValueError(
                f"Mesh vertex count {n} != expected {self.n_vertices_expected}; "
                "topology mismatch (not the calibrated MakeHuman base mesh?)."
            )
        for name, idx in {**self.vertices, **self.levels}.items():
            if not (0 <= idx < n):
                raise ValueError(f"Landmark '{name}' index {idx} out of range (n={n}).")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_landmarks.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/landmarks.py tests/mpfb_ingest/test_landmarks.py
git commit -m "feat(mpfb_ingest): landmark registry + topology validation"
```

---

## Task 6: Measurements — circumferences

**Files:**
- Create: `mpfb_ingest/measurements.py`
- Test: `tests/mpfb_ingest/test_measurements_circ.py`

Circumferences read a level (a landmark vertex's Y) and slice. Field→level→pick:
`waist`→`waist` longest · `bust`→`bust` longest · `underbust`→`underbust` longest ·
`hips`→`hips` longest · `wrist`→`wrist` nearest(wrist_r) · `leg_circ`→`thigh` nearest(thigh_r).

- [ ] **Step 1: Write the failing test**

`tests/mpfb_ingest/test_measurements_circ.py`:

```python
import json
import numpy as np
from mpfb_ingest.landmarks import Landmarks
from mpfb_ingest import measurements


def test_circumferences_on_cylinder(cylinder_cm):
    # Build fixture landmarks: levels at known Y; limb landmarks at the surface.
    lm = Landmarks({
        "n_vertices_expected": len(cylinder_cm.vertices),
        "vertices": {"wrist_r": 0, "thigh_r": 0},
        "levels": {"waist": 0, "bust": 0, "underbust": 0, "hips": 0,
                   "wrist": 0, "thigh": 0},
    })
    # force all levels to y=50 by monkeypatching via a level override map
    measured = measurements.circumferences(cylinder_cm, lm, level_y=lambda n: 50.0)
    expect = 2 * np.pi * 15.0
    for field in ["waist", "bust", "underbust", "hips"]:
        assert abs(measured[field] - expect) < 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_measurements_circ.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpfb_ingest.measurements'`

- [ ] **Step 3: Write minimal implementation**

`mpfb_ingest/measurements.py`:

```python
"""Compute GarmentCode's 26 base measurements from a cm body mesh + landmarks.

Implemented from docs/Body Measurements GarmentCode.pdf (spec section 2.4).
"""
from collections import OrderedDict
from . import geometry as geo


def circumferences(mesh, lm, level_y=None):
    """waist, bust, underbust, hips (longest loop) + wrist, leg_circ (nearest limb).

    Fields whose level is not available are skipped (Task 10/CLI fills the gaps).
    """
    def ly(n):
        if level_y is not None:
            return level_y(n)
        return lm.level_y(mesh, n) if n in lm.levels else None

    out = {}
    for field in ["waist", "bust", "underbust", "hips"]:
        y = ly(field)
        if y is None:
            continue
        out[field] = geo.slice_perimeter(mesh, y, pick="longest")
    if "wrist_r" in lm.vertices and ly("wrist") is not None:
        p = lm.point(mesh, "wrist_r")
        out["wrist"] = geo.slice_perimeter(mesh, ly("wrist"), pick="nearest",
                                           point=(p[0], p[2]))
    if "thigh_r" in lm.vertices and ly("thigh") is not None:
        p = lm.point(mesh, "thigh_r")
        out["leg_circ"] = geo.slice_perimeter(mesh, ly("thigh"), pick="nearest",
                                              point=(p[0], p[2]))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_measurements_circ.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/measurements.py tests/mpfb_ingest/test_measurements_circ.py
git commit -m "feat(mpfb_ingest): circumference measurements"
```

---

## Task 7: Measurements — back-section widths + neck_w

**Files:**
- Modify: `mpfb_ingest/measurements.py` (append)
- Test: `tests/mpfb_ingest/test_measurements_back.py`

Back widths take a level slice and the back arc between the two **side** landmarks
(`side_l_*`, `side_r_*`). `waist_back_width`→waist level, `back_width`→bust level,
`hip_back_width`→hips level, `neck_w`→neck level.

- [ ] **Step 1: Write the failing test**

`tests/mpfb_ingest/test_measurements_back.py`:

```python
import numpy as np
from mpfb_ingest.landmarks import Landmarks
from mpfb_ingest import measurements


def test_back_widths_on_cylinder(cylinder_cm):
    loop = measurements.geo.slice_loops(cylinder_cm, 50.0)[0]
    li = int(np.argmin(loop[:, 0]))
    ri = int(np.argmax(loop[:, 0]))
    # map those loop points to nearest mesh vertices for landmark indices
    vi = lambda pt: int(np.argmin(np.linalg.norm(cylinder_cm.vertices - pt, axis=1)))
    lm = Landmarks({
        "n_vertices_expected": len(cylinder_cm.vertices),
        "vertices": {"side_l_waist": vi(loop[li]), "side_r_waist": vi(loop[ri])},
        "levels": {"waist": 0},
    })
    out = measurements.back_widths(cylinder_cm, lm, level_y=lambda n: 50.0)
    assert abs(out["waist_back_width"] - np.pi * 15.0) < 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_measurements_back.py -q`
Expected: FAIL — `AttributeError: module 'mpfb_ingest.measurements' has no attribute 'back_widths'`

- [ ] **Step 3: Write minimal implementation (append to `measurements.py`)**

```python
_BACK = {
    "waist_back_width": ("waist", "side_l_waist", "side_r_waist"),
    "back_width":       ("bust",  "side_l_bust",  "side_r_bust"),
    "hip_back_width":   ("hips",  "side_l_hips",  "side_r_hips"),
    "neck_w":           ("neck",  "side_l_neck",  "side_r_neck"),
}


def back_widths(mesh, lm, level_y=None, back_sign=-1.0):
    ly = level_y if level_y is not None else (lambda n: lm.level_y(mesh, n))
    out = {}
    for field, (level, lname, rname) in _BACK.items():
        if lname not in lm.vertices or rname not in lm.vertices:
            continue
        loops = geo.slice_loops(mesh, ly(level))
        loop = max(loops, key=lambda L: len(L))
        out[field] = geo.arc_between(loop, lm.point(mesh, lname),
                                     lm.point(mesh, rname),
                                     side="back", back_sign=back_sign)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_measurements_back.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/measurements.py tests/mpfb_ingest/test_measurements_back.py
git commit -m "feat(mpfb_ingest): back-section widths + neck width"
```

---

## Task 8: Measurements — distances (euclidean, ΔY, geodesic)

**Files:**
- Modify: `mpfb_ingest/measurements.py` (append)
- Test: `tests/mpfb_ingest/test_measurements_dist.py`

Field map:
- Euclidean: `shoulder_w`(collar_l,collar_r) · `head_l`(nape,crown) · `bust_points`(bust_l,bust_r) · `bum_points`(bum_l,bum_r) · `armscye_depth`(shoulder_r,armpit_r) · `arm_length`(shoulder_r,wrist_r).
- ΔY: `height`(overall) · `hips_line`(waist_lvl,hips_lvl) · `crotch_hip_diff`(hips_lvl,crotch) · `vert_bust_line`(nape,bust_lvl).
- Geodesic: `waist_line`(nape,waist_back) · `bust_line`(shoulder_r,bust_r) · `waist_over_bust_line`(neck_base,waist_front).

- [ ] **Step 1: Write the failing test**

`tests/mpfb_ingest/test_measurements_dist.py`:

```python
import numpy as np
import trimesh
from mpfb_ingest.landmarks import Landmarks
from mpfb_ingest import measurements


def test_euclidean_and_dy_and_geodesic(tiny_mesh):
    lm = Landmarks({
        "n_vertices_expected": 4,
        "vertices": {"collar_l": 0, "collar_r": 1,     # (0,0,0)-(30,0,0) -> 30
                     "nape": 0, "crown": 2,            # (0,0,0)-(0,40,0) -> 40 / dy 40
                     "shoulder_r": 0, "wrist_r": 3},   # geodesic 0->3 on flat = 50
        "levels": {"waist": 0, "hips": 2},
    })
    out = measurements.distances(tiny_mesh, lm)
    assert abs(out["shoulder_w"] - 30.0) < 1e-6
    assert abs(out["head_l"] - 40.0) < 1e-6
    assert abs(out["height"] - 40.0) < 1e-6                # total Y extent
    assert abs(out["hips_line"] - 40.0) < 1e-6             # |waist y0 - hips y40|
    assert abs(out["arm_length"] - 50.0) < 1e-4            # geodesic
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_measurements_dist.py -q`
Expected: FAIL — `AttributeError: module 'mpfb_ingest.measurements' has no attribute 'distances'`

- [ ] **Step 3: Write minimal implementation (append to `measurements.py`)**

```python
_EUCLID = {
    "shoulder_w":    ("collar_l", "collar_r"),
    "head_l":        ("nape", "crown"),
    "bust_points":   ("bust_l", "bust_r"),
    "bum_points":    ("bum_l", "bum_r"),
    "armscye_depth": ("shoulder_r", "armpit_r"),
    "arm_length":    ("shoulder_r", "wrist_r"),   # geodesic (see below) overrides
}
_DELTA_Y = {
    "hips_line":       ("waist", "hips"),
    "crotch_hip_diff": ("hips", "crotch_lvl"),
    "vert_bust_line":  ("nape_lvl", "bust"),
}
_GEODESIC = {
    "waist_line":           ("nape", "waist_back"),
    "bust_line":            ("shoulder_r", "bust_r"),
    "waist_over_bust_line": ("neck_base", "waist_front"),
    "arm_length":           ("shoulder_r", "wrist_r"),
}


def distances(mesh, lm, level_y=None):
    ly = level_y if level_y is not None else (lambda n: lm.level_y(mesh, n))
    out = {}
    out["height"] = float(mesh.bounds[1][1] - mesh.bounds[0][1])

    for field, (a, b) in _EUCLID.items():
        if field == "arm_length":
            continue   # prefer geodesic version below
        if a in lm.vertices and b in lm.vertices:
            out[field] = geo.euclidean(lm.point(mesh, a), lm.point(mesh, b))

    for field, (a, b) in _DELTA_Y.items():
        la = a if a in lm.levels else None
        lb = b if b in lm.levels else None
        if la and lb:
            out[field] = abs(ly(la) - ly(lb))

    for field, (a, b) in _GEODESIC.items():
        if a in lm.vertices and b in lm.vertices:
            out[field] = geo.geodesic(mesh, lm.vertex_index(a), lm.vertex_index(b))
    return out
```

> **Note:** `_DELTA_Y` keys reference levels (`crotch_lvl`, `nape_lvl`). Define these as `levels` entries in the calibrated JSON (Task 13). Fields whose landmarks are absent are simply omitted; Task 10 fills any GarmentCode-required field that is still missing.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_measurements_dist.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/measurements.py tests/mpfb_ingest/test_measurements_dist.py
git commit -m "feat(mpfb_ingest): euclidean/deltaY/geodesic distance measurements"
```

---

## Task 9: Measurements — angles + `arm_pose_angle`, and `compute_all`

**Files:**
- Modify: `mpfb_ingest/measurements.py` (append)
- Test: `tests/mpfb_ingest/test_measurements_angles.py`

- [ ] **Step 1: Write the failing test**

`tests/mpfb_ingest/test_measurements_angles.py`:

```python
import numpy as np
from mpfb_ingest.landmarks import Landmarks
from mpfb_ingest import measurements


def test_shoulder_incl_angle(tiny_mesh):
    # neck_base (0,40,0) -> collar_r (30,0,0): drop of 40 over 30 horiz -> 53.13 deg
    lm = Landmarks({
        "n_vertices_expected": 4,
        "vertices": {"neck_base": 2, "collar_r": 1, "waist_side": 0, "hip_side": 0},
        "levels": {},
    })
    out = measurements.angles(tiny_mesh, lm, arm_pose_angle=90.0)
    assert abs(out["shoulder_incl"] - 53.130102) < 1e-3
    assert out["arm_pose_angle"] == 90.0


def test_compute_all_returns_dict(cylinder_cm):
    lm = Landmarks({"n_vertices_expected": len(cylinder_cm.vertices),
                    "vertices": {}, "levels": {}})
    # with no landmarks, only height + (no) others; must not raise
    result = measurements.compute_all(cylinder_cm, lm, arm_pose_angle=90.0,
                                      level_y=lambda n: 50.0)
    assert "height" in result and "arm_pose_angle" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_measurements_angles.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'angles'`

- [ ] **Step 3: Write minimal implementation (append to `measurements.py`)**

```python
def angles(mesh, lm, arm_pose_angle):
    out = {"arm_pose_angle": float(arm_pose_angle)}
    if "neck_base" in lm.vertices and "collar_r" in lm.vertices:
        out["shoulder_incl"] = geo.angle_to_horizontal(
            lm.point(mesh, "neck_base"), lm.point(mesh, "collar_r"))
    if "waist_side" in lm.vertices and "hip_side" in lm.vertices:
        out["hip_inclination"] = geo.angle_to_vertical(
            lm.point(mesh, "waist_side"), lm.point(mesh, "hip_side"))
    return out


def compute_all(mesh, lm, arm_pose_angle, level_y=None):
    """Run every group; return an OrderedDict of all available base fields."""
    result = OrderedDict()
    result.update(circumferences(mesh, lm, level_y=level_y))
    result.update(back_widths(mesh, lm, level_y=level_y))
    result.update(distances(mesh, lm, level_y=level_y))
    result.update(angles(mesh, lm, arm_pose_angle=arm_pose_angle))
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_measurements_angles.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/measurements.py tests/mpfb_ingest/test_measurements_angles.py
git commit -m "feat(mpfb_ingest): angle measurements + compute_all aggregator"
```

---

## Task 10: Emit — validation + hand-off to `BodyParameters`

**Files:**
- Create: `mpfb_ingest/emit.py`
- Test: `tests/mpfb_ingest/test_emit.py`

`emit` validates the 26-field set, then builds measurements via GarmentCode's own
`BodyParameters.load_from_dict` so the derived `_`-fields and YAML format are produced
by GarmentCode itself (single source of truth).

- [ ] **Step 1: Write the failing test**

`tests/mpfb_ingest/test_emit.py`:

```python
import yaml
from mpfb_ingest import emit

# A full, plausible 26-field measurement dict (cm / degrees), from mean_all.yaml.
FULL = {
    "arm_length": 53.97, "arm_pose_angle": 90.0, "armscye_depth": 12.87,
    "back_width": 47.68, "bum_points": 18.23, "bust": 99.84, "bust_line": 25.69,
    "bust_points": 16.95, "crotch_hip_diff": 8.81, "head_l": 26.33, "height": 171.99,
    "hip_back_width": 54.82, "hip_inclination": 9.86, "hips": 103.48, "hips_line": 23.48,
    "leg_circ": 60.20, "neck_w": 18.93, "shoulder_incl": 21.68, "shoulder_w": 36.46,
    "underbust": 86.25, "vert_bust_line": 21.14, "waist": 84.33, "waist_back_width": 39.14,
    "waist_line": 36.89, "waist_over_bust_line": 40.56, "wrist": 16.59,
}


def test_missing_required_fields_raises():
    bad = {k: v for k, v in FULL.items() if k != "waist"}
    try:
        emit.validate(bad)
        assert False, "should have raised"
    except ValueError as e:
        assert "waist" in str(e)


def test_emit_writes_yaml_with_derived_fields(tmp_path):
    out = emit.to_body_yaml(FULL, tmp_path, name="mpfb_test")
    assert out.name == "mpfb_test.yaml"
    data = yaml.safe_load(out.read_text())["body"]
    assert abs(data["waist"] - 84.33) < 1e-6
    assert "_waist_level" in data          # derived field computed by BodyParameters
    assert "_leg_length" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_emit.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpfb_ingest.emit'`

- [ ] **Step 3: Write minimal implementation**

`mpfb_ingest/emit.py`:

```python
"""Validate measurements and emit a GarmentCode body YAML via BodyParameters."""
from pathlib import Path
from assets.bodies.body_params import BodyParameters

REQUIRED = [
    "arm_length", "arm_pose_angle", "armscye_depth", "back_width", "bum_points",
    "bust", "bust_line", "bust_points", "crotch_hip_diff", "head_l", "height",
    "hip_back_width", "hip_inclination", "hips", "hips_line", "leg_circ", "neck_w",
    "shoulder_incl", "shoulder_w", "underbust", "vert_bust_line", "waist",
    "waist_back_width", "waist_line", "waist_over_bust_line", "wrist",
]

# Sanity ranges (cm / degrees) — gross-error guard, not anthropometric precision.
RANGES = {
    "height": (120, 220), "bust": (60, 160), "waist": (50, 160), "hips": (60, 170),
    "shoulder_w": (25, 55), "arm_length": (40, 75), "arm_pose_angle": (0, 180),
    "shoulder_incl": (0, 45), "hip_inclination": (0, 45),
}


def validate(measurements: dict):
    missing = [f for f in REQUIRED if f not in measurements]
    if missing:
        raise ValueError(f"Missing required measurement field(s): {missing}")
    for field, (lo, hi) in RANGES.items():
        v = measurements[field]
        if not (lo <= v <= hi):
            raise ValueError(f"Measurement '{field}'={v} out of sane range [{lo},{hi}].")


def to_body_yaml(measurements: dict, out_dir, name: str) -> Path:
    validate(measurements)
    body = BodyParameters()                 # empty, no file
    body.load_from_dict({k: float(v) for k, v in measurements.items()})
    body.save(out_dir, name=name)           # writes <out_dir>/<name>.yaml
    return Path(out_dir) / f"{name}.yaml"
```

> **Note:** `BodyParameters()` must construct without a file. Confirm `BodyParametrizationBase.__init__` tolerates `param_file=''`; the current code calls `self.load(param_file)` unconditionally. **If `BodyParameters()` raises on empty path, add a guard** in a 1-line change: in `pygarment/garmentcode/params.py` `__init__`, wrap `if param_file: self.load(param_file)`. Make that change in this task if the test fails on construction, and commit it together.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_emit.py -q`
Expected: PASS (2 passed). If it fails on `BodyParameters()` construction, apply the guard noted above, re-run.

- [ ] **Step 5: Commit**

```bash
git add mpfb_ingest/emit.py tests/mpfb_ingest/test_emit.py
# include params.py only if the empty-path guard was needed:
# git add pygarment/garmentcode/params.py
git commit -m "feat(mpfb_ingest): measurement validation + GarmentCode YAML emit"
```

---

## Task 11: CLI — `ingest_mpfb_body.py`

**Files:**
- Create: `ingest_mpfb_body.py` (repo root)
- Test: `tests/mpfb_ingest/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/mpfb_ingest/test_cli.py`:

```python
import numpy as np
import trimesh
import yaml
from ingest_mpfb_body import run


def _proxy_obj(tmp_path):
    cyl = trimesh.creation.cylinder(radius=0.15, height=1.7, sections=64)
    R = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0])
    cyl.apply_transform(R)
    p = tmp_path / "avatar.obj"
    cyl.export(str(p))
    return p


def test_cli_run_smoke(tmp_path, monkeypatch):
    obj = _proxy_obj(tmp_path)
    # Minimal landmarks JSON that only enables height (cylinder has no anatomy).
    lm = tmp_path / "lm.json"
    lm.write_text('{"n_vertices_expected": 0, "vertices": {}, "levels": {}}')
    # Force-fill missing fields so emit.validate passes (gross proxy values).
    out = run(str(obj), out_dir=str(tmp_path), name="avatar",
              landmarks_path=str(lm), arm_pose_angle=90.0, height_m=1.7,
              fill_defaults=True)
    data = yaml.safe_load((tmp_path / "avatar.yaml").read_text())["body"]
    assert abs(data["height"] - 170.0) < 3.0
    assert data["arm_pose_angle"] == 90.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingest_mpfb_body'`

- [ ] **Step 3: Write minimal implementation**

`ingest_mpfb_body.py`:

```python
"""CLI: MPFB body OBJ -> GarmentCode body-measurements YAML.

Usage:
  ./.venv/bin/python ingest_mpfb_body.py avatar.obj --name avatar \
      --landmarks mpfb_ingest/data/makehuman_landmarks.json \
      --arm-pose-angle 90 --out assets/bodies --save-obj
"""
import argparse
from pathlib import Path

from mpfb_ingest import mesh_io, measurements, emit
from mpfb_ingest.landmarks import Landmarks

# Conservative fallback values (cm/deg) used only with --fill-defaults for fields
# whose landmarks are not yet calibrated. From mean_all.yaml.
_DEFAULTS = {
    "arm_length": 53.97, "armscye_depth": 12.87, "back_width": 47.68,
    "bum_points": 18.23, "bust": 99.84, "bust_line": 25.69, "bust_points": 16.95,
    "crotch_hip_diff": 8.81, "head_l": 26.33, "hip_back_width": 54.82,
    "hip_inclination": 9.86, "hips": 103.48, "hips_line": 23.48, "leg_circ": 60.20,
    "neck_w": 18.93, "shoulder_incl": 21.68, "shoulder_w": 36.46, "underbust": 86.25,
    "vert_bust_line": 21.14, "waist": 84.33, "waist_back_width": 39.14,
    "waist_line": 36.89, "waist_over_bust_line": 40.56, "wrist": 16.59,
}


def run(obj_path, out_dir, name, landmarks_path, arm_pose_angle,
        height_m=1.7, save_obj=False, fill_defaults=False):
    raw = mesh_io.load_body(obj_path)
    mesh_m, report = mesh_io.normalize(raw, expected_height_m=height_m)
    cm = mesh_io.to_cm(mesh_m)

    lm = Landmarks.load(landmarks_path)
    if lm.n_vertices_expected:
        lm.validate(cm)

    measured = measurements.compute_all(cm, lm, arm_pose_angle=arm_pose_angle)
    measured["height"] = float(cm.bounds[1][1] - cm.bounds[0][1])

    if fill_defaults:
        for k, v in _DEFAULTS.items():
            measured.setdefault(k, v)

    out_yaml = emit.to_body_yaml(measured, out_dir, name)
    if save_obj:
        mesh_io.save_body_obj(mesh_m, out_dir, name)
    print(f"Wrote {out_yaml}  (scale_to_m={report['scale_to_m']:.4f}, "
          f"verts={report['n_vertices']})")
    return out_yaml


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("obj")
    ap.add_argument("--name", required=True)
    ap.add_argument("--landmarks", required=True)
    ap.add_argument("--arm-pose-angle", type=float, required=True,
                    help="Arm pose at the shoulder joint (deg). See module README.")
    ap.add_argument("--out", default="assets/bodies")
    ap.add_argument("--height-m", type=float, default=1.7)
    ap.add_argument("--save-obj", action="store_true")
    ap.add_argument("--fill-defaults", action="store_true",
                    help="Fill not-yet-calibrated fields with neutral-body values.")
    a = ap.parse_args()
    run(a.obj, a.out, a.name, a.landmarks, a.arm_pose_angle,
        height_m=a.height_m, save_obj=a.save_obj, fill_defaults=a.fill_defaults)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest/test_cli.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest tests/mpfb_ingest -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add ingest_mpfb_body.py tests/mpfb_ingest/test_cli.py
git commit -m "feat(mpfb_ingest): CLI orchestration + end-to-end smoke test"
```

---

## Task 12: Determine the `arm_pose_angle` convention (investigation)

**Files:**
- Modify: `mpfb_ingest/README.md` (create in this task)
- Read-only: `assets/garment_programs/sleeves.py`, `assets/bodies/*.yaml`

- [ ] **Step 1: Inspect how `arm_pose_angle` is consumed**

Run: `grep -rn "arm_pose_angle\|arm_pose\|pose_angle" assets/garment_programs/`
Read the sleeve-alignment usage to determine the zero and sign (e.g. measured from the
horizontal vs from the torso-down vertical).

- [ ] **Step 2: Cross-check reference values**

Reference: `mean_all.yaml` `arm_pose_angle: 45.483`, SMPL `*_A40` ≈ 40 (these are A-pose
bodies). Infer the T-pose value (arms horizontal) from the established convention.

- [ ] **Step 3: Record the decision**

Create `mpfb_ingest/README.md` with a "Pose conventions" section stating: the meaning of
`arm_pose_angle`, the A-pose reference values, and the value to pass for a T-pose MPFB
avatar. Add the clean-room provenance note (implemented from the published spec; no use of
GPLv3 GarmentMeasurements).

- [ ] **Step 4: Commit**

```bash
git add mpfb_ingest/README.md
git commit -m "docs(mpfb_ingest): arm_pose_angle convention + provenance note"
```

---

## Task 13: Landmark calibration on the real MakeHuman base mesh (ASSET-GATED)

> **Prerequisite:** an actual MPFB/MakeHuman export OBJ (the base mesh, or any one model — topology is identical). This task cannot be completed without it.

**Files:**
- Create: `mpfb_ingest/data/makehuman_landmarks.json`
- Create: `scripts/calibrate_landmarks.py` (interactive helper)
- Test: `tests/mpfb_ingest/test_calibration_realmesh.py` (skipped unless the asset is present)

- [ ] **Step 1: Capture the topology constant**

Run: `.venv/bin/python -c "import trimesh; print(len(trimesh.load('PATH/to/makehuman.obj', force='mesh').vertices))"`
Record the vertex count → `n_vertices_expected` in the JSON.

- [ ] **Step 2: Identify landmark vertex indices**

For each landmark name used in `measurements.py` (`nape`, `crown`, `collar_l/r`,
`neck_base`, `shoulder_r`, `armpit_r`, `wrist_r`, `bust_l/r`, `bum_l/r`, `crotch_lvl`,
`thigh_r`, `side_l/r_{waist,bust,hips,neck}`, `waist_back`, `waist_front`, `waist_side`,
`hip_side`, and the `levels`), find the vertex index on the base mesh. Use one of:
- MakeHuman's CC0 measurement vertex data (its Measure-tab loops) as seeds where they align;
- `scripts/calibrate_landmarks.py`: load the mesh, print the K nearest vertices to a
  clicked/typed XYZ, and write selections to the JSON. Build this helper to dump
  `vertex_index, xyz` for visual confirmation in Blender.

- [ ] **Step 3: Write the JSON**

Populate `mpfb_ingest/data/makehuman_landmarks.json` with `n_vertices_expected`,
`vertices`, and `levels` for every name above.

- [ ] **Step 4: End-to-end validation test (asset-gated)**

`tests/mpfb_ingest/test_calibration_realmesh.py`:

```python
import os
import pytest

MESH = os.environ.get("MPFB_TEST_OBJ")          # path to a real export
pytestmark = pytest.mark.skipif(not MESH, reason="set MPFB_TEST_OBJ to run")


def test_realmesh_measurements_in_sane_ranges(tmp_path):
    from ingest_mpfb_body import run
    out = run(MESH, out_dir=str(tmp_path), name="cal",
              landmarks_path="mpfb_ingest/data/makehuman_landmarks.json",
              arm_pose_angle=90.0, height_m=1.7, fill_defaults=False)
    import yaml
    d = yaml.safe_load(out.read_text())["body"]
    assert 150 <= d["height"] <= 200
    assert 70 <= d["bust"] <= 130
    assert 60 <= d["waist"] <= 120
    assert d["waist_back_width"] < d["waist"]      # back arc < full girth
```

Run: `MPFB_TEST_OBJ=/path/to/export.obj .venv/bin/python -m pytest tests/mpfb_ingest/test_calibration_realmesh.py -q`
Expected: PASS, and the printed measurements look anatomically plausible.

- [ ] **Step 5: Cross-check against MPFB's own readouts**

Where MPFB exposes a circumference (bust/waist/hips), compare to the extracted value;
they should agree within a few cm. Note discrepancies in `mpfb_ingest/README.md`.

- [ ] **Step 6: Commit**

```bash
git add mpfb_ingest/data/makehuman_landmarks.json scripts/calibrate_landmarks.py \
        tests/mpfb_ingest/test_calibration_realmesh.py mpfb_ingest/README.md
git commit -m "feat(mpfb_ingest): calibrate MakeHuman landmarks + real-mesh validation"
```

---

## Task 14: Integrate into GarmentCode pattern generation (end-to-end)

**Files:**
- Modify: `mpfb_ingest/README.md` (append usage)
- Read-only: `test_garmentcode.py`

- [ ] **Step 1: Generate a pattern on the MPFB body**

Produce `assets/bodies/<name>.yaml` via the CLI (Task 11), then point a generation run at
it. Quickest check: edit `test_garmentcode.py` `bodies_measurements` to add
`'mpfb': './assets/bodies/<name>.yaml'`, set `body_to_use = 'mpfb'`, run:

Run: `.venv/bin/python test_garmentcode.py`
Expected: `Success! ... saved to ...` with no measurement KeyErrors.

- [ ] **Step 2: Document the full workflow**

Append to `mpfb_ingest/README.md`: export from MPFB → `ingest_mpfb_body.py` → drop YAML in
`assets/bodies/` → use in generation. Add a pointer that **draping** additionally needs the
body OBJ (`--save-obj`) **and** a segmentation JSON + `PathCofig.body_seg` extension —
tracked as the separate sibling plan (spec §4.5).

- [ ] **Step 3: Commit**

```bash
git add mpfb_ingest/README.md
git commit -m "docs(mpfb_ingest): end-to-end usage with GarmentCode generation"
```

---

## Self-review notes (for the implementer)

- **Spec coverage:** §2 fields → Tasks 6–9; §2.2 loader hand-off → Task 10; §2.6 units/`b_scale` → Task 2; §4.1 normalization → Task 2; §4.3 method per field group → Tasks 3–9; §4.4 module shape → Tasks 10–11; §4.5 integration + segmentation flag → Task 14; §5 licensing/provenance → Task 1 docstring + Task 12 README; §6.3 arm_pose_angle → Task 12; §6.2 calibration → Task 13; §6.7 validation → Tasks 10 & 13.
- **Asset gate:** Tasks 1–12 are fully testable now with synthetic fixtures. Tasks 13–14 require a real MPFB export and must not be marked done without it.
- **Type consistency:** landmark names are shared between `measurements.py` (consumer) and the JSON (producer, Task 13) — the names listed in Task 13 Step 2 are the authoritative set; keep them in sync if measurement functions change.
- **Known approximation:** `arc_between` back/front selection uses a facing sign (`back_sign`, front=+Z). Confirm MPFB facing during Task 13 and set `back_sign` accordingly (wire it through `back_widths` if needed).
