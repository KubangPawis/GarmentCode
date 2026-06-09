"""Fit a garment design to body measurements -> a serialized sewing pattern.

Mirrors pattern_fitter._save_sample: MetaGarment(name, body, design) ->
piece.assembly() -> pattern.serialize(...). The serialized folder contains
<name>_specification.json, which PathConfig consumes for the box-mesh + sim.
"""
from __future__ import annotations
from pathlib import Path

from assets.bodies.body_params import BodyParameters
from assets.garment_programs.meta_garment import MetaGarment


def fit_pattern(body_yaml, design, out_dir, name):
    """Return (spec_folder, name). Writes <spec_folder>/<name>_specification.json."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    body = BodyParameters(str(body_yaml))
    piece = MetaGarment(name, body, design)
    pattern = piece.assembly()
    spec_folder = pattern.serialize(
        str(out_dir),
        tag="",
        to_subfolder=True,
        with_3d=False,
        with_text=False,
        view_ids=False,
    )
    return str(spec_folder), name
