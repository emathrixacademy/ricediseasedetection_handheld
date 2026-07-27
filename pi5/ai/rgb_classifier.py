"""RGB leaf-disease classifier (MobileNetV3-Small style)."""

import time

import numpy as np

from .model_loader import load_model

try:
    from config import CLASSES, IMAGE_SIZE, NORM_MEAN, NORM_STD, RGB_MODEL_PATH
except ImportError:  # pragma: no cover
    from pi5.config import CLASSES, IMAGE_SIZE, NORM_MEAN, NORM_STD, RGB_MODEL_PATH


def _softmax(logits):
    logits = np.asarray(logits, dtype=np.float32).ravel()
    shifted = logits - np.max(logits)
    exp = np.exp(shifted)
    return exp / np.sum(exp)


class RGBClassifier:
    """Classify rice leaf RGB images into one of the disease CLASSES."""

    def __init__(self, model_path=RGB_MODEL_PATH):
        self.model = load_model(model_path)
        self.classes = CLASSES

    def preprocess(self, img):
        """Resize to 224x224, scale to [0,1], normalize, return NCHW float32."""
        arr = np.asarray(img, dtype=np.float32)

        # Basic center/resize handling for common shapes.
        if arr.ndim == 2:  # grayscale -> 3 channels
            arr = np.stack([arr] * 3, axis=-1)
        if arr.shape[:2] != IMAGE_SIZE:
            arr = self._resize(arr, IMAGE_SIZE)

        if arr.max() > 1.0:
            arr = arr / 255.0

        mean = np.array(NORM_MEAN, dtype=np.float32)
        std = np.array(NORM_STD, dtype=np.float32)
        arr = (arr - mean) / std

        # HWC -> NCHW
        arr = np.transpose(arr, (2, 0, 1))[np.newaxis, ...]
        return arr.astype(np.float32)

    @staticmethod
    def _resize(arr, size):
        """Lightweight nearest-neighbor resize (avoids a hard PIL/cv2 dep)."""
        h, w = arr.shape[:2]
        yi = (np.linspace(0, h - 1, size[0])).astype(int)
        xi = (np.linspace(0, w - 1, size[1])).astype(int)
        return arr[np.ix_(yi, xi)]

    def predict(self, img):
        """Run inference; return prediction dict with timing."""
        start = time.perf_counter()
        tensor = self.preprocess(img)
        logits = self.model(tensor)
        probs = _softmax(logits)
        idx = int(np.argmax(probs))
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return {
            "prediction": self.classes[idx],
            "confidence": float(probs[idx]),
            "probs": {c: float(p) for c, p in zip(self.classes, probs)},
            "processing_time_ms": round(elapsed_ms, 2),
        }


if __name__ == "__main__":
    clf = RGBClassifier()
    dummy = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    print(clf.predict(dummy))
