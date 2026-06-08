from pathlib import Path
import numpy as np
from mpfb_ingest import mesh_io, autolandmarks as al

BASE = Path("mpfb_ingest/data/mpfb_base_body.obj")


def _base_cm():
    raw = mesh_io.load_body(str(BASE))
    mm, _ = mesh_io.normalize(raw, expected_height_m=1.7)
    return mesh_io.to_cm(mm)


def test_find_levels_ordered_on_real_base():
    cm = _base_cm()
    lv = al.find_levels(cm)
    # anatomical ordering by height (cm, feet at 0)
    assert lv["crotch"] < lv["hips"] < lv["waist"] < lv["underbust"] < lv["bust"] < lv["neck"]
    # plausible bands for a ~170 cm body
    assert 70 <= lv["hips"] <= 100
    assert 95 <= lv["waist"] <= 120
    assert 120 <= lv["bust"] <= 145
