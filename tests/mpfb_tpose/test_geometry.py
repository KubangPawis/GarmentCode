import numpy as np
import pytest
from mpfb_tpose import geometry as g


def _drooped(side, deg, length=30.0):
    """A straight arm of `length` cm drooping `deg` below horizontal on `side`."""
    sx = -1.0 if side == "l" else 1.0
    shoulder = np.array([sx * 5.0, 150.0, 0.0])
    wrist = shoulder + np.array([sx * length * np.cos(np.radians(deg)),
                                 0.0, -length * np.sin(np.radians(deg))])
    return shoulder, wrist


def test_rotate_about_y_quarter_turn():
    # Right-handed about +Y: +X maps to -Z (matches mathutils.Matrix.Rotation).
    out = g.rotate_about_y([1.0, 0.0, 0.0], np.pi / 2)
    assert np.allclose(out, [0.0, 0.0, -1.0], atol=1e-9)


@pytest.mark.parametrize("side", ["l", "r"])
@pytest.mark.parametrize("deg", [10.0, 30.0, 45.0, 60.0])
def test_rotation_brings_arm_horizontal(side, deg):
    sh, wr = _drooped(side, deg)
    phi = g.y_rotation_to_horizontal(sh, wr)
    out = g.rotate_about_y(wr - sh, phi)
    assert abs(out[2]) < 1e-9                          # z -> 0 (horizontal)
    assert np.sign(out[0]) == np.sign((wr - sh)[0])    # lateral side preserved


@pytest.mark.parametrize("side", ["l", "r"])
def test_already_horizontal_needs_no_rotation(side):
    sh, wr = _drooped(side, 0.0)
    assert abs(g.y_rotation_to_horizontal(sh, wr)) < 1e-9


def test_left_and_right_take_opposite_signs():
    a = g.y_rotation_to_horizontal(*_drooped("l", 45.0))
    b = g.y_rotation_to_horizontal(*_drooped("r", 45.0))
    assert a * b < 0


def test_droop_metric_zero_when_horizontal():
    assert g.droop_from_horizontal_deg(*_drooped("r", 0.0)) < 1e-6


def test_droop_metric_matches_input_angle():
    assert abs(g.droop_from_horizontal_deg(*_drooped("r", 35.0)) - 35.0) < 1e-6


@pytest.mark.parametrize("side", ["l", "r"])
def test_fallback_brings_canonical_arm_horizontal(side):
    phi = g.fallback_y_rotation(side, 45.0)
    sx = -1.0 if side == "l" else 1.0
    v = np.array([sx * np.cos(np.radians(45)), 0.0, -np.sin(np.radians(45))])
    out = g.rotate_about_y(v, phi)
    assert abs(out[2]) < 1e-9
    assert np.sign(out[0]) == sx
