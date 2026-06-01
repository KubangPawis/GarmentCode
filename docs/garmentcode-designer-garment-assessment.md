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

## §2 How GarmentCode works — the constraint that matters

## §3 Case study — the DVF dress teardown

## §4 Generalized taxonomy — scaling to the corpus

## §5 The bridging problem (image → parameters)

## §6 Cost of closing the gaps

## §7 Alternatives & decision framework

## §8 Appendix
