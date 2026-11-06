"""RGB leaf-disease classifier (MobileNetV3-Small, Hailo-8L when compiled)."""

import time

import numpy as np

from .model_loader import load_model, probs_in_config_order, resolve_model_path

try:
    from config import (CLASSES, IMAGE_SIZE, NORM_MEAN, NORM_STD,
                        RGB_MODEL_CANDIDATES, RGB_MODEL_PATH)
except ImportError:  # pragma: no cover
    from pi5.config import (CLASSES, IMAGE_SIZE, NORM_MEAN, NORM_STD,
                            RGB_MODEL_CANDIDATES, RGB_MODEL_PATH)


class RGBClassifier:
    """Classify rice leaf RGB images into one of the disease CLASSES."""

    def __init__(self, model_path=None):
        path = resolve_model_path(model_path or RGB_MODEL_PATH, RGB_MODEL_CANDIDATES)
        self.model = load_model(path)
        self.classes = CLASSES
        self.backend = getattr(self.model, "backend", "mock")
        # True when load_model fell back to random logits.
        self.mock = self.backend == "mock"

    def preprocess(self, img):
        """Resize to 224x224, scale to [0,1], normalize, return NCHW float32."""
        arr = np.asarray(img, dtype=np.float32)

        # Basic center/resize handling for common shapes.
        if arr.ndim == 2:  # grayscale -> 3 channels
            arr = np.stack([arr] * 3, axis=-1)
        arr = arr[..., :3]
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
        probs = probs_in_config_order(logits, self.model.class_names, self.classes)
        pred = max(probs, key=probs.get)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return {
            "prediction": pred,
            "confidence": probs[pred],
            "probs": probs,
            "backend": self.backend,
            "processing_time_ms": round(elapsed_ms, 2),
            "mock": self.mock,
        }


if __name__ == "__main__":
    clf = RGBClassifier()
    dummy = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    print(clf.predict(dummy))
