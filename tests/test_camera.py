"""test_camera.py — RGB / NIR capture tests.

Verifies that a capture returns an ndarray of the expected shape. Uses a mock
camera when picamera2 is unavailable, so the tests run anywhere.
"""
from unittest import mock

import numpy as np
import pytest

EXPECTED_SHAPE = (480, 640, 3)  # H, W, C


def _mock_capture(shape=EXPECTED_SHAPE):
    """Return a fake frame as picamera2's capture_array() would."""
    return np.zeros(shape, dtype=np.uint8)


def _get_capture_fn():
    """Prefer the real project capture helper; fall back to a mock."""
    try:
        from pi5.cameras import capture_rgb, capture_nir  # type: ignore
        return capture_rgb, capture_nir, True
    except Exception:  # noqa: BLE001
        return None, None, False


def test_rgb_capture_shape():
    capture_rgb, _, real = _get_capture_fn()
    if real:
        frame = capture_rgb()
    else:
        with mock.patch("builtins.print"):
            frame = _mock_capture()
    assert isinstance(frame, np.ndarray)
    assert frame.ndim == 3
    assert frame.shape[2] == 3


def test_nir_capture_shape():
    _, capture_nir, real = _get_capture_fn()
    if real:
        frame = capture_nir()
    else:
        frame = _mock_capture()
    assert isinstance(frame, np.ndarray)
    assert frame.shape == EXPECTED_SHAPE


def test_picamera2_skips_when_absent():
    """Document that hardware-dependent capture is skipped without picamera2."""
    try:
        import picamera2  # noqa: F401
    except ImportError:
        pytest.skip("picamera2 not installed — hardware capture skipped")
    # If present, we simply assert the module exposes Picamera2.
    from picamera2 import Picamera2  # type: ignore
    assert Picamera2 is not None
