"""Save the normalized .blend and a clean, ingest-ready T-pose .glb (runs in
Blender). export_tpose_glb MUTATES the basemesh (strips helpers) -- call it
AFTER save_blend so the .blend keeps the full rigged body."""
import bpy


def _bake_shape_keys(ob):
    keys = ob.data.shape_keys
    if not keys or not keys.key_blocks:
        return
    ob.shape_key_add(name="_baked", from_mix=True)
    for kb in list(ob.data.shape_keys.key_blocks):
        if kb.name != "_baked":
            ob.shape_key_remove(kb)
    ob.shape_key_remove(ob.data.shape_keys.key_blocks["_baked"])


def save_blend(path):
    bpy.ops.wm.save_as_mainfile(filepath=path)


def export_tpose_glb(basemesh, export_svc, path):
    """Body-only clean glTF: strip MPFB helper geometry (so mpfb_ingest sees a
    clean body, matching the gen_mpfb_testset bodies), no morph targets, Y-up."""
    export_svc.bake_modifiers_remove_helpers(basemesh, remove_helpers=True)
    _bake_shape_keys(basemesh)
    bpy.ops.object.select_all(action="DESELECT")
    basemesh.select_set(True)
    bpy.context.view_layer.objects.active = basemesh
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True,
                              export_format="GLB", export_yup=True,
                              export_morph=False)
