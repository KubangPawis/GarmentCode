import yaml
from mpfb_ingest import emit

# A full, plausible 26-field measurement dict (cm / degrees), from mean_all.yaml.
FULL = {
    "arm_length": 53.97, "arm_pose_angle": 90.0, "armscye_depth": 12.87,
    "back_width": 47.68, "bum_points": 18.23, "bust": 99.84, "bust_line": 25.69,
    "bust_points": 16.95, "crotch_hip_diff": 8.81, "head_l": 26.33, "height": 171.99,
    "hip_back_width": 54.82, "hip_inclination": 9.86, "hips": 103.48, "hips_line": 23.48,
    "leg_circ": 60.20, "neck_w": 18.93, "shoulder_incl": 21.68, "shoulder_w": 36.46,
    "underbust": 86.25, "vert_bust_line": 21.14, "waist": 84.33, "waist_back_width": 39.14,
    "waist_line": 36.89, "waist_over_bust_line": 40.56, "wrist": 16.59,
}


def test_missing_required_fields_raises():
    bad = {k: v for k, v in FULL.items() if k != "waist"}
    try:
        emit.validate(bad)
        assert False, "should have raised"
    except ValueError as e:
        assert "waist" in str(e)


def test_emit_writes_yaml_with_derived_fields(tmp_path):
    out = emit.to_body_yaml(FULL, tmp_path, name="mpfb_test")
    assert out.name == "mpfb_test.yaml"
    data = yaml.safe_load(out.read_text())["body"]
    # GarmentCode serializes body floats at 3 significant figures
    # (pygarment/data_config.py), so 84.33 round-trips as 84.3.
    assert abs(data["waist"] - 84.33) < 0.5
    assert "_waist_level" in data          # derived field computed by BodyParameters
    assert "_leg_length" in data
