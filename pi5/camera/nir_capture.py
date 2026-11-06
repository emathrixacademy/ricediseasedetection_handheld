"""NIR / NoIR camera capture using Picamera2 (CSI port 1).

Provides NDVI computation from the near-infrared and red channels.
Falls back to a mock implementation when hardware/libraries are missing.
"""

import os

import numpy as np

try:
    from picamera2 import Picamera2  # type: ignore
    _PICAMERA_AVAILABLE = True
except Exception:
    Picamera2 = None
    _PICAMERA_AVAILABLE = False

try:
    from PIL import Image  # type: ignore
    _PIL_AVAILABLE = True
except Exception:
    Image = None
    _PIL_AVAILABLE = False

from .. import config


class NIRCapture:
    """Capture NIR frames from the CSI-1 NoIR camera."""

    def __init__(self, camera_num=config.NIR_CAMERA_NUM,
                 resolution=config.CAPTURE_RESOLUTION):
        self.camera_num = camera_num
        self.resolution = resolution
        self.mock = not _PICAMERA_AVAILABLE
        self._cam = None
        if not self.mock:
            try:
                self._cam = Picamera2(camera_num=camera_num)
                cfg = self._cam.create_still_configuration(
                    main={"size": resolution, "format": "RGB888"}
                )
                self._cam.configure(cfg)
                self._cam.start()
            except Exception as exc:
                print(f"[NIRCapture] hardware init failed, using mock: {exc}")
                self.mock = True
                self._cam = None

    def capture(self):
        """Return an HxWx3 uint8 numpy array from the NoIR sensor."""
        if self.mock or self._cam is None:
            w, h = self.resolution
            return np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)
        return self._cam.capture_array("main")

    def save(self, path, frame=None):
        """Save ``frame`` (or a fresh capture) to ``path``. Returns the array.

        Pass the frame that was classified, so the stored image is the one
        the diagnosis was made from.
        """
        if frame is None:
            frame = self.capture()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if _PIL_AVAILABLE:
            Image.fromarray(frame).save(path)
        else:
            np.save(os.path.splitext(path)[0] + ".npy", frame)
        return frame

    def compute_ndvi(self, frame=None):
        """Per-pixel NDVI map (float32, [-1, 1]); see ai.nir_classifier.ndvi_map."""
        from ..ai.nir_classifier import ndvi_map

        if frame is None:
            frame = self.capture()
        return ndvi_map(frame)

    def close(self):
        if self._cam is not None:
            try:
                self._cam.stop()
            except Exception:
                pass


if __name__ == "__main__":
    cam = NIRCapture()
    print(f"[NIRCapture] mock={cam.mock}")
    img = cam.capture()
    print(f"Captured NIR frame: shape={img.shape}, dtype={img.dtype}")
    ndvi = cam.compute_ndvi(img)
    print(f"NDVI map: shape={ndvi.shape}, "
          f"min={ndvi.min():.3f}, max={ndvi.max():.3f}, mean={ndvi.mean():.3f}")
    cam.close()
