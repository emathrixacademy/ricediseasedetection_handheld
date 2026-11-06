"""NIR classifier: same interface as RGBClassifier plus NDVI computation."""

import time

import numpy as np

from .model_loader import load_model, probs_in_config_order, resolve_model_path

try:
    from config import (CLASSES, IMAGE_SIZE, NDVI_NIR_CHANNEL, NDVI_VIS_CHANNEL,
                        NIR_MODEL_CANDIDATES, NIR_MODEL_PATH, NIR_NORM_MEAN,
                        NIR_NORM_STD)
except ImportError:  # pragma: no cover
    from pi5.config import (CLASSES, IMAGE_SIZE, NDVI_NIR_CHANNEL,
                            NDVI_VIS_CHANNEL, NIR_MODEL_CANDIDATES,
                            NIR_MODEL_PATH, NIR_NORM_MEAN, NIR_NORM_STD)


def ndvi_map(frame):
    """Per-pixel NDVI from a filtered NoIR frame, float32 in [-1, 1].

    NDVI = (NIR - VIS) / (NIR + VIS). Which colour channel carries the NIR
    and which the visible band depends on the filter fitted to the NoIR
    camera; see NDVI_NIR_CHANNEL / NDVI_VIS_CHANNEL in config.py.
    """
    arr = np.asarray(frame, dtype=np.float32)
    if arr.ndim < 3 or arr.shape[-1] < 3:
        return np.zeros(arr.shape[:2], dtype=np.float32)
    nir = arr[..., NDVI_NIR_CHANNEL]
    vis = arr[..., NDVI_VIS_CHANNEL]
    denom = nir + vis
    denom[denom == 0] = 1e-6
    return np.clip((nir - vis) / denom, -1.0, 1.0).astype(np.float32)


class NIRClassifier:
    """Classify NoIR images and derive an NDVI vegetation index.

    The model is the single-channel network from training/train_nir.py: the
    frame is converted to greyscale (ITU-R 601 weights, as torchvision's
    Grayscale) and normalised with NIR_NORM_MEAN / NIR_NORM_STD.
    """

    def __init__(self, model_path=None):
        path = resolve_model_path(model_path or NIR_MODEL_PATH, NIR_MODEL_CANDIDATES)
        self.model = load_model(path)
        self.classes = CLASSES
        self.backend = getattr(self.model, "backend", "mock")
        # True when load_model fell back to random logits.
        self.mock = self.backend == "mock"

    @staticmethod
    def _resize(arr, size):
        h, w = arr.shape[:2]
        yi = np.linspace(0, h - 1, size[0]).astype(int)
        xi = np.linspace(0, w - 1, size[1]).astype(int)
        return arr[np.ix_(yi, xi)]

    def compute_ndvi(self, img):
        """Mean NDVI of the frame, in [-1, 1]."""
        return float(np.mean(ndvi_map(img)))

    def preprocess(self, img):
        """Greyscale, resize, normalise; return a (1, 1, H, W) float32 tensor."""
        arr = np.asarray(img, dtype=np.float32)
        if arr.ndim == 3 and arr.shape[-1] >= 3:
            arr = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
        elif arr.ndim == 3:
            arr = arr[..., 0]
        if arr.shape[:2] != IMAGE_SIZE:
            arr = self._resize(arr, IMAGE_SIZE)
        if arr.max() > 1.0:
            arr = arr / 255.0
        arr = (arr - NIR_NORM_MEAN) / NIR_NORM_STD
        return arr[np.newaxis, np.newaxis, ...].astype(np.float32)

    def predict(self, img):
        """Run inference; return prediction dict including ndvi_value."""
        start = time.perf_counter()
        ndvi = self.compute_ndvi(img)
        tensor = self.preprocess(img)
        logits = self.model(tensor)
        probs = probs_in_config_order(logits, self.model.class_names, self.classes)
        pred = max(probs, key=probs.get)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return {
            "prediction": pred,
            "confidence": probs[pred],
            "probs": probs,
            "ndvi_value": round(ndvi, 4),
            "backend": self.backend,
            "processing_time_ms": round(elapsed_ms, 2),
            "mock": self.mock,
        }


if __name__ == "__main__":
    clf = NIRClassifier()
    dummy = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    print(clf.predict(dummy))
