# Can GarmentCode Genuinely Recreate a Designer Fashion Garment?
*Internal engineering decision memo*

- **Date:** 2026-06-01
- **Assessed:** GarmentCode @ commit `db94b2c`, `pygarment` v2.0.2
- **Case study:** DVF floral chiffon tiered-ruffle maxi dress (`DVF_3008_R1`)
- **Decision:** Whether to adopt GarmentCode as the garment-reconstruction backend for an image-scan → 3D-garment pipeline.
- **Confidence:** High on categorical-gap claims (verified against library source); Medium on effort estimates.

## §0 Executive verdict

**No — GarmentCode cannot genuinely recreate this class of garment.** Pointed at the DVF floral chiffon tiered-ruffle maxi dress, the best it can produce is a *simplified, editable, sewable parametric cousin*: a long-sleeve, fitted-bodice, flared/tiered maxi with a flat waistband and ruffled cuffs that shares the silhouette family — and nothing more. The traits that make the dress *that dress* (the sheer-over-slip layering, the cascading tiered ruffles, the tied sash, the print and lurex shimmer) are absent from the output, not merely approximated.

This is a structural limit, not a tuning problem. GarmentCode is a forward parametric generator that draws from a fixed, largely symmetric, single-layer garment-program library and carries no fabric-appearance model. The dress's defining traits therefore land as *categorical gaps* — there is no design vocabulary to map them onto — rather than out-of-range parameters that more careful tuning could reach.

**Recommendation:** Do **not** adopt GarmentCode as a fidelity-preserving reconstruction backend for couture-class items. Use it only where the deliverable is a clean, editable parametric stand-in re-skinned with the scanned texture; route faithful digital twins to a neural garment/cloth reconstruction path; and prefer a **hybrid triage** that routes by garment complexity (full argument in §7).

The most damning, defining traits — each a categorical gap:

| Defining trait of the dress | GarmentCode |
|---|---|
| Two-layer sheer overlay over opaque slip | ❌ |
| Multi-tier cascading ruffle sleeves & hem | ❌ |
| Tied sash bow with hanging tails | ❌ |
| Floral print + lurex shimmer + sheer chiffon | ❌ |
| Keyhole / plunging slit neckline | ❌ |

## §1 Context & scope

We assessed GarmentCode at commit `db94b2c` against the published `pygarment` v2.0.2 library. The concrete test case is the DVF floral chiffon tiered-ruffle maxi dress catalogued as `DVF_3008_R1`. We picked it deliberately: it is a representative designer/couture item, not a staple, and it exercises nearly every dimension where a parametric pattern generator can fail.

Its construction, annotated: a printed sheer chiffon shell shot through with lurex thread; a round neck broken by a deep keyhole/plunging slit; long bell sleeves finished with stacked ruffle flounces rather than a single cuff; a fitted bodice joined to the skirt at a waist seam; a tied sash bow with hanging tails at the waist; and an asymmetric high-low, tiered, cascading ruffle skirt that reads as a *sheer overlay* draped over a separate opaque yellow slip. The garment's identity lives in the combination of these features, not in any one of them.

The fidelity bar for this memo is deliberately strict. "Genuinely recreate" means **visual and constructional fidelity sufficient to stand in as a digital twin** of *this* garment — the layering, the ruffle cascade, the tie, the print all present and correct. It does **not** mean "produces something that evokes the same silhouette family." A long-sleeve fitted maxi that omits the layering, the cascade, the tie, and the print is a different garment that happens to share an outline; under our bar that is a failure, not a near-miss.

## §2 How GarmentCode works — the constraint that matters

GarmentCode is a **forward, procedural generator**: the data flow is strictly `parameters → garment`. Its inputs are a YAML file of design parameters plus a YAML file of body measurements (scalars such as bust, waist, height). Its output is a 2D **sewing-pattern specification** as JSON, rendered to SVG/PNG/PDF through `pattern/wrappers.py`. There is no 3D mesh in the core pipeline; a mesh exists *only* if you additionally run the optional NVIDIA Warp cloth simulation under `meshgen/`, which drapes the flat pattern onto a body. Nothing in this path runs backward — there is no `image → parameters` inference (see §5).

The design space is not open-ended. It is a **fixed library of garment programs** that are composed by a single top-level class, `MetaGarment` (`assets/garment_programs/meta_garment.py`). `MetaGarment` assembles exactly one `upper` (bodice/shirt/tee), one `bottom` (skirt or pants), and one `wb` (waistband/belt). That is the entire topology: one upper, one bottom, one band. By construction this is **single-layer** — there is no slot for a second, independently-draped garment such as a sheer overlay over a slip. Whatever a garment "is," it must be expressible as one upper plus one bottom plus one band drawn from the library's named classes.

There is also **no appearance model**. Print, sheer, and lurex are not pattern concepts anywhere in the generator — the pattern knows panels, seams, and interfaces, not what the fabric looks like. Appearance is handled entirely out-of-band as a rendering step: texture is projected onto the mesh's UVs via `texture_utils` and pyrender, after the pattern already exists.

The point to carry forward: the library of garment programs plus the `MetaGarment` one-upper/one-bottom/one-band topology *is* the expressivity ceiling. Everything the rest of this memo concludes follows from reading the garment against that ceiling — if a feature has no class in the library and no place in that topology, no amount of parameter tuning produces it.

## §3 Case study — the DVF dress teardown

This is the centerpiece. We decompose the dress feature by feature and judge each against the library, using a three-symbol legend that the rest of the memo reuses unchanged.

> Legend: ✅ supported · 🟡 out-of-range (param/range gap, extendable by tuning) · ❌ categorical gap (no vocabulary; needs new code or impossible).

| Feature in the image | Verdict | Closest library capability |
|---|---|---|
| Maxi A-line / full skirt silhouette | ✅ | `circle_skirt.SkirtCircle`, `skirt_paneled.SkirtManyPanels` |
| Fitted bodice + waist seam | ✅ | `bodice.FittedShirt` / `bodice.BodiceHalf` |
| Long sleeves | ✅ | `sleeves.Sleeve` |
| Round neckline | ✅ | `collars` (front/back collar set) |
| Tiered (stacked-level) skirt | ✅ | `skirt_levels.SkirtLevels` |
| Asymmetric high-low hem | 🟡 | `circle_skirt.AsymmSkirtCircle` — exists, but separately from tiers |
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

Read top to bottom, the matrix splits cleanly. The ✅ rows are the garment's *generic* properties — it is long-sleeved, fitted at the bodice, full and tiered in the skirt, round at the neck. These are exactly the staples the library was built around, so each maps onto a named class (`Sleeve`, `FittedShirt`/`BodiceHalf`, `SkirtLevels`, the `collars` set). The 🟡 rows are features the library *gestures at* but cannot reach in the configuration the dress needs: `AsymmSkirtCircle` gives asymmetry and `SkirtLevels` gives tiers, but they are separate classes that do not compose; `connect_ruffle` plus a cuff gives *one* ruffle, not a stack; `StraightWB`/`FittedWB` give a flat band where the dress has a knotted sash. These are reachable in principle by writing more code (§6), not by tuning an existing parameter.

The ❌ rows cluster into six themes, and each is a *vocabulary* gap — there is simply nothing in the design language to map the feature onto, so the question "what parameter value produces it?" has no answer:

- **Structural asymmetry combined with tiering and cascade.** The library has asymmetry (`AsymmSkirtCircle`) and tiering (`SkirtLevels`) as disjoint classes; the dress needs them fused with a diagonal cascade, and there is no composite class that expresses all three at once.
- **True layering.** `MetaGarment`'s one-upper/one-bottom/one-band topology has no slot for a second, independently-draped garment, so a sheer overlay registered over an opaque slip cannot be represented at all.
- **Cascade ruffles.** Sleeve ruffling is a single `connect_ruffle`/cuff event and skirt levels stack vertically; neither produces the stacked-flounce cascade on the sleeves nor the diagonal ruffle-wrap on the skirt.
- **Draped ties.** A tied sash bow with hanging tails is a posed/draped result of manipulating fabric, not a flat pattern piece; `bands` only emits flat straight or fitted bands.
- **Complex necklines.** `collars.py` tops out at V-neck, square, turtle, lapel, and hood — a keyhole or plunging slit is not in the set.
- **Appearance.** Floral print, lurex shimmer, and sheer chiffon are not pattern concepts anywhere; the generator has no place to record them.

The punchline is uncomfortable and decisive: the ❌ rows are precisely the features that make this dress visually distinctive. The ✅ rows describe a generic long-sleeve tiered maxi that a hundred other garments also satisfy. So when GarmentCode runs, the *silhouette family* survives — and the garment's *identity* does not.

## §4 Generalized taxonomy — scaling to the corpus

The dress teardown generalizes. Rather than re-running a full analysis for every corpus item, we lift the findings into seven reusable **feature axes**. For each axis, GarmentCode occupies a position on a ✅/🟡/❌ scale (same legend as §3), and any new garment can be scored axis by axis. The axes:

| Axis | ✅ Supported | 🟡 Out-of-range | ❌ Categorical gap |
|---|---|---|---|
| Symmetry | symmetric panels | mild asymmetry | structural asymmetry |
| Layering | single layer | lining as a 2nd separate garment (2 runs, no registration) | integrated sheer-over-slip |
| Ruffles / gathers | single edge ruffle (`ruffle` interface param) | one cuff or one skirt level | multi-tier cascade |
| Closures & ties | seam / dart | flat band (`StraightWB`) | tied knot / bow / draped tie |
| Necklines / collars | V / square / turtle / lapel / hood | minor variants | keyhole / slit / sculpted |
| Appearance | solid color (render-side) | — | any print, sheer, metallic |
| Drape / fabric | stable wovens | soft fabrics | chiffon flutter, fine gathers |

Each row names a real construction concern. The first asks whether the garment's panels mirror left-to-right; GarmentCode is built around symmetric panels and only mildly tolerant of off-center construction, with no representation for a structurally one-sided cut. The second asks whether the garment is one shell or several interacting layers; the generator is single-layer, and the most it can do is run twice for an unregistered lining, never an integrated sheer-over-slip. The third distinguishes a single gathered edge (the `ruffle` interface param) from one localized gather (a cuff or one skirt level) from a stacked cascade, which has no class. The fourth separates structural seams and darts from flat bands (`StraightWB`) from draped knots and bows, which are posed artifacts rather than pattern pieces. The fifth is bounded by the fixed `collars` set, so anything sculpted or slit falls off the end. The sixth is render-side only — solid color survives, but any print, sheer, or metallic finish is not a pattern concept at all. The seventh captures how forgiving the cloth sim is: stable wovens behave, soft fabrics are harder, and fine chiffon flutter is at the edge of what cloth sim does well in general.

This gives a one-line decision rule:

> **If a garment's identity rests on any ❌ axis, GarmentCode reproduces its silhouette but not its identity.**

To apply the table to a new corpus item, score it once on each of the seven axes — symmetric or not, single-layer or layered, which ruffle/tie/neckline/appearance/drape class it needs — then ask where its *defining* features sit. If everything that matters is ✅ (and at worst 🟡, closeable by tuning or modest extension), GarmentCode is a reasonable backend for that item. The moment a feature the garment is known *for* lands on ❌, the heuristic fires: the output will share an outline and lose the thing that made the garment worth scanning.

## §5 The bridging problem (image → parameters)

## §6 Cost of closing the gaps

## §7 Alternatives & decision framework

## §8 Appendix
