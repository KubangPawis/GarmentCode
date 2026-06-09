# mpfb_tpose — MPFB → T-pose normalizer

Generates an MPFB (MakeHuman) human from macro parameters and normalizes it to a
**true T-pose** (arms horizontal, `arm_pose_angle = 0`), emitting a clean
ingest-ready `.glb` (consumable by [`mpfb_ingest`](../mpfb_ingest)) plus a
normalized `.blend`. It sits **downstream of MPFB generation** and **upstream of
`mpfb_ingest` measurement** — the steady module any MPFB-generation process hands
off to before body measurements are extracted.

## Run

```bash
scripts/run_tpose_normalize.sh --out-glb .temp/body.glb --out-blend .temp/body.blend \
    --gender 0.0 --weight 0.5 --height 0.5 --cupsize 0.5
```

All macro flags (`--gender --weight --height --muscle --cupsize --age --race`)
are optional and default to the MPFB neutral (0.5 / caucasian). The wrapper drives
the Windows Blender headless from WSL; on success it prints `TPOSE_OK <glb>`.

Then ingest the T-pose into GarmentCode body measurements:

```bash
./.venv/bin/python ingest_mpfb_body.py .temp/body.glb --name body --arm-pose-angle 0
```

(`--arm-pose-angle 0` because the export is a true T-pose — see `mpfb_ingest/README.md`.)

## How it maps to the manual 12-step procedure

| Manual step | Code |
|---|---|
| 1 generate human | `human.create` → `HumanService.create_human(..., feet_on_ground=True)` |
| 2 Game-engine ▸ Import Weights ▸ Add Standard Rig | `rig.add_game_engine_rig` → `HumanService.add_builtin_rig(basemesh, "game_engine", import_weights=True)` |
| 3–5 pose-mode rotate shoulders | `rig.measure_and_rotate_shoulders` — **measure-to-horizontal** (below) |
| 6 object mode; 7–8 Apply All shape keys | `normalize._bake_shape_keys` (`shape_key_add(from_mix=True)` then drop all keys) |
| 9–10 Apply Armature modifier | `normalize._apply_armature_modifier` → bakes the raised-arm pose into mesh verts |
| 11–12 Apply Pose as Rest Pose | `RigService.apply_pose_as_rest_pose(armature)` |
| (clean export) | `export.export_tpose_glb` → `ExportService.bake_modifiers_remove_helpers(remove_helpers=True)` + glTF `export_morph=False, export_yup=True` |

**Ordering constraint (encoded):** shape keys MUST be applied before the Armature
modifier — Blender refuses `modifier_apply` on a mesh with shape keys.

## Measure-to-horizontal (not a hardcoded 45°)

Rather than the manual's fixed ±45°, each `upperarm_{l,r}` bone (its head = the
shoulder joint) is rotated about world **+Y** by the *measured* droop so the
shoulder→wrist line lands horizontal. Measured reality: MPFB's default arm droop
is **≈43°, not 45°** — and the applied correction lands the droop at ~0°. The
per-side sign is derived from the geometry (no hardcoded left/right sign); a fixed
±45° is used only as a degenerate-geometry fallback. All of this lives in the pure
`geometry.py` and is unit-tested.

## Design split (why two modules of code)

Blender's bundled Python is **3.13**; the project venv is **3.9** — they cannot
share a process. So:

- **`geometry.py`** is pure numpy (no `bpy`, no `mathutils`) and imports under
  *both* interpreters. All sign/axis/rotation math lives here and is fast
  unit-tested in the venv (`tests/mpfb_tpose/test_geometry.py`).
- **`human.py` / `rig.py` / `normalize.py` / `export.py`** are thin `bpy` adapters
  that run *inside* Blender, validated end-to-end by the gated integration test.

## Files

```
mpfb_tpose/
  geometry.py   pure numpy: rotate_about_y, y_rotation_to_horizontal, droop_from_horizontal_deg, fallback_y_rotation
  human.py      macro_dict + create (MPFB human from macro params)
  rig.py        services(); add_game_engine_rig; measure_and_rotate_shoulders
  normalize.py  normalize_human (the 12-step orchestration)
  export.py     save_blend + export_tpose_glb (clean, helper-stripped, Y-up glTF)
tpose_normalize_mpfb.py        CLI (runs inside Blender)
scripts/run_tpose_normalize.sh WSL → Windows-Blender headless wrapper
scripts/run_blender.sh         generic "run a repo script in Blender" helper
scripts/spike_tpose_api.py     headless API probe (diagnostic)
tests/mpfb_tpose/
  test_geometry.py               fast, pure (venv)
  test_normalize_integration.py  slow, gated (skips if Blender absent)
```

## Verification

`tests/mpfb_tpose/test_normalize_integration.py` drives the whole pipeline in
Blender for two presets (neutral female, heavy male) and asserts the exported
`.glb` is a true T-pose, **using `mpfb_ingest`'s own loader/landmarks**:

- arm span (X) / stature > 0.70 (a T-pose ≈ 0.85; drooped ≈ 0.45);
- the hands (lateral extremes) sit at > 0.65 of stature, i.e. near shoulder height
  (drooped ≈ 0.45);
- `mpfb_ingest.measurements.compute_all(..., arm_pose_angle=0)` returns sane
  measurements — proving the output ingests downstream.

The test **skips** (does not fail) when the Windows Blender + MPFB is unavailable.

## Gotchas

- **Two Python versions** — keep `geometry.py` numpy/stdlib-only.
- **cats-blender exit noise** — an unrelated addon prints
  `EXCEPTION_ACCESS_VIOLATION` / `ValueError: the return value must be None` on
  Blender *exit*. It is harmless; the wrapper ends with `|| true` and success is
  keyed on the `TPOSE_OK` line + output files, not the exit code.
- **Shape keys must be baked before glTF export** (`export_morph=False`) — else
  MPFB macros leak as glTF morph targets and every body loads identical (the
  `gen_mpfb_testset` lesson).
- **`TPOSE_INFO` `pre_span` is the neutral pre-bake basis width** (macro shape
  keys aren't baked into the basis until step 8), so it reads the same across
  bodies; the *post* span and the absolute T-pose gates are the meaningful values.
- MPFB output and macro targets are **CC0**.
