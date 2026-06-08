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
    """Single-axis sweeps off a fixed female base + a male base, so the
    cross-body property tests always have clean one-variable groups (vary
    weight only / height only / cup only / gender only). Deterministic.
    """
    base = dict(g=0.0, a=0.5, w=0.5, mu=0.5, h=0.5, c=0.5, race="caucasian")
    out = [("neutral", _macro(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, "caucasian"))]
    seen = {"neutral"}

    def add(**kw):
        p = {**base, **kw}
        gname = "m" if p["g"] >= 0.5 else "f"
        idn = (f"{gname}_a{int(p['a'] * 100)}_w{int(p['w'] * 100)}"
               f"_mu{int(p['mu'] * 100)}_h{int(p['h'] * 100)}"
               f"_c{int(p['c'] * 100)}_{p['race'][:3]}")
        if idn in seen:
            return
        seen.add(idn)
        out.append((idn, _macro(p["g"], p["a"], p["w"], p["mu"],
                                p["h"], p["c"], p["race"])))

    add()                                            # female base
    for w in (0.0, 0.25, 0.5, 0.75, 1.0):            # weight sweep -> waist
        add(w=w)
    for h in (0.0, 0.25, 0.5, 0.75):                 # height sweep -> stature
        add(h=h)                                     # h=1.0 ~ 2.3 m, past sane range
    for c in (0.0, 0.25, 0.5, 0.75, 1.0):            # cup sweep -> bust
        add(c=c)
    for mu in (0.0, 0.5, 1.0):                       # muscle sweep
        add(mu=mu)
    for race in ("caucasian", "asian", "african"):   # ethnicity at base
        add(race=race)
    # male base (cup irrelevant) + male weight/height sweeps; the female and
    # male c=0 bodies differ only in gender -> shoulder_w comparison.
    for w in (0.0, 0.5, 1.0):
        add(g=1.0, c=0.0, w=w)
    for h in (0.0, 0.5, 0.75):
        add(g=1.0, c=0.0, h=h)

    if limit:
        out = out[:limit]
    return out


def _bake_shape_keys(ob):
    """Flatten MPFB macro shape keys into the mesh basis.

    MPFB drives the macro sliders (weight/height/cup/...) as Blender shape
    keys, so the un-baked mesh basis is the neutral body for every macro and
    glTF would export the morph as a target the downstream trimesh loader
    ignores. Bake the current mix into the basis, then drop all keys.
    """
    keys = ob.data.shape_keys
    if not keys or not keys.key_blocks:
        return
    ob.shape_key_add(name="_baked", from_mix=True)
    for kb in list(ob.data.shape_keys.key_blocks):
        if kb.name != "_baked":
            ob.shape_key_remove(kb)
    ob.shape_key_remove(ob.data.shape_keys.key_blocks["_baked"])


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
        _bake_shape_keys(copy)
        bpy.ops.object.select_all(action="DESELECT")
        copy.select_set(True)
        bpy.context.view_layer.objects.active = copy
        path = os.path.join(out_dir, idn + ".glb")
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True,
                                  export_format="GLB", export_yup=True,
                                  export_morph=False)
        manifest[idn] = macro
        print("WROTE", path)

    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("DONE", len(manifest), "bodies")


if __name__ == "__main__":
    main()
