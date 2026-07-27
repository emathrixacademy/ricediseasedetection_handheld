"""Hailo-8 accelerator inference wrapper (with mock fallback).

Uses the ``hailo_platform`` SDK when present. When the SDK or the compiled HEF
file is unavailable, a mock backend returning random logits is used so the rest
of the pipeline can run on a development machine.
"""

import os
import time

import numpy as np

try:
    from hailo_platform import (
        HEF,
        ConfigureParams,
        FormatType,
        HailoStreamInterface,
        InferVStreams,
        InputVStreamParams,
        OutputVStreamParams,
        VDevice,
    )

    _HAS_HAILO = True
except ImportError:  # pragma: no cover - Hailo SDK is Pi-only
    _HAS_HAILO = False

try:
    from config import CLASSES, HAILO_HEF_PATH, NUM_CLASSES
except ImportError:  # pragma: no cover
    from pi5.config import CLASSES, HAILO_HEF_PATH, NUM_CLASSES


class HailoInference:
    """Run inference on a Hailo device, or mock it when unavailable."""

    def __init__(self, hef_path=HAILO_HEF_PATH):
        self.hef_path = hef_path
        self.classes = CLASSES
        self.mock = True
        self._target = None
        self._network_group = None
        self._in_params = None
        self._out_params = None

        if _HAS_HAILO and hef_path and os.path.exists(hef_path):
            try:
                self._load_hef(hef_path)
                self.mock = False
            except Exception as exc:  # pragma: no cover - hardware dependent
                print(f"[hailo] load failed: {exc}; falling back to mock")

    def _load_hef(self, hef_path):  # pragma: no cover - requires hardware
        hef = HEF(hef_path)
        self._target = VDevice()
        configure_params = ConfigureParams.create_from_hef(
            hef=hef, interface=HailoStreamInterface.PCIe
        )
        self._network_group = self._target.configure(hef, configure_params)[0]
        self._in_params = InputVStreamParams.make(
            self._network_group, format_type=FormatType.FLOAT32
        )
        self._out_params = OutputVStreamParams.make(
            self._network_group, format_type=FormatType.FLOAT32
        )

    def infer(self, input_array):
        """Return dict with logits and processing time."""
        start = time.perf_counter()

        if self.mock:
            logits = np.random.randn(1, NUM_CLASSES).astype(np.float32)
        else:  # pragma: no cover - requires hardware
            with InferVStreams(
                self._network_group, self._in_params, self._out_params
            ) as pipeline:
                with self._network_group.activate():
                    name = self._network_group.get_input_vstream_infos()[0].name
                    results = pipeline.infer({name: np.asarray(input_array)})
            logits = np.asarray(list(results.values())[0], dtype=np.float32)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "logits": logits,
            "backend": "mock" if self.mock else "hailo",
            "processing_time_ms": round(elapsed_ms, 2),
        }


if __name__ == "__main__":
    engine = HailoInference()
    dummy = np.random.rand(1, 224, 224, 3).astype(np.float32)
    print(engine.infer(dummy))
