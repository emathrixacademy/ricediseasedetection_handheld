"""Late fusion with a calibrated biosensor (replaces the F-6 characterisation).

F-6 found that the biosensor only scaled the imaging consensus, so it could
change neither the class nor the confidence. The biosensor now carries its
own class distribution (BiosensorClassifier, from calibration data), and
joins fusion only when calibrated.
"""

import json

import numpy as np
import pytest

from pi5.ai.biosensor_model import BiosensorClassifier
from pi5.ai.fusion import DecisionFusion
from pi5.config import CLASSES


def _confident(label, confidence):
    others = (1.0 - confidence) / (len(CLASSES) - 1)
    return {"probs": {c: (confidence if c == label else others) for c in CLASSES}}


def test_imaging_only_when_biosensor_absent():
    fused = DecisionFusion().fuse(_confident("healthy", 0.85),
                                  _confident("healthy", 0.80))
    assert fused["final_diagnosis"] == "healthy"
    assert fused["modalities"] == ["nir", "rgb"]
    assert sum(fused["fused_probs"].values()) == pytest.approx(1.0)


def test_weights_are_renormalised_over_present_modalities():
    fused = DecisionFusion().fuse(_confident("rice_blast", 1.0), None)
    assert fused["final_confidence"] == pytest.approx(1.0)
    assert fused["weights_used"] == {"rgb": 1.0}


def test_biosensor_can_change_the_class():
    """Leaf leaning healthy, strong calibrated biosensor evidence of blight.

    With the biosensor at weight 0.2 it overrides a weak imaging verdict
    (30 % healthy) but not a firm one: that balance is set by FUSION_WEIGHTS.
    """
    rgb = _confident("healthy", 0.30)
    nir = _confident("healthy", 0.30)
    bio = _confident("bacterial_leaf_blight", 0.98)
    without = DecisionFusion().fuse(rgb, nir)
    with_bio = DecisionFusion().fuse(rgb, nir, bio)
    assert without["final_diagnosis"] == "healthy"
    assert with_bio["final_diagnosis"] == "bacterial_leaf_blight"


def test_biosensor_moves_confidence():
    rgb, nir = _confident("rice_blast", 0.7), _confident("rice_blast", 0.7)
    agree = DecisionFusion().fuse(rgb, nir, _confident("rice_blast", 0.9))
    disagree = DecisionFusion().fuse(rgb, nir, _confident("healthy", 0.9))
    assert agree["final_confidence"] > disagree["final_confidence"] + 0.1


@pytest.fixture
def calibration(tmp_path):
    feats = ["peak_height_ua", "peak_voltage_v"]
    cal = {"analytes": {"H2O2": {"features": feats, "classes": {
        "healthy": {"mean": [0.6, 0.25], "std": [0.2, 0.02], "n": 20},
        "bacterial_leaf_blight": {"mean": [4.0, 0.25], "std": [0.6, 0.02], "n": 20},
    }}}}
    path = tmp_path / "cal.json"
    path.write_text(json.dumps(cal))
    return str(path)


def test_uncalibrated_biosensor_returns_none(tmp_path):
    clf = BiosensorClassifier(path=str(tmp_path / "missing.json"))
    assert not clf.calibrated
    assert clf.predict({"H2O2": {"peak_height_ua": 4.0, "peak_voltage_v": 0.25}}) is None


def test_calibrated_biosensor_picks_nearest_class(calibration):
    clf = BiosensorClassifier(path=calibration)
    high = clf.predict({"H2O2": {"peak_height_ua": 3.8, "peak_voltage_v": 0.25}})
    low = clf.predict({"H2O2": {"peak_height_ua": 0.5, "peak_voltage_v": 0.25}})
    assert high["prediction"] == "bacterial_leaf_blight"
    assert low["prediction"] == "healthy"
    assert sum(high["probs"].values()) == pytest.approx(1.0)
    # Classes with no calibration data never win over calibrated ones.
    assert high["probs"]["heat_stress"] <= high["probs"]["healthy"] + 1e-12


def test_biosensor_ignores_uncalibrated_analyte(calibration):
    clf = BiosensorClassifier(path=calibration)
    assert clf.predict({"NO3": {"peak_height_ua": 1.0, "peak_voltage_v": -0.4}}) is None


def test_fused_probs_are_a_distribution():
    rng = np.random.default_rng(0)
    for _ in range(20):
        mods = []
        for _ in range(3):
            p = rng.dirichlet(np.ones(len(CLASSES)))
            mods.append({"probs": dict(zip(CLASSES, p))})
        fused = DecisionFusion().fuse(*mods)
        assert sum(fused["fused_probs"].values()) == pytest.approx(1.0)
