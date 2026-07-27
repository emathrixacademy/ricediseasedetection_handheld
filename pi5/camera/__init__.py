"""Camera package: RGB and NIR capture for the rice disease scanner."""

from .rgb_capture import RGBCapture
from .nir_capture import NIRCapture

__all__ = ["RGBCapture", "NIRCapture"]
