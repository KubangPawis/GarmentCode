# mpfb_drape — Auto-fit + Auto-drape Garments onto Normalized MPFB Bodies

**Status:** Design approved (brainstorming). Pending plan.
**Date:** 2026-06-09
**Branch:** `worktree-feat+mpfb-drape`
**Depends on:** `mpfb_tpose` (DONE), `mpfb_ingest` (DONE), `pygarment` Warp sim (working in this env).

---

## 1. Goal

Close the last gap in the Zeelum pipeline: take a **normalized, true-T-pose MPFB body** (produced by `mpfb_tpose` → `mpfb_ingest`) plus a set of garment designs, and **programmatically fit + drape** each garment onto that body using **GarmentCode's native Warp cloth simulator** — no manual Blender steps.

Today there is no programmatic bridge from an ingested MPFB body to a draped garment. The only "drape onto a custom T-posed human" path is the manual Blender workflow in `docs/Draping_GarmentCode_onto_TPosed_Character.md`. `pattern_fitter.py` produces 2-D patterns only (`with_3d=False`). The native `run_sim` is wired for the bundled bodies + dataset generation. This feature adds the missing orchestration.

**MVP scope:** *many designs × one body* (dress one avatar in a wardrobe). The internal primitive is a single `(design, body)` drape; the CLI loops it over a design set.

---

## 2. Pipeline data flow (end-to-end)

```
mpfb_tpose   ->  tpose.glb        (Y-up, metres, single watertight mesh, true T-pose, arms horizontal)
mpfb_ingest  ->  avatar.yaml      (26 measurements, cm; arm_pose_angle = 0)   [default out: assets/bodies/]
                 avatar.obj       (metres, feet at Y=0, centred X/Z)          [--save-obj]
                              │
                              ▼   NEW: mpfb_drape
   for each design.yaml in the wardrobe:
     (fit)    BodyParameters(avatar.yaml) + design  -> MetaGarment -> pattern.assembly().serialize()
                                                     -> <spec_dir>/<design>_specification.json
     (stage)  ensure body obj + yaml in a bodies dir under <body_name>
              generate <body_name>_bodyseg.json  (topology-matched body segmentation)
     (mesh)   BoxMesh(spec) -> load() -> serialize(paths)  -> <design>_boxmesh.obj + _sim_segmentation.txt
     (drape)  run_sim(...)  collider = avatar.obj, body_seg = avatar_bodyseg.json
                            -> <design>_sim.glb / _sim.obj
     (verify) acceptance(stats + sim.obj)  -> PASS / FAIL + metrics
   -> per-design GarmentCode export folders  +  wardrobe_manifest.json
```

**Pose-alignment win.** The avatar is a *true* T-pose (`arm_pose_angle = 0`) and the pattern is generated with `arm_pose_angle = 0`, so the boxmesh sleeves are laid out horizontally and drape onto horizontal arms. Matching poses is the clean case. The manual Blender doc fought a *mismatch* (pre-folded 45° garment vs T-pose body); we avoid it by construction.

---

## 3. Verified facts grounding this design

These were confirmed by reading the code, not assumed:

| Fact | Source | Consequence |
|---|---|---|
| Single-garment drape recipe = `BoxMesh(spec) → load() → serialize(paths) → run_sim(...)` | `pygarment/meshgen/datasim_utils.py:289` (`template_simulation`) | **Reuse `template_simulation`** rather than re-implement. |
| `run_sim(cloth_name, props, paths)` records penetration + settle into `props['sim']['stats']` | `simulation.py:163,208,218,225` | Verify layer mostly **reads existing stats** (`body_collisions`, `self_collisions`, `static_equilibrium` fail). |
| Body collider resolved as `bodies_path/<body_name>.obj`; measurements `<body_name>.yaml`; both required | `sim_config.py:57,66` (`PathCofig`) | Staging = place avatar `.obj` + `.yaml` under a bodies dir, pass `body_name`. |
| Body vertices scaled by hard-coded `b_scale = 100.0` (m → cm) | `garment.py:39,102` | Avatar `.obj` must be **metres** (ingest `--save-obj` writes metres ✓). |
| `mean_all.obj` = 23752 verts, metres, feet at Y=0 | inspected | Confirms metres + feet-grounded frame; ingest output matches. |
| `body_seg = ggg_body_segmentation.json` loaded **unconditionally**, then used by `panel_assignment` (not behind a flag) | `garment.py:100,185` | A body segmentation is **mandatory**, not optional. |
| `ggg_body_segmentation.json` = `{body,left_arm,right_arm,left_leg,right_leg,face_internal}` → **vertex-index lists**, max index 23751 (bound to `mean_all` topology) | inspected | These indices are **invalid for any other topology** (MPFB ≈ 16k verts → wrong/out-of-range). Must generate a topology-matched seg. |
| `paths.body_seg` is a plain attribute set in `PathCofig.__init__` | `sim_config.py:68` | Override point: `paths.body_seg = <staged avatar_bodyseg.json>` after construction. |
| Default sim preset with attachment + collision filters | `assets/Sim_props/default_sim_props.yaml`, `datasim_utils.init_sim_props` | Start props from this preset. |

---

## 4. Module layout

```
mpfb_drape/
  __init__.py
  fit.py        # BodyParameters(yaml) + design dict -> MetaGarment -> serialize spec.json
                #   (reuses the assembly/serialize recipe from pattern_fitter._save_sample)
  bodyseg.py    # geometry-based body segmentation: {body,left_arm,right_arm,left_leg,
                #   right_leg,face_internal} -> vertex-index lists in the avatar's own topology
  body_stage.py # stage avatar .obj + .yaml into a bodies dir under <body_name>;
                #   write <body_name>_bodyseg.json; return paths + body_name
  pipeline.py   # drape_one(body, design) : fit -> stage -> PathCofig(+seg override)
                #   -> template_simulation -> verify ; returns a per-design result record
  verify.py     # acceptance(stats, sim_obj_path, body_obj_path) -> verdict (PASS/FAIL + reasons + metrics)
  manifest.py   # aggregate per-design results -> wardrobe_manifest.json
  README.md     # as-built usage + pose conventions, mirroring the other two modules' READMEs

drape_mpfb_garment.py   # root CLI (one body × folder-or-list of designs)
tests/mpfb_drape/       # fast unit tests + one gated end-to-end (Warp) test
```

Each unit has one purpose and a narrow interface, mirroring `mpfb_ingest` / `mpfb_tpose` conventions (root CLI thin wrapper over a focused package).

---

## 5. Body segmentation (`bodyseg.py`) — the core new algorithm

**Problem.** `ggg_body_segmentation.json` is vertex-index-bound to `mean_all` (23752 verts). The MPFB avatar has different topology, so the sim needs a segmentation expressed in the *avatar's* vertex indices, with the same six region keys.

**Chosen approach (A): geometry-based, self-contained in `mpfb_drape`.** Derive regions from the mesh geometry, reusing the same anatomical reasoning `mpfb_ingest.autolandmarks` already performs (level detection, limb geometry). The avatar is a known true T-pose in a known frame (Y-up, metres, feet Y=0, centred X/Z), which makes the cuts robust:

- **left_arm / right_arm:** vertices laterally beyond the shoulder joint (|X| > shoulder half-width), split by sign of X. Arms are horizontal, so this is a clean X-threshold above the torso level.
- **left_leg / right_leg:** vertices below the crotch level, split by sign of X.
- **body:** the remaining torso/head/pelvis vertices (everything not arm/leg).
- **face_internal:** interior head-cavity faces. Default **empty** — the exported MPFB body has helpers stripped and an empty filter is harmless; an interior-detection refinement is a documented future option.

Output: a dict in the exact ggg shape (six keys → index lists), serialized to `<body_name>_bodyseg.json`. The partition must be **complete** (every vertex labelled) and **disjoint** for arms/legs/body so the Warp face filters behave.

**Rejected approach (B): rig-based seg emitted by `mpfb_tpose`.** Use game_engine bone weights to label vertices at export. More anatomically exact, but couples segmentation to the Blender step, requires re-running `mpfb_tpose`, and only works for MPFB-origin bodies. Kept as a documented future enhancement; **A** is decoupled and runs on any ingested body.

---

## 6. Drape pipeline (`pipeline.py`)

`drape_one(body, design, out_dir, sim_props, render=False)`:

1. **Fit** (`fit.py`): build `BodyParameters(avatar.yaml)`, construct `MetaGarment(name, body, design)`, `pattern = piece.assembly()`, `pattern.serialize(spec_dir, tag='', to_subfolder=True, with_3d=False, ...)`, and write `design_params.yaml` + body measurements next to it — matching what `PathCofig` expects in `in_element_path` (`<in_name>_specification.json`).
2. **Stage** (`body_stage.py`): ensure `<bodies_dir>/<body_name>.obj` (metres) + `<body_name>.yaml` exist; write `<body_name>_bodyseg.json`.
3. **Paths**: construct `PathCofig(in_element_path=spec_dir, out_path=out_dir, in_name=design, body_name=<body_name>, default_body=True)`, then **inject** `paths.body_seg = <staged bodyseg path>` (the single override).
4. **Mesh + drape**: call the existing `template_simulation(paths, props)` (it does `BoxMesh → load → serialize → run_sim`).
5. **Verify**: `verify.acceptance(props_stats, paths.g_sim, paths.in_body_obj)`.
6. Return a result record: `{design, verdict, metrics, out_folder, sim_glb}`.

Sim props start from `assets/Sim_props/default_sim_props.yaml` via the project's `Properties`/`init_sim_props` defaults (attachment + collision filters on). `render=False` by default for batch speed; `--render` enables the existing render step.

Units are verified compatible end-to-end: avatar metres → `b_scale` ×100 → cm; garment boxmesh already in cm.

---

## 7. Verify / acceptance (`verify.py`)

A drape **PASSES** when all hold; otherwise **FAIL** with explicit reasons + metrics. Most signals are already computed by `run_sim`:

- **Settle:** `static_equilibrium` not recorded in `props['sim']['stats']['fails']` (sim reached `Cloth.is_static`).
- **Body penetration:** `body_collisions[name] ≤ max_body_collisions` (from `count_body_intersections`).
- **Self penetration:** `self_collisions[name] ≤ max_self_collisions`.
- **No hard failures:** none of `crashes`, `fast_finish`, frame/sim timeout, pattern/mesh errors recorded for this design.
- **Sanity (extra, light, computed here):** load `<design>_sim.obj`; assert finite coords (no NaN/Inf), vertex count equals the boxmesh vertex count, and bbox lies within the body bbox expanded by a margin (catches explosion / fly-away that the collision counters can miss).

`verify` is pure and unit-testable on synthetic stats dicts + a tiny OBJ — no GPU required.

---

## 8. CLI + output (`drape_mpfb_garment.py`)

```
.venv/bin/python drape_mpfb_garment.py \
    --body assets/bodies/avatar.yaml \         # measurements; .obj resolved as sibling or via --body-obj
    --designs assets/design_params/ \          # a directory OR one-or-more *.yaml files (both accepted)
    --out .temp/wardrobe \
    [--body-obj path] [--sim-props assets/Sim_props/default_sim_props.yaml] [--render]
```

- `--body` takes the `mpfb_ingest` output YAML; the sibling `.obj` (same stem) is used as collider, overridable with `--body-obj`.
- `--designs` accepts **a folder** (drape every `*.yaml`) **or explicit file paths** — cheap flexibility to re-drape a single failed design.
- **Outputs:** one GarmentCode-standard export folder per design (`*_sim.glb` / `*_sim.obj`, `*_boxmesh.obj`, `*_sim_segmentation.txt`, `*_material.mtl` + fabric texture), **plus** a top-level `wardrobe_manifest.json`: `{ body, designs: [{name, verdict, metrics, out_folder, sim_glb}], summary }`. The manifest is what makes a batch usable without hand-inspecting N folders.

CLI errors are clear on malformed args / missing body files / missing designs (mirroring the error-clarity style already adopted in `mpfb_tpose`).

---

## 9. Testing strategy (TDD)

**Fast unit tests (`.venv`, no GPU, no Blender):**

- `bodyseg`: on a synthetic T-pose humanoid (reuse the `mpfb_ingest` conftest-style fixture), assert the partition is complete + disjoint, arm/leg vertices fall on the correct side (sign of X), indices in range, six keys present, JSON shape matches ggg.
- `verify`: synthetic stats dicts + tiny OBJ → correct PASS / FAIL classification and reasons (settled vs not, over-penetration, NaN, vert-count mismatch, fly-away bbox).
- `fit`: `BodyParameters` + a design dict → `<name>_specification.json` exists and has valid panels.
- `manifest`: aggregation + summary counts.
- CLI arg parsing: folder vs explicit list; clear errors on bad/missing args.

**Gated end-to-end (Warp; skipped when CUDA/sim env absent — mirrors existing gated tests):**

- Use a small ingested MPFB fixture body (or generate one) → drape `t-shirt.yaml` → assert `run_sim` completes, `verify` returns PASS, `<design>_sim.glb` exists, body penetration under threshold, garment settled.

Baseline before implementation: `tests/mpfb_ingest` + `tests/mpfb_tpose/test_geometry.py` = 57 passed, 13 skipped, 0 failures.

---

## 10. Risks (resolved during implementation via TDD)

- **Segmentation accuracy (A):** geometric limb cuts must be clean enough that the arm/leg Warp filters work; the penetration metric in the gated test is the proof. If a simple X-threshold is insufficient near the armpit/crotch, refine with connected-component splitting.
- **Facing / axis alignment:** the MPFB Y-up frame must match GarmentCode's body frame (front = ±Z, left/right = ±X). A back-to-front avatar → high penetration. Mitigation: an alignment sanity check at stage time and an optional `--yaw-180` flag; verify via the penetration metric.
- **True-T-pose drape stability:** matched poses *should* settle, but tight sleeve/armpit self-collision may need a tuned sim preset (quality/self-collision distance). The gated test is the empirical gate; if needed, ship an `mpfb_drape` sim preset under `assets/Sim_props/`.

---

## 11. Out of scope (documented future work)

- **Combined dressed-avatar GLB** (merge draped garment + body into one textured character file) — the eventual Zeelum end-product; deferred to keep the MVP focused on the fit+drape engine. Fast-follow.
- **One-design × many-bodies** size-grading batch and **rig-based segmentation (approach B)**.
- Re-texturing / re-rigging the draped result (the manual Blender doc already covers this for hand workflows).
