import numpy as np
import mpfb_ingest.geometry as geo


def test_central_loop_is_torso_not_arm(tpose_body_cm):
    # At arm height (140) the cut grazes both arms (~94 cm) AND the torso
    # (~100 cm). The central loop must be the torso: centred on X~=0, not an
    # arm centred near X~=+-36.
    loop = geo.central_loop(tpose_body_cm, 140.0)
    assert abs(float(np.mean(loop[:, 0]))) < 5.0
    assert 90.0 <= geo.central_perimeter(tpose_body_cm, 140.0) <= 110.0


def test_central_loop_plain_torso(tpose_body_cm):
    # Below the arms (y=100) only the torso is cut.
    assert 90.0 <= geo.central_perimeter(tpose_body_cm, 100.0) <= 110.0
