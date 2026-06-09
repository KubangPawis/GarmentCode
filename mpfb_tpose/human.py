"""macro params -> MPFB human (basemesh). Runs INSIDE Blender."""
import bpy


def macro_dict(gender=0.5, age=0.5, weight=0.5, muscle=0.5, height=0.5,
               cupsize=0.5, firmness=0.5, proportions=0.5, race="caucasian"):
    r = {"asian": 0.0, "caucasian": 0.0, "african": 0.0}
    r[race] = 1.0
    return {"gender": gender, "age": age, "muscle": muscle, "weight": weight,
            "proportions": proportions, "height": height, "cupsize": cupsize,
            "firmness": firmness, "race": r}


def create(human_svc, macro):
    """Clear the scene and create a fresh MPFB human; return its basemesh object."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    return human_svc.create_human(macro_detail_dict=macro, feet_on_ground=True)
