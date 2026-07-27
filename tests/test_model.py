"""test_model.py — classifier interface inference test with a mock model.

Runs a synthetic 224x224x3 image through the classifier and asserts the output
is a valid 6-class probability distribution (softmax sums to ~1).
"""
import numpy as np
import pytest

CLASSES = [
    "healthy",
    "rice_blast",
    "bacterial_leaf_blight",
    "nitrogen_deficiency",
    "water_deficit",
    "heat_stress",
]
NUM_CLASSES = len(CLASSES)


def softmax(x):
    x = np.asarray(x, dtype=np.float64)
    e = np.exp(x - np.max(x))
    return e / e.sum()


class MockClassifier:
    """Stand-in for the RGB MobileNetV3 / Hailo classifier interface.

    Real implementation would run ONNX/HEF inference; here we produce
    deterministic pseudo-logits from the image content.
    """

    classes = CLASSES

    def preprocess(self, image):
        assert image.shape == (224, 224, 3), "expected 224x224x3 input"
        return image.astype(np.float32) / 255.0

    def predict(self, image):
        x = self.preprocess(image)
        # Deterministic pseudo-logits derived from channel-region means.
        rng = np.random.default_rng(int(x.sum()) % (2**32))
        logits = rng.standard_normal(NUM_CLASSES)
        probs = softmax(logits)
        return {self.classes[i]: float(probs[i]) for i in range(NUM_CLASSES)}


@pytest.fixture
def synthetic_image():
    rng = np.random.default_rng(42)
    return (rng.random((224, 224, 3)) * 255).astype(np.uint8)


def test_output_has_six_classes(synthetic_image):
    out = MockClassifier().predict(synthetic_image)
    assert len(out) == NUM_CLASSES
    assert set(out.keys()) == set(CLASSES)


def test_probs_sum_to_one(synthetic_image):
    out = MockClassifier().predict(synthetic_image)
    assert sum(out.values()) == pytest.approx(1.0, abs=1e-6)


def test_probs_in_range(synthetic_image):
    out = MockClassifier().predict(synthetic_image)
    assert all(0.0 <= p <= 1.0 for p in out.values())


def test_rejects_wrong_shape():
    bad = np.zeros((100, 100, 3), dtype=np.uint8)
    with pytest.raises(AssertionError):
        MockClassifier().predict(bad)


def test_late_fusion_weights():
    """Fusion weights RGB 0.5 / NIR 0.3 / Bio 0.2 must sum to 1 and produce
    a valid distribution."""
    w_rgb, w_nir, w_bio = 0.5, 0.3, 0.2
    assert w_rgb + w_nir + w_bio == pytest.approx(1.0)

    rgb = softmax(np.random.default_rng(1).standard_normal(NUM_CLASSES))
    nir = softmax(np.random.default_rng(2).standard_normal(NUM_CLASSES))
    bio = softmax(np.random.default_rng(3).standard_normal(NUM_CLASSES))
    fused = w_rgb * rgb + w_nir * nir + w_bio * bio
    assert fused.sum() == pytest.approx(1.0, abs=1e-6)
    assert 0 <= int(np.argmax(fused)) < NUM_CLASSES
