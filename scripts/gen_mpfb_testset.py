"""Generate a varied MPFB body-type test set (runs INSIDE Blender, headless).

Invoke via scripts/run_mpfb_gen.sh. Exports each body as <out>/<id>.glb
(body-only: helpers baked + removed) plus manifest.json mapping id -> macro
sliders, so the stress tests know each body's expected qualitative direction.
MPFB output is CC0. No Rigify (keeps the headless path stable).
"""
import bpy
import sys
import os
import json
import itertools
import importlib


def _services():
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.blender_org.mpfb")
    except Exception as e:                       # noqa: BLE001
        print("WARN addon_enable:", e)
    base = "bl_ext.blender_org.mpfb.services."
    human = importlib.import_module(base + "humanservice").HumanService
    export = importlib.import_module(base + "exportservice").ExportService
    return human, export


def _macro(gender, age, weight, muscle, height, cup, race):
    r = {"asian": 0.0, "caucasian": 0.0, "african": 0.0}
    r[race] = 1.0
    return {"gender": gender, "age": age, "muscle": muscle, "weight": weight,
            "proportions": 0.5, "height": height, "cupsize": cup,
            "firmness": 0.5, "race": r}


def _grid(limit=None):
    out = [("neutral", _macro(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, "caucasian"))]
    genders = [0.0, 1.0]
    ages = [0.5, 0.9]
    weights = [0.0, 0.5, 1.0]
    muscles = [0.0, 0.5, 1.0]
    heights = [0.0, 0.5, 1.0]
    cups = [0.0, 0.5, 1.0]
    races = ["caucasian", "asian", "african"]
    i = 0
    for g, a, w, m, h, c, race in itertools.product(
            genders, ages, weights, muscles, heights, cups, races):
        i += 1
        extreme = (w in (0.0, 1.0) or h in (0.0, 1.0) or c in (0.0, 1.0))
        if not extreme and i % 7 != 0:
            continue
        gname = "m" if g >= 0.5 else "f"
        idn = (f"{gname}_a{int(a * 100)}_w{int(w * 100)}_mu{int(m * 100)}"
               f"_h{int(h * 100)}_c{int(c * 100)}_{race[:3]}")
        out.append((idn, _macro(g, a, w, m, h, c, race)))
        if limit and len(out) >= limit:
            break
    return out


def _arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_dir = _arg(argv, "--out", "/tmp/testset")
    limit = _arg(argv, "--limit")
    limit = int(limit) if limit else None
    os.makedirs(out_dir, exist_ok=True)

    human_svc, export_svc = _services()
    manifest = {}
    for idn, macro in _grid(limit):
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()
        human = human_svc.create_human(macro_detail_dict=macro, feet_on_ground=True)
        copy = export_svc.create_character_copy(human)
        export_svc.bake_modifiers_remove_helpers(copy, remove_helpers=True)
        bpy.ops.object.select_all(action="DESELECT")
        copy.select_set(True)
        bpy.context.view_layer.objects.active = copy
        path = os.path.join(out_dir, idn + ".glb")
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True,
                                  export_format="GLB", export_yup=True)
        manifest[idn] = macro
        print("WROTE", path)

    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("DONE", len(manifest), "bodies")


if __name__ == "__main__":
    main()
