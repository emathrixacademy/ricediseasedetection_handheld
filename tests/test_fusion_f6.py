"""Characterisation tests for finding F-6 — biosensor influence on fusion.

WARNING TO FUTURE READERS
-------------------------
These tests **document current behaviour, which is under review as F-6**.
They are NOT a specification of desired behaviour. Do not "fix" a failure here
by adjusting the assertion — if these tests start failing, it most likely means
the fusion redesign landed, and the tests should be rewritten to match the new
intended semantics (and this docstring deleted).

The finding
-----------
``DecisionFusion.fuse()`` gives RGB and NIR a full six-class probability
vector each, but the biosensor contributes only a *scalar* in [0, 1]. That
scalar does not vote for any class. It is applied as::

    bio_weight = weights["biosensor"] * signal
    combined  += bio_weight * (combined / total_weight)

which scales the existing imaging consensus by a positive constant. Every
class is scaled by the *same* factor and the vector is then renormalised, so
the scaling cancels exactly.

The consequence is stronger than "the biosensor cannot change the class". It
contributes **no information at all**: with the biosensor at 0 uA, at 40 uA,
or absent entirely, the fused distribution is identical to within float32
rounding (observed delta ~6e-8, below the float32 epsilon of 1.19e-7). Neither
the diagnosed class nor the reported confidence moves by any meaningful
amount. Its nominal 0.2 weight is applied to a quantity that is then divided
straight back out. These tests pin that down numerically.

Why that matters for this device: the microneedle biosensor is the project's
novel contribution, and its clinical value is detecting biotic infection
*before* visible symptoms appear. In the current design a pre-symptomatic
infection — healthy-looking leaf, strong biosensor signal — cannot overturn a
confident ``healthy`` imaging verdict. Whether that is acceptable is a design
decision recorded as F-6 and awaiting sign-off.
"""

import numpy as np
import pytest

from pi5.ai.fusion import DecisionFusion
from pi5.config import CLASSES

# Biosensor signal is normalised in main.py as peak_current_ua / 50.0.
BIO_FULL_SCALE_UA = 50.0


def _confident_probs(label, confidence):
    """A probability vector concentrated on `label`, remainder spread evenly."""
    others = (1.0 - confidence) / (len(CLASSES) - 1)
    return {c: (confidence if c == label else others) for c in CLASSES}


def _signal_from_ua(peak_ua):
    """Mirror RiceScanner._biosensor_signal()."""
    return max(0.0, min(1.0, peak_ua / BIO_FULL_SCALE_UA))


def test_biosensor_cannot_override_imaging_consensus(capsys):
    """A 40 uA biosensor signal cannot overturn a confident `healthy` verdict.

    DOCUMENTS CURRENT BEHAVIOUR (F-6) — not desired behaviour. See module
    docstring before changing this assertion.
    """
    fusion = DecisionFusion()
    rgb = {"probs": _confident_probs("healthy", 0.85)}
    nir = {"probs": _confident_probs("healthy", 0.80)}

    strong = fusion.fuse(rgb, nir, biosensor_signal=_signal_from_ua(40.0))
    absent = fusion.fuse(rgb, nir, biosensor_signal=_signal_from_ua(0.0))

    with capsys.disabled():
        print()
        print("  F-6 characterisation — imaging says healthy (RGB .85 / NIR .80)")
        print(f"    biosensor 40 uA (signal {_signal_from_ua(40.0):.2f}): "
              f"{strong['final_diagnosis']:<10} "
              f"confidence {strong['final_confidence']:.12f}  "
              f"bio_weight {strong['biosensor_weight']}")
        print(f"    biosensor  0 uA (signal {_signal_from_ua(0.0):.2f}): "
              f"{absent['final_diagnosis']:<10} "
              f"confidence {absent['final_confidence']:.12f}  "
              f"bio_weight {absent['biosensor_weight']}")
        delta = strong["final_confidence"] - absent["final_confidence"]
        print(f"    class identical: "
              f"{strong['final_diagnosis'] == absent['final_diagnosis']}"
              f"   confidence delta: {delta:+.3e}  "
              f"(float32 eps = {np.finfo(np.float32).eps:.3e})")

    # A strong biosensor signal does not change the diagnosed class...
    assert strong["final_diagnosis"] == "healthy"
    # ...and neither does its complete absence.
    assert absent["final_diagnosis"] == "healthy"
    # The class outcome is identical regardless of biosensor input.
    assert strong["final_diagnosis"] == absent["final_diagnosis"]

    # The weight really was applied -- this is not a skipped code path...
    assert strong["biosensor_weight"] > 0.0
    assert absent["biosensor_weight"] == 0.0
    # ...yet the confidence is unchanged to within float32 rounding, because
    # the uniform scaling cancels in renormalisation. The biosensor
    # contributes no usable information. 1e-6 is far below any confidence
    # change an operator could act on, and far above float32 epsilon.
    assert strong["final_confidence"] == pytest.approx(
        absent["final_confidence"], abs=1e-6)


def test_biosensor_changes_neither_class_nor_confidence_across_full_range():
    """Sweeping the biosensor 0 -> 80 uA changes neither class nor confidence.

    DOCUMENTS CURRENT BEHAVIOUR (F-6). Demonstrates the invariance is
    structural, not an artefact of the two values chosen above.
    """
    fusion = DecisionFusion()
    rgb = {"probs": _confident_probs("healthy", 0.85)}
    nir = {"probs": _confident_probs("healthy", 0.80)}

    diagnoses, confidences = set(), set()
    for peak_ua in (0.0, 5.0, 12.5, 25.0, 37.5, 50.0, 80.0):
        fused = fusion.fuse(rgb, nir, biosensor_signal=_signal_from_ua(peak_ua))
        diagnoses.add(fused["final_diagnosis"])
        confidences.add(fused["final_confidence"])

    assert diagnoses == {"healthy"}, (
        "biosensor input changed the diagnosed class -- if this is intended, "
        "F-6 has been redesigned and this test must be rewritten"
    )
    # The scaling cancels in renormalisation, so confidence is invariant too
    # (to within float32 rounding across the whole 0 -> 80 uA range).
    assert max(confidences) - min(confidences) < 1e-6, (
        f"confidence spread {max(confidences) - min(confidences):.3e} exceeds "
        f"float32 noise -- the biosensor may now carry real weight (F-6 "
        f"redesign?); rewrite this test to match the new semantics"
    )


def test_fused_distribution_is_scaled_not_reweighted():
    """The biosensor scales the imaging distribution uniformly.

    DOCUMENTS CURRENT BEHAVIOUR (F-6). This is the mechanism behind the
    invariance: post-renormalisation the distribution is *unchanged*, so the
    biosensor contributes no class-discriminative information at all.
    """
    fusion = DecisionFusion()
    rgb = {"probs": _confident_probs("healthy", 0.85)}
    nir = {"probs": _confident_probs("rice_blast", 0.60)}

    with_bio = fusion.fuse(rgb, nir, biosensor_signal=1.0)
    without = fusion.fuse(rgb, nir, biosensor_signal=None)

    a = np.array([with_bio["fused_probs"][c] for c in CLASSES])
    b = np.array([without["fused_probs"][c] for c in CLASSES])

    # Identical to floating-point tolerance: the biosensor moved nothing.
    assert np.allclose(a, b, atol=1e-6), (
        "biosensor altered the fused distribution -- F-6 may have been "
        "redesigned; rewrite this test to match the new semantics"
    )


@pytest.mark.parametrize("imaging_label", ["healthy", "rice_blast"])
def test_invariance_holds_regardless_of_imaging_verdict(imaging_label):
    """The invariance is not specific to a `healthy` consensus.

    DOCUMENTS CURRENT BEHAVIOUR (F-6).
    """
    fusion = DecisionFusion()
    rgb = {"probs": _confident_probs(imaging_label, 0.85)}
    nir = {"probs": _confident_probs(imaging_label, 0.80)}

    hot = fusion.fuse(rgb, nir, biosensor_signal=1.0)
    cold = fusion.fuse(rgb, nir, biosensor_signal=0.0)

    assert hot["final_diagnosis"] == cold["final_diagnosis"] == imaging_label
