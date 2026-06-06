# mpfb_ingest — MPFB/MakeHuman → GarmentCode body-measurement ingestion

Reads an MPFB/MakeHuman body mesh (OBJ) and emits a GarmentCode body-measurements
YAML (the 26 base fields), so GarmentCode can fit/drape garments on custom MPFB
avatars instead of only the bundled SMPL-derived bodies.

```
OBJ ──load/normalize──▶ cm mesh ──landmarks + geometry──▶ 26 measurements
                                                              │
                                          BodyParameters.save ▼
                                            assets/bodies/<name>.yaml
```

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

```bash
.venv/bin/python ingest_mpfb_body.py path/to/avatar.obj \
    --name my_avatar \
    --landmarks mpfb_ingest/data/makehuman_landmarks.json \
    --arm-pose-angle 0 \
    --out assets/bodies \
    --save-obj
```

- `--landmarks` — the calibrated MakeHuman vertex-index JSON (see "Calibration" below).
- `--arm-pose-angle` — `0` for a T-pose MPFB avatar (see above).
- `--height-m` — known stature in metres; overrides the height-from-extent heuristic.
- `--save-obj` — also write the normalized metres OBJ (needed for *draping*, below).
- `--fill-defaults` — backfill not-yet-calibrated fields with neutral-body values
  (from `mean_all.yaml`) so emit passes while landmark calibration is incomplete.

The result `assets/bodies/<name>.yaml` is consumed directly by pattern generation via
`MetaGarment(name, body, design)`.

## Calibration (asset-gated)

Measurement extraction relies on `mpfb_ingest/data/makehuman_landmarks.json` mapping
semantic landmark names to **constant vertex indices** on MakeHuman's fixed topology.
That file is produced by a one-time calibration against a real MPFB export OBJ and is
**not yet present** — until it is, run with `--fill-defaults` (and a minimal landmarks
JSON enabling only `height`) for a smoke-level result.

## Draping note (out of scope here)

This module produces the **measurements YAML** only, which is the sole input pattern
*generation* needs. Physical *draping* additionally requires the body OBJ
(`--save-obj`) **and** a body-segmentation JSON plus a `PathCofig.body_seg` extension —
tracked as a separate sibling plan (handoff spec §4.5).
