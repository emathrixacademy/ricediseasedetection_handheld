"""Model loader supporting .pt (PyTorch), .tflite (TensorFlow) and .onnx.

Each loader returns a plain callable wrapper: ``wrapper(input_array) -> logits``
so downstream classifiers do not need to know the backend. When a backend or
model file is unavailable, a mock wrapper that emits random logits is returned.
"""

import os

import numpy as np

# --- optional heavy imports (wrapped so the module always loads) ------------
try:
    import torch

    _HAS_TORCH = True
except ImportError:  # pragma: no cover - depends on environment
    torch = None
    _HAS_TORCH = False

try:
    import tensorflow as tf

    _HAS_TF = True
except ImportError:  # pragma: no cover
    tf = None
    _HAS_TF = False

try:
    import onnxruntime as ort

    _HAS_ONNX = True
except ImportError:  # pragma: no cover
    ort = None
    _HAS_ONNX = False

try:
    from config import NUM_CLASSES
except ImportError:  # pragma: no cover
    from pi5.config import NUM_CLASSES


def _mock_wrapper(num_classes=NUM_CLASSES):
    """Return a callable that produces deterministic-shaped random logits."""

    def _run(x):
        batch = 1
        if isinstance(x, np.ndarray) and x.ndim == 4:
            batch = x.shape[0]
        return np.random.randn(batch, num_classes).astype(np.float32)

    _run.backend = "mock"
    return _run


def _load_torch(path):
    model = torch.load(path, map_location="cpu")
    if hasattr(model, "eval"):
        model.eval()

    def _run(x):
        tensor = torch.as_tensor(np.asarray(x, dtype=np.float32))
        with torch.no_grad():
            out = model(tensor)
        return out.cpu().numpy()

    _run.backend = "pytorch"
    return _run


def _load_tflite(path):
    interpreter = tf.lite.Interpreter(model_path=path)
    interpreter.allocate_tensors()
    in_detail = interpreter.get_input_details()[0]
    out_detail = interpreter.get_output_details()[0]

    def _run(x):
        interpreter.set_tensor(in_detail["index"], np.asarray(x, dtype=np.float32))
        interpreter.invoke()
        return interpreter.get_tensor(out_detail["index"])

    _run.backend = "tflite"
    return _run


def _load_onnx(path):
    session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    def _run(x):
        return session.run(None, {input_name: np.asarray(x, dtype=np.float32)})[0]

    _run.backend = "onnx"
    return _run


def load_model(path, num_classes=NUM_CLASSES):
    """Load a model artifact and return a callable ``wrapper(x) -> logits``.

    Falls back to a random-logit mock when the file or backend is missing.
    """
    if not path or not os.path.exists(path):
        return _mock_wrapper(num_classes)

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pt" and _HAS_TORCH:
            return _load_torch(path)
        if ext == ".tflite" and _HAS_TF:
            return _load_tflite(path)
        if ext == ".onnx" and _HAS_ONNX:
            return _load_onnx(path)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[model_loader] failed to load {path}: {exc}; using mock")

    return _mock_wrapper(num_classes)


if __name__ == "__main__":
    wrapper = load_model("nonexistent.pt")
    dummy = np.zeros((1, 3, 224, 224), dtype=np.float32)
    print("backend:", wrapper.backend)
    print("logits:", wrapper(dummy))
