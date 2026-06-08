# GarmentCode Body-Measurement & Garment-Parameter Pipeline — Handoff for MPFB Ingestion

**Date:** 2026-06-05 (outcome backfilled 2026-06-08)
**Status:** Reference design seed — **IMPLEMENTED.** The `mpfb_ingest/` module is built and the quick-pass calibration shipped; an MPFB-derived body generates a garment end-to-end. See **§8** for what was actually built, what changed versus this seed, and which §6 risks are now closed.
**Audience:** Technical implementer (human or AI agent) with repo access. Anchors are given as `path:line` and class/method names so they survive minor line drift.

---

## 0. Purpose, scope, and the locked decision

This document explains **how GarmentCode currently turns body measurements and garment (design) parameters into a draped 3D garment**, in enough depth to build a **custom body-measurement ingestion module** that feeds GarmentCode from **MPFB (MakeHuman Plugin for Blender)** human models defined parametrically.

**Locked approach (decided during brainstorming):** a **clean-room Python geometry extractor**, written in *our* MIT fork of GarmentCode, that computes GarmentCode's measurement fields directly from the MPFB-exported body mesh and writes a GarmentCode body-measurements YAML. We do **not** depend on, vendor, or port the team's existing `mbotsch/GarmentMeasurements` tool — it is **GPLv3** (see §5).

**Two channels, only one is in scope:**
- **Body measurements** (`body:` YAML) — *the target of the ingestion module.* Deep coverage in §2.
- **Garment/design parameters** (`design:` YAML) — orthogonal, unchanged by this work. Companion coverage in §3.

**Out of scope but flagged (§4.5, §6):** a custom body also needs a **body-segmentation JSON** to *drape* (not to generate patterns). That is a sibling workstream, not part of measurement ingestion.

---

## 1. System context — end to end

Two independent inputs converge in a garment program, then flow to simulation:

```
 body measurements (body: YAML) ─┐
                                 ├─► MetaGarment(name, body, design) ─► .assembly()
 design params     (design: YAML)┘        (2D parametric sewing pattern, JSON/SVG, units = cm)
                                                   │
                                                   ▼
                                   BoxMesh  (boxmeshgen.py) ── triangulate panels, place in 3D,
                                                   │            set up sewing-spring constraints  → *_boxmesh.obj
                                                   ▼
                                   Cloth + Warp XPBD (garment.py, simulation.py)
                                       loads BODY .obj (collision) + BODY segmentation JSON
                                       drapes panels onto body  → *_sim.obj
```

Minimal canonical driver: `test_garmentcode.py` — loads a body YAML via `BodyParameters`, a design YAML, builds `MetaGarment(df, body, design)`, calls `.assembly()`, serializes the pattern. **For pattern generation, only the measurements YAML is needed.** The body **.obj** and **segmentation JSON** are needed only later, for draping.

Pattern→drape batch entry: `pattern_data_sim.py` → `pygarment/meshgen/datasim_utils.py::batch_sim` (`:19`) → `template_simulation` (`:289`) → `simulation.py::run_sim` (`:163`) → `garment.py::Cloth` (`:19`).

---

## 2. Body-measurement pipeline (PRIMARY)

### 2.1 File format

A body is a flat YAML under a single `body:` key. Values are **centimetres** (height ≈ 171.99) except the three **angles**, which are **degrees**.

`assets/bodies/mean_all.yaml` (the "neutral" GarmentMeasurements body) defines **26 base measurements**. Example (abridged):

```yaml
body:
  height: 171.99
  bust: 99.8407
  waist: 84.3338
  hips: 103.478
  shoulder_w: 36.4568
  waist_back_width: 39.1358
  arm_pose_angle: 45.483
  shoulder_incl: 21.6777
  # ... 26 fields total
```

**Field-set is not fixed across bodies.** The SMPL body YAML (`f_smpl_average_A40.yaml`) omits some fields (e.g. `vert_bust_line`). Code tolerates this via guarded derivations (see §2.3). **Implication for MPFB:** you must emit the fields the garment programs actually read (§2.4–2.5); a few are optional.

### 2.2 Loader — `BodyParametrizationBase`

`pygarment/garmentcode/params.py:11`. A thin dict wrapper:

- `load(file)` reads `yaml.safe_load(f)['body']` into `self.params`, then calls `eval_dependencies()`.
- `__getitem__`/`__setitem__` — garment code reads `body['field']`; setting a value re-runs `eval_dependencies(key)`.
- `load_from_dict(in_dict)` — **load measurements from an in-memory dict** (no file). Useful entry point for the ingestion module if you want to construct measurements programmatically.
- `save(path, name='body_measurements')` — dumps `{'body': params}` back to YAML.

### 2.3 Derived fields — `BodyParameters.eval_dependencies`

`assets/bodies/body_params.py:6` subclasses the base and computes **7 derived `_`-prefixed fields** from the base measurements. These are what several garment programs actually consume:

| Derived field | Formula (from `body_params.py`) | Depends on |
|---|---|---|
| `_waist_level` | `height - head_l - waist_line` | height, head_l, waist_line |
| `_leg_length` | `_waist_level - hips_line` | (above), hips_line |
| `_base_sleeve_balance` | `shoulder_w - 2` | shoulder_w |
| `_bust_line` | `(2/3)*vert_bust_line + (1/3)*bust_line` if `vert_bust_line` present, else `bust_line` | vert_bust_line?, bust_line |
| `_hip_inclination` | `hip_inclination / 2` | hip_inclination |
| `_shoulder_incl` | `shoulder_incl` (pass-through) | shoulder_incl |
| `_armscye_depth` | `armscye_depth + 2.5` (ease) | armscye_depth |

The `_bust_line` guard is the precedent showing optional base fields are acceptable.

### 2.4 The measurement fields — authoritative definitions

From `docs/Body Measurements GarmentCode.pdf`. Grouped, with **how often garment programs read each** (direct `body['x']` occurrences across `assets/garment_programs/*.py`) and an **extraction-difficulty** rating for the MPFB extractor (§4.3).

> **"Balance line"** = a vertical line through the side of the body along the coronal plane. The back-section widths measure the **back arc** between the two balance lines.

**Circumferences** (parallel to the floor):

| Field | Definition | Uses | MPFB extract |
|---|---|---|---|
| `waist` | mid ribs↔hips | 14 | Slice ⊥ Y at waist level → perimeter |
| `bust` | through bust points | 10 | Slice at bust-peak height |
| `underbust` | right below bust | 0* | Slice below bust |
| `hips` | through bum points | 9 | Slice at hip level |
| `leg_circ` | thickest thigh, one leg | 2 | Slice one thigh at max girth |
| `wrist` | thinnest at hand root | 2 | Slice at wrist landmark |

**Sections** (balance-line to balance-line, measured on the back):

| Field | Definition | Uses | MPFB extract |
|---|---|---|---|
| `waist_back_width` | back width at waist | **23 (most-used body field)** | Back arc/chord between side landmarks at waist level |
| `back_width` | back width at bust | 5 | Same, at bust level |
| `hip_back_width` | back width at hips | 7 | Same, at hip level |

**Distances**:

| Field | Definition | Uses | MPFB extract |
|---|---|---|---|
| `waist_line` | nape→waist, **geodesic on back surface** | 6 | Geodesic from nape vertex |
| `waist_over_bust_line` | neck base→waist **over the bust** (tape-like convex/geodesic, front) | 1 | Front geodesic over bust |
| `bust_line` | shoulder level→bust points (along the above) | 0 direct (feeds `_bust_line`, 5×) | Geodesic shoulder→bust peak |
| `vert_bust_line` | **vertical** nape→bust-circ line | 0* (feeds `_bust_line`) | ΔY nape→bust level |
| `arm_length` | shoulder→wrist | 3 | Geodesic/euclidean along arm |
| `height` | feet→top of head | 9 | Y extent (trivial) |
| `head_l` | nape→top of head, euclidean | 10 | Euclidean nape→crown |
| `shoulder_w` | collarbone-end L→collarbone-end R | 8 | Euclidean between collarbone landmarks |
| `armscye_depth` | shoulder→underarm-pit bottom, on back | 0 direct (feeds `_armscye_depth`, 2×) | Euclidean shoulder→armpit landmark |
| `bust_points` | breast peak↔peak | 4 | Distance between two peak vertices |
| `hips_line` | waist level→hip level, vertical | 3 | ΔY between levels |
| `bum_points` | buttock peak↔peak | 3 | Distance between two peak vertices |
| `crotch_hip_diff` | hip level→crotch, vertical | 1 | ΔY hip level→crotch vertex |
| `neck_w` | neck-base width, back, balance-to-balance | 1 | Back arc at neck base |

**Angles (degrees)**:

| Field | Definition | Uses | MPFB extract |
|---|---|---|---|
| `hip_inclination` | waist→hip angle on the body side; 0 = vertical side | 0 direct (feeds `_hip_inclination`, 2×) | atan2 of side profile waist→hip |
| `shoulder_incl` | neck-base→collarbone-end line vs horizontal | 0 direct (feeds `_shoulder_incl`, 8×) | angle of shoulder landmark line |
| `arm_pose_angle` | **the arm pose at the shoulder joint** — used to align sleeves; assumes both arms equal | 2 | **Pose constant, not shape** — set from the body's arm pose (see §4.3, §6) |

\* `underbust`, `vert_bust_line` are read indirectly or unused by current programs but should still be emitted for compatibility.

### 2.5 Consumers — how the values are used

Garment programs receive the `BodyParameters` object and read `body['field']` directly (e.g. `tee.py`, `bodice.py`, `pants.py`, `sleeves.py`, `bands.py`). The most load-bearing fields are the **drafting-specific** ones — `waist_back_width` (23×), `head_l`, `bust`, `hips`, `height`, `shoulder_w`, plus derived `_waist_level` (13×), `_shoulder_incl`, `_leg_length`. A wrong/missing high-use field distorts the pattern silhouette directly; the optional-field guard in §2.3 is the only graceful-degradation precedent.

### 2.6 Where measurements meet the mesh — `PathCofig` and units

`pygarment/meshgen/sim_config.py::PathCofig._update_in_paths` (`:47`) resolves, by **body name**:

```python
self.in_body_mes = self.bodies_path / f'{self._body_name}.yaml'   # measurements
self.in_body_obj = self.bodies_path / f'{self._body_name}.obj'    # collision mesh  (:66)
self.body_seg    = bodies_default_path / ('ggg_body_segmentation.json'
                                          if not use_smpl_seg
                                          else 'smpl_vert_segmentation.json')   # (:68)
```

`bodies_path` comes from `system.json::bodies_default_path` (= `./assets/bodies`). **So a custom body is three same-named files dropped into `assets/bodies/`** — *except* `body_seg`, which is **hardcoded to one of two files and not keyed by body name** (integration gotcha — §4.5).

**Units / orientation** (`garment.py::Cloth`):
- `b_scale = 100.0` (`:39`): body vertices are multiplied by 100 → the body OBJ is expected in **metres** (height ≈ 1.72 → 172 cm). `c_scale = 1.0` (`:38`): the cloth/boxmesh is already **cm**.
- `get_shift_param` (`:455`) computes a **Y shift** applied to both body and cloth (ground/registration alignment).
- Body is **Y-up**. (Draping guide convention for the garment side: Up = Y, Fwd = −Z.)

---

## 3. Garment/design-parameter pipeline (COMPANION — out of scope, do not touch)

- **Format:** a `design:` root YAML. Each leaf parameter is `{v: <value>, range: [...], type: float|int|bool|select|select_null, default_prob: <p>}`. Top-level groups in `assets/design_params/default.yaml`: `meta`, `waistband`, `shirt`, `collar`, `sleeve`, `left`, `skirt`, `pants`.
- **Loader / sampler:** `DesignSampler` (`params.py:66`) — `load()` reads `['design']`; `randomize()` walks the nested dict and samples each leaf by `type`/`range`/`default_prob`.
- **Assembly:** `MetaGarment(name, body, design)` (`assets/garment_programs/meta_garment.py:26`). It selects components from `design['meta']['upper'|'bottom'|'wb']['v']` and instantiates each as `Component(body, design)`. **Both channels enter every component**, but they are independent inputs — design chooses *style/parameters*, body supplies *measurements*. The ingestion module changes the body channel only; design is untouched.

---

## 4. MPFB → GarmentCode bridging (the design seed)

### 4.1 MPFB / MakeHuman facts that matter

- **Fixed topology.** All MPFB humans are morphs of the same MakeHuman base mesh → **identical vertex count and ordering** across every parametric model. This is the linchpin (§4.3).
- **Licensing:** MakeHuman base mesh, targets, and exported models are **CC0** → commercially usable (§5). *(Confirm on MakeHuman's license page; not re-verified this session.)*
- **Pose:** Zeelum uses **T-pose** avatars (arms horizontal). GarmentCode's own bodies are **A-pose** (`*_A40`, `arm_pose_angle ≈ 40–45`).
- **Units/orientation:** MakeHuman/MPFB export scale depends on export settings (metres vs decimetres). **Must be normalised** so the body lands in the same space GarmentCode expects (metres for the OBJ; §2.6).

### 4.2 Gap analysis

GarmentCode's fields are **garment-drafting** measurements, **not** standard anthropometrics. Neither MPFB's slider/modifier values nor a tape-measure table can supply the back-section widths, nape-anchored geodesics, balance-line constructs, or angles that dominate usage (§2.4). **Geometry-driven extraction from the mesh is the only complete source** — confirmed as the reason the clean-room approach was chosen.

### 4.3 Recommended method — clean-room geometric extraction on fixed topology

The decisive advantage over a generic extractor (e.g. GarmentMeasurements' heuristic landmarking): **because MakeHuman topology is fixed, landmarks become constant vertex indices**, calibrated **once**, reused for every MPFB model. That turns the hard part (landmark detection) into a lookup table.

Per field group:
- **Constant landmark vertices** (calibrate once on the MakeHuman base mesh): nape-of-neck, crown, collarbone ends (L/R), shoulder points, armpit/underarm, bust peaks (L/R), buttock peaks (L/R), crotch, wrists, side "balance" points at waist/bust/hip levels. *(MakeHuman ships measurement vertex definitions for its Measure tab — CC0 — locate and reuse them as seed loops where they align.)*
- **Circumferences** — intersect the mesh with a horizontal plane (⊥ Y) at the landmark height; sum the closed cross-section perimeter. (`trimesh.section` or libigl.)
- **Back-section widths** — at the level plane, take the two side balance landmarks and measure the **back arc/chord** between them.
- **Geodesics** (`waist_line`, `waist_over_bust_line`, `bust_line`, `arm_length`) — surface distance from the relevant landmark (e.g. nape) via heat-method geodesics (libigl `heat_geodesic` / `exact_geodesic`).
- **Euclidean distances & ΔY** (`height`, `head_l`, `shoulder_w`, `bust_points`, `bum_points`, `hips_line`, `crotch_hip_diff`, `armscye_depth`) — direct vector norms / Y-differences between landmark vertices.
- **Angles** (`shoulder_incl`, `hip_inclination`) — `atan2` over the relevant landmark vectors.
- **`arm_pose_angle`** — **set from the body's actual arm pose**, not extracted as shape. Confirm the zero/sign convention against `assets/garment_programs/sleeves.py` and the A-pose reference values (≈40–45) before fixing the T-pose value (§6).

Permissive libs only: **trimesh** (BSD), **libigl** (MPL2), numpy/scipy (BSD). Avoid GPL geometry deps.

### 4.4 Module shape

```
Input:  MPFB-exported body OBJ (+ known pose tag, e.g. "tpose")
  1. Normalise: units → metres, Y-up, centre/ground; verify against a known-height check.
  2. Extract:   landmark lookup (fixed indices) → per-field geometry (§4.3), computed in cm.
  3. Post-process: set arm_pose_angle from pose; fill optional/derived-safe fields; range-validate.
  4. Emit:      BodyParameters.load_from_dict(...).save(out_dir, name=<body_name>)  → <body_name>.yaml
Output: GarmentCode body-measurements YAML  (drop into assets/bodies/)
```

The cleanest insertion point is `BodyParametrizationBase.load_from_dict` + `save` (§2.2) — build the measurement dict, hand it to a `BodyParameters` instance, let GarmentCode compute the derived `_` fields and serialize.

### 4.5 Integration points

- **Pattern generation** (the module's immediate consumer): point `BodyParameters` at the emitted `<body_name>.yaml`, or construct via `load_from_dict`. No other change needed — `MetaGarment` consumes it directly.
- **Draping** needs two more same-named files in `assets/bodies/`: the **`<body_name>.obj`** (in metres, Y-up) and a **body-segmentation JSON**.
- **Gotcha:** `PathCofig.body_seg` (`sim_config.py:68`) is **hardcoded** to `ggg_body_segmentation.json` or `smpl_vert_segmentation.json`, selected by the `use_smpl_seg` flag — **not** by body name. Supporting an MPFB segmentation requires either overwriting one of those files or extending `PathCofig` (and the `smpl_body`/`use_smpl_seg` plumbing through `panel_assignment`, `garment.py:185`) to accept a third, body-keyed option.

---

## 5. Licensing constraints (engineering analysis — not legal advice)

| Component | License | Effect |
|---|---|---|
| GarmentCode / pygarment | **MIT** (`LICENSE`, `setup.cfg`) | Permissive: build on, modify, ship commercially; keep the notice. |
| MPFB-exported bodies | **CC0** (MakeHuman assets/output) | Public domain → commercial OK. *(Confirm on MakeHuman license page.)* |
| SMPL default bodies (`*_smpl_*`) | Research / non-commercial | Encumbered (`assets/bodies/Readme.md`). Replaced by MPFB. |
| `mbotsch/GarmentMeasurements` | **GPLv3** | Strong copyleft. **Do not vendor, port, or link.** |
| `cgal` (in pygarment `install_requires`) | **GPLv3 / commercial dual** | Pre-existing diligence item for the pipeline; confirm whether CGAL paths are exercised and under which license. |

**Why the clean-room Python extractor is GPL-clean:**
- Copyright protects **expression** (source code), not **methods, algorithms, or facts**. Implementing the *same geometry* from the **published measurement definitions** (the PDF) is **independent creation**, not a derivative — even if results are identical (merger doctrine reinforces this for math-dictated code).
- "Plugging into the same GarmentCode" creates **no** contamination: GarmentMeasurements is *itself external* to GarmentCode (which is MIT and ships its YAML output). Copyleft propagates through **deriving from GM's code**, not through sharing a downstream consumer.
- **Hygiene rules:** implement from the spec, treat GM's `src/` as off-limits (don't read/transliterate); develop in the MIT fork, never inside the GPL repo; don't bundle the GM binary; document that the extractor was built from the published spec.

For commercial release, have IP counsel bless the clean-room process and the CGAL question.

---

## 6. Risks & open questions

1. **Clean-room discipline** (highest priority): no copying/transliterating GarmentMeasurements source; build from the §2.4 definitions. Defeats copyright, not patents (no known patent here).
2. **Landmark calibration on MakeHuman topology:** identify and freeze the constant vertex indices (§4.3). Validate visually on the base mesh before trusting derived measurements. Reuse MakeHuman's CC0 measurement vertex data if locatable.
3. **`arm_pose_angle` convention:** determine the zero/sign from `sleeves.py` and A-pose values before setting the T-pose value; wrong convention misaligns sleeves.
4. **T-pose vs A-pose effects:** the pose changes both (a) some measurement readings (arm-adjacent geodesics, armscye) and (b) draping initialization. GarmentCode bodies are A-pose; confirm the drafting math tolerates T-pose inputs, or document required adjustments.
5. **Units/orientation normalization:** verify MPFB export scale (metres vs decimetres) and Y-up; add a known-height sanity check in step 1 (§4.4).
6. **Segmentation integration gotcha** (§4.5): `body_seg` is not body-keyed; plan the `PathCofig`/`panel_assignment` extension. (Sibling workstream — produce the MPFB segmentation JSON; out of measurement-ingestion scope.)
7. **Validation strategy:** cross-check extracted measurements against (a) MPFB's own Measure-tab readouts for the circumferences it does provide, and (b) the existing `mean_all.yaml` ranges, to catch gross errors.

---

## 7. Appendix — code index

| Concern | Location |
|---|---|
| Measurement loader / base class | `pygarment/garmentcode/params.py:11` (`BodyParametrizationBase`) |
| Derived fields | `assets/bodies/body_params.py:6` (`BodyParameters.eval_dependencies`) |
| Field definitions (authoritative) | `docs/Body Measurements GarmentCode.pdf` |
| Design-param sampler | `pygarment/garmentcode/params.py:66` (`DesignSampler`) |
| Garment assembly | `assets/garment_programs/meta_garment.py:26` (`MetaGarment.__init__`) |
| Path resolution (body files) | `pygarment/meshgen/sim_config.py:47` (`PathCofig._update_in_paths`); `in_body_obj` `:66`, `body_seg` `:68` |
| Body load / units / scale | `pygarment/meshgen/garment.py` — `b_scale` `:39`, body load `:99`, panel_assignment `:185`, `get_shift_param` `:455` |
| Sim entry / batch | `pattern_data_sim.py`; `datasim_utils.py:19` (`batch_sim`), `:289` (`template_simulation`); `simulation.py:163` (`run_sim`) |
| System paths | `system.json` (`bodies_default_path` = `./assets/bodies`) |
| Minimal driver (gen only) | `test_garmentcode.py` |
| Body assets | `assets/bodies/` (`mean_all*.obj/.yaml`, `*_smpl_*`, `ggg_body_segmentation.json`, `smpl_vert_segmentation.json`) |

---

## 8. Implementation outcome (backfilled 2026-06-08)

The design seed above was executed in full. This section records what was actually built, where reality diverged from the seed, and the current state of each §6 risk. Branch: `zeelum/phase0-rnd`. Execution method: `superpowers:subagent-driven-development` (TDD per task; implementer → spec+quality review → fix → commit). Companion plan with full per-task code: `docs/superpowers/plans/2026-06-05-mpfb-body-measurement-ingestion.md`.

### 8.1 What shipped

The 14-task plan (T1–T14) is **complete**; the suite is **24 tests green** (`tests/mpfb_ingest/`). The module matches the §4.4 shape:

| File | Status |
|---|---|
| `mpfb_ingest/mesh_io.py` | load OBJ; `normalize()`→metres (Y-up, grounded), `to_cm()`→×100 working copy |
| `mpfb_ingest/geometry.py` | slice perimeter, slice loops, back-arc, geodesic, euclidean, ΔY, angles |
| `mpfb_ingest/landmarks.py` | `Landmarks` registry over the index JSON + topology validation |
| `mpfb_ingest/measurements.py` | the 26-field computations (circumferences / back_widths / distances / angles / `compute_all`) |
| `mpfb_ingest/emit.py` | range validation + `BodyParameters.load_from_dict(...).save(...)` |
| `ingest_mpfb_body.py` (root) | CLI orchestration + `--fill-defaults` |
| `mpfb_ingest/data/mpfb_base_body.obj` | calibrated body-only mesh (13,345 verts, CC0) |
| `mpfb_ingest/data/makehuman_landmarks.json` | calibrated vertex indices (body-only numbering) |
| `scripts/calibrate_landmarks.py` | the quick-pass calibrator (§8.3) |
| `assets/bodies/mpfb_base.yaml` | the generated calibrated body |
| `mpfb_ingest/README.md` | usage + clean-room provenance + pose convention |

**End-to-end proof:** `mpfb_base.yaml` → `MetaGarment` → a t-shirt pattern generated with no self-intersection (SVG/JSON output). Pattern generation needs only the measurements YAML, as §1/§4.5 predicted.

### 8.2 Divergences from the seed

- **The asset gate dissolved — no user export was ever required.** §4.1/§6 assumed T13–T14 were blocked pending an MPFB-exported OBJ. In fact the MPFB Blender extension **bundles `data/3dobjs/base.obj`** (the MakeHuman hm08 base mesh, 21,833 verts) plus the CC0 `data/targets/measure-*.target.gz` morph regions. Calibration ran against those directly. Path on this machine: `/mnt/c/Users/KubangPawis/AppData/Roaming/Blender Foundation/Blender/5.1/extensions/blender_org/mpfb/data`.
- **Helper geometry must be stripped first.** The base mesh's body proper is indices `[0, 13380)`; everything at/above is helper geometry (eyes, teeth, tongue, genitals, **joint cubes**). Helpers corrupt the bounding box (and therefore height) and inject stray slice loops into circumferences. The calibrator keeps only faces fully within the body range, compacts the referenced vertices to a fresh `0..N-1` numbering, and commits the result as `mpfb_base_body.obj` (13,345 verts). **All committed landmark indices are in this body-only numbering** — a consumer's raw export must be run through the same strip and checked against `n_vertices_expected` (13345) before its indices are valid.
- **One plan-authorized edit to shared GarmentCode code.** `pygarment/garmentcode/params.py::BodyParametrizationBase.__init__` now guards `if param_file: self.load(param_file)` so `BodyParameters()` constructs empty for `load_from_dict`. Real-path loading is unchanged.
- **A false "numpy monkey-patches yaml" diagnosis was caught and reverted in review** (T10). The 3-significant-figure float formatting in emitted YAML is **deliberate and global**, from `pygarment/data_config.py:30` (`yaml.add_representer(float, f'{data:.3g}')`) — every GarmentCode body is formatted this way, so emit preserves it rather than overriding it.

### 8.3 Calibration reality — quick pass, not full fidelity

The seed (§4.3, §6.2) hoped to reuse MakeHuman's measurement vertex data as constant landmarks. Reality:

- **MakeHuman `joint-*` vertex groups are useless for landmarks** — in `base.obj` their helper verts are **parked at the feet** (joint-head/spine sit at Y≈−8), not at anatomical positions.
- **`measure-*.target.gz` are CC0 morph regions** (`<vertex_index> dx dy dz`), and only the **waist** ring places cleanly. The bust/hips/neck rings are broad deform regions whose extreme-X verts land near the armpits and mis-size the back arc — the bust ring gave `back_width` 24.8 vs reference 47.68, which **degenerates the armscye and crashes sleeve generation** (`AssertionError: Start and end of an edge should differ`).

So the quick pass derives real geometry for **height, waist, bust, underbust, hips, and `waist_back_width`** — the four torso levels via an **anatomical girth scan** (`scripts/calibrate_landmarks.py::_find_levels`: legs merge into pelvis at a crotch girth-jump; hips = max girth just above it; waist = min girth above hips; bust = max girth below the arm-merge jump; underbust = the waist/bust midpoint level), and the waist side-pair from the CC0 waist ring. `waist_back_width` lands 39.9 vs reference 39.14 — validated by `tests/mpfb_ingest/test_calibration_realmesh.py`. **Everything else** (`back_width`, `hip_back_width`, `neck_w`, all geodesic anchors, bust/bum points, limb circumferences) is served by the CLI's `--fill-defaults` (neutral-body values from `mean_all.yaml`) and is the **full-fidelity pass deferred to future work**.

### 8.4 §6 risk status

| # | Risk | Status |
|---|---|---|
| 1 | Clean-room discipline | **Held.** Built from the §2.4 PDF definitions; GarmentMeasurements `src/` never read. Deps permissive (trimesh BSD, libigl MPL2, numpy/scipy BSD). |
| 2 | Landmark calibration | **Partially closed.** Torso levels + waist pair are real and validated; remaining anchors are defaulted (§8.3). Full-fidelity calibration is the main open item. |
| 3 | `arm_pose_angle` convention | **Closed.** It is arm droop from horizontal: **T-pose = 0.0**, *not* 90. Pinned by `mean_all_tpose.yaml` being byte-identical to `mean_all.yaml` except 45.483→0.0. Consumed at `sleeves.py:340` (Z-rotation) and `bodice.py:297` (`gap = -1 - arm_pose_angle/10`). Pass `--arm-pose-angle 0` for MPFB. |
| 4 | T-pose vs A-pose drafting | **Closed for generation.** `arm_pose_angle=0` generates cleanly; the earlier crash was the bad `back_width`, not the pose. Draping under T-pose is untested (draping is out of scope, §4.5). |
| 5 | Units / orientation | **Closed.** `normalize()` grounds to metres with an `expected_height_m` sanity check; `to_cm()` drives all measurement math. |
| 6 | Segmentation gotcha | **Unchanged / still open.** Sibling draping workstream, untouched by this module. |
| 7 | Validation strategy | **In place.** Synthetic-fixture tests (T1–T12) plus the real-mesh anatomical-range + ordering test (T13). Cross-check against MPFB Measure-tab readouts still pending a user avatar. |

### 8.5 Remaining work (deferred, not started)

1. **Full-fidelity anchor pass** — replace `--fill-defaults` for `back_width`, `hip_back_width`, `neck_w`, the geodesic distances (`waist_line`, `waist_over_bust_line`, `bust_line`, `arm_length`), and the bust/bum point pairs with real geometry. Requires reliable side-balance and nape/crown/collarbone landmarks the broad measure rings don't provide.
2. **Consumer-export validation** — confirm a real user MPFB export's topology matches `n_vertices_expected` (13345) after the same body-only strip, or recalibrate if it differs (subdivision/proxies change the count). Wire the strip into the CLI so raw exports work directly.
3. **Draping** — body OBJ (`--save-obj`) is emitted, but the body-segmentation JSON + the `PathCofig.body_seg` un-hardcoding (§4.5) remain the sibling workstream.

### 8.6 Phase 2 (2026-06-08) — full-fidelity + topology-agnostic + stress (DONE)

§8.5 items **1 and 2 are closed**. Spec + plan: `docs/superpowers/{specs,plans}/2026-06-08-mpfb-full-fidelity-topology-agnostic-and-stress.md`. Suite is now **69 tests green**.

- **Topology-agnostic auto path is the default.** `mpfb_ingest/autolandmarks.py::derive(mesh)` derives every landmark per-mesh by geometric scan (no fixed vertex indices, no JSON), so any human mesh works regardless of vertex count — including the user's `.temp/avatar_base.glb` (14,517 verts, ≠ the calibrated 13,345). `--landmarks` is now **optional** (committed-index path kept only for the base regression); `--height-m` is an override only — `mesh_io.normalize()` auto-detects the unit scale and **measures** stature. `.glb` ingests directly.
- **All 26 fields are real geometry.** The 20 previously `--fill-defaults` anchors (`back_width`, `hip_back_width`, `neck_w`, geodesics `waist_line`/`waist_over_bust_line`/`bust_line`/`arm_length`, `bust_points`/`bum_points`, `wrist`, `leg_circ`, `armscye_depth`, `shoulder_incl`, `hip_inclination`, …) are computed from auto-landmarks. `--fill-defaults` is now a last-resort fallback, not the primary source.
- **T-pose safe.** Horizontal arms corrupt naive horizontal slices (merged/extra loops → a 372 cm "girth"). `geometry.central_loop` excludes arms by picking the body-axis loop and clipping `|X| > 1.6·torso_halfwidth`; `find_levels` keys the arm-merge boundary on a **lateral X-width** jump (a deltoid/shoulder shelf widens X) rather than a perimeter jump (a bust widens Z), and the clavicle scan runs top-down for stability.
- **Real-MPFB test set + stress suite.** `scripts/gen_mpfb_testset.py` (+ `run_mpfb_gen.sh`) drives MPFB2 headless (Blender 5.1, CC0 output) to emit single-axis macro sweeps as `.glb` + `manifest.json` (shape keys baked into the basis so morphs survive glTF export). `tests/mpfb_ingest/test_testset_assets.py` gates the assets; `test_stress_testset.py` proves every body is complete/in-range/ordered, generation never crashes, and measurements track the sliders (weight↑⇒waist↑, height↑⇒stature↑, cup↑⇒bust↑, male⇒broader shoulders). `test_stress_glb.py` does the same end-to-end on the real T-pose avatar. All skip cleanly when assets are absent.
- **Still open:** §8.5 item 3 (draping segmentation) — unchanged sibling workstream. The `arm_pose_angle` remains a pose **input** (`0` for T-pose); it is not inferred from the mesh.
