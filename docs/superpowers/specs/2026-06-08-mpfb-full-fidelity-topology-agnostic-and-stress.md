# MPFB Ingestion — Full-Fidelity, Topology-Agnostic Extractor + Real-MPFB Test Set + Stress Suite

**Date:** 2026-06-08
**Status:** Spec — ready for planning/implementation.
**Branch:** `zeelum/phase0-rnd`
**Predecessor:** `docs/superpowers/specs/2026-06-05-garmentcode-mpfb-measurement-ingestion-handoff.md`
(the quick-pass shipped; this spec closes its §8.5 deferred items 1 & 2 and adds stress testing).

---

## 1. Purpose & scope

The shipped `mpfb_ingest/` module (spec 2026-06-05 §8) is a **quick pass**: of the 26 GarmentCode body
fields, only **6 are real geometry** (height + waist/bust/underbust/hips circumferences + `waist_back_width`);
the other **20 are `--fill-defaults` neutral constants**. The runtime is also **locked to one exact MakeHuman
topology** (13345 body-only verts) via `Landmarks.validate()`, so any other mesh — including the user's
`.temp/avatar_base.glb` (**14517 verts**) — is rejected.

This spec covers two deliverables:

1. **A topology-agnostic, full-fidelity extractor** — all 26 fields computed from per-mesh geometry, working
   on any human mesh (the glb, raw MPFB exports, synthesized bodies), T-pose safe.
2. **A real-MPFB headless test-set generator + a stress/validation suite** that proves the module behaves
   correctly across the full range of body types MPFB can create.

**Out of scope (unchanged):** draping — the body-segmentation JSON and `PathCofig.body_seg` un-hardcoding
(predecessor §4.5). Pattern generation needs only the measurements YAML.

---

## 2. Verified feasibility (established 2026-06-08)

These were tested live before writing this spec; the plan relies on them:

- **MPFB2 headless works.** Blender 5.1.2 runs from WSL (`--background`); the MPFB 2.0.15 service API enables
  and runs headless — `HumanService.create_human()` produced a 19158-vert human. An earlier crash was an
  unrelated `cats-blender-plugin` addon (+ a harmless on-exit access violation), **not** MPFB.
- **`create_human(macro_detail_dict=…)`** takes the body sliders directly. Verified schema:
  `{"gender","age","muscle","weight","proportions","height","cupsize","firmness": float∈[0,1],
  "race": {"asian","caucasian","african": float}}` (race blends sum to 1).
- **Clean export path:** `ExportService.create_character_copy(human)` →
  `ExportService.bake_modifiers_remove_helpers(copy, remove_helpers=True)` → `bpy.ops.export_scene.gltf`.
  No Rigify (the fragile `bpy.ops` path) is needed.
- **`.glb` ingestion already works**: `mesh_io.load_body` concatenates the scene's geometry (`trimesh.load`).
- **End-to-end generation works**:
  `MetaGarment(BodyParameters('assets/bodies/mpfb_base.yaml'), design).assembly()` → `VisPattern`.
- **Blender path on this machine:** `/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe`.
  MPFB data: `…/AppData/Roaming/Blender Foundation/Blender/5.1/extensions/blender_org/mpfb/data`.

---

## 3. Root-cause analysis of the two ceilings

**Ceiling A — topology lock.** `measurements.circumferences`/`back_widths` read stored compact-numbering
vertex indices (`levels.waist=4462`, `side_l_waist=3987`…) from `makehuman_landmarks.json`.
`Landmarks.validate()` raises on any other vertex count. The girth-scan that *finds* levels exists only in
the offline `scripts/calibrate_landmarks.py`, never at runtime. → Only morphs of the exact calibrated base work.

**Ceiling B — defaulted majority.** 20 fields are body-type-invariant constants → silhouette details don't
track body type.

**Latent bugs found:**
- **T-pose corrupts horizontal slices.** `measurements.circumferences` uses `slice_perimeter(pick="longest")`;
  with horizontal T-pose arms a slice runs *along* the arms, so the "longest loop" is an arm/merged artifact
  (observed `torso_max=372 cm`; bust loops `[134, 36.9, 36.9, …]`). Arm-exclusion is required.
- **Height is never measured.** `mesh_io.normalize` rescales every mesh to exactly `--height-m`, discarding
  true stature (the glb is already 1.729 m metric+grounded; it gets forced to 1.700 m).

---

## 4. Design

### 4.1 Key insight — reuse `measurements.py` unchanged

`measurements.compute_all(mesh, lm, …)` already maps semantic landmark names (`side_l_waist`, `nape`,
`bust_l`, `shoulder_r`, level names …) to fields, and guards missing names. So the full-fidelity work is to
supply a **richer landmarks object computed per-mesh** that populates the *complete* name set — then
`compute_all` yields all 26 fields with no rewrite. Only one measurements edit is needed: switch
`circumferences` from `pick="longest"` to the arm-excluded **central torso loop**.

### 4.2 New module: `mpfb_ingest/autolandmarks.py`

`derive(cm_mesh, *, arm_pose='tpose') -> Landmarks` returns a `Landmarks`-compatible object (same
`.vertices`, `.levels`, `.point`, `.level_y`, `.vertex_index` interface) whose indices are computed
geometrically, no JSON, no fixed-count assumption:

- **Levels** (girth scan on arm-excluded central loops): `crotch` (leg-split height), `hips` (max girth above
  crotch), `waist` (min girth above hips), `bust` (max girth below arm-merge), `underbust` (mid waist/bust),
  `neck` (min girth between shoulders and crown), plus `thigh` (max leg girth) and `wrist` (hand-root) levels.
- **Side-balance pairs** at each torso level: extreme-X points of the central loop → `side_l/r_{waist,bust,hips}`,
  `side_l/r_neck`; plus `waist_side`, `hip_side` for `hip_inclination`.
- **Peaks**: `bust_l/r` (max +Z per side at bust level), `bum_l/r` (max −Z per side at hip level).
- **Vertical anatomy**: `crown` (max-Y), `nape` (back-most central point at neck level), `neck_base`
  (front-center of neck), `collar_l/r` & `shoulder_r` (widest-X torso points at shoulder level), `armpit_r`
  (lowest Y where a side arm-loop separates), `crotch_lvl`, `nape_lvl`.
- **Limb tips**: `wrist_r` (max-|X| arm vertex), `thigh_r` (leg-loop centroid).
- **Geodesic anchors**: `waist_back` (back-most waist point), `waist_front` (front-center waist point).

### 4.3 New geometry primitives: `mpfb_ingest/geometry.py`

- `central_loop(mesh, y)` — the section loop straddling the body axis (arm/leg side-loops excluded).
- helpers used by `autolandmarks`: extreme-X pair, extreme ±Z point per half, limb-loop selection,
  loop-count / leg-split detection.

Reuse existing: `slice_loops`, `_loop_perimeter`, `arc_between`, `geodesic` (igl exact), `euclidean`,
`angle_to_horizontal`, `angle_to_vertical`.

### 4.4 `mpfb_ingest/mesh_io.py`

- `detect_scale_to_m(raw_height)` — bucket the raw bbox-Y: ~1–3 ⇒ metres (×1), ~10–25 ⇒ decimetres (×0.1),
  >50 ⇒ MakeHuman/cm units (×0.01). `normalize()` uses it, **measures** height, and only honors an explicit
  `expected_height_m` override when provided (default: measure, don't force).

### 4.5 CLI `ingest_mpfb_body.py`

- Default to the auto path (`autolandmarks.derive`). `--landmarks <json>` switches to the committed-index path
  (regression / the calibrated base). `--fill-defaults` becomes a last-resort fallback for any field the auto
  path leaves unresolved, not the primary source.

### 4.6 Test-set generator (real MPFB)

- `scripts/gen_mpfb_testset.py` (runs inside Blender) + `scripts/run_mpfb_gen.sh` (WSL launcher). Sweeps
  `macro_detail_dict` across gender/age/weight/muscle/height/cupsize/ethnicity → ~80–150 bodies into
  `.temp/testset/<id>.glb` + `manifest.json` (id → sliders). Always includes neutral + the axis extremes for
  monotonicity tests.

---

## 5. Acceptance criteria

1. `.temp/avatar_base.glb` (14517 verts) ingests through the auto path → a 26-field YAML, every field within
   `emit.RANGES`, anatomically ordered (`waist < underbust < bust`, `waist < hips`, `waist_back_width < waist`).
2. That YAML drives `MetaGarment(...).assembly()` for t-shirt, dress, pants, and fitted bodice with **no
   self-intersection** and no exception.
3. Across the generated MPFB set, **cross-body property tests** hold: weight↑ ⇒ waist↑; height-slider↑ ⇒
   measured height↑; cupsize↑ ⇒ `bust_points`/bust↑; male ⇒ larger `shoulder_w` than matched female; every
   body yields ordered, in-range, generatable measurements.
4. No field is a frozen neutral default for a non-neutral body (the 20 anchor fields respond to shape).
5. The committed base body regression (`test_calibration_realmesh.py`) stays green.
6. Units/height: a metric, already-grounded mesh keeps its true height (glb → ~172.9 cm, not forced 170).

---

## 6. Licensing (clean-room, unchanged)

MPFB-exported bodies and the macro targets are **CC0** → commercial OK. The generator uses MPFB's own
official Python API + CC0 assets. The extractor is built from the published measurement definitions
(predecessor §2.4). The GPLv3 `GarmentMeasurements` `src/` is never read, ported, or linked. Deps remain
permissive (trimesh BSD, libigl MPL2, numpy/scipy BSD).

---

## 7. Risks

- **Topology-agnostic landmark heuristics are empirical.** Nape/collarbone/shoulder/armpit detection without
  fixed indices is the hard part. Mitigation: the generated test set + property/ordering tests are the
  acceptance harness that drives the heuristics to correctness (TDD); first-cut implementations are refined
  against real bodies, not guessed once.
- **T-pose vs A-pose.** All MPFB exports are T-pose (`arm_pose_angle=0`); the central-loop arm-exclusion is
  the primary mitigation. Draping under T-pose remains out of scope.
- **Generator headless stability.** Avoid Rigify; disable the interfering `cats-blender-plugin`; tolerate the
  harmless on-exit access violation (files are written before exit).
- **Consumer export topology drift** (subdivision/proxies) — the auto path is count-independent, so this is
  no longer a hard blocker; a sanity check on height/Y-up still guards malformed input.
