"""CLI: fit + drape GarmentCode garments onto a normalized MPFB body.

Usage:
  .venv/bin/python drape_mpfb_garment.py \
      --body assets/bodies/avatar.yaml \
      --designs assets/design_params/ \
      --out .temp/wardrobe [--body-obj path] [--sim-props ...]

--designs accepts a directory (every *.yaml) or explicit file paths.
Pass a true-T-pose avatar ingested with `--arm-pose-angle 0`.
GarmentCode's preview render (front/back PNGs) runs per design as part of the sim.
"""
import argparse
import sys
from pathlib import Path

DEFAULT_SIM_PROPS = "assets/Sim_props/mpfb_drape_sim_props.yaml"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", required=True, help="body-measurements YAML (mpfb_ingest output)")
    ap.add_argument("--body-obj", default=None, help="collider OBJ (default: sibling <body>.obj)")
    ap.add_argument("--designs", nargs="+", required=True, help="design YAML dir or files")
    ap.add_argument("--out", required=True, help="output dir for the wardrobe run")
    ap.add_argument("--sim-props", default=DEFAULT_SIM_PROPS)
    a = ap.parse_args(argv)

    from mpfb_drape import pipeline

    body_yaml = Path(a.body)
    if not body_yaml.is_file():
        ap.error(f"--body not found: {body_yaml}")
    body_obj = Path(a.body_obj) if a.body_obj else body_yaml.with_suffix(".obj")
    if not body_obj.is_file():
        ap.error(f"body OBJ not found: {body_obj} (pass --body-obj or place <body>.obj beside the yaml)")

    designs = pipeline.resolve_designs(a.designs)
    if not designs:
        ap.error(f"no design YAMLs found in: {a.designs}")

    man = pipeline.drape_wardrobe(
        body_yaml, body_obj, designs, out_dir=a.out, sim_props_yaml=a.sim_props)

    s = man["summary"]
    print(f"DRAPE_DONE total={s['total']} passed={s['passed']} failed={s['failed']} "
          f"manifest={Path(a.out) / 'wardrobe_manifest.json'}")
    return 0 if s["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
