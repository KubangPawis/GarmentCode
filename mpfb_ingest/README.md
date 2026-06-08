# mpfb_ingest — MPFB/MakeHuman → GarmentCode body-measurement ingestion

Reads an MPFB/MakeHuman body mesh (**OBJ or GLB**) and emits a GarmentCode
body-measurements YAML (the 26 base fields), so GarmentCode can fit/drape garments
on custom MPFB avatars instead of only the bundled SMPL-derived bodies.

```
OBJ/GLB ──load/normalize──▶ cm mesh ──auto-landmarks + geometry──▶ 26 measurements
                                                                       │
                                                   BodyParameters.save ▼
                                                     assets/bodies/<name>.yaml
```

**Default path is topology-agnostic and full-fidelity:** all 26 fields are derived
as real geometry from per-mesh geometric landmarking (`autolandmarks.derive`) — no
fixed vertex indices, no landmark JSON, works on **any** human mesh regardless of
vertex count (a true T-pose included). Unit scale is auto-detected and stature is
**measured**, not forced. The fixed-index path (`--landmarks`) is retained only as a
calibrated-base regression; `--fill-defaults` is a last-resort fallback.

## Clean-room provenance

This module is implemented **clean-room from the published GarmentCode measurement
definitions** (`docs/Body Measurements GarmentCode.pdf`). It does **not** use, link,
port, or derive from the GPLv3 `mbotsch/GarmentMeasurements` tool. Dependencies are
permissive only: trimesh (BSD), libigl (MPL2, already a GarmentCode dep), numpy/scipy
(BSD). The emitted YAML is produced by GarmentCode's own `BodyParameters.save`, so the
file format — including GarmentCode's global 3-significant-figure float formatting
(`pygarment/data_config.py`) — matches every other body in `assets/bodies`.

## Units convention

- `mesh_io.normalize()` returns the mesh in **metres** (Y-up, feet grounded at Y=0,
  centred in X/Z). This is the mesh saved as the GarmentCode body OBJ; GarmentCode
  scales it ×100 via `b_scale` at drape time.
- `mesh_io.to_cm()` returns a ×100 **centimetre** copy. **All measurement math runs on
  the cm mesh**, so the outputs are in centimetres and match the YAML directly. Angles
  are unitless degrees.

## Pose conventions — `arm_pose_angle`

`arm_pose_angle` is the angle (degrees) by which the arm is rotated **down from the
horizontal**. GarmentCode consumes it in two places:

- `assets/garment_programs/sleeves.py:340` — a final `R.from_euler('XYZ', [0, 0,
  arm_pose_angle])` rotation of the sleeve panel, swinging it down to follow the arm.
- `assets/garment_programs/bodice.py:297` — a sleeve-into-armhole placement gap,
  `gap = -1 - arm_pose_angle / 10` (a heuristic the source notes is "tuned for arm
  poses 30 deg–60 deg used in the dataset").

### Reference values (from `assets/bodies/`)

| Body file                     | `arm_pose_angle` | Pose                          |
|-------------------------------|------------------|-------------------------------|
| `mean_all_tpose.yaml`         | **0.0**          | **T-pose** (arms horizontal)  |
| `f_smpl_average_A40.yaml`     | 40               | A-pose                        |
| `m_smpl_average_A40.yaml`     | 40               | A-pose                        |
| `mean_all.yaml`               | 45.483           | A-pose                        |
| `mean_female.yaml`            | 45.487           | A-pose                        |
| `mean_male.yaml`              | 45.4775          | A-pose                        |

`mean_all_tpose.yaml` is byte-identical to `mean_all.yaml` apart from this single
field (45.483 → 0.0), which pins the convention: **0° is arms-horizontal (T-pose)**,
larger values droop the arm toward the torso.

### Value to pass for an MPFB T-pose avatar

**Use `--arm-pose-angle 0`.** MPFB exports are T-posed (arms horizontal), which is
exactly the 0° reference. (The CLI smoke test passes `90` only to exercise value
passthrough; it is not the recommended T-pose value.)

## Usage

Default (topology-agnostic auto path — recommended; works on any OBJ/GLB):

```bash
.venv/bin/python ingest_mpfb_body.py path/to/avatar.glb \
    --name my_avatar \
    --arm-pose-angle 0 \
    --out assets/bodies \
    --save-obj
```

- `--arm-pose-angle` — `0` for a T-pose MPFB avatar (see above). This is a pose
  **input**; it is not inferred from the mesh.
- `--landmarks` *(optional)* — the calibrated MakeHuman vertex-index JSON. Supplying
  it switches to the **fixed-index** path (only valid for the calibrated base
  topology, `n_vertices_expected` verts); kept for regression. Omit it for the auto
  path.
- `--height-m` *(optional, override)* — known stature in metres. By default
  `mesh_io.normalize()` auto-detects the unit scale and measures stature from the
  mesh; pass this only to force a known height.
- `--save-obj` — also write the normalized metres OBJ (needed for *draping*, below).
- `--fill-defaults` — last-resort backfill from neutral-body values (`mean_all.yaml`)
  for any field the auto path can't resolve; not needed in normal use.

The result `assets/bodies/<name>.yaml` is consumed directly by pattern generation via
`MetaGarment(name, body, design)`.

## Topology-agnostic extraction (`autolandmarks.py`)

`autolandmarks.derive(cm_mesh)` returns a `Landmarks`-compatible object with every
landmark placed by per-mesh geometric scan, so `measurements.compute_all` runs
unchanged on any human mesh:

- **Levels** (`find_levels`) by an anatomical girth scan on **arm-excluded** loops:
  crotch = leg-merge girth jump; hips = max girth above it; waist = min girth above
  hips; bust = max girth below the arm zone; underbust = mid; neck = min girth above
  the arm zone.
- **Arm exclusion (T-pose safe).** Horizontal arms otherwise corrupt horizontal
  slices (merged/extra loops → a ~372 cm "girth"). `geometry.central_loop` picks the
  body-axis loop and clips `|X| > 1.6·torso_halfwidth`. The arm-merge boundary is
  detected by a **lateral X-width** jump (the deltoid/shoulder shelf widens X), *not*
  a perimeter jump — so a large bust (which widens Z) is not mistaken for the arm
  zone. The clavicle level is found top-down for stability across morphs.
- **Anchors:** crown/nape/neck-base (constrained to the largest body component to
  avoid skull cavities), clavicle collar pair, right-side armpit, wrist/thigh limb
  loops, bust/bum peak pairs, side-balance pairs at each level — feeding the back
  arcs, geodesics (welded mesh, `igl.exact_geodesic`), point pairs and angles.

## MPFB test-set generator + stress suite

`scripts/gen_mpfb_testset.py` (+ `scripts/run_mpfb_gen.sh`) drives **MPFB2 headless**
(Blender 5.1 `--background`; MPFB output is CC0) to emit a varied body-type grid:

```bash
scripts/run_mpfb_gen.sh .temp/testset        # full curated grid (~22 bodies)
scripts/run_mpfb_gen.sh .temp/testset 8      # cap to 8 bodies
```

It sweeps single macro axes (weight / height / cupsize / gender / muscle / race) off
a fixed base — so the cross-body tests get clean one-variable groups — and writes each
body as `<id>.glb` plus `manifest.json` (id → macro sliders). Macro shape keys are
baked into the mesh basis before glTF export (otherwise the morphs export as glTF
morph targets and every body loads identical). The height slider is capped at 0.75
(~1.95 m); 1.0 yields a ~2.3 m giant outside the sane range.

The stress suite (skips cleanly when `.temp/testset` is absent):

- `tests/mpfb_ingest/test_testset_assets.py` — every `.glb` loads, is Y-up, grounded,
  NaN-free, unit-detects to plausible stature; manifest matches the set on disk.
- `tests/mpfb_ingest/test_stress_testset.py` — every body emits a complete, in-range,
  ordered measurement set; generation never crashes; and measurements track the
  sliders (**weight↑⇒waist↑, height↑⇒stature↑, cup↑⇒bust↑, male⇒broader shoulders**).
- `tests/mpfb_ingest/test_stress_glb.py` — the same end-to-end on the real T-pose
  avatar `.temp/avatar_base.glb` (14,517 verts).

## Fixed-index calibration (regression path only)

> The auto path above is the default and needs none of this. The committed
> fixed-index landmarks exist only so `tests/mpfb_ingest/test_calibration_realmesh.py`
> can regression-guard the calibrated base mesh against drift. Use `--landmarks`
> only to reproduce that path.

The fixed-index path relies on `mpfb_ingest/data/makehuman_landmarks.json` mapping
semantic landmark names to **constant vertex indices** on MakeHuman's fixed topology.

### Quick-pass calibration (present)

`scripts/calibrate_landmarks.py` calibrates against MakeHuman's bundled base mesh
(the MPFB extension's `data/3dobjs/base.obj`, 21,833 verts). It:

1. **Strips helper geometry** — keeps only faces within the body vertex range
   (`[0, 13380)`); eyes/teeth/joint-cube helpers are dropped, since they skew the
   bounding box and inject stray slice loops. The result is committed as the
   body-only mesh `mpfb_ingest/data/mpfb_base_body.obj` (13,345 verts).
2. **Finds the torso levels by an anatomical girth scan** (waist = narrowest torso
   slice, hips/bust = the widening below/above it, underbust between).
3. **Takes the waist side-landmarks from MakeHuman's CC0 `measure-waist-circ` ring.**

This yields real geometry for **height, waist, bust, underbust, hips, and
`waist_back_width`** (validated by `tests/mpfb_ingest/test_calibration_realmesh.py`).
On this fixed-index path the remaining back-section widths and geodesic/point anchors
were served by `--fill-defaults`. The **auto path supersedes this** — it computes all
26 fields as real geometry on any mesh (see "Topology-agnostic extraction" above), so
the fixed-index path is now kept solely for regression.

Regenerate the calibration + body mesh with:

```bash
MPFB_BASE_OBJ_DATA="/path/to/mpfb/data" \
  PYTHONPATH=. .venv/bin/python scripts/calibrate_landmarks.py
```

### Using your own MPFB avatar

**Just run the default auto path** (no `--landmarks`). It is topology-agnostic, so a
raw MPFB OBJ/GLB export works directly regardless of vertex count, helper geometry, or
subdivision/proxies — the per-mesh scan finds the landmarks; no index match against
`n_vertices_expected` is required. (Generate a varied set yourself with
`scripts/run_mpfb_gen.sh`.) The fixed-index path below only applies to the calibrated
base topology.

## Draping note (out of scope here)

This module produces the **measurements YAML** only, which is the sole input pattern
*generation* needs. Physical *draping* additionally requires the body OBJ
(`--save-obj`) **and** a body-segmentation JSON plus a `PathCofig.body_seg` extension —
tracked as a separate sibling plan (handoff spec §4.5).
