"""Orchestrate a single drape and a wardrobe of drapes onto one MPFB body.

drape_one: fit -> stage -> PathCofig (+ body_seg injection) ->
template_simulation (BoxMesh -> load -> serialize -> run_sim) -> verify.
"""
from __future__ import annotations
from pathlib import Path

from pygarment.data_config import Properties
import pygarment.meshgen.datasim_utils as sim
from pygarment.meshgen.sim_config import PathCofig


def make_sim_props(sim_props_yaml):
    """Build the Properties object template_simulation expects.

    Loads the sim/render config, ensures the full stats structure via
    init_sim_props, and forces optimize_storage off so the .obj/.glb/texture
    are preserved for verification and export.
    """
    props = Properties(str(sim_props_yaml))
    sim.init_sim_props(props)                 # adds meshgen_time/face_count/etc.
    props["sim"]["config"]["optimize_storage"] = False
    return props
