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

## §4 Generalized taxonomy — scaling to the corpus

## §5 The bridging problem (image → parameters)

## §6 Cost of closing the gaps

## §7 Alternatives & decision framework

## §8 Appendix
