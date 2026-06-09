"""CLI (runs INSIDE Blender): generate an MPFB human from macro params, normalize
to a true T-pose, export a clean .glb + normalized .blend.

Invoke via scripts/run_tpose_normalize.sh. Prints 'TPOSE_OK <glb>' on success.
Pass --arm-pose-angle 0 to mpfb_ingest downstream (the export is a true T-pose)."""
import os
import sys


def _argv():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--repo" in argv:
        sys.path.insert(0, argv[argv.index("--repo") + 1])
    return argv


def _arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def main():
    argv = _argv()
    from mpfb_tpose import (human as humanmod, normalize as normmod,
                            export as exportmod, rig as rigmod)

    out_glb = _arg(argv, "--out-glb", "/tmp/tpose.glb")
    out_blend = _arg(argv, "--out-blend", "/tmp/tpose.blend")
    fallback = float(_arg(argv, "--fallback-deg", "45"))
    macro = humanmod.macro_dict(
        gender=float(_arg(argv, "--gender", "0.5")),
        weight=float(_arg(argv, "--weight", "0.5")),
        height=float(_arg(argv, "--height", "0.5")),
        muscle=float(_arg(argv, "--muscle", "0.5")),
        cupsize=float(_arg(argv, "--cupsize", "0.5")),
        age=float(_arg(argv, "--age", "0.5")),
        race=_arg(argv, "--race", "caucasian"),
    )
    for p in (out_glb, out_blend):
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)

    H, E, R = rigmod.services()
    basemesh = humanmod.create(H, macro)
    info = normmod.normalize_human(basemesh, H, R, fallback_deg=fallback)
    exportmod.save_blend(out_blend)            # full rigged body first
    exportmod.export_tpose_glb(basemesh, E, out_glb)   # then destructive helper strip

    print("TPOSE_INFO", info["pre_span"], info["post_span"])
    if os.path.isfile(out_glb) and os.path.isfile(out_blend):
        print("TPOSE_OK", out_glb)
    else:
        print("TPOSE_FAIL missing output")
        sys.exit(1)


if __name__ == "__main__":
    main()
