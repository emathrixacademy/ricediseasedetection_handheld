"""NIR classifier: same interface as RGBClassifier plus NDVI computation."""

import time

import numpy as np

from .model_loader import load_model

try:
    from config import CLASSES, IMAGE_SIZE, NIR_MODEL_PATH
except ImportError:  # pragma: no cover
    from pi5.config import CLASSES, IMAGE_SIZE, NIR_MODEL_PATH


def _softmax(logits):
    logits = np.asarray(logits, dtype=np.float32).ravel()
    shifted = logits - np.max(logits)
    exp = np.exp(shifted)
    return exp / np.sum(exp)


class NIRClassifier:
    """Classify near-infrared imagery and derive an NDVI vegetation index.

    Input images are expected with at least two channels ordered as
    (NIR, RED, ...) or a 2-channel (NIR, RED) array. NDVI = (NIR-RED)/(NIR+RED).
    """

    def __init__(self, model_path=NIR_MODEL_PATH):
        self.model = load_model(model_path)
        self.classes = CLASSES

    @staticmethod
    def _resize(arr, size):
        h, w = arr.shape[:2]
        yi = np.linspace(0, h - 1, size[0]).astype(int)
        xi = np.linspace(0, w - 1, size[1]).astype(int)
        return arr[np.ix_(yi, xi)]

    def compute_ndvi(self, img):
        """Return mean NDVI in [-1, 1] from an (H, W, >=2) array (NIR, RED)."""
        arr = np.asarray(img, dtype=np.float32)
        if arr.ndim < 3 or arr.shape[-1] < 2:
            return 0.0
        nir = arr[..., 0]
        red = arr[..., 1]
        denom = nir + red
        denom[denom == 0] = 1e-6
        ndvi = (nir - red) / denom
        return float(np.clip(np.mean(ndvi), -1.0, 1.0))

    def preprocess(self, img):
        """Resize to model input and produce an NCHW float32 tensor."""
        arr = np.asarray(img, dtype=np.float32)
        if arr.ndim == 2:
            arr = arr[..., np.newaxis]
        if arr.shape[:2] != IMAGE_SIZE:
            arr = self._resize(arr, IMAGE_SIZE)

        # Pad/trim to 3 channels for a shared backbone.
        if arr.shape[-1] < 3:
            pad = np.repeat(arr[..., :1], 3 - arr.shape[-1], axis=-1)
            arr = np.concatenate([arr, pad], axis=-1)
        arr = arr[..., :3]

        if arr.max() > 1.0:
            arr = arr / 255.0
        arr = np.transpose(arr, (2, 0, 1))[np.newaxis, ...]
        return arr.astype(np.float32)

    def predict(self, img):
        """Run inference; return prediction dict including ndvi_value."""
        start = time.perf_counter()
        ndvi = self.compute_ndvi(img)
        tensor = self.preprocess(img)
        logits = self.model(tensor)
        probs = _softmax(logits)
        idx = int(np.argmax(probs))
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return {
            "prediction": self.classes[idx],
            "confidence": float(probs[idx]),
            "probs": {c: float(p) for c, p in zip(self.classes, probs)},
            "ndvi_value": round(ndvi, 4),
            "processing_time_ms": round(elapsed_ms, 2),
        }


if __name__ == "__main__":
    clf = NIRClassifier()
    dummy = np.random.rand(224, 224, 2).astype(np.float32)
    print(clf.predict(dummy))
