# GarmentCode Designer-Garment Assessment Memo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write a single, self-contained internal engineering decision memo answering whether GarmentCode can genuinely recreate a designer fashion garment (DVF dress case study) and whether to adopt it as a reconstruction backend.

**Architecture:** A prose deliverable, not code. The memo is built section-by-section in the order fixed by the spec (verdict-first / BLUF). Each task writes one section (or a tight cluster), runs an acceptance check (grep/read assertions instead of unit tests, since markdown has no runtime), and commits. The authoritative content — verdict, the DVF teardown matrix, the taxonomy axes, and verified repo facts — already lives in the approved spec; this plan turns it into finished prose.

**Tech Stack:** Markdown. Verification via `grep`/`rg` and manual read. Git for commits. Source of truth: `docs/superpowers/specs/2026-06-01-garmentcode-designer-garment-assessment-design.md`.

**Deliverable:** `docs/garmentcode-designer-garment-assessment.md`

**Resolved defaults (from spec §7 open questions):**
- Memo location: `docs/garmentcode-designer-garment-assessment.md` (repo `docs/` root).
- §7 recommendation: **commit to hybrid triage**, with a conditional corpus-mix trigger.
- §6: **include** a T-shirt-size effort estimate, explicitly tagged Medium confidence.
- Corpus mix: unknown — frame the recommendation trigger conditionally (no hard fraction asserted).

**Legend used throughout the memo (define once, in §3):** ✅ supported · 🟡 out-of-range (param/range gap, extendable by tuning) · ❌ categorical gap (no vocabulary; needs new code or impossible).

---

## File Structure

| File | Responsibility |
|---|---|
| `docs/garmentcode-designer-garment-assessment.md` | The entire memo. Single file, self-contained. |

No other files are created or modified. The spec file is read-only reference.

Memo section map (final headings, fixed order):
- `§0 Executive verdict`
- `§1 Context & scope`
- `§2 How GarmentCode works — the constraint that matters`
- `§3 Case study — the DVF dress teardown` (centerpiece; defines the legend)
- `§4 Generalized taxonomy — scaling to the corpus`
- `§5 The bridging problem (image → parameters)`
- `§6 Cost of closing the gaps`
- `§7 Alternatives & decision framework`
- `§8 Appendix`

---

## Task 1: Scaffold the memo file

**Files:**
- Create: `docs/garmentcode-designer-garment-assessment.md`

- [ ] **Step 1: Write the skeleton (title, metadata, all section headers, empty bodies)**

````markdown
# Can GarmentCode Genuinely Recreate a Designer Fashion Garment?
*Internal engineering decision memo*

- **Date:** 2026-06-01
- **Assessed:** GarmentCode @ commit `db94b2c`, `pygarment` v2.0.2
- **Case study:** DVF floral chiffon tiered-ruffle maxi dress (`DVF_3008_R1`)
- **Decision:** Whether to adopt GarmentCode as the garment-reconstruction backend for an image-scan → 3D-garment pipeline.
- **Confidence:** High on categorical-gap claims (verified against library source); Medium on effort estimates.

## §0 Executive verdict

## §1 Context & scope

## §2 How GarmentCode works — the constraint that matters

## §3 Case study — the DVF dress teardown

## §4 Generalized taxonomy — scaling to the corpus

## §5 The bridging problem (image → parameters)

## §6 Cost of closing the gaps

## §7 Alternatives & decision framework

## §8 Appendix
````

- [ ] **Step 2: Acceptance check — all 9 headers present**

Run: `grep -c '^## §' docs/garmentcode-designer-garment-assessment.md`
Expected: `9`

- [ ] **Step 3: Commit**

```bash
git add docs/garmentcode-designer-garment-assessment.md
git commit -m "docs: scaffold GarmentCode designer-garment assessment memo"
```

---

## Task 2: §0 Executive verdict + at-a-glance table

**Files:**
- Modify: `docs/garmentcode-designer-garment-assessment.md` (`## §0` body)

- [ ] **Step 1: Write the verdict paragraph + recommendation + at-a-glance table**

Content requirements (write as finished prose, ≤1 screen):
- One paragraph stating: **No** — GarmentCode cannot genuinely recreate this class of garment; it produces a *simplified, editable, sewable parametric cousin* (long-sleeve, fitted-bodice, flared/tiered maxi with a waistband and ruffled cuffs) sharing the silhouette family only.
- One sentence on *why it's structural*: forward parametric generator over a fixed, largely symmetric, single-layer library with no appearance model → defining traits are categorical gaps, not tuning gaps.
- One-line recommendation: do **not** use GarmentCode as a fidelity-preserving backend for couture-class items; use it only for editable parametric stand-ins re-skinned with scanned texture; route faithful twins to neural reconstruction; prefer a hybrid triage (full argument in §7).
- The at-a-glance table of the most damning traits:

```markdown
| Defining trait of the dress | GarmentCode |
|---|---|
| Two-layer sheer overlay over opaque slip | ❌ |
| Multi-tier cascading ruffle sleeves & hem | ❌ |
| Tied sash bow with hanging tails | ❌ |
| Floral print + lurex shimmer + sheer chiffon | ❌ |
| Keyhole / plunging slit neckline | ❌ |
```

- [ ] **Step 2: Acceptance check — verdict is BLUF and recommendation present**

Run: `sed -n '/## §0/,/## §1/p' docs/garmentcode-designer-garment-assessment.md | grep -iE 'cannot genuinely|recommend|hybrid'`
Expected: at least the "cannot genuinely" and a recommendation line match.

- [ ] **Step 3: Commit**

```bash
git add docs/garmentcode-designer-garment-assessment.md
git commit -m "docs: write executive verdict (§0)"
```

---

## Task 3: §1 Context & scope and §2 How GarmentCode works

**Files:**
- Modify: `docs/garmentcode-designer-garment-assessment.md` (`## §1`, `## §2` bodies)

- [ ] **Step 1: Write §1 Context & scope**

Content requirements:
- What was assessed and at what commit/version (mirror header).
- The DVF dress as test case: one annotated description of its construction — printed sheer chiffon (with lurex), round neck with deep keyhole slit, long bell sleeves with stacked ruffle flounces, fitted bodice + waist seam, tied sash bow, asymmetric high-low tiered cascading ruffle skirt as a sheer overlay over an opaque yellow slip.
- Define the fidelity bar: "genuinely recreate" = visual + constructional fidelity sufficient for a digital twin, NOT merely "evokes the same silhouette."

- [ ] **Step 2: Write §2 How GarmentCode works — the constraint that matters**

Content requirements:
- Forward/procedural: `parameters → garment`. Inputs are YAML design params + YAML body measurements (scalars). Output is a 2D sewing-pattern JSON (+ SVG/PNG/PDF via `pattern/wrappers.py`); a 3D mesh exists only from the optional Warp sim (`meshgen/`).
- Design space = a fixed library of garment programs composed by `MetaGarment` (`assets/garment_programs/meta_garment.py`) = exactly one `upper` + one `bottom` + one `wb` (belt). Single-layer by construction.
- No appearance model: print/sheer/lurex are not pattern concepts; texture is an out-of-band render step (`texture_utils`, pyrender).
- Close the section explicitly: the library + `MetaGarment` topology *is* the expressivity ceiling — this is the lens for everything that follows.

- [ ] **Step 3: Acceptance check — concrete repo references present**

Run: `sed -n '/## §2/,/## §3/p' docs/garmentcode-designer-garment-assessment.md | grep -E 'MetaGarment|meta_garment.py|wrappers.py|meshgen'`
Expected: matches for `MetaGarment` and at least one file path.

- [ ] **Step 4: Commit**

```bash
git add docs/garmentcode-designer-garment-assessment.md
git commit -m "docs: write context, scope, and GarmentCode constraint sections (§1–§2)"
```

---

## Task 4: §3 DVF dress teardown (centerpiece)

**Files:**
- Modify: `docs/garmentcode-designer-garment-assessment.md` (`## §3` body)

- [ ] **Step 1: Write the legend, the support matrix, and the post-matrix narrative**

First, the legend line (this is where ✅/🟡/❌ are defined):
> Legend: ✅ supported · 🟡 out-of-range (param/range gap, extendable by tuning) · ❌ categorical gap (no vocabulary; needs new code or impossible).

Then the authoritative matrix (copy verbatim — verified against library source):

```markdown
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
```

Then the narrative (finished prose):
- Cluster the ❌ rows into themes: structural asymmetry, true layering, cascade ruffles, draped ties, complex necklines, appearance.
- Argue each ❌ is a *vocabulary* gap (nothing to map onto), not a parameter-range gap.
- State the punchline: the ❌ traits are precisely the visually defining ones — so the silhouette survives but the garment's identity does not.

- [ ] **Step 2: Acceptance check — matrix complete and legend defined**

Run: `sed -n '/## §3/,/## §4/p' docs/garmentcode-designer-garment-assessment.md | grep -c '|'`
Expected: ≥ 18 (16 matrix data rows + header + separator).

Run: `sed -n '/## §3/,/## §4/p' docs/garmentcode-designer-garment-assessment.md | grep -E 'Legend:.*categorical gap'`
Expected: one match.

- [ ] **Step 3: Commit**

```bash
git add docs/garmentcode-designer-garment-assessment.md
git commit -m "docs: write DVF dress teardown matrix and analysis (§3)"
```

---

## Task 5: §4 Generalized taxonomy

**Files:**
- Modify: `docs/garmentcode-designer-garment-assessment.md` (`## §4` body)

- [ ] **Step 1: Write the seven feature axes + heuristic**

Reframe the dress findings into reusable axes. For each axis give: definition, GarmentCode position, where corpus items likely land. Use this axis table:

```markdown
| Axis | ✅ Supported | 🟡 Out-of-range | ❌ Categorical gap |
|---|---|---|---|
| Symmetry | symmetric panels | mild asymmetry | structural asymmetry |
| Layering | single layer | lining as a 2nd separate garment (2 runs, no registration) | integrated sheer-over-slip |
| Ruffles / gathers | single edge ruffle (`ruffle` interface param) | one cuff or one skirt level | multi-tier cascade |
| Closures & ties | seam / dart | flat band (`StraightWB`) | tied knot / bow / draped tie |
| Necklines / collars | V / square / turtle / lapel / hood | minor variants | keyhole / slit / sculpted |
| Appearance | solid color (render-side) | — | any print, sheer, metallic |
| Drape / fabric | stable wovens | soft fabrics | chiffon flutter, fine gathers |
```

- Follow with the one-line heuristic, verbatim:
  > **If a garment's identity rests on any ❌ axis, GarmentCode reproduces its silhouette but not its identity.**
- Add 2–3 sentences on how to apply the table to a new corpus item (classify each axis, then apply the heuristic).

- [ ] **Step 2: Acceptance check — all seven axes and the heuristic present**

Run: `sed -n '/## §4/,/## §5/p' docs/garmentcode-designer-garment-assessment.md | grep -cE 'Symmetry|Layering|Ruffles|Closures|Necklines|Appearance|Drape'`
Expected: `7`

Run: `sed -n '/## §4/,/## §5/p' docs/garmentcode-designer-garment-assessment.md | grep -i 'silhouette but not its identity'`
Expected: one match.

- [ ] **Step 3: Commit**

```bash
git add docs/garmentcode-designer-garment-assessment.md
git commit -m "docs: write generalized designer-garment feature taxonomy (§4)"
```

---

## Task 6: §5 The bridging problem

**Files:**
- Modify: `docs/garmentcode-designer-garment-assessment.md` (`## §5` body)

- [ ] **Step 1: Write the bridging analysis**

Content requirements (finished prose):
- The pipeline's upstream is multi-view images; GarmentCode is forward-only, so the pipeline needs the inverse `images → design+body params`. That inverse model is **not in the repo** — `pattern_fitter.py` only refits an already-chosen design to body sizes.
- The key argument: a *perfect* inverse model can only emit parameters the forward model accepts, so ❌ features are silently collapsed to the nearest staple. Bridging does not raise the ceiling; it just reaches it.
- Note GarmentCodeData's stated purpose (garment reconstruction) — the dataset exists to *train* such inverse models, relevant only for the supported subset.
- Appearance is bridged separately (project scanned texture onto UVs) and recovers look, not construction.
- Include a small ASCII flow showing where the missing inverse step sits and where ❌ collapse happens.

- [ ] **Step 2: Acceptance check — the collapse argument and pattern_fitter note present**

Run: `sed -n '/## §5/,/## §6/p' docs/garmentcode-designer-garment-assessment.md | grep -iE 'pattern_fitter|collapse|inverse'`
Expected: matches for `pattern_fitter` and `inverse`/`collapse`.

- [ ] **Step 3: Commit**

```bash
git add docs/garmentcode-designer-garment-assessment.md
git commit -m "docs: write image-to-parameters bridging analysis (§5)"
```

---

## Task 7: §6 Cost of closing the gaps

**Files:**
- Modify: `docs/garmentcode-designer-garment-assessment.md` (`## §6` body)

- [ ] **Step 1: Write the gap-closing cost analysis with effort estimate**

Content requirements:
- What extending the garment-program library buys: new `Component`/`Panel` classes can add e.g. cascading ruffle tiers, keyhole collars, asymmetric tiered overlays — but this is per-construction-type engineering, not config.
- What extension **cannot** buy, ever: fabric print/sheer/lurex (appearance, not pattern), true integrated multi-layer interaction, physically tied knots/bows (a pose/sim artifact).
- Effort estimate, explicitly tagged **(Medium confidence)**, as a T-shirt-size table:

```markdown
| Gap | Closeable by library work? | Rough effort |
|---|---|---|
| Keyhole / slit necklines | Yes — new collar class | S |
| Multi-tier cascading ruffles (sleeve & hem) | Yes — new ruffle/flounce component | M |
| Asymmetric + tiered + cascading skirt | Yes — new composite skirt class | M–L |
| Integrated two-layer sheer-over-slip | Partly — needs layering model + drape registration | L |
| Tied sash bow with tails | No (pattern); sim/pose only | — |
| Print / sheer / lurex appearance | No (out-of-band texture/render) | — |
```

- One sentence framing: this is a *library R&D track*, and even fully funded it cannot reach the "No" rows — which are among the dress's defining traits.

- [ ] **Step 2: Acceptance check — effort table and confidence tag present**

Run: `sed -n '/## §6/,/## §7/p' docs/garmentcode-designer-garment-assessment.md | grep -iE 'Medium confidence|effort'`
Expected: both match.

- [ ] **Step 3: Commit**

```bash
git add docs/garmentcode-designer-garment-assessment.md
git commit -m "docs: write gap-closing cost and effort estimate (§6)"
```

---

## Task 8: §7 Alternatives & decision framework

**Files:**
- Modify: `docs/garmentcode-designer-garment-assessment.md` (`## §7` body)

- [ ] **Step 1: Write the alternatives, decision table, and committed recommendation**

List the four options with one-line trade-offs:
1. **GarmentCode-only** — clean/editable/sewable; fidelity capped at library; best for staples.
2. **Neural garment/cloth reconstruction** (multi-view → surface) — high fidelity to arbitrary garments; output is messy, non-editable, non-sewable mesh.
3. **Hybrid / triage** — classify garment complexity; staples → GarmentCode (editable), couture → reconstruction (faithful); optionally fit GarmentCode params to a reconstructed mesh where editability helps.
4. **Photogrammetry + sewability post-process** — faithful capture then infer seams; heavy, separate track.

Decision table keyed on the real axis:

```markdown
| Priority | Best fit |
|---|---|
| Editability / sewability / parametric control | GarmentCode |
| Fidelity to an arbitrary intricate original | Neural reconstruction |
| Both, across a mixed corpus | Hybrid triage |
```

Committed recommendation (finished prose):
- **Adopt hybrid triage.** Use GarmentCode only for the supported staple subset (re-skinned with scanned texture); route couture-class items (any garment failing a ❌ axis) to neural reconstruction.
- State the conditional trigger explicitly: *if* the corpus turns out to be overwhelmingly staples (low ❌-axis incidence), collapse to GarmentCode-only; *if* it is largely couture, GarmentCode earns its place only as an optional editability layer on reconstructed meshes. Since corpus mix is currently unknown, recommend a quick corpus audit against the §4 axes as the deciding measurement.

- [ ] **Step 2: Acceptance check — four options, decision table, and committed hybrid recommendation**

Run: `sed -n '/## §7/,/## §8/p' docs/garmentcode-designer-garment-assessment.md | grep -ciE 'GarmentCode-only|neural|hybrid|photogrammetry'`
Expected: ≥ 4.

Run: `sed -n '/## §7/,/## §8/p' docs/garmentcode-designer-garment-assessment.md | grep -iE 'adopt hybrid|corpus audit'`
Expected: both match.

- [ ] **Step 3: Commit**

```bash
git add docs/garmentcode-designer-garment-assessment.md
git commit -m "docs: write alternatives and decision framework (§7)"
```

---

## Task 9: §8 Appendix

**Files:**
- Modify: `docs/garmentcode-designer-garment-assessment.md` (`## §8` body)

- [ ] **Step 1: Write the appendix**

Content requirements:
- Library inventory — classes per garment-program file. Use this list (verified):

```markdown
- `tee.py` — TorsoFrontHalfPanel, TorsoBackHalfPanel
- `bodice.py` — BodiceFrontHalf, BodiceBackHalf, BodiceHalf, Shirt, FittedShirt
- `sleeves.py` — SleevePanel, Sleeve
- `collars.py` — VNeckHalf, SquareNeckHalf, NoPanelsCollar, Turtle, SimpleLapel(Panel), Hood(Panel/Hood2Panels)
- `bands.py` — StraightBandPanel, StraightWB, FittedWB, CuffBand, CuffSkirt, CuffBandSkirt
- `skirt_paneled.py` — SkirtPanel, ThinSkirtPanel, FittedSkirtPanel, PencilSkirt, Skirt2, SkirtManyPanels
- `circle_skirt.py` — CircleArcPanel, AsymHalfCirclePanel, SkirtCircle, AsymmSkirtCircle
- `skirt_levels.py` — SkirtLevels
- `godet.py` — Insert, GodetSkirt
- `pants.py` — PantPanel, PantsHalf, Pants
- `meta_garment.py` — MetaGarment (upper + bottom + wb composer)
- `base_classes.py` — BaseBodicePanel, BaseBottoms, StackableSkirtComponent, BaseBand
```

- Entry points: `gui.py`, `test_garmentcode.py`, `test_garment_sim.py`, `pattern_sampler.py`, `pattern_data_sim.py`.
- References: GarmentCode (SIGGRAPH Asia 2023, ACM TOG 42(6), doi 10.1145/3618351); GarmentCodeData (ECCV 2024); repo `github.com/maria-korosteleva/GarmentCode`; sim fork `NvidiaWarp-GarmentCode`.

- [ ] **Step 2: Acceptance check — inventory and references present**

Run: `sed -n '/## §8/,$p' docs/garmentcode-designer-garment-assessment.md | grep -cE 'meta_garment.py|skirt_levels.py|ECCV|3618351'`
Expected: ≥ 3.

- [ ] **Step 3: Commit**

```bash
git add docs/garmentcode-designer-garment-assessment.md
git commit -m "docs: write appendix — library inventory and references (§8)"
```

---

## Task 10: Final consistency pass

**Files:**
- Modify: `docs/garmentcode-designer-garment-assessment.md` (any fixes)

- [ ] **Step 1: Verify spec coverage — every spec §4 memo section is present and non-empty**

Run: `for s in 0 1 2 3 4 5 6 7 8; do echo "§$s:"; sed -n "/## §$s/,/## §/p" docs/garmentcode-designer-garment-assessment.md | grep -cv '^## §\|^$'; done`
Expected: each section reports ≥ 1 non-empty, non-header line.

- [ ] **Step 2: Legend consistency — symbols used only as defined**

Run: `grep -oE '✅|🟡|❌' docs/garmentcode-designer-garment-assessment.md | sort | uniq -c`
Expected: nonzero counts for all three; visually confirm no other status glyphs were introduced.

- [ ] **Step 3: Cross-reference & placeholder scan**

Run: `grep -nE 'TBD|TODO|FIXME|\bWIP\b' docs/garmentcode-designer-garment-assessment.md`
Expected: no matches.

Run: `grep -nE '§[0-9]' docs/garmentcode-designer-garment-assessment.md`
Expected: every referenced section number (e.g. "argued in §7") points to an existing heading. Fix any stale reference inline.

- [ ] **Step 4: Read-through for verdict-first**

Open the file; confirm §0 contains the verdict + recommendation before any deep evidence, and that the BLUF reads cleanly. Fix wording inline as needed.

- [ ] **Step 5: Final commit**

```bash
git add docs/garmentcode-designer-garment-assessment.md
git commit -m "docs: final consistency pass on assessment memo"
```

---

## Self-Review (performed during planning)

**1. Spec coverage:** Spec §4 memo sections §0–§8 each map to a task (Tasks 2–9); spec §3 verdict → Task 2; spec §3 matrix → Task 4; spec §4 taxonomy → Task 5; spec §5 bridging → Task 6; spec §6 cost → Task 7; spec §7 alternatives → Task 8; spec §8 appendix → Task 9. Spec §5 evidence basis is distributed into §2/§3/§8 content requirements. Spec §6 final-artifact decision → resolved in plan header (option (a), this plan). No gaps.

**2. Placeholder scan:** No "TBD/TODO/implement later" in task bodies. The corpus-mix unknown is handled as a conditional recommendation (Task 8), not a placeholder. Task 10 actively greps for placeholders.

**3. Type/term consistency:** Legend defined once in §3 (Task 4) and reused in §4 (Task 5) and §6 (Task 7) with identical glyphs ✅/🟡/❌. Class/file names (`MetaGarment`, `SkirtLevels`, `AsymmSkirtCircle`, `connect_ruffle`, `StraightWB`) are used identically across Tasks 3, 4, 5, 9 and match the spec evidence basis. Section cross-references (verdict → §7) are checked in Task 10 Step 3.
