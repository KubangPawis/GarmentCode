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
    if name not in argv:
        return default
    i = argv.index(name)
    if i + 1 >= len(argv):
        raise ValueError("%s requires a value but is the last argument" % name)
    return argv[i + 1]


def _float_arg(argv, name, default):
    raw = _arg(argv, name, str(default))
    try:
        return float(raw)
    except ValueError:
        raise ValueError("%s expects a float, got %r" % (name, raw))


def main():
    argv = _argv()
    from mpfb_tpose import (human as humanmod, normalize as normmod,
                            export as exportmod, rig as rigmod)

    out_glb = _arg(argv, "--out-glb", "/tmp/tpose.glb")
    out_blend = _arg(argv, "--out-blend", "/tmp/tpose.blend")
    fallback = _float_arg(argv, "--fallback-deg", 45.0)
    macro = humanmod.macro_dict(
        gender=_float_arg(argv, "--gender", 0.5),
        weight=_float_arg(argv, "--weight", 0.5),
        height=_float_arg(argv, "--height", 0.5),
        muscle=_float_arg(argv, "--muscle", 0.5),
        cupsize=_float_arg(argv, "--cupsize", 0.5),
        age=_float_arg(argv, "--age", 0.5),
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
