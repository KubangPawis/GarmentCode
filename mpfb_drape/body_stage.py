"""Stage an ingested MPFB avatar so the GarmentCode sim can collide against it.

PathCofig resolves the body collider as <bodies_dir>/<name>.obj (metres) and
measurements as <name>.yaml. The bundled ggg segmentation is topology-bound to
mean_all, so we also write <name>_bodyseg.json for THIS avatar's topology; the
pipeline injects it via paths.body_seg.
"""
from __future__ import annotations
import shutil
from pathlib import Path

import trimesh

from mpfb_drape import bodyseg


def stage_body(body_yaml, body_obj, bodies_dir, name=None):
    """Copy avatar obj+yaml into bodies_dir and write its body segmentation.

    Returns {body_name, bodies_dir, obj, yaml, body_seg} as str paths.
    """
    body_yaml, body_obj, bodies_dir = Path(body_yaml), Path(body_obj), Path(bodies_dir)
    if name is None:
        name = body_yaml.stem
    bodies_dir.mkdir(parents=True, exist_ok=True)

    dst_obj = bodies_dir / f"{name}.obj"
    dst_yaml = bodies_dir / f"{name}.yaml"
    if dst_obj.resolve() != body_obj.resolve():
        shutil.copyfile(body_obj, dst_obj)
    if dst_yaml.resolve() != body_yaml.resolve():
        shutil.copyfile(body_yaml, dst_yaml)

    mesh = trimesh.load(str(dst_obj), process=False, force="mesh")
    seg = bodyseg.build_segmentation(mesh.vertices)
    seg_path = bodyseg.write_segmentation(seg, bodies_dir / f"{name}_bodyseg.json")

    return {
        "body_name": name,
        "bodies_dir": str(bodies_dir),
        "obj": str(dst_obj),
        "yaml": str(dst_yaml),
        "body_seg": str(seg_path),
    }
