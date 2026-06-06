"""Validate measurements and emit a GarmentCode body YAML via BodyParameters.

The YAML is written by GarmentCode's own ``BodyParameters.save`` so the body
file matches every other body in ``assets/bodies`` exactly -- including
GarmentCode's global 3-significant-figure float formatting registered in
``pygarment/data_config.py`` (e.g. 84.33 -> 84.3). That precision is the
pipeline's native convention; we deliberately do not override it.
"""
from pathlib import Path
from assets.bodies.body_params import BodyParameters

REQUIRED = [
    "arm_length", "arm_pose_angle", "armscye_depth", "back_width", "bum_points",
    "bust", "bust_line", "bust_points", "crotch_hip_diff", "head_l", "height",
    "hip_back_width", "hip_inclination", "hips", "hips_line", "leg_circ", "neck_w",
    "shoulder_incl", "shoulder_w", "underbust", "vert_bust_line", "waist",
    "waist_back_width", "waist_line", "waist_over_bust_line", "wrist",
]

# Sanity ranges (cm / degrees) — gross-error guard, not anthropometric precision.
RANGES = {
    "height": (120, 220), "bust": (60, 160), "waist": (50, 160), "hips": (60, 170),
    "shoulder_w": (25, 55), "arm_length": (40, 75), "arm_pose_angle": (0, 180),
    "shoulder_incl": (0, 45), "hip_inclination": (0, 45),
}


def validate(measurements: dict):
    missing = [f for f in REQUIRED if f not in measurements]
    if missing:
        raise ValueError(f"Missing required measurement field(s): {missing}")
    for field, (lo, hi) in RANGES.items():
        v = measurements[field]
        if not (lo <= v <= hi):
            raise ValueError(f"Measurement '{field}'={v} out of sane range [{lo},{hi}].")


def to_body_yaml(measurements: dict, out_dir, name: str) -> Path:
    validate(measurements)
    body = BodyParameters()                 # empty, no file
    body.load_from_dict({k: float(v) for k, v in measurements.items()})
    body.save(out_dir, name=name)           # writes <out_dir>/<name>.yaml
    return Path(out_dir) / f"{name}.yaml"
