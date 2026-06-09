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


from mpfb_drape import fit as _fit
from mpfb_drape import body_stage as _stage
from mpfb_drape import verify as _verify


def drape_one(body_yaml, body_obj, design, out_dir, bodies_dir, name,
              sim_props_yaml, run=None, render=False):
    """Fit + drape one design onto one staged avatar; return a result record.

    `run` is the sim entry point (default datasim_utils.template_simulation);
    injectable so unit tests can stub the GPU sim. Returns:
        {design, body_name, verdict, out_folder, sim_obj, sim_glb}
    """
    run = run if run is not None else sim.template_simulation
    out_dir, bodies_dir = Path(out_dir), Path(bodies_dir)

    # 1) fit -> spec folder containing <name>_specification.json
    spec_dir, name = _fit.fit_pattern(body_yaml, design, out_dir / "_specs", name=name)

    # 2) stage avatar + topology-matched body segmentation into the bodies dir
    staged = _stage.stage_body(body_yaml, body_obj, bodies_dir)

    if not staged["arms_detected"]:
        raise ValueError(
            f"No lateral arms detected in body '{staged['body_name']}'. "
            "mpfb_drape requires a true T-pose body (arm_pose_angle ~= 0, e.g. an "
            "mpfb_tpose export). Arms-down / A-pose bodies are not supported."
        )

    # 3) PathCofig reads the body yaml from system.json's bodies_default_path at
    #    construction, so bodies_dir must be that dir. Override body paths after:
    #    collider = staged avatar obj; segmentation = OUR topology-matched seg.
    props = make_sim_props(sim_props_yaml)
    paths = PathCofig(
        in_element_path=spec_dir,
        out_path=str(out_dir),
        in_name=name,
        body_name=staged["body_name"],
        default_body=True,
    )
    paths.in_body_obj = Path(staged["obj"])
    paths.body_seg = Path(staged["body_seg"])

    # 4) drape (BoxMesh -> load -> serialize -> run_sim). template_simulation
    #    records failures into props rather than raising.
    run(paths, props)

    # 5) verify against the recorded stats + the draped obj
    cfg = props["sim"]["config"]
    verdict = _verify.acceptance(
        props["sim"]["stats"], name, paths.g_sim, paths.in_body_obj,
        max_body_collisions=cfg.get("max_body_collisions", 35),
        max_self_collisions=cfg.get("max_self_collisions", 300),
    )

    sim_glb = Path(paths.g_sim_glb)
    return {
        "design": name,
        "body_name": staged["body_name"],
        "verdict": verdict,
        "out_folder": str(paths.out_el),
        "sim_obj": str(paths.g_sim),
        "sim_glb": str(sim_glb) if sim_glb.exists() else None,
    }


import yaml as _yaml
from mpfb_drape import manifest as _manifest

DEFAULT_BODIES_DIR = "assets/bodies"


def resolve_designs(designs):
    """Accept a dir, a single file, or a list of dirs/files -> sorted file list."""
    if isinstance(designs, (str, Path)):
        designs = [designs]
    out = []
    for d in designs:
        d = Path(d)
        if d.is_dir():
            out.extend(sorted(d.glob("*.yaml")))
        else:
            out.append(d)
    return out


def drape_wardrobe(body_yaml, body_obj, designs, out_dir, sim_props_yaml,
                   bodies_dir=DEFAULT_BODIES_DIR, render=False):
    """Drape many designs onto one avatar; write + return the manifest."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results, body_name = [], None
    for design_file in resolve_designs(designs):
        design = _yaml.safe_load(Path(design_file).read_text())["design"]
        name = Path(design_file).stem
        res = drape_one(body_yaml, body_obj, design, out_dir=out_dir,
                        bodies_dir=bodies_dir, name=name,
                        sim_props_yaml=sim_props_yaml, render=render)
        body_name = res["body_name"]
        results.append(res)
    man = _manifest.build(body_name, results)
    _manifest.write(man, out_dir / "wardrobe_manifest.json")
    return man
