"""Blender-side rig operations for T-pose normalization (py3.13). All math is
delegated to mpfb_tpose.geometry (pure numpy)."""
import importlib
import bpy
import mathutils
import numpy as np
from . import geometry

# Pivot bone (head = shoulder joint) and the wrist bone, per side, in the
# MPFB Standard "game_engine" rig.
ARM = {"l": ("upperarm_l", "hand_l"), "r": ("upperarm_r", "hand_r")}


def services():
    """Enable MPFB and return (HumanService, ExportService, RigService)."""
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.blender_org.mpfb")
    except Exception as e:                       # noqa: BLE001
        print("WARN addon_enable:", e)
    base = "bl_ext.blender_org.mpfb.services."
    H = importlib.import_module(base + "humanservice").HumanService
    E = importlib.import_module(base + "exportservice").ExportService
    R = importlib.import_module(base + "rigservice").RigService
    return H, E, R


def add_game_engine_rig(basemesh, human_svc):
    """Add the MPFB Standard 'Game engine' rig with imported weights (creates an
    Armature modifier on basemesh). Returns the armature object."""
    arm = human_svc.add_builtin_rig(basemesh, "game_engine", import_weights=True)
    if arm is None:
        raise RuntimeError("add_builtin_rig returned None (game_engine rig missing)")
    return arm


def _bone_head_world(rig_svc, armature, name):
    return np.asarray(rig_svc.find_pose_bone_head_world_location(name, armature),
                      dtype=np.float64)


def _rotate_bone_world_y(armature, bone_name, angle):
    """Rotate a pose bone about the world +Y axis through its head (the manual
    'R Y' about the bone head). Works headless (sets pose matrix; no view op)."""
    pb = armature.pose.bones[bone_name]
    # Rotate about world +Y through the bone's WORLD head. Valid for any armature
    # object transform: reduces to the identity case MPFB gives us (human at
    # origin), but does not silently tilt the pose if a caller moves the armature.
    mw = armature.matrix_world
    head_world = mw @ pb.matrix.translation
    Ry = mathutils.Matrix.Rotation(angle, 4, "Y")
    T = mathutils.Matrix.Translation(head_world)
    pb.matrix = mw.inverted() @ T @ Ry @ T.inverted() @ mw @ pb.matrix
    bpy.context.view_layer.update()


def measure_and_rotate_shoulders(armature, rig_svc, fallback_deg=45.0):
    """Steps 3-5: in pose mode, rotate each upperarm about world +Y so the
    shoulder->wrist line is horizontal. Returns {side: applied_angle_rad}."""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    applied = {}
    for side, (upper, hand) in ARM.items():
        try:
            shoulder = _bone_head_world(rig_svc, armature, upper)
            wrist = _bone_head_world(rig_svc, armature, hand)
            if not np.all(np.isfinite([shoulder, wrist])):
                raise ValueError("non-finite bone head")
            # geometry.y_rotation_to_horizontal is the single source of truth for
            # "degenerate": it raises on coincident shoulder/wrist (caught below).
            angle = geometry.y_rotation_to_horizontal(shoulder, wrist)
        except Exception as e:                   # noqa: BLE001
            print("WARN measure failed (%s): %s -> fallback %.0f deg"
                  % (side, e, fallback_deg))
            angle = geometry.fallback_y_rotation(side, fallback_deg)
        _rotate_bone_world_y(armature, upper, angle)
        applied[side] = angle
    return applied
