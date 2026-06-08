"""Load and normalize an MPFB-exported body mesh into GarmentCode's space."""
from __future__ import annotations
from pathlib import Path
import trimesh


def load_body(path) -> trimesh.Trimesh:
    """Load an OBJ as a single Trimesh (concatenate scene geometry if needed)."""
    obj = trimesh.load(str(path), process=False, force="mesh")
    if not isinstance(obj, trimesh.Trimesh):
        obj = trimesh.util.concatenate(tuple(obj.geometry.values()))
    return obj


def detect_scale_to_m(raw_height: float) -> float:
    """Factor to bring a raw Y-extent to metres, by magnitude bucket.

    ~1-3 -> already metres (x1); ~10-25 -> decimetres (x0.1);
    >50 -> centimetres / MakeHuman raw units (x0.01). Mid-gaps fall to the
    nearest plausible human bucket.
    """
    if raw_height <= 0:
        raise ValueError("Mesh has zero Y-extent; is it Y-up?")
    if raw_height < 4.0:
        return 1.0
    if raw_height < 40.0:
        return 0.1
    return 0.01


def normalize(mesh: trimesh.Trimesh, expected_height_m: float | None = None) -> tuple[trimesh.Trimesh, dict]:
    """Return (mesh_in_metres, report).

    Auto-detects the unit scale and MEASURES true height. Pass
    `expected_height_m` only to force a known stature (override). Then centre
    X/Z on the bbox midpoint and ground feet to Y=0. Assumes Y-up.
    """
    mesh = mesh.copy()
    raw_height = float(mesh.bounds[1][1] - mesh.bounds[0][1])
    if raw_height <= 0:
        raise ValueError("Mesh has zero Y-extent; is it Y-up?")
    if expected_height_m is not None:
        scale_to_m = expected_height_m / raw_height
    else:
        scale_to_m = detect_scale_to_m(raw_height)
    mesh.apply_scale(scale_to_m)

    (x0, _, z0), (x1, _, z1) = mesh.bounds
    x_mid = 0.5 * (x0 + x1)
    z_mid = 0.5 * (z0 + z1)
    min_y = mesh.bounds[0][1]
    mesh.apply_translation([-x_mid, -min_y, -z_mid])

    report = {
        "scale_to_m": scale_to_m,
        "height_m": float(mesh.bounds[1][1] - mesh.bounds[0][1]),
        "n_vertices": int(len(mesh.vertices)),
    }
    return mesh, report


def to_cm(mesh_m: trimesh.Trimesh) -> trimesh.Trimesh:
    """Return a centimetre copy (x100) for measurement math."""
    cm = mesh_m.copy()
    cm.apply_scale(100.0)
    return cm


def save_body_obj(mesh_m: trimesh.Trimesh, out_dir, name: str) -> Path:
    """Save the metres mesh as <name>.obj for GarmentCode draping."""
    out = Path(out_dir) / f"{name}.obj"
    mesh_m.export(str(out))
    return out
