# Draping a GarmentCode Garment onto Your Own T-Posed Human Model (Blender)

This guide takes the export folder produced by the GarmentCode GUI (e.g.
`Configured_design_260604-21-13-12/`) and re-drapes that garment onto a
**T-posed, normalized human mesh** of your own using Blender's Cloth simulator.

It is written for the t-shirt export but the workflow generalizes to any
GarmentCode garment.

---

## 0. Understand the Export Artifacts

Inside the export folder you have (names prefixed by your design name):

| File | What it is | Use here |
|------|-----------|----------|
| `*_sim.obj` | Garment **already draped** on the GarmentCode body (45° arms), 7990 verts, Y-up, **units = cm** | Preview only |
| `*_boxmesh.obj` | **Undraped** flat/neutral sewn shell, same 7990 verts | **Import this for re-sim** |
| `*_material.mtl` | `newmtl panels_texture`, points at the fabric PNG | Re-texture later |
| `*_texture_fabric.png` | The fabric color/UV texture | Re-texture later |
| `*_sim_segmentation.txt` | 7990 lines, one per vertex, comma-joined panel labels (`left_ftorso`, `right_sleeve_f`, `stitch_N`, …) | Build vertex groups + pin group |

**Why `boxmesh` and not `sim`:** `*_sim.obj` is already collapsed onto a
45°-arm body. Re-draping that pre-folded mesh onto a T-pose forces the solver
to *un*-fold cloth — it fights the existing geometry and explodes. The
`boxmesh` is the clean, low-bias starting shell the GarmentCode solver itself
starts from. Start there.

> If your export has no `*_boxmesh.obj`, you can fall back to `*_sim.obj`, but
> expect to manually rotate the sleeves outward (Phase 2) much more.

---

## Phase 1 — Prepare Your Character Model

Goal: a watertight-ish, single-mesh, T-posed human at real-world scale (meters),
arms horizontal, facing **−Y** (Blender front view, Numpad 1).

1. Import / open your character.
2. **Scale to meters.** A human should be ~1.6–1.9 m tall on the Z axis. Check
   in the `N` panel ▸ Item ▸ Dimensions. Scale if needed, then
   `Object ▸ Apply ▸ All Transforms` (Ctrl+A). Scale **must** read 1.0 after.
3. **T-pose check.** Arms straight out horizontally (along ±X). If your model
   is A-posed or rigged, pose it to T first and apply the pose as rest, or
   `Apply ▸ Visual Geometry to Mesh`.
4. **Single mesh, faces outward.** Enter Edit Mode, `A` select all,
   `Shift+N` recalc normals outside. Enable `Overlays ▸ Face Orientation`:
   the whole body must read **blue**. Any red = flipped face, fix it.
5. **Watertight enough.** Cloth collision needs a continuous surface. Small
   holes (mouth, nostrils) are fine; large open gaps under the arms or at the
   neck let cloth tunnel through.

---

## Phase 2 — Import & Align the Garment

1. `File ▸ Import ▸ Wavefront (.obj)`. Select `*_boxmesh.obj`.
2. **Critical import settings** (right panel of the import dialog):
   - **Up Axis: Y**
   - **Forward Axis: −Z**
   - **Scale: 0.01**  ← converts GarmentCode cm → Blender m
3. After import: `Object ▸ Apply ▸ All Transforms` (Ctrl+A). Scale must read 1.0.
4. **Recalculate normals.** Edit Mode ▸ `A` ▸ `Shift+N`. With Face Orientation
   on, the garment is a **single-sided shell**: outside reads untinted/blue,
   inside reads **red**. That is correct — do **not** flip it.
5. **Position the garment around the torso.** In Object Mode, move (`G`) /
   rotate (`R`) the whole shirt so the torso shell surrounds the character's
   chest and the neck hole sits at the character's neck. It will not fit
   perfectly yet — the sim closes the gap.
6. **Open out the sleeves to follow the arms.** The boxmesh sleeves hang near
   the torso; your character's arms are horizontal. For each sleeve:
   - Use the **segmentation vertex groups** (Phase 3) to select the sleeve
     cleanly, OR select the sleeve loops manually.
   - Enable **Proportional Editing** (`O`), set falloff small (scroll wheel
     during transform shrinks the influence circle).
   - Set pivot to **3D cursor** placed at the shoulder, or Median Point.
   - Rotate (`R`) the sleeve up to roughly horizontal so it sleeves over the
     arm. Repeat for the other sleeve.
   - You only need it *close* — the cloth solver slides it onto the arm.

> Proportional editing rotating the **whole** garment = falloff radius too big.
> Scroll-wheel down during the rotate to shrink the circle, or toggle `O` off
> and select the sleeve exactly via its vertex group.

---

## Phase 3 — Build Vertex Groups + Pin Group from Segmentation

The segmentation file maps every vertex to its panel. This script creates one
vertex group per panel label and a `pin` group from the top band of the torso
(the collar/shoulder ring that should stay put while everything else drapes).

1. Select the **imported garment** mesh (Object Mode).
2. Open a **Scripting** workspace tab, paste the script below, set `SEG_PATH`
   to your export's `*_sim_segmentation.txt`, **Run**.

```python
import bpy

SEG_PATH = r"/path/to/Configured_design_..._sim_segmentation.txt"
PIN_TOP_FRACTION = 0.08   # raise to 0.12-0.15 if the shirt slides down in sim

obj = bpy.context.active_object
assert obj and obj.type == 'MESH', "Select the imported garment mesh first"
mesh = obj.data

with open(SEG_PATH) as f:
    lines = [ln.strip() for ln in f if ln.strip() != ""]

n_v = len(mesh.vertices)
assert len(lines) == n_v, (
    f"Vertex count {n_v} != seg lines {len(lines)}. "
    "Re-import OBJ without merging/triangulating that changes vert count."
)

# label -> [vertex indices]
label_to_verts = {}
for i, ln in enumerate(lines):
    for label in ln.split(","):
        label = label.strip()
        if label:
            label_to_verts.setdefault(label, []).append(i)

# one vertex group per panel label
for label, idxs in label_to_verts.items():
    vg = obj.vertex_groups.get(label) or obj.vertex_groups.new(name=label)
    vg.add(idxs, 1.0, 'REPLACE')

# pin group = top PIN_TOP_FRACTION band of all torso verts (collar/shoulders)
torso_labels = [l for l in label_to_verts if "torso" in l]
torso_idx = sorted({i for l in torso_labels for i in label_to_verts[l]})
if torso_idx:
    zs = [mesh.vertices[i].co.z for i in torso_idx]
    zmin, zmax = min(zs), max(zs)
    cutoff = zmax - (zmax - zmin) * PIN_TOP_FRACTION
    pin_idx = [i for i in torso_idx if mesh.vertices[i].co.z >= cutoff]
    pin = obj.vertex_groups.get("pin") or obj.vertex_groups.new(name="pin")
    pin.add(pin_idx, 1.0, 'REPLACE')

print(f"Created {len(label_to_verts)} panel groups, "
      f"pin = {len(pin_idx) if torso_idx else 0} verts")
```

3. **Verify the pin group.** Object Data Properties (green triangle) ▸ Vertex
   Groups ▸ select `pin` ▸ Edit Mode ▸ Deselect All ▸ **Select** (the group's
   Select button). The collar/shoulder ring lights up.

> The front neckline dips below the cutoff, so `pin` covers the collar ring
> **except the front dip** — that is expected and fine; shoulders + back hold
> the shirt up. If the shirt slides down during sim, raise `PIN_TOP_FRACTION`
> to `0.12`–`0.15` and re-run the script.

---

## Phase 4 — Make the Character a Collider

1. Select the **character** mesh.
2. `Physics Properties` (blue bouncing-ball icon) ▸ **Collision**.
3. **Outer thickness ≈ 0.010 m.** Lower → cloth hugs closer; raise (0.015) if
   cloth pokes through.
4. Confirm the **entire body** (arms included) is one collision mesh. Separate
   arm objects → each needs its own Collision modifier.

---

## Phase 5 — Add Cloth Physics to the Garment

1. Select the **garment**.
2. `Physics Properties` ▸ **Cloth**.
3. **Presets ▸ Cotton** (good default for a t-shirt).
4. **Shape ▸ Pin Group →** select **`pin`**.
5. **Collisions ▸ Object Collisions** ON, **Distance ≈ 0.012**.
6. **Collisions ▸ Self Collisions** ON, **Distance ≈ 0.006**. (T-pose sleeves
   fold against the torso — self-collision keeps fabric from passing through
   itself.)
7. **Quality Steps → 12.** (Default 5 explodes on tight contact; 12–15 is
   stable for a fitted shirt.)

---

## Phase 6 — Simulate

1. Timeline: **Start 1**, **End ~120**.
2. **Inspect frame 1 (the start frame).** In Object Mode, orbit around the
   character. The garment must start **outside** the body, sleeves roughly
   over the arms, no big chunks of mesh already buried inside the torso.
   Pre-existing deep intersections at frame 1 = the sim explodes. Fix by
   nudging the garment outward before playing.
3. Press **Spacebar** (Play). Watch it settle: torso shell pulls onto the
   chest, sleeve fabric drapes down off the arms, collar held by the `pin`.
4. Let it run to a calm/still frame (~50–100).

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Cloth jitters / explodes | Quality too low, or non-1.0 scale | Quality Steps 15–20; re-check both objects Scale = 1.0 (`N` panel) |
| Cloth pokes through body | Collision distance too small / body collision quality | Object Collision Distance 0.015; on character Collision raise quality |
| Shirt slides off / down | Pin group too small | `PIN_TOP_FRACTION` 0.12, re-run Phase 3 script |
| Sleeves never reach arms | Sleeves started too far from arms | Phase 2 step 6 — rotate sleeves closer before playing |
| Solver slow | High quality + self-collision is expensive | Drop End frame; only raise quality if unstable |

---

## Phase 7 — Bake & Finalize

1. With a good settle reached, go to `Physics Properties ▸ Cloth ▸ Cache`.
   Set the cache **Start/End** to match your timeline.
2. **Bake.** This freezes the sim so it won't recompute on scrub.
3. **Lock the shape (optional).** To keep the draped mesh as static geometry:
   move to the settled frame, `Object ▸ Convert ▸ Mesh` (or
   `Object ▸ Apply ▸ Visual Geometry to Mesh`) to bake the deformed shape into
   the mesh, then remove the Cloth modifier.

### Re-texture

1. Garment ▸ Material Properties ▸ new material (or reuse the imported one).
2. Base Color ▸ Image Texture ▸ open `*_texture_fabric.png`.
3. The boxmesh import carried the **UVs** (8343 UVs in the export), so the
   fabric maps correctly without re-unwrapping.

### Rig (optional)

To pose the dressed character afterward: parent the baked garment mesh to your
character's armature with **Automatic Weights**, or use a **Surface Deform**
modifier (Target = character body) so the shirt follows body deformation.

---

## Quick Reference — One-Screen Checklist

```
CHARACTER:  meters · T-pose · single mesh · normals out (all blue) · Apply All Transforms
GARMENT:    import boxmesh.obj  Up=Y  Fwd=-Z  Scale=0.01 · Apply All Transforms · Shift+N
SEGMENT:    run script → panel vgroups + 'pin' group · verify pin = collar ring
COLLIDER:   character → Collision · Outer 0.010
CLOTH:      garment → Cloth · Cotton · Pin Group=pin · ObjColl 0.012 · SelfColl 0.006 · Quality 12
SIM:        End ~120 · check frame 1 outside body · Spacebar · settle 50-100
BAKE:       Cache Bake · Convert to Mesh · re-texture w/ fabric.png
```
