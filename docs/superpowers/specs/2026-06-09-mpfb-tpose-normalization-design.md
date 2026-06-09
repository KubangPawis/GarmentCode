# MPFB T-Pose Normalization — Design Spec

**Date:** 2026-06-09
**Branch:** `worktree-zeelum+mpfb-tpose-normalize` (worktree off `main` @ f81f1ee)
**Status:** Implemented — geometry units (22) + gated end-to-end T-pose verification (2 presets) green; full suite 59 passed / 13 skipped, no `mpfb_ingest` regression. Measured: MPFB default arm droop ≈43° → 0° after normalize.

## 1. Problem & Context

A freshly-generated MPFB (MakeHuman) human is created in MPFB's default stance — arms
drooped ~45° below horizontal. Downstream garment fitting (`mpfb_ingest/` → GarmentCode
body measurements) assumes a **T-pose** avatar: arms straight out, horizontal
(`arm_pose_angle = 0`, i.e. arm droop from horizontal = 0).

Today T-posing is a manual 12-step Blender procedure. This project automates it as a
**steady, reusable downstream module**: any upstream MPFB-generation process hands off
macro parameters, and this module emits a normalized T-posed avatar.

### The manual procedure being automated
1. Generate the desired MPFB human from parameters.
2. Add a rig: *Game engine* preset → check *Import Weights* → *Add Standard Rig*.
3. Enter Pose Mode.
4. Select the shoulder bone.
5. Rotate shoulders: **Left** `R Y -45°`, **Right** `R Y +45°` (about global Y).
6. Object Mode.
7. Select the human mesh.
8. Object Data Properties → Shape Keys → *Apply All*.
9. Modifier Properties tab.
10. On the Armature modifier → *Apply*.
11. Pose Mode.
12. Pose → Apply → *Apply Pose as Rest Pose*.

## 2. Goals / Non-Goals

**Goals**
- Automate generate → T-pose → export, headless, deterministic, no GUI.
- Faithful to the manual procedure, but **robust**: rotate shoulders by the *measured*
  droop (→ true horizontal) rather than a hardcoded 45°.
- Emit a clean **T-posed `.glb`** (helpers removed, ingest-ready) + a normalized **`.blend`**.
- Isolate the correctness-critical math from Blender so it is fast-unit-tested.
- Validate true T-pose by feeding the output through existing `mpfb_ingest` and asserting
  `arm_pose_angle ≈ 0`.

**Non-Goals**
- Not changing `mpfb_ingest/` (consumer, must stay green).
- Not inferring macro parameters (those are inputs).
- Not handling arbitrary external rigs — only the MPFB **Standard / Game engine** rig.
- Not producing a fully re-bound rigged character; after the bake the mesh is a static
  T-posed asset with a T-pose-rest skeleton (unbound is acceptable).

## 3. Constraints & Environment

(Established facts; see project memory `mpfb-headless-blender`, `zeelum-mpfb-ingestion-status`.)

- **Blender** `5.1.2` at `/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe`,
  run from WSL: `"$BL" --background -noaudio --python <win-path>` (`wslpath -w` for paths).
- **Blender Python is 3.13**; the project **`.venv` is Python 3.9** at the main checkout
  (`/home/kubangpawis/dev/GarmentCode/.venv`). They **cannot share a process** → two-process
  design. Code shared across the boundary must import under both → **pure stdlib + numpy
  only** (numpy ships in both Blender and the venv); no `mathutils` in shared code.
- **MPFB 2.0.15** enabled via extension namespace:
  `bpy.ops.preferences.addon_enable(module="bl_ext.blender_org.mpfb")`.
- **MPFB API confirmed** by source inspection:
  - Generate: `HumanService.create_human(macro_detail_dict=…, feet_on_ground=True)`.
  - Add rig: `bpy.ops.mpfb.add_standard_rig()`, driven by scene props
    `ADR_standard_rig="game_engine"` + `ADR_import_weights=True`
    (the *Game engine* preset = `data/rigs/standard/rig.game_engine.json`; importing
    weights creates vertex groups + an Armature modifier on the basemesh).
  - Apply Pose as Rest Pose: MPFB pose op exists
    (`ui/operations/poseops/operators/apply_pose.py`) plus `RigService`.
  - Clean export precedent (`scripts/gen_mpfb_testset.py`): bake macro shape keys into the
    basis and pass `export_morph=False`, else MPFB macros leak as glTF morph targets and
    every body loads identical.
- **Known harmless noise:** `cats-blender-plugin` raises `ValueError: the return value must
  be None` on background load, and Blender prints `EXCEPTION_ACCESS_VIOLATION` *on exit* —
  both are noise; files are written before exit. The wrapper must not read these as failure.

## 4. Architecture

Mirror the proven `mpfb_ingest` + `gen_mpfb_testset` split. **The correctness risk (measuring
droop, per-side sign/axis) lives in pure numpy and is fast-unit-tested; bpy code stays thin
and is validated end-to-end.**

```
mpfb_tpose/
  __init__.py
  geometry.py     # PURE numpy. Droop angle, signed Y-correction, horizontality check.
                  #   No bpy / no mathutils. Imported by BOTH 3.9 tests and 3.13 Blender.
  human.py        # bpy: macro-dict -> HumanService.create_human(...). Thin.
  rig.py          # bpy: add_standard_rig(game_engine, import_weights); resolve shoulder/
                  #   wrist bones; read bone positions; apply pose-bone rotation about world Y.
  normalize.py    # bpy: orchestrates the 12 steps; delegates ALL math to geometry.py.
  export.py       # bpy: clean glTF (.glb, helpers removed, export_morph=False) + .blend save.
  README.md
tpose_normalize_mpfb.py        # CLI entry, runs INSIDE Blender (like ingest_mpfb_body.py).
scripts/run_tpose_normalize.sh # blender.exe --background --python wrapper (like run_mpfb_gen.sh).
tests/mpfb_tpose/
  conftest.py
  test_geometry.py              # FAST, pure, .venv pytest. Synthetic vectors.
  test_normalize_integration.py # SLOW/gated. Shells to Blender -> ingests .glb ->
                                #   asserts arm_pose_angle ≈ 0. Skips if Blender absent.
```

**Module responsibilities & interfaces**
- `geometry.py` (pure): given shoulder-pivot & wrist 3D positions, return the signed rotation
  about world **+Y** that brings the arm to horizontal, the current droop angle, and a
  horizontality predicate. Inputs/outputs are plain numpy arrays / floats. *Depends on:*
  numpy only.
- `human.py`: `create(macro_detail_dict) -> human_objects`. Wraps MPFB generation. *Depends
  on:* bpf/MPFB. Reuse `gen_mpfb_testset` macro schema; extract a shared helper only if
  trivial, else a thin local wrapper (avoid premature refactor).
- `rig.py`: `add_standard_rig(...)`, `resolve_arm_bones(armature) -> {side: (pivot, wrist)}`,
  `rotate_shoulder_to_horizontal(pose_bone, angle)`. Converts world-Y correction (from
  `geometry`) into the pose bone's local space via `mathutils`. *Depends on:* bpy + geometry.
- `normalize.py`: `normalize_human(human, *, fallback_deg=45.0) -> human`. The orchestrator;
  pure sequencing + guards, no math. *Depends on:* rig, geometry, bpy.
- `export.py`: `export_tpose(human, glb_path, blend_path)`. *Depends on:* bpy.

## 5. Normalize Algorithm

### 5.1 Manual → headless mapping
| # | Manual step | Headless operation |
|---|---|---|
| 1 | Generate human | `human.create(macro_dict)` → `HumanService.create_human(..., feet_on_ground=True)` |
| 2 | Game engine ▸ Import Weights ▸ Add Standard Rig | set `ADR_standard_rig="game_engine"`, `ADR_import_weights=True`; `bpy.ops.mpfb.add_standard_rig()` |
| 3 | Pose Mode | `bpy.ops.object.mode_set(mode='POSE')` on the armature |
| 4–5 | Select & rotate shoulders | **measure-to-horizontal** (§5.2) per side; fallback ±`fallback_deg` |
| 6–7 | Object Mode, select mesh | `mode_set('OBJECT')`; make basemesh active |
| 8 | Apply All shape keys | `bpy.ops.object.shape_key_remove(all=True, apply_mix=True)` — **must precede** modifier apply |
| 9–10 | Apply Armature modifier | `bpy.ops.object.modifier_apply(modifier=<armature mod name>)` → bakes the posed deformation into mesh verts (mesh now physically T-pose) |
| 11–12 | Apply Pose as Rest Pose | MPFB pose op / `RigService` → skeleton rest = T-pose (keeps `.blend` consistent) |
| — | Clean export | remove helper geometry + glTF `export_morph=False` (`export.py`) |

**Ordering constraint (encoded):** shape keys MUST be applied before the armature modifier —
Blender refuses `modifier_apply` on a mesh that still has shape keys. This is exactly why the
manual order is step 8 before step 10.

### 5.2 Measure-to-horizontal (the robust rotation)
Goal: replace the hardcoded ±45° with the measured droop so any MPFB default stance lands at
true horizontal.

1. After the rig is added, resolve per side the **shoulder pivot bone** (the bone the manual
   selects/rotates) and the **distal arm bone** (wrist/hand). Names resolved from
   `rig.game_engine.json` in the spike (§7); selection validated geometrically (rotating the
   pivot about Y must elevate the distal end).
2. Read positions in **armature space**: `p = pivot_head`, `w = wrist/hand tip`.
   Arm vector `v = w − p`.
3. The droop lives in the frontal plane (rotation axis = world **+Y**). `geometry.py` computes
   the signed angle that rotates `v` about +Y until its vertical (Z) component is zero —
   i.e. the arm tip is level with the pivot. **Sign is derived from `v` itself** (opposite for
   left/right because their X have opposite signs) — no hardcoded per-side sign.
4. `rig.py` converts that world-+Y rotation into the pose bone's local space (`mathutils`) and
   applies it; `bpy.context.view_layer.update()`.
5. **Fallback:** if the wrist bone is missing or `v`'s in-plane magnitude is ~0 (degenerate /
   NaN), rotate by fixed ±`fallback_deg` (sign from `sign(v_x)`), matching the manual exactly.
6. **In-Blender self-check (optional log):** re-read `v`, assert |droop| < tol; warn if not.

Because the arm is approximately straight in MPFB's default and a single shoulder rotation is
what the manual uses, leveling the endpoints ≈ making the arm horizontal — confirmed
downstream by the `arm_pose_angle` gate (§6).

## 6. I/O Contract & Data Flow

```
macro params ──> [Blender headless process] ──────────────> files            [.venv process / test]
                  human.create                                .glb (T-pose) ──> trimesh.load
                  rig.add_standard_rig                         .blend            mpfb_ingest.autolandmarks
                  normalize_human (measure-to-horizontal)                        compute arm_pose_angle ≈ 0 ?
                  export_tpose
```

- **CLI** `tpose_normalize_mpfb.py` (runs inside Blender): inputs = macro params (preset name
  or `--macro key=val …`, reusing the gen schema) + `--out-glb` / `--out-blend`; outputs =
  T-posed `.glb` (helpers removed, ingest-ready) + normalized `.blend`. Non-zero exit on
  failure; structured log lines for the wrapper to parse.
- **Shell wrapper** `scripts/run_tpose_normalize.sh`: resolves Blender path, `wslpath -w` for
  script/out paths, `--background -noaudio --python`, tolerates the harmless cats-blender /
  exit-noise (success determined by output-file existence + a sentinel log line, not exit code
  alone).
- **Library** `normalize.normalize_human(human) -> human`: callable inside any Blender session
  for future upstreams (composability).

### Error handling
- Missing MPFB / addon enable failure → explicit error, non-zero exit.
- `add_standard_rig` produced no armature / no Armature modifier → abort with diagnostic.
- Shape-key apply or modifier apply error → abort (do not silently export a non-T-posed mesh).
- Degenerate arm geometry → fallback rotation + warning (not fatal).
- Wrapper: absent output file ⇒ failure even if Blender exit code is 0 (guards the exit-noise).

## 7. Phase-0 Spike (first task, before TDD-proper)

One cheap Blender-headless run to confirm three unknowns; findings feed the plan. Nothing
downstream is blocked on guesses.
1. **Bone names** in `rig.game_engine.json`: exact shoulder-pivot and wrist/hand bone names
   per side, and confirm which the manual "shoulder bone" maps to.
2. **Property mechanism:** how `add_standard_rig` reads `ADR_*` props headless (set via
   `SceneConfigSet`/`ADD_RIG_PROPERTIES.set_value(...)` vs plain `scene` attribute).
3. **Apply-pose-as-rest** exact call (operator `bl_idname` vs `RigService` method) and that it
   runs headless.

## 8. Testing Strategy (TDD)

- **Red→green pure units first** (`test_geometry.py`, fast, `.venv`): this is where T-pose
  correctness is actually proven.
  - signed Y-correction for synthetic L/R arms drooped 45°, 30°, 10°; already-horizontal → ~0.
  - per-side sign correctness (left vs right) derived purely from the vector.
  - horizontality predicate at tolerance.
  - fallback trigger on degenerate / NaN input.
- **Gated integration** (`test_normalize_integration.py`, slow): pytest shells to Blender for
  generate → normalize → export on 1–2 macro presets, then loads the `.glb` with trimesh and:
  - runs `mpfb_ingest` autolandmarks → asserts `arm_pose_angle ≤ ~5°` (target ≈ 0) — **the
    money metric**;
  - asserts post-normalize bbox X-width > the pre-normalize X-width (arms moved outward) —
    `normalize_human` logs the lateral span before and after, and the CLI emits both so the
    test compares the same body against itself (no separate reference asset needed);
  - asserts vertex count within the expected ingest band and `.blend` written.
  - **Skips** (not fails) when Blender/MPFB is unavailable, matching the existing asset-gated
    `mpfb_ingest` stress tests.
- **No regression:** existing fast `mpfb_ingest` suite stays green (baseline: 35 passed,
  13 skipped).

## 9. Risks & Mitigations
| Risk | Mitigation |
|---|---|
| `add_standard_rig` behaves differently headless (UI-context assumptions) | Spike confirms; set scene props + ensure correct active/selected object & context override |
| Bone naming differs from assumption | Spike reads `rig.game_engine.json`; selection validated geometrically, not by name alone |
| Arm not perfectly straight ⇒ endpoint-level ≠ fully horizontal | Accept (matches manual single-rotation); validated by `arm_pose_angle` gate with tolerance |
| Helper geometry leaks into `.glb` and corrupts ingest | Reuse proven clean-export (remove helpers + `export_morph=False`) |
| Blender exit-noise misread as failure | Wrapper keys success on output-file existence + sentinel log line |
| Two Python versions | Shared `geometry.py` restricted to numpy + stdlib |

## 10. Success Criteria
- Pure geometry unit tests green in `.venv` (fast).
- Gated integration: generate→normalize→export yields `.glb` + `.blend`; ingesting the `.glb`
  gives `arm_pose_angle ≤ ~5°` and a wider bbox than the drooped reference, on ≥1 preset.
- CLI runnable headless via the wrapper; exit/lifecycle correct despite cats-blender noise.
- `mpfb_ingest` untouched and still green.
- `mpfb_tpose/README.md` documents the path, the API facts, and the gotchas.

## 11. Out of Scope / Future
- Re-bound rigged-character export; multi-rig support; finger/face posing.
- Batch test-set T-posing across the full MPFB property grid (a later stress suite, mirroring
  the existing cross-body stress work).
- Inferring `arm_pose_angle` from arbitrary meshes (stays a pose input upstream).
