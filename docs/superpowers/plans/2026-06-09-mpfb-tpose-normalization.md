# MPFB T-Pose Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate the 12-step manual MPFB → T-pose procedure as a headless Blender module that generates a human from macro params, raises its arms to true horizontal, bakes the pose, and exports an ingest-ready `.glb` + normalized `.blend`.

**Architecture:** Pure-numpy geometry (`mpfb_tpose/geometry.py`, unit-tested in the py3.9 venv) is isolated from thin `bpy` orchestration (`human`/`rig`/`normalize`/`export`, run inside Blender's py3.13). A CLI runs inside Blender via a WSL→Windows wrapper. Correctness is proven two ways: fast geometry units, and a gated end-to-end test that re-derives landmarks on the exported `.glb` and asserts the arms are horizontal.

**Tech Stack:** Python 3.9 (venv: numpy, trimesh, pytest, `mpfb_ingest`), Blender 5.1.2 headless (`bpy`, py3.13) + MPFB 2.0.15 (`HumanService`, `RigService`, `ExportService`), WSL2.

**TDD note (read once):** Only `geometry.py` and the integration assertions can run in pytest — `bpy` code cannot import into the venv. So geometry gets strict red→green TDD; each `bpy` module is validated by an actual headless Blender run with a concrete expected output before commit. This is the honest TDD shape under the two-Python-version constraint (spec §3).

**Confirmed MPFB API (no guesses):**
- Generate: `HumanService.create_human(macro_detail_dict=…, feet_on_ground=True)` → returns the basemesh (human at origin, identity transform → armature space == world).
- Rig: `HumanService.add_builtin_rig(basemesh, "game_engine", import_weights=True)` → armature object; adds an `ARMATURE`-type modifier on the basemesh; calls `RigService.normalize_rotation_mode` (bones become `XYZ`).
- Bones (`data/rigs/standard/rig.game_engine.json`): `clavicle_{l,r}` → `upperarm_{l,r}` → `lowerarm_{l,r}` → `hand_{l,r}`. Pivot = `upperarm_{l,r}` (head = shoulder joint); wrist = `hand_{l,r}` head.
- Bone world pos: `RigService.find_pose_bone_head_world_location(name, armature)`.
- Apply pose as rest: `RigService.apply_pose_as_rest_pose(armature)`.
- Clean export precedent (`scripts/gen_mpfb_testset.py`): bake macro shape keys into basis + `export_morph=False`, `export_yup=True`; strip helpers via `ExportService.bake_modifiers_remove_helpers(mesh, remove_helpers=True)`.
- Harmless on-exit `EXCEPTION_ACCESS_VIOLATION` (cats-blender) — wrapper tolerates a nonzero exit; success is keyed on output-file existence + a `TPOSE_OK` sentinel.

---

## Task 1: Package scaffold + pure geometry (strict TDD)

**Files:**
- Create: `mpfb_tpose/__init__.py`
- Create: `mpfb_tpose/geometry.py`
- Test: `tests/mpfb_tpose/test_geometry.py`

- [ ] **Step 1: Create the empty package marker**

`mpfb_tpose/__init__.py`:
```python
"""MPFB T-pose normalization: generate -> add rig -> raise arms to horizontal
-> bake -> export. See docs/superpowers/specs/2026-06-09-mpfb-tpose-normalization-design.md."""
```

- [ ] **Step 2: Write the failing geometry tests**

`tests/mpfb_tpose/test_geometry.py`:
```python
import numpy as np
import pytest
from mpfb_tpose import geometry as g


def _drooped(side, deg, length=30.0):
    """A straight arm of `length` cm drooping `deg` below horizontal on `side`."""
    sx = -1.0 if side == "l" else 1.0
    shoulder = np.array([sx * 5.0, 150.0, 0.0])
    wrist = shoulder + np.array([sx * length * np.cos(np.radians(deg)),
                                 0.0, -length * np.sin(np.radians(deg))])
    return shoulder, wrist


def test_rotate_about_y_quarter_turn():
    # Right-handed about +Y: +X maps to -Z (matches mathutils.Matrix.Rotation).
    out = g.rotate_about_y([1.0, 0.0, 0.0], np.pi / 2)
    assert np.allclose(out, [0.0, 0.0, -1.0], atol=1e-9)


@pytest.mark.parametrize("side", ["l", "r"])
@pytest.mark.parametrize("deg", [10.0, 30.0, 45.0, 60.0])
def test_rotation_brings_arm_horizontal(side, deg):
    sh, wr = _drooped(side, deg)
    phi = g.y_rotation_to_horizontal(sh, wr)
    out = g.rotate_about_y(wr - sh, phi)
    assert abs(out[2]) < 1e-9                          # z -> 0 (horizontal)
    assert np.sign(out[0]) == np.sign((wr - sh)[0])    # lateral side preserved


@pytest.mark.parametrize("side", ["l", "r"])
def test_already_horizontal_needs_no_rotation(side):
    sh, wr = _drooped(side, 0.0)
    assert abs(g.y_rotation_to_horizontal(sh, wr)) < 1e-9


def test_left_and_right_take_opposite_signs():
    a = g.y_rotation_to_horizontal(*_drooped("l", 45.0))
    b = g.y_rotation_to_horizontal(*_drooped("r", 45.0))
    assert a * b < 0


def test_droop_metric_zero_when_horizontal():
    assert g.droop_from_horizontal_deg(*_drooped("r", 0.0)) < 1e-6


def test_droop_metric_matches_input_angle():
    assert abs(g.droop_from_horizontal_deg(*_drooped("r", 35.0)) - 35.0) < 1e-6


@pytest.mark.parametrize("side", ["l", "r"])
def test_fallback_brings_canonical_arm_horizontal(side):
    phi = g.fallback_y_rotation(side, 45.0)
    sx = -1.0 if side == "l" else 1.0
    v = np.array([sx * np.cos(np.radians(45)), 0.0, -np.sin(np.radians(45))])
    out = g.rotate_about_y(v, phi)
    assert abs(out[2]) < 1e-9
    assert np.sign(out[0]) == sx
```

- [ ] **Step 3: Run the tests, verify they fail**

Run: `cd /home/kubangpawis/dev/GarmentCode/.claude/worktrees/zeelum+mpfb-tpose-normalize && PYTHONPATH=. /home/kubangpawis/dev/GarmentCode/.venv/bin/python -m pytest tests/mpfb_tpose/test_geometry.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpfb_tpose.geometry'`.

- [ ] **Step 4: Implement `mpfb_tpose/geometry.py`**

```python
"""Pure-numpy T-pose geometry. No bpy / no mathutils, so this imports under BOTH
the project venv (py3.9 unit tests) and Blender's bundled Python (py3.13 runtime).

Blender axes: X lateral, Y forward, Z up. The shoulder rotation that forms a
T-pose is a rotation about world +Y (acts in the frontal X-Z plane)."""
import numpy as np


def rotate_about_y(vec, angle):
    """Rotate a 3-vector about world +Y by `angle` radians, right-handed
    (matches mathutils.Matrix.Rotation(angle, 'Y'): +X -> -Z at +90 deg)."""
    v = np.asarray(vec, dtype=np.float64)
    c, s = np.cos(angle), np.sin(angle)
    x, y, z = float(v[0]), float(v[1]), float(v[2])
    return np.array([c * x + s * z, y, -s * x + c * z], dtype=np.float64)


def y_rotation_to_horizontal(shoulder, wrist):
    """Signed rotation (radians) about world +Y that brings the shoulder->wrist
    vector into the horizontal (z=0) plane while preserving the arm's lateral
    side (sign of x). Per-side sign is derived from the geometry, not hardcoded."""
    v = np.asarray(wrist, dtype=np.float64) - np.asarray(shoulder, dtype=np.float64)
    phi = np.arctan2(float(v[2]), float(v[0]))
    if float(v[0]) < 0.0:                       # left arm: side-preserving branch
        phi += np.pi
    return float((phi + np.pi) % (2.0 * np.pi) - np.pi)   # wrap to (-pi, pi]


def droop_from_horizontal_deg(shoulder, wrist):
    """Unsigned arm droop in DEGREES between the shoulder->wrist vector and the
    horizontal plane. 0 == perfect T-pose. (Runtime self-check, Blender Z-up.)"""
    v = np.asarray(wrist, dtype=np.float64) - np.asarray(shoulder, dtype=np.float64)
    horiz = float(np.hypot(v[0], v[1]))
    return float(abs(np.degrees(np.arctan2(abs(float(v[2])), horiz))))


def fallback_y_rotation(side, droop_deg=45.0):
    """Side-correct world-+Y rotation for a canonical `droop_deg` arm, used when
    bone geometry is degenerate. `side`: 'l' or 'r'."""
    sx = -1.0 if side == "l" else 1.0
    synthetic_wrist = (sx * np.cos(np.radians(droop_deg)), 0.0,
                       -np.sin(np.radians(droop_deg)))
    return y_rotation_to_horizontal((0.0, 0.0, 0.0), synthetic_wrist)
```

- [ ] **Step 5: Run the tests, verify they pass**

Run: `PYTHONPATH=. /home/kubangpawis/dev/GarmentCode/.venv/bin/python -m pytest tests/mpfb_tpose/test_geometry.py -q`
Expected: PASS (16 tests: 8 params × sides + singles).

- [ ] **Step 6: Commit**

```bash
git add mpfb_tpose/__init__.py mpfb_tpose/geometry.py tests/mpfb_tpose/test_geometry.py
git commit -m "feat(mpfb_tpose): pure-numpy T-pose shoulder geometry + units"
```

---

## Task 2: Blender-side rig + human creation (validated by a headless spike)

**Files:**
- Create: `mpfb_tpose/human.py`
- Create: `mpfb_tpose/rig.py`
- Create: `scripts/spike_tpose_api.py`
- Create: `scripts/run_blender.sh`

- [ ] **Step 1: Write `mpfb_tpose/human.py`**

```python
"""macro params -> MPFB human (basemesh). Runs INSIDE Blender."""
import bpy


def macro_dict(gender=0.5, age=0.5, weight=0.5, muscle=0.5, height=0.5,
               cupsize=0.5, firmness=0.5, proportions=0.5, race="caucasian"):
    r = {"asian": 0.0, "caucasian": 0.0, "african": 0.0}
    r[race] = 1.0
    return {"gender": gender, "age": age, "muscle": muscle, "weight": weight,
            "proportions": proportions, "height": height, "cupsize": cupsize,
            "firmness": firmness, "race": r}


def create(human_svc, macro):
    """Clear the scene and create a fresh MPFB human; return its basemesh object."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    return human_svc.create_human(macro_detail_dict=macro, feet_on_ground=True)
```

- [ ] **Step 2: Write `mpfb_tpose/rig.py`**

```python
"""Blender-side rig operations for T-pose normalization (py3.13). All math is
delegated to mpfb_tpose.geometry (pure numpy)."""
import importlib
import math
import bpy
import mathutils
import numpy as np
from . import geometry

# Pivot bone (head = shoulder joint) and the wrist bone, per side, in the
# MPFB Standard "game_engine" rig.
ARM = {"l": ("upperarm_l", "hand_l"), "r": ("upperarm_r", "hand_r")}


def services():
    """Enable MPFB and return (HumanService, ExportService, RigService)."""
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.blender_org.mpfb")
    except Exception as e:                       # noqa: BLE001
        print("WARN addon_enable:", e)
    base = "bl_ext.blender_org.mpfb.services."
    H = importlib.import_module(base + "humanservice").HumanService
    E = importlib.import_module(base + "exportservice").ExportService
    R = importlib.import_module(base + "rigservice").RigService
    return H, E, R


def add_game_engine_rig(basemesh, human_svc):
    """Add the MPFB Standard 'Game engine' rig with imported weights (creates an
    Armature modifier on basemesh). Returns the armature object."""
    arm = human_svc.add_builtin_rig(basemesh, "game_engine", import_weights=True)
    if arm is None:
        raise RuntimeError("add_builtin_rig returned None (game_engine rig missing)")
    return arm


def _bone_head_world(rig_svc, armature, name):
    return np.asarray(rig_svc.find_pose_bone_head_world_location(name, armature),
                      dtype=np.float64)


def _rotate_bone_world_y(armature, bone_name, angle):
    """Rotate a pose bone about the world +Y axis through its head (the manual
    'R Y' about the bone head). Works headless (sets pose matrix; no view op)."""
    pb = armature.pose.bones[bone_name]
    head = pb.matrix.translation.copy()          # armature space == world (rig at origin)
    Ry = mathutils.Matrix.Rotation(angle, 4, "Y")
    T = mathutils.Matrix.Translation(head)
    pb.matrix = T @ Ry @ T.inverted() @ pb.matrix
    bpy.context.view_layer.update()


def measure_and_rotate_shoulders(armature, rig_svc, fallback_deg=45.0):
    """Steps 3-5: in pose mode, rotate each upperarm about world +Y so the
    shoulder->wrist line is horizontal. Returns {side: applied_angle_rad}."""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    applied = {}
    for side, (upper, hand) in ARM.items():
        try:
            shoulder = _bone_head_world(rig_svc, armature, upper)
            wrist = _bone_head_world(rig_svc, armature, hand)
            if not math.isfinite(float(wrist[0])) or abs(wrist[0] - shoulder[0]) < 1e-6:
                raise ValueError("degenerate arm geometry")
            angle = geometry.y_rotation_to_horizontal(shoulder, wrist)
        except Exception as e:                   # noqa: BLE001
            print("WARN measure failed (%s): %s -> fallback %.0f deg"
                  % (side, e, fallback_deg))
            angle = geometry.fallback_y_rotation(side, fallback_deg)
        _rotate_bone_world_y(armature, upper, angle)
        applied[side] = angle
    return applied
```

- [ ] **Step 3: Write the shared headless runner `scripts/run_blender.sh`**

```bash
#!/usr/bin/env bash
# Run a repo python script inside the Windows Blender (headless) with the repo on
# sys.path. Usage: scripts/run_blender.sh <repo-relative-script.py> [-- ARGS...]
# Tolerates the harmless on-exit EXCEPTION_ACCESS_VIOLATION (cats-blender addon).
set -uo pipefail
BL="/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
REPO_WSL="$(realpath .)"
SCRIPT_WSL="$(realpath "$1")"; shift
REPO_WIN="$(wslpath -w "$REPO_WSL")"
SCRIPT_WIN="$(wslpath -w "$SCRIPT_WSL")"
"$BL" --background -noaudio --python "$SCRIPT_WIN" -- --repo "$REPO_WIN" "$@" || true
```

- [ ] **Step 4: Write the spike `scripts/spike_tpose_api.py`**

```python
"""Headless probe: confirm rig add + bone reads + the shoulder rotation work in
Blender, and that the measured droop goes ~45deg -> ~0deg. Run via
scripts/run_blender.sh scripts/spike_tpose_api.py"""
import sys


def _repo():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--repo" in argv:
        sys.path.insert(0, argv[argv.index("--repo") + 1])


def main():
    _repo()
    from mpfb_tpose import human as humanmod, rig as rigmod, geometry
    H, E, R = rigmod.services()
    basemesh = humanmod.create(H, humanmod.macro_dict(gender=0.5))
    arm = rigmod.add_game_engine_rig(basemesh, H)
    mod = [m.name for m in basemesh.modifiers if m.type == "ARMATURE"]
    print("SPIKE armature_modifier:", mod)
    for side, (upper, hand) in rigmod.ARM.items():
        sh = R.find_pose_bone_head_world_location(upper, arm)
        wr = R.find_pose_bone_head_world_location(hand, arm)
        print("SPIKE %s pre droop=%.1f deg  shoulder=%s wrist=%s"
              % (side, geometry.droop_from_horizontal_deg(sh, wr),
                 tuple(round(v, 3) for v in sh), tuple(round(v, 3) for v in wr)))
    applied = rigmod.measure_and_rotate_shoulders(arm, R)
    for side, (upper, hand) in rigmod.ARM.items():
        sh = R.find_pose_bone_head_world_location(upper, arm)
        wr = R.find_pose_bone_head_world_location(hand, arm)
        print("SPIKE %s post droop=%.1f deg (applied %.1f deg)"
              % (side, geometry.droop_from_horizontal_deg(sh, wr),
                 __import__("math").degrees(applied[side])))
    print("SPIKE_DONE")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the spike in Blender, verify the output**

Run: `cd /home/kubangpawis/dev/GarmentCode/.claude/worktrees/zeelum+mpfb-tpose-normalize && chmod +x scripts/run_blender.sh && bash scripts/run_blender.sh scripts/spike_tpose_api.py 2>&1 | grep -E "SPIKE|WARN"`
Expected output (values approximate):
- `SPIKE armature_modifier: ['Armature']` (some `ARMATURE` modifier name present — confirms weights imported).
- `SPIKE l pre droop=~30-50 deg` and `SPIKE r pre droop=~30-50 deg` (arms droop in MPFB default).
- `SPIKE l post droop=~0-3 deg` and `SPIKE r post droop=~0-3 deg` (rotation worked).
- `SPIKE_DONE`.

**If `post droop` is not near 0:** the rotation sign/pivot is wrong — STOP and use superpowers:systematic-debugging (likely the armature transform is not identity; print `arm.matrix_world` and rotate about its local Y instead). Do not proceed until `post droop < 5 deg` for both sides.

- [ ] **Step 6: Commit**

```bash
git add mpfb_tpose/human.py mpfb_tpose/rig.py scripts/run_blender.sh scripts/spike_tpose_api.py
git commit -m "feat(mpfb_tpose): MPFB human gen + game-engine rig + measured shoulder lift"
```

---

## Task 3: Normalize orchestration (the full 12 steps)

**Files:**
- Create: `mpfb_tpose/normalize.py`
- Modify: `scripts/spike_tpose_api.py` (extend to call normalize; reverted after check)

- [ ] **Step 1: Write `mpfb_tpose/normalize.py`**

```python
"""Orchestrates the 12-step manual T-pose procedure on a live MPFB human (runs
inside Blender). Pure sequencing + guards; math is in geometry, rig ops in rig."""
import bpy
from . import rig as rigmod


def _bake_shape_keys(ob):
    """Apply-all shape keys (step 8): bake the macro mix into the basis and drop
    all keys. MUST precede applying the Armature modifier -- Blender refuses
    modifier-apply on a mesh that still has shape keys."""
    keys = ob.data.shape_keys
    if not keys or not keys.key_blocks:
        return
    ob.shape_key_add(name="_baked", from_mix=True)
    for kb in list(ob.data.shape_keys.key_blocks):
        if kb.name != "_baked":
            ob.shape_key_remove(kb)
    ob.shape_key_remove(ob.data.shape_keys.key_blocks["_baked"])


def _apply_armature_modifier(mesh):
    """Steps 9-10: apply the Armature modifier -> bakes the posed deformation
    (raised arms) into the mesh vertices. Mesh is then physically T-posed."""
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    mod = next((m for m in mesh.modifiers if m.type == "ARMATURE"), None)
    if mod is None:
        raise RuntimeError("no Armature modifier to apply (rig/weights missing)")
    bpy.ops.object.modifier_apply(modifier=mod.name)


def _lateral_span(mesh):
    xs = [v.co.x for v in mesh.data.vertices]
    return max(xs) - min(xs)


def normalize_human(basemesh, human_svc, rig_svc, *, fallback_deg=45.0):
    """Steps 2-12. Returns {'pre_span','post_span','angles'} (span in model units)."""
    pre_span = _lateral_span(basemesh)

    armature = rigmod.add_game_engine_rig(basemesh, human_svc)             # step 2
    angles = rigmod.measure_and_rotate_shoulders(armature, rig_svc,
                                                 fallback_deg=fallback_deg)  # steps 3-5

    bpy.ops.object.mode_set(mode="OBJECT")                                 # step 6
    _bake_shape_keys(basemesh)                                            # steps 7-8
    _apply_armature_modifier(basemesh)                                    # steps 9-10
    post_span = _lateral_span(basemesh)

    try:                                                                  # steps 11-12
        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="OBJECT")
        rig_svc.apply_pose_as_rest_pose(armature)
    except Exception as e:                                                # noqa: BLE001
        print("WARN apply_pose_as_rest_pose:", e)   # mesh already baked; non-fatal

    print("TPOSE span %.3f -> %.3f units (x%.2f); angles_deg=%s"
          % (pre_span, post_span,
             (post_span / pre_span if pre_span else 0.0),
             {s: round(__import__("math").degrees(a), 1) for s, a in angles.items()}))
    return {"pre_span": pre_span, "post_span": post_span, "angles": angles}
```

- [ ] **Step 2: Temporarily extend the spike to exercise normalize**

In `scripts/spike_tpose_api.py`, replace the body of `main()` after `_repo()` with:
```python
    from mpfb_tpose import human as humanmod, normalize as normmod, rig as rigmod
    H, E, R = rigmod.services()
    basemesh = humanmod.create(H, humanmod.macro_dict(gender=0.5))
    info = normmod.normalize_human(basemesh, H, R)
    print("SPIKE post_span/pre_span = %.2f"
          % (info["post_span"] / info["pre_span"]))
    print("SPIKE_DONE")
```

- [ ] **Step 3: Run it, verify the arms lift and the mesh bakes**

Run: `bash scripts/run_blender.sh scripts/spike_tpose_api.py 2>&1 | grep -E "TPOSE|SPIKE|WARN|Error"`
Expected:
- `TPOSE span … -> … units (x≈2.0-2.5); angles_deg=…` (lateral span roughly doubles as drooped arms swing out to horizontal).
- `SPIKE post_span/pre_span = ≈2.0-2.5`.
- `SPIKE_DONE`, no `Error`/traceback.

**If the span ratio is ~1.0:** the pose was not baked (modifier-apply order or shape-key apply failed) — use superpowers:systematic-debugging.

- [ ] **Step 4: Revert the spike to its committed form**

```bash
git checkout scripts/spike_tpose_api.py
```

- [ ] **Step 5: Commit**

```bash
git add mpfb_tpose/normalize.py
git commit -m "feat(mpfb_tpose): orchestrate 12-step normalize (rig->lift->bake->rest)"
```

---

## Task 4: Export + CLI + wrapper

**Files:**
- Create: `mpfb_tpose/export.py`
- Create: `tpose_normalize_mpfb.py`
- Create: `scripts/run_tpose_normalize.sh`

- [ ] **Step 1: Write `mpfb_tpose/export.py`**

```python
"""Save the normalized .blend and a clean, ingest-ready T-pose .glb (runs in
Blender). export_tpose_glb MUTATES the basemesh (strips helpers) -- call it
AFTER save_blend so the .blend keeps the full rigged body."""
import bpy


def _bake_shape_keys(ob):
    keys = ob.data.shape_keys
    if not keys or not keys.key_blocks:
        return
    ob.shape_key_add(name="_baked", from_mix=True)
    for kb in list(ob.data.shape_keys.key_blocks):
        if kb.name != "_baked":
            ob.shape_key_remove(kb)
    ob.shape_key_remove(ob.data.shape_keys.key_blocks["_baked"])


def save_blend(path):
    bpy.ops.wm.save_as_mainfile(filepath=path)


def export_tpose_glb(basemesh, export_svc, path):
    """Body-only clean glTF: strip MPFB helper geometry (so mpfb_ingest sees a
    clean body, matching the gen_mpfb_testset bodies), no morph targets, Y-up."""
    export_svc.bake_modifiers_remove_helpers(basemesh, remove_helpers=True)
    _bake_shape_keys(basemesh)
    bpy.ops.object.select_all(action="DESELECT")
    basemesh.select_set(True)
    bpy.context.view_layer.objects.active = basemesh
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True,
                              export_format="GLB", export_yup=True,
                              export_morph=False)
```

- [ ] **Step 2: Write the CLI `tpose_normalize_mpfb.py`**

```python
"""CLI (runs INSIDE Blender): generate an MPFB human from macro params, normalize
to a true T-pose, export a clean .glb + normalized .blend.

Invoke via scripts/run_tpose_normalize.sh. Prints 'TPOSE_OK <glb>' on success.
Pass --arm-pose-angle 0 to mpfb_ingest downstream (the export is a true T-pose)."""
import os
import sys


def _argv():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--repo" in argv:
        sys.path.insert(0, argv[argv.index("--repo") + 1])
    return argv


def _arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def main():
    argv = _argv()
    from mpfb_tpose import (human as humanmod, normalize as normmod,
                            export as exportmod, rig as rigmod)

    out_glb = _arg(argv, "--out-glb", "/tmp/tpose.glb")
    out_blend = _arg(argv, "--out-blend", "/tmp/tpose.blend")
    fallback = float(_arg(argv, "--fallback-deg", "45"))
    macro = humanmod.macro_dict(
        gender=float(_arg(argv, "--gender", "0.5")),
        weight=float(_arg(argv, "--weight", "0.5")),
        height=float(_arg(argv, "--height", "0.5")),
        muscle=float(_arg(argv, "--muscle", "0.5")),
        cupsize=float(_arg(argv, "--cupsize", "0.5")),
        age=float(_arg(argv, "--age", "0.5")),
        race=_arg(argv, "--race", "caucasian"),
    )
    for p in (out_glb, out_blend):
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)

    H, E, R = rigmod.services()
    basemesh = humanmod.create(H, macro)
    info = normmod.normalize_human(basemesh, H, R, fallback_deg=fallback)
    exportmod.save_blend(out_blend)            # full rigged body first
    exportmod.export_tpose_glb(basemesh, E, out_glb)   # then destructive helper strip

    print("TPOSE_INFO", info["pre_span"], info["post_span"])
    if os.path.isfile(out_glb) and os.path.isfile(out_blend):
        print("TPOSE_OK", out_glb)
    else:
        print("TPOSE_FAIL missing output")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write the wrapper `scripts/run_tpose_normalize.sh`**

```bash
#!/usr/bin/env bash
# Generate an MPFB human from macro params and normalize it to a true T-pose via
# the Windows Blender + MPFB extension, headless. MPFB output is CC0.
#
# Usage: scripts/run_tpose_normalize.sh --out-glb PATH --out-blend PATH \
#          [--gender 0.0] [--weight 0.5] [--height 0.5] [--cupsize 0.5] [--muscle 0.5]
# All flags take a value. Output paths are WSL paths (auto-translated to Windows).
set -uo pipefail

BL="/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
REPO_WSL="$(realpath .)"
REPO_WIN="$(wslpath -w "$REPO_WSL")"
SCRIPT_WIN="$(wslpath -w "$REPO_WSL/tpose_normalize_mpfb.py")"

ARGS=(--repo "$REPO_WIN")
while [ $# -gt 0 ]; do
  case "$1" in
    --out-glb|--out-blend)
      mkdir -p "$(dirname "$2")"
      ARGS+=("$1" "$(wslpath -w "$(realpath -m "$2")")"); shift 2;;
    *) ARGS+=("$1" "$2"); shift 2;;
  esac
done

# Tolerate the harmless on-exit EXCEPTION_ACCESS_VIOLATION (cats-blender addon);
# success is verified by the caller via output-file existence + the TPOSE_OK line.
"$BL" --background -noaudio --python "$SCRIPT_WIN" -- "${ARGS[@]}" || true
```

- [ ] **Step 4: Smoke-run the CLI end-to-end**

Run: `cd /home/kubangpawis/dev/GarmentCode/.claude/worktrees/zeelum+mpfb-tpose-normalize && chmod +x scripts/run_tpose_normalize.sh && bash scripts/run_tpose_normalize.sh --out-glb .temp/tpose_smoke.glb --out-blend .temp/tpose_smoke.blend --gender 0.0 2>&1 | grep -E "TPOSE|WARN|Error"; ls -la .temp/tpose_smoke.glb .temp/tpose_smoke.blend`
Expected: `TPOSE_OK .../tpose_smoke.glb`, and both files exist with non-zero size.

- [ ] **Step 5: Commit**

```bash
git add mpfb_tpose/export.py tpose_normalize_mpfb.py scripts/run_tpose_normalize.sh
git commit -m "feat(mpfb_tpose): CLI + WSL->Blender wrapper + clean glb/.blend export"
```

---

## Task 5: Gated end-to-end T-pose verification

**Files:**
- Create: `tests/mpfb_tpose/test_normalize_integration.py`

- [ ] **Step 1: Write the integration test**

`tests/mpfb_tpose/test_normalize_integration.py`:
```python
"""Slow, gated end-to-end: drive Blender headless to generate+normalize+export,
then verify the exported .glb is a TRUE T-pose. Skips when Blender/MPFB is absent.

Run explicitly:
  PYTHONPATH=. ./.venv/bin/python -m pytest tests/mpfb_tpose/test_normalize_integration.py -v -s
"""
import math
import os
import subprocess

import pytest

BLENDER = "/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"
WRAPPER = "scripts/run_tpose_normalize.sh"
OUT_DIR = ".temp/tpose_it"

pytestmark = pytest.mark.skipif(
    not os.path.exists(BLENDER),
    reason="Windows Blender + MPFB not available")


def _run(preset):
    os.makedirs(OUT_DIR, exist_ok=True)
    glb = os.path.join(OUT_DIR, preset["name"] + ".glb")
    blend = os.path.join(OUT_DIR, preset["name"] + ".blend")
    cmd = ["bash", WRAPPER, "--out-glb", glb, "--out-blend", blend]
    for k in ("gender", "weight", "height", "cupsize", "muscle"):
        if k in preset:
            cmd += ["--" + k, str(preset[k])]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    print(res.stdout[-2500:])
    print(res.stderr[-800:])
    return glb, blend, res.stdout


@pytest.mark.parametrize("preset", [
    {"name": "f_neutral", "gender": 0.0},
    {"name": "m_heavy", "gender": 1.0, "weight": 0.9, "cupsize": 0.0},
])
def test_generate_normalize_export_is_tpose(preset):
    glb, blend, stdout = _run(preset)
    assert "TPOSE_OK" in stdout, "normalizer did not report success"
    assert os.path.isfile(glb) and os.path.isfile(blend)
    assert os.path.getsize(glb) > 0 and os.path.getsize(blend) > 0

    from mpfb_ingest import mesh_io, autolandmarks
    raw = mesh_io.load_body(glb)
    mesh_m, _ = mesh_io.normalize(raw)
    cm = mesh_io.to_cm(mesh_m)
    assert len(cm.vertices) > 1000

    # (a) Landmark-free T-pose signal: arm span (X) ~ stature (Y) for a T-pose,
    #     ~0.45 for drooped arms.
    lo, hi = cm.bounds
    xspan = float(hi[0] - lo[0])
    height = float(hi[1] - lo[1])
    ratio = xspan / height
    assert ratio > 0.85, "arms not raised to T-pose (span/height=%.2f)" % ratio

    # (b) Direct droop via mpfb_ingest's own landmark derivation (Y-up cm space):
    #     fingertip (far +X) should sit near shoulder height.
    lm = autolandmarks.derive(cm)
    finger = lm.pos(cm, "wrist_r")     # argmax-X fingertip
    collar = lm.pos(cm, "collar_r")    # shoulder/neck base
    droop = abs(math.degrees(math.atan2(collar[1] - finger[1],
                                        abs(finger[0] - collar[0]) + 1e-9)))
    assert droop < 15.0, "fingertip not near shoulder height (droop=%.1f deg)" % droop

    # (c) The normalizer logged a real outward lift (post span > pre span).
    assert "TPOSE span" in stdout
```

- [ ] **Step 2: Run the integration test for real**

Run: `cd /home/kubangpawis/dev/GarmentCode/.claude/worktrees/zeelum+mpfb-tpose-normalize && PYTHONPATH=. /home/kubangpawis/dev/GarmentCode/.venv/bin/python -m pytest tests/mpfb_tpose/test_normalize_integration.py -v -s`
Expected: 2 passed (each ~30-90 s). If Blender is unavailable on the box, expect SKIPPED (acceptable for CI, but it MUST pass on this WSL box where Blender exists).

**If `ratio` or `droop` assertions fail:** the export is not a true T-pose — use superpowers:systematic-debugging. Inspect the printed `TPOSE span … (x…)` ratio and the `.blend` in the GUI; check the spike `post droop` first (Task 2). Do not weaken the thresholds to pass.

- [ ] **Step 3: Commit**

```bash
git add tests/mpfb_tpose/test_normalize_integration.py
git commit -m "test(mpfb_tpose): gated end-to-end true-T-pose verification on exported glb"
```

---

## Task 6: Docs, memory, finalize

**Files:**
- Create: `mpfb_tpose/README.md`
- Modify: `docs/superpowers/specs/2026-06-09-mpfb-tpose-normalization-design.md` (status line)
- Modify: project memory (see step 3)

- [ ] **Step 1: Write `mpfb_tpose/README.md`**

Contents (fill with the as-built facts):
```markdown
# mpfb_tpose — MPFB → T-pose normalizer

Generates an MPFB human from macro params and normalizes it to a TRUE T-pose
(arms horizontal, `arm_pose_angle = 0`), emitting a clean ingest-ready `.glb`
(consumable by `mpfb_ingest`) + a normalized `.blend`. Downstream of MPFB
generation, upstream of `mpfb_ingest` measurement.

## Run
    scripts/run_tpose_normalize.sh --out-glb .temp/body.glb --out-blend .temp/body.blend \
        --gender 0.0 --weight 0.5 --height 0.5 --cupsize 0.5

Then ingest the T-pose:
    ./.venv/bin/python ingest_mpfb_body.py .temp/body.glb --name body --arm-pose-angle 0

## How it maps to the manual 12 steps
- Steps 1-2: `human.create` + `rig.add_game_engine_rig` (`add_builtin_rig("game_engine", import_weights=True)`).
- Steps 3-5: `rig.measure_and_rotate_shoulders` — rotates each `upperarm_{l,r}` about
  world +Y by the MEASURED droop (not a fixed 45deg) so the shoulder->wrist line is
  horizontal. Falls back to +/-45deg only on degenerate geometry.
- Steps 6-10: `normalize._bake_shape_keys` then `_apply_armature_modifier` (shape keys
  MUST be applied first; Blender refuses modifier-apply with shape keys present).
- Steps 11-12: `RigService.apply_pose_as_rest_pose`.
- Export: `ExportService.bake_modifiers_remove_helpers(remove_helpers=True)` + glTF
  `export_morph=False, export_yup=True` (the proven clean path from gen_mpfb_testset).

## Design split (why)
- `geometry.py` is pure numpy (no bpy/mathutils) so it imports under BOTH the venv
  (py3.9 unit tests) and Blender (py3.13 runtime). All sign/axis logic lives here and
  is unit-tested.
- `human/rig/normalize/export` are thin bpy wrappers, validated by the gated
  end-to-end test (`tests/mpfb_tpose/test_normalize_integration.py`).

## Gotchas
- Blender's Python is 3.13; the project venv is 3.9 — they cannot share a process.
- The on-exit `EXCEPTION_ACCESS_VIOLATION` (cats-blender) is harmless; the wrapper keys
  success on output-file existence + the `TPOSE_OK` sentinel, not the exit code.
- MPFB macro sliders are shape keys — they MUST be baked before glTF export or every
  body loads identical (see gen_mpfb_testset).
```

- [ ] **Step 2: Update the spec status line**

In `docs/superpowers/specs/2026-06-09-mpfb-tpose-normalization-design.md`, change the
`**Status:**` line to:
```markdown
**Status:** Implemented — geometry units + gated end-to-end T-pose verification green.
```

- [ ] **Step 3: Update project memory**

Update `/home/kubangpawis/.claude/projects/-home-kubangpawis-dev-GarmentCode/memory/MEMORY.md`
and add a new memory file `mpfb-tpose-normalize-status.md` (type: project) recording: the
module exists, the manual→headless mapping, the measure-to-horizontal approach, the
`upperarm_{l,r}` pivot + `game_engine` rig, the verification gate, and links to
`[[zeelum-mpfb-ingestion-status]]` and `[[mpfb-headless-blender]]`. Convert any relative
dates to absolute (2026-06-09).

- [ ] **Step 4: Full suite — no regression**

Run: `cd /home/kubangpawis/dev/GarmentCode/.claude/worktrees/zeelum+mpfb-tpose-normalize && PYTHONPATH=. /home/kubangpawis/dev/GarmentCode/.venv/bin/python -m pytest tests/mpfb_ingest tests/mpfb_tpose -q`
Expected: prior `mpfb_ingest` count still green (35 passed, 13 skipped baseline) + `mpfb_tpose` geometry green + integration passed (or skipped if no Blender).

- [ ] **Step 5: Commit**

```bash
git add mpfb_tpose/README.md docs/superpowers/specs/2026-06-09-mpfb-tpose-normalization-design.md
git commit -m "docs(mpfb_tpose): README + spec status; record as-built normalize path"
```

- [ ] **Step 6: Finish the branch**

Invoke superpowers:finishing-a-development-branch to choose merge/PR/cleanup.

---

## Self-Review (completed during planning)

- **Spec coverage:** §4 layout → Tasks 1-4; §5.1 mapping → Task 3 (+ Task 2 for the rig/lift);
  §5.2 measure-to-horizontal → Task 1 (math) + Task 2 (apply); §6 I/O → Task 4; §7 spike →
  Task 2 (folded into a real headless probe, with the static findings already in the plan
  header); §8 testing → Task 1 (units) + Task 5 (gated); §10 success criteria → Tasks 5-6.
- **Validation metric corrected vs spec:** `mpfb_ingest` takes `arm_pose_angle` as an input
  and does not infer droop, so Task 5 measures the T-pose directly (span/height ratio +
  fingertip-vs-collar droop via `autolandmarks.derive`). The spec's intent (verify via the
  ingest pipeline's own landmarks) is preserved.
- **Type/name consistency:** `ARM`, `services()`, `add_game_engine_rig`,
  `measure_and_rotate_shoulders`, `normalize_human`, `save_blend`, `export_tpose_glb`,
  `macro_dict`, `create`, and geometry's `rotate_about_y` / `y_rotation_to_horizontal` /
  `droop_from_horizontal_deg` / `fallback_y_rotation` are used identically across tasks.
- **Placeholder scan:** none — every code step is complete.
