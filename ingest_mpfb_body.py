"""CLI: MPFB body OBJ -> GarmentCode body-measurements YAML.

Usage:
  ./.venv/bin/python ingest_mpfb_body.py avatar.obj --name avatar \
      --landmarks mpfb_ingest/data/makehuman_landmarks.json \
      --arm-pose-angle 90 --out assets/bodies --save-obj
"""
import argparse

from mpfb_ingest import mesh_io, measurements, emit
from mpfb_ingest.landmarks import Landmarks

# Conservative fallback values (cm/deg) used only with --fill-defaults for fields
# whose landmarks are not yet calibrated. From mean_all.yaml.
_DEFAULTS = {
    "arm_length": 53.97, "armscye_depth": 12.87, "back_width": 47.68,
    "bum_points": 18.23, "bust": 99.84, "bust_line": 25.69, "bust_points": 16.95,
    "crotch_hip_diff": 8.81, "head_l": 26.33, "hip_back_width": 54.82,
    "hip_inclination": 9.86, "hips": 103.48, "hips_line": 23.48, "leg_circ": 60.20,
    "neck_w": 18.93, "shoulder_incl": 21.68, "shoulder_w": 36.46, "underbust": 86.25,
    "vert_bust_line": 21.14, "waist": 84.33, "waist_back_width": 39.14,
    "waist_line": 36.89, "waist_over_bust_line": 40.56, "wrist": 16.59,
}


def run(obj_path, out_dir, name, landmarks_path, arm_pose_angle,
        height_m=1.7, save_obj=False, fill_defaults=False):
    raw = mesh_io.load_body(obj_path)
    mesh_m, report = mesh_io.normalize(raw, expected_height_m=height_m)
    cm = mesh_io.to_cm(mesh_m)

    lm = Landmarks.load(landmarks_path)
    if lm.n_vertices_expected:
        lm.validate(cm)

    measured = measurements.compute_all(cm, lm, arm_pose_angle=arm_pose_angle)
    # height also comes from compute_all (measurements.distances); reasserted here
    # so the CLI owns it directly even if the measurement grouping is refactored.
    measured["height"] = float(cm.bounds[1][1] - cm.bounds[0][1])

    if fill_defaults:
        for k, v in _DEFAULTS.items():
            measured.setdefault(k, v)

    out_yaml = emit.to_body_yaml(measured, out_dir, name)
    if save_obj:
        mesh_io.save_body_obj(mesh_m, out_dir, name)
    print(f"Wrote {out_yaml}  (scale_to_m={report['scale_to_m']:.4f}, "
          f"verts={report['n_vertices']})")
    return out_yaml


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("obj")
    ap.add_argument("--name", required=True)
    ap.add_argument("--landmarks", required=True)
    ap.add_argument("--arm-pose-angle", type=float, required=True,
                    help="Arm pose at the shoulder joint (deg). See module README.")
    ap.add_argument("--out", default="assets/bodies")
    ap.add_argument("--height-m", type=float, default=1.7)
    ap.add_argument("--save-obj", action="store_true")
    ap.add_argument("--fill-defaults", action="store_true",
                    help="Fill not-yet-calibrated fields with neutral-body values.")
    a = ap.parse_args()
    run(a.obj, a.out, a.name, a.landmarks, a.arm_pose_angle,
        height_m=a.height_m, save_obj=a.save_obj, fill_defaults=a.fill_defaults)


if __name__ == "__main__":
    main()
