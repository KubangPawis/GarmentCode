"""Load and normalize an MPFB-exported body mesh into GarmentCode's space."""
from pathlib import Path
import numpy as np
import trimesh


def load_body(path) -> trimesh.Trimesh:
    """Load an OBJ as a single Trimesh (concatenate scene geometry if needed)."""
    obj = trimesh.load(str(path), process=False, force="mesh")
    if not isinstance(obj, trimesh.Trimesh):
        obj = trimesh.util.concatenate(tuple(obj.geometry.values()))
    return obj


def normalize(mesh: trimesh.Trimesh, expected_height_m: float = 1.7):
    """Return (mesh_in_metres, report).

    Steps: detect unit scale from total Y-extent vs expected human height,
    scale to metres, centre X/Z on the centroid, ground feet to Y=0.
    Assumes the mesh is already Y-up (MakeHuman default).
    """
    mesh = mesh.copy()
    raw_height = float(mesh.bounds[1][1] - mesh.bounds[0][1])
    if raw_height <= 0:
        raise ValueError("Mesh has zero Y-extent; is it Y-up?")
    scale_to_m = expected_height_m / raw_height
    mesh.apply_scale(scale_to_m)

    cx, _, cz = mesh.centroid
    min_y = mesh.bounds[0][1]
    mesh.apply_translation([-cx, -min_y, -cz])

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
