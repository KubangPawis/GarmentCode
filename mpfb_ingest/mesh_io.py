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


def normalize(mesh: trimesh.Trimesh, expected_height_m: float = 1.7) -> tuple[trimesh.Trimesh, dict]:
    """Return (mesh_in_metres, report).

    Steps: detect unit scale from total Y-extent vs expected human height,
    scale to metres, centre X/Z on the axis-aligned bounding-box midpoint,
    ground feet to Y=0. Bounding-box midpoint (not mass centroid) is used so
    centring is deterministic and independent of mesh density/asymmetry.
    Assumes the mesh is already Y-up (MakeHuman default).
    """
    mesh = mesh.copy()
    raw_height = float(mesh.bounds[1][1] - mesh.bounds[0][1])
    if raw_height <= 0:
        raise ValueError("Mesh has zero Y-extent; is it Y-up?")
    scale_to_m = expected_height_m / raw_height
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
