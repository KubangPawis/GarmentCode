# mpfb_drape — fit + drape garments onto a normalized MPFB body

The third and final pipeline stage: takes a **normalized, true-T-pose MPFB body**
(produced by `mpfb_tpose` → `mpfb_ingest`) plus a set of GarmentCode design YAMLs and
**fits and drapes each garment** via GarmentCode's native Warp cloth simulator.
Scope: many designs × one body (dress one avatar in a wardrobe).

```
mpfb_tpose  ──▶  mpfb_ingest ──▶  mpfb_drape
(T-pose .glb)    (body .yaml/.obj)   fit pattern ──▶ Warp sim ──▶ *_sim.obj/.glb
                                                                    wardrobe_manifest.json
```

## Module files

```
mpfb_drape/
  bodyseg.py    derive_thresholds + geometric body segmentation (arms/legs/torso/face)
  body_stage.py stage_body — copy body .obj/.yaml into GarmentCode bodies dir + write bodyseg JSON
  fit.py        fit_pattern — BodyParameters + design → MetaGarment → *_specification.json
  verify.py     acceptance — sanity + penetration + settle verdict from sim stats + draped OBJ
  manifest.py   aggregate per-design results → wardrobe_manifest.json
  pipeline.py   drape_one + drape_wardrobe — top-level orchestration
```

### bodyseg.py

GarmentCode's bundled `ggg_body_segmentation.json` is vertex-index-bound to its own
`mean_all` body (23,752 verts) and is invalid for an arbitrary MPFB avatar.
`bodyseg.py` derives a `{body, left_arm, right_arm, left_leg, right_leg, face_internal}`
segmentation in the **avatar's own topology**, geometrically:

- `derive_thresholds` estimates the torso half-width from a band of vertices just below
  the armpit (P97 of |X|); vertices extending beyond that threshold are labelled as arms.
- Legs are split below mid-stature (left vs right by X sign).
- `arms_detected(seg)` reports whether lateral arms were found — the guard that enforces
  the T-pose requirement (see Pose convention below).

**Key limitation:** the geometric heuristic requires a **true T-pose** body
(`arm_pose_angle ≈ 0`). On an arms-down / A-pose body the arms are not laterally
separable from the torso and segmentation silently under-labels them.

### body_stage.py

`stage_body(body_obj, body_yaml, out_dir, name=None)` copies the avatar `.obj` + `.yaml`
into GarmentCode's `assets/bodies/` directory (the path `PathCofig` reads from
`system.json` at construction) under a namespaced name and writes `<name>_bodyseg.json`
alongside. Returns the staged paths and the `arms_detected` flag. `pipeline.py` uses the
`_mpfbdrape_<stem>` prefix so the staged files can never collide with a bundled body;
they are removed in a `finally` block after the sim completes.

### fit.py

`fit_pattern(body_name, design_yaml, out_dir)` loads `BodyParameters` from the staged
YAML, instantiates `MetaGarment`, and serializes the 2-D pattern as
`<name>_specification.json`. No 3-D sim yet — this is the pure fit/pattern step.

### verify.py

`acceptance(sim_stats, draped_obj, body_obj)` computes the acceptance verdict from three
checks:

- **Sanity** — draped mesh is finite, non-empty, and its bounding box sits within the
  body's bounding box (computed from the draped OBJ).
- **Penetration** — body intersections and self-intersections are read from the stats
  dict `run_sim` writes.
- **Settle** — convergence flag from the same stats dict.

**Unit note:** the draped `*_sim.obj` is in **centimetres** while the body collider OBJ
is in **metres** (the sim scales the body ×100 internally). `verify.py` accounts for
this scale difference when comparing bounding boxes.

### manifest.py

Aggregates per-design dicts into `wardrobe_manifest.json`:

```json
{
  "body": "<name>",
  "designs": [ { "design": "...", "verdict": "pass|fail", ... }, ... ],
  "summary": { "total": N, "passed": N, "failed": N }
}
```

### pipeline.py

`drape_one(body_yaml, design_yaml, out_dir, ...)` — full single-design pipeline:

1. `fit_pattern` → 2-D specification JSON
2. `stage_body` → staged OBJ + bodyseg JSON
3. Build `PathCofig` with `body_seg` injected
4. `template_simulation` (native Warp `run_sim`)
5. `acceptance` → verdict

`drape_wardrobe(body_yaml, designs, out_dir, ...)` resolves a designs directory (every
`*.yaml`) or an explicit list, calls `drape_one` per design, then writes the manifest.

If the body is not a true T-pose (`arms_detected` is False), `drape_one` raises a clear
error before entering the Warp sim.

## CLI usage

```bash
.venv/bin/python drape_mpfb_garment.py \
    --body  assets/bodies/avatar.yaml \
    --designs assets/design_params/ \
    --out   .temp/wardrobe \
    [--body-obj path/to/avatar.obj] \
    [--sim-props path/to/sim_props.yaml]
```

- `--body` — `mpfb_ingest` measurements YAML. The sibling `<body>.obj` is used as the
  collision mesh unless `--body-obj` overrides it.
- `--designs` — a directory (every `*.yaml` is draped) or one or more explicit files.
- `--out` — output root; one sub-folder per design is created automatically.
- `--sim-props` — defaults to `assets/Sim_props/mpfb_drape_sim_props.yaml`.

The avatar is staged automatically into GarmentCode's bodies dir (under a namespaced
`_mpfbdrape_<stem>` name to avoid collisions) and cleaned up after each design.
GarmentCode's preview render (front/back PNGs) runs per design as part of
`template_simulation`; a render-off batch-speed mode is documented future work.

## Pose convention — T-pose required

Ingest the avatar with `--arm-pose-angle 0` (MPFB exports a true T-pose via `mpfb_tpose`).
Arms-down / A-pose bodies are **not supported**: `pipeline.py` rejects them with a clear
error rather than crashing deep inside the Warp sim.

## Sim preset

`assets/Sim_props/mpfb_drape_sim_props.yaml` is tuned for avatar dressing:

| Setting | This preset | Bundled default | Rationale |
|---|---|---|---|
| `body_collision_thickness` | **1.0** cm | 0.25 cm | GarmentCode custom-body guide recommends ~1.2 cm |
| `max_body_collisions` | **50** | 35 | extra margin for full-wardrobe draping |
| `optimize_storage` | **false** | true | keep all artifacts (OBJ, GLB, segmentation) |

On the bundled `mean_all_tpose` body a t-shirt settles at ~35 body intersections and
0 self-intersections (well within the acceptance bar).

## Outputs

Per design (inside `--out/<design_name>/`):

- `*_sim.obj` — draped garment mesh (centimetres)
- `*_sim.glb` — draped garment GLB
- `*_boxmesh.obj` — bounding-box collision proxy
- `*_sim_segmentation.txt` — GarmentCode panel segmentation
- material + fabric files

Top-level:

- `wardrobe_manifest.json` — aggregated pass/fail summary across all designs

## Tests

**Fast unit tests** (CPU, no CUDA or Blender required):

```bash
.venv/bin/python -m pytest tests/mpfb_drape -q --ignore=tests/mpfb_drape/test_end_to_end.py
```

Covers bodyseg (against the real bundled `mean_all_tpose` body), body_stage, fit,
verify, manifest, pipeline, and CLI.

**Gated end-to-end test** (`tests/mpfb_drape/test_end_to_end.py`) — runs the real Warp
drape of a t-shirt onto the bundled true-T-pose body and asserts the verdict passes.
Skipped automatically unless CUDA is available:

```bash
.venv/bin/python -m pytest tests/mpfb_drape/test_end_to_end.py -v
```

## Drape variance

GPU cloth simulation is non-deterministic: a given design may settle at slightly
different body-penetration counts from run to run, so a per-design verdict in the
wardrobe manifest may occasionally FAIL on a design that passes on a re-run. If a
design fails, re-running `drape_one` (or re-invoking the CLI) is sufficient to
recover an accepted drape in most cases. As a documented future enhancement, the
wardrobe driver (`drape_wardrobe`) could auto-retry failed designs rather than
requiring a manual re-drape.

## Known limitations / future work

- **Combined dressed-avatar GLB** (garment + body merged into a single file) — the
  eventual Zeelum end product; planned as a fast-follow.
- **One design × many bodies** (grading across a body grid) — not in scope here; the
  primitive `drape_one` is `(design, body)` and could be fan-out driven.
- **Rig-based body segmentation** — using the game-engine rig bone weights for
  precise arm/leg labelling; current geometric heuristic is sufficient for T-pose
  collision filtering but may mis-label outer shoulders as arm.
- **A-pose / arbitrary pose bodies** — unsupported; requires a pose-aware segmentation
  strategy not yet designed.
