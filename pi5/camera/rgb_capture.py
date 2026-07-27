"""RGB camera capture using Picamera2 (CSI port 0).

Falls back to a mock implementation returning random numpy arrays when
Picamera2 or the camera hardware is unavailable, so the module can be
imported and exercised on a development laptop.
"""

import os

import numpy as np

try:
    from picamera2 import Picamera2  # type: ignore
    _PICAMERA_AVAILABLE = True
except Exception:  # ImportError or libcamera runtime errors
    Picamera2 = None
    _PICAMERA_AVAILABLE = False

try:
    from PIL import Image  # type: ignore
    _PIL_AVAILABLE = True
except Exception:
    Image = None
    _PIL_AVAILABLE = False

from .. import config


class RGBCapture:
    """Capture RGB frames from the CSI-0 camera."""

    def __init__(self, camera_num=config.RGB_CAMERA_NUM,
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
            except Exception as exc:  # hardware not present at runtime
                print(f"[RGBCapture] hardware init failed, using mock: {exc}")
                self.mock = True
                self._cam = None

    def capture(self):
        """Return an HxWx3 uint8 numpy array (RGB)."""
        if self.mock or self._cam is None:
            w, h = self.resolution
            return np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)
        return self._cam.capture_array("main")

    def save(self, path):
        """Capture a frame and save it to ``path``. Returns the array."""
        frame = self.capture()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if _PIL_AVAILABLE:
            Image.fromarray(frame).save(path)
        else:
            np.save(os.path.splitext(path)[0] + ".npy", frame)
        return frame

    def close(self):
        if self._cam is not None:
            try:
                self._cam.stop()
            except Exception:
                pass


if __name__ == "__main__":
    cam = RGBCapture()
    print(f"[RGBCapture] mock={cam.mock}")
    img = cam.capture()
    print(f"Captured RGB frame: shape={img.shape}, dtype={img.dtype}")
    cam.close()
