"""Pure-numpy T-pose geometry. No bpy / no mathutils, so this imports under BOTH
the project venv (py3.9 unit tests) and Blender's bundled Python (py3.13 runtime).

Blender axes: X lateral, Y forward, Z up. The shoulder rotation that forms a
T-pose is a rotation about world +Y (acts in the frontal X-Z plane)."""
import numpy as np


def rotate_about_y(vec, angle):
    """Rotate a 3-vector about world +Y by `angle` radians, right-handed
    (matches mathutils.Matrix.Rotation(angle, 'Y'): +X -> -Z at +90 deg)."""
    v = np.asarray(vec, dtype=np.float64)
    c, s = np.cos(angle), np.sin(angle)
    x, y, z = float(v[0]), float(v[1]), float(v[2])
    return np.array([c * x + s * z, y, -s * x + c * z], dtype=np.float64)


def y_rotation_to_horizontal(shoulder, wrist):
    """Signed rotation (radians) about world +Y that brings the shoulder->wrist
    vector into the horizontal (z=0) plane while preserving the arm's lateral
    side (sign of x). Per-side sign is derived from the geometry, not hardcoded.
    Raises ValueError if shoulder and wrist coincide (no arm direction)."""
    v = np.asarray(wrist, dtype=np.float64) - np.asarray(shoulder, dtype=np.float64)
    if float(np.linalg.norm(v)) < 1e-9:
        raise ValueError("shoulder and wrist are coincident; cannot compute rotation")
    phi = np.arctan2(float(v[2]), float(v[0]))
    if float(v[0]) < 0.0:                       # left arm: side-preserving branch
        phi += np.pi
    return float((phi + np.pi) % (2.0 * np.pi) - np.pi)   # wrap to [-pi, pi)


def droop_from_horizontal_deg(shoulder, wrist):
    """Unsigned arm droop in DEGREES between the shoulder->wrist vector and the
    horizontal plane. 0 == perfect T-pose. (Runtime self-check, Blender Z-up.)"""
    v = np.asarray(wrist, dtype=np.float64) - np.asarray(shoulder, dtype=np.float64)
    horiz = float(np.hypot(v[0], v[1]))
    return float(abs(np.degrees(np.arctan2(abs(float(v[2])), horiz))))


def fallback_y_rotation(side, droop_deg=45.0):
    """Side-correct world-+Y rotation for a canonical `droop_deg` arm, used when
    bone geometry is degenerate. `side`: 'l' or 'r'. Raises ValueError on a bad side."""
    if side not in ("l", "r"):
        raise ValueError("side must be 'l' or 'r', got %r" % (side,))
    sx = -1.0 if side == "l" else 1.0
    synthetic_wrist = (sx * np.cos(np.radians(droop_deg)), 0.0,
                       -np.sin(np.radians(droop_deg)))
    return y_rotation_to_horizontal((0.0, 0.0, 0.0), synthetic_wrist)
