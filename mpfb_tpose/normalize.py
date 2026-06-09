"""Orchestrates the 12-step manual T-pose procedure on a live MPFB human (runs
inside Blender). Pure sequencing + guards; math is in geometry, rig ops in rig."""
import bpy
from . import rig as rigmod


def _bake_shape_keys(ob):
    """Apply-all shape keys (step 8): bake the macro mix into the basis and drop
    all keys. MUST precede applying the Armature modifier -- Blender refuses
    modifier-apply on a mesh that still has shape keys."""
    keys = ob.data.shape_keys
    if not keys or not keys.key_blocks:
        return
    ob.shape_key_add(name="_baked", from_mix=True)
    for kb in list(ob.data.shape_keys.key_blocks):
        if kb.name != "_baked":
            ob.shape_key_remove(kb)
    ob.shape_key_remove(ob.data.shape_keys.key_blocks["_baked"])


def _apply_armature_modifier(mesh):
    """Steps 9-10: apply the Armature modifier -> bakes the posed deformation
    (raised arms) into the mesh vertices. Mesh is then physically T-posed."""
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    mod = next((m for m in mesh.modifiers if m.type == "ARMATURE"), None)
    if mod is None:
        raise RuntimeError("no Armature modifier to apply (rig/weights missing)")
    bpy.ops.object.modifier_apply(modifier=mod.name)


def _lateral_span(mesh):
    xs = [v.co.x for v in mesh.data.vertices]
    return max(xs) - min(xs)


def normalize_human(basemesh, human_svc, rig_svc, *, fallback_deg=45.0):
    """Steps 2-12. Returns {'pre_span','post_span','angles'} (span in model units)."""
    pre_span = _lateral_span(basemesh)

    armature = rigmod.add_game_engine_rig(basemesh, human_svc)             # step 2
    angles = rigmod.measure_and_rotate_shoulders(armature, rig_svc,
                                                 fallback_deg=fallback_deg)  # steps 3-5

    bpy.ops.object.mode_set(mode="OBJECT")                                 # step 6
    _bake_shape_keys(basemesh)                                            # steps 7-8
    _apply_armature_modifier(basemesh)                                    # steps 9-10
    post_span = _lateral_span(basemesh)

    try:                                                                  # steps 11-12
        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="OBJECT")
        rig_svc.apply_pose_as_rest_pose(armature)
    except Exception as e:                                                # noqa: BLE001
        print("WARN apply_pose_as_rest_pose:", e)   # mesh already baked; non-fatal

    print("TPOSE span %.3f -> %.3f units (x%.2f); angles_deg=%s"
          % (pre_span, post_span,
             (post_span / pre_span if pre_span else 0.0),
             {s: round(__import__("math").degrees(a), 1) for s, a in angles.items()}))
    return {"pre_span": pre_span, "post_span": post_span, "angles": angles}
