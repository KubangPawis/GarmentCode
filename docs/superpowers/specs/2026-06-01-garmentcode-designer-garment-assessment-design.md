# Design Spec — Assessment Memo: Can GarmentCode Genuinely Recreate a Designer Fashion Garment?

- **Date:** 2026-06-01
- **Type:** Design spec / blueprint for an internal engineering decision memo
- **Status:** Draft for review
- **Author:** Engineering (assessment of GarmentCode @ `db94b2c`, `pygarment` v2.0.2)

---

## 1. Purpose

Produce an internal engineering decision memo that answers one question with evidence:

> **Can GarmentCode genuinely recreate a designer fashion garment** (case study: the DVF floral chiffon tiered-ruffle maxi dress, `assets/reference/client-ai-tests/TLS/DVF_3008_R1`), and **should we adopt GarmentCode as the garment-reconstruction backend** for a pipeline whose most-upstream input is a multi-view real-garment image scan?

The memo must drive a build decision, not merely describe. It is verdict-first (BLUF), technical, and references repo internals.

### Audience
Internal engineering team deciding pipeline architecture. Assumed comfortable with 3D/cloth-sim concepts, Python, and reading repo structure. Not the end client.

### Out of scope
- Tutorial on using GarmentCode.
- Re-derivation of the GarmentCode/GarmentCodeData papers.
- Final selection/benchmarking of a specific neural reconstruction model (the memo surveys and frames; a follow-up spike benchmarks).

---

## 2. Success criteria

The memo is done when a reader can, in one pass:

1. State the verdict and its confidence without reading past the first screen.
2. See, per garment feature, whether GarmentCode supports it — and *why* (tied to a concrete library class/param).
3. Apply the feature taxonomy to a **new** garment from the corpus and predict supportability without re-running this analysis.
4. Understand the bridging (image→parameters) problem and why it does not rescue the categorical gaps.
5. Choose among GarmentCode / neural reconstruction / hybrid using the decision framework, with a stated recommendation.

---

## 3. The verdict the memo will defend

**No — GarmentCode cannot genuinely recreate this class of garment.** It can synthesize a *simplified, editable, sewable parametric cousin* (a long-sleeve, fitted-bodice, flared/tiered maxi with a waistband and ruffled cuffs) that shares the silhouette family, but it cannot reproduce the garment's defining intricacy.

The reason is structural, not a tuning problem: GarmentCode is a **forward, parametric generator** over a **fixed garment-program library** of largely **symmetric, single-layer** staples, and it models **no fabric appearance** (print/sheer/lurex). The dress's defining traits are *categorical gaps* — there is nothing in the design vocabulary to map them onto — not merely out-of-range parameters.

**Recommendation (to be argued in §7):** Do not use GarmentCode as a fidelity-preserving reconstruction backend for designer/couture corpus items. Use it only where the goal is a clean, editable, sewable parametric stand-in re-skinned with the scanned texture. For faithful digital twins, route couture-class garments to a garment/cloth neural-reconstruction path; consider a hybrid that triages by garment complexity.

Confidence: **High** for the categorical-gap claims (verified against library source); **Medium** for effort estimates in §7.

---

## 4. Document structure (final memo)

Order is fixed (verdict-first). Each section lists its job and the evidence it must cite.

### §0 Executive verdict (≤1 screen)
- The verdict (§3) in one paragraph + one-line recommendation + confidence.
- A 4–6 row "at a glance" mini-table of the most damning features (tied bow, two-layer sheer, cascading ruffles, print) marked ❌.

### §1 Context & scope
- What was assessed and at what commit/version.
- The DVF dress as the test case; one annotated description of its construction.
- Definition of the fidelity bar: what "genuinely recreate" means here (visual + constructional fidelity sufficient for a digital twin, vs. "evokes the same silhouette").

### §2 How GarmentCode works — the constraint that matters
- Forward/procedural: `parameters → garment`. Inputs are YAML design params + YAML body measurements (scalars); output is a 2D sewing-pattern JSON (+ SVG/PNG/PDF), optionally draped to a 3D mesh via the Warp sim.
- Design space = a **fixed library of garment programs** composed by `MetaGarment` = one `upper` + one `bottom` + one `wb` (belt). Single-layer by construction.
- No appearance model: print/sheer/lurex are not pattern concepts; texture is an out-of-band render step (`texture_utils`, pyrender).
- Conclusion of section: the library + `MetaGarment` topology *is* the expressivity ceiling.

### §3 Case study — the DVF dress teardown (centerpiece)
- Feature-by-feature decomposition with a support matrix. Columns: Feature | Verdict | Closest library capability | Note.
- Verdict legend: ✅ supported · 🟡 out-of-range (param/range gap, extendable by tuning) · ❌ categorical gap (no vocabulary; needs new code or impossible).
- Matrix content (authoritative — verified against source):

  | Feature in the image | Verdict | Closest library capability |
  |---|---|---|
  | Maxi A-line / full skirt silhouette | ✅ | `circle_skirt.SkirtCircle`, `skirt_paneled.SkirtManyPanels` |
  | Fitted bodice + waist seam | ✅ | `bodice.FittedShirt` / `bodice.BodiceHalf` |
  | Long sleeves | ✅ | `sleeves.Sleeve` |
  | Round neckline | ✅ | `collars` (front/back collar set) |
  | Tiered (stacked-level) skirt | ✅ | `skirt_levels.SkirtLevels` |
  | Asymmetric high-low hem | 🟡 | `circle_skirt.AsymmSkirtCircle` — exists, but *separately* from tiers |
  | Single flared / ruffled cuff | 🟡 | `sleeves` `connect_ruffle` + `cuff` (one ruffle, `CuffBand`/`CuffSkirt`) |
  | Flat waist-band piece | 🟡 | `bands.StraightWB` / `FittedWB` (a band, not a tie) |
  | Multi-tier cascading ruffle sleeves (2–3 stacked flounces) | ❌ | none |
  | Cascading diagonal ruffle-wrap overlay on skirt | ❌ | none |
  | Asymmetric AND tiered AND cascading simultaneously | ❌ | no such composition |
  | Tied sash bow with hanging tails | ❌ | a knotted bow is a draped/posed result, not a pattern |
  | Keyhole / plunging slit neckline | ❌ | collars limited to V-neck / square / turtle / lapel / hood |
  | Two-layer sheer overlay over opaque slip | ❌ | single-layer; `MetaGarment` = one upper + one bottom + one belt |
  | Floral print + lurex shimmer + sheer chiffon look | ❌ | not a pattern concept; texture/material/render only |
  | Soft fluttering chiffon drape | 🟡 | sim material setting; chiffon flutter is hard for cloth sim generally |

- Narrative after the table: cluster the ❌ rows and explain each is a *vocabulary* gap. Emphasize the ❌ traits are the visually defining ones.

### §4 Generalized taxonomy — scaling to the corpus
- Reframe the dress findings into garment-feature **axes** so future corpus items can be classified without re-deriving:
  - **Symmetry** — symmetric ✅ / mild asymmetry 🟡 / structural asymmetry ❌
  - **Layering** — single layer ✅ / lining-as-second-garment 🟡(via 2 runs, no registration) / integrated sheer-over-slip ❌
  - **Ruffles/gathers** — single edge ruffle (`ruffle` interface param) ✅ / one cuff or level ruffle 🟡 / multi-tier cascade ❌
  - **Closures & ties** — seam/dart ✅ / flat band 🟡 / tied knot/bow, draped tie ❌
  - **Necklines/collars** — V/square/turtle/lapel/hood ✅ / variants 🟡 / keyhole/slit/complex ❌
  - **Appearance** — solid color (render) 🟡 / any print, sheer, metallic ❌ (out-of-band texture only)
  - **Drape/fabric** — stable wovens ✅ / soft fabrics 🟡 / chiffon flutter & fine gathers ❌-ish (sim limits)
- Each axis: definition, GarmentCode position, where the corpus likely lands.
- Deliver a one-line heuristic: *"If a garment's identity rests on any ❌ axis, GarmentCode reproduces its silhouette but not its identity."*

### §5 The bridging problem (image → parameters)
- GarmentCode is forward-only; the pipeline needs the inverse `images → design+body params`. That inverse model is **not in the repo** (`pattern_fitter.py` only refits a chosen design to body sizes).
- Why bridging does not rescue the gaps: a perfect inverse model can only emit parameters the forward model accepts → ❌ features are silently collapsed to nearest staples.
- GarmentCodeData's stated purpose (garment reconstruction) means the dataset exists to *train* such inverse models — relevant if we pursue the supported subset.
- Appearance is bridged separately (project scanned texture onto UVs); does not recover construction.

### §6 Cost of closing the gaps
- What extending the garment-program library buys: new `Component`/`Panel` classes can add e.g. cascading ruffle tiers, keyhole collars, asymmetric tiered overlays — per-construction-type engineering.
- What extension **cannot** buy: fabric print/sheer/lurex (appearance, not pattern), true integrated multi-layer interaction, physically tied knots/bows (posing/sim artifact).
- Rough effort shape (Medium confidence): per new garment-feature class = design + panel geometry + interfaces + stitching + sim labels + validation; multiply by feature diversity of the corpus. Frame as "library R&D track," not a config change.

### §7 Alternatives & decision framework
- Options:
  1. **GarmentCode-only** — clean/editable/sewable; fidelity capped at library; best for staples.
  2. **Neural garment/cloth reconstruction** (multi-view → surface) — high fidelity to arbitrary garments; output is messy, non-editable, non-sewable mesh.
  3. **Hybrid / triage** — classify garment complexity; route staples to GarmentCode (editable), couture to reconstruction (faithful); optionally fit GarmentCode params to a reconstructed mesh for editability where it helps.
  4. **Photogrammetry + sewability post-process** — faithful capture then infer seams; heavy, separate.
- Decision table keyed on the real axis: **fidelity-to-original vs. editability/sewability/parametric control**.
- Recommendation: comparative table + a committed recommendation (hybrid triage; GarmentCode for the supported subset only). State the trigger that would change the recommendation (e.g., if corpus is ≥80% staples).

### §8 Appendix
- Library inventory: classes per garment program file (`tee`, `bodice`, `sleeves`, `collars`, `bands`, `skirt_paneled`, `circle_skirt`, `skirt_levels`, `godet`, `pants`, `meta_garment`, `base_classes`).
- Key repo paths and entry points (`gui.py`, `test_garmentcode.py`, `test_garment_sim.py`, `pattern_sampler.py`, `pattern_data_sim.py`).
- References: GarmentCode (SIGGRAPH Asia 2023), GarmentCodeData (ECCV 2024), repo, NvidiaWarp-GarmentCode fork.

---

## 5. Evidence basis (verified facts the memo relies on)

- `MetaGarment` (`assets/garment_programs/meta_garment.py`) composes exactly one `upper` + one `bottom` + one `wb` from named classes — single-layer topology.
- Collar vocabulary (`collars.py`): `VNeckHalf`, `SquareNeckHalf`, `NoPanelsCollar`, `Turtle`, `SimpleLapel`, `Hood2Panels` — no keyhole/slit.
- Sleeve ruffle support (`sleeves.py`): `connect_ruffle` at opening + one `cuff` with `top_ruffle`; cuff types from `bands` — single ruffle, not stacked tiers.
- Skirt vocabulary: `SkirtLevels` (tiers), `AsymmSkirtCircle` (asymmetry) exist as *separate* classes; no combined cascading asymmetric tiered overlay.
- Bands (`bands.py`): `StraightWB`, `FittedWB`, `CuffBand`, `CuffSkirt` — flat bands; no tied/knotted sash.
- Output is a 2D sewing pattern (`*_specification.json` + SVG/PNG/PDF via `pattern/wrappers.py`); 3D mesh only from the optional Warp sim (`meshgen/`).
- No appearance/print modeling in pattern generation; texture is render-side.

---

## 6. Style & format constraints

- Markdown, single file, self-contained. Length scaled to substance (target ~1,500–2,500 words + the matrix/tables).
- BLUF: verdict and recommendation before any deep evidence.
- Every ❌/🟡 claim cites a concrete class/param or states "no such capability."
- Use the legend ✅ / 🟡 / ❌ consistently.
- Tone: direct, no hedging beyond stated confidence levels.

### Final-artifact decision (to confirm at review gate)
This spec is the blueprint. Two options for the implementation step:
- **(a)** Treat this spec as the outline; writing-plans → write the full prose memo as the deliverable.
- **(b)** This spec is detailed enough that the memo can be written in one pass.
Default: **(a)** — proceed through writing-plans to produce the full memo at `docs/garmentcode-designer-garment-assessment.md` (final location TBD with user).

---

## 7. Open questions for reviewer

1. Final location/filename of the *memo* (vs. this spec): `docs/` root, or alongside the spec?
2. §7 recommendation — commit to "hybrid triage," or keep it comparative and let the team decide?
3. Is an effort/T-shirt-size estimate in §6 wanted, or omit to avoid over-promising?
4. Corpus composition: roughly what fraction is couture-class vs. staples? (Sharpens the §8 recommendation trigger.)
