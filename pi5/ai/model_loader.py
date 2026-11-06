"""Model loader: Hailo .hef, ONNX, PyTorch checkpoint (.pt) and TFLite.

Each loader returns a plain callable ``wrapper(nchw_float32) -> logits`` so the
classifiers do not need to know the backend. The wrapper carries:

    backend       "hailo" | "onnx" | "pytorch" | "tflite" | "mock"
    class_names   the network's output order (see below)
    path          the file it came from

Output order: training uses torchvision ImageFolder, which numbers classes
ALPHABETICALLY, not in pi5/config.py order. export_onnx.py writes the real
order to ``<model>.classes.json`` (convert_hef.py copies it next to the .hef);
a .pt checkpoint carries it as ``class_names``. With neither, alphabetical
order is assumed and a warning printed.

When no model file or backend is available, a mock wrapper emitting random
logits is returned -- loudly, and flagged via ``backend == "mock"``.
"""

import json
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
    from config import CLASSES, NUM_CLASSES
except ImportError:  # pragma: no cover
    from pi5.config import CLASSES, NUM_CLASSES


def resolve_model_path(explicit, candidates):
    """``explicit`` if given, else the first candidate file that exists."""
    if explicit:
        return explicit
    for path in candidates:
        if os.path.exists(path):
            return path
    print(f"[model_loader] none of {[os.path.basename(c) for c in candidates]} "
          f"found in {os.path.dirname(candidates[0]) if candidates else '?'}")
    return None


def _sidecar_classes(path):
    side = os.path.splitext(path)[0] + ".classes.json"
    try:
        with open(side, encoding="utf-8") as f:
            return list(json.load(f)["class_names"])
    except (OSError, ValueError, KeyError):
        return None


def _default_order():
    print("[model_loader] WARNING: no class order recorded with the model -- "
          "assuming alphabetical (ImageFolder) order")
    return sorted(CLASSES)


def _mock_wrapper(num_classes=NUM_CLASSES):
    """Return a callable that produces deterministic-shaped random logits."""

    def _run(x):
        batch = 1
        if isinstance(x, np.ndarray) and x.ndim == 4:
            batch = x.shape[0]
        return np.random.randn(batch, num_classes).astype(np.float32)

    _run.backend = "mock"
    _run.class_names = list(CLASSES)
    return _run


def _build_torchvision(backbone, num_classes, in_channels):
    """Rebuild the training architecture (training/train_rgb.build_model)."""
    import torch.nn as nn
    from torchvision import models

    if backbone == "efficientnet_b0":
        model = models.efficientnet_b0(weights=None)
        first = model.features[0][0]
        head = model.classifier
        head[1] = nn.Linear(head[1].in_features, num_classes)
    else:
        model = models.mobilenet_v3_small(weights=None)
        first = model.features[0][0]
        head = model.classifier
        head[3] = nn.Linear(head[3].in_features, num_classes)
    if in_channels != 3:
        new = nn.Conv2d(in_channels, first.out_channels, first.kernel_size,
                        first.stride, first.padding, bias=first.bias is not None)
        first.__dict__.update(new.__dict__)
    return model


def _load_torch(path):
    obj = torch.load(path, map_location="cpu", weights_only=False)
    names = None
    if isinstance(obj, dict) and "model_state" in obj:
        # A training checkpoint (train_rgb.py / train_nir.py), not a module.
        model = _build_torchvision(obj.get("backbone", "mobilenet_v3_small"),
                                   obj.get("num_classes", NUM_CLASSES),
                                   obj.get("in_channels", 3))
        model.load_state_dict(obj["model_state"])
        names = obj.get("class_names")
    else:
        model = obj
    model.eval()

    def _run(x):
        tensor = torch.as_tensor(np.asarray(x, dtype=np.float32))
        with torch.no_grad():
            out = model(tensor)
        return out.cpu().numpy()

    _run.backend = "pytorch"
    _run.class_names = names or _sidecar_classes(path) or _default_order()
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
    _run.class_names = _sidecar_classes(path) or _default_order()
    return _run


def _load_onnx(path):
    session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    def _run(x):
        return session.run(None, {input_name: np.asarray(x, dtype=np.float32)})[0]

    _run.backend = "onnx"
    _run.class_names = _sidecar_classes(path) or _default_order()
    return _run


def _load_hef(path):
    """Run the compiled network on the Hailo-8L. Hailo takes NHWC input."""
    try:
        from .hailo_inference import HailoInference
    except ImportError:  # pragma: no cover - run as a script
        from pi5.ai.hailo_inference import HailoInference

    engine = HailoInference(path)
    if engine.mock:
        raise RuntimeError("Hailo runtime or device not available")

    def _run(x):
        nhwc = np.ascontiguousarray(np.transpose(np.asarray(x, dtype=np.float32),
                                                 (0, 2, 3, 1)))
        return engine.infer(nhwc)["logits"]

    _run.backend = "hailo"
    _run.class_names = _sidecar_classes(path) or _default_order()
    return _run


def load_model(path, num_classes=NUM_CLASSES):
    """Load a model artifact and return a callable ``wrapper(x) -> logits``.

    Falls back to a random-logit mock when the file or backend is missing.
    """
    if not path or not os.path.exists(path):
        # Loud, not silent: a missing model means every prediction downstream
        # is a random number, and that must be visible in the process output.
        print(f"[model_loader] WARNING: no model{f" at {path!r}" if path else " file"} -- "
              f"falling back to RANDOM MOCK predictions")
        return _mock_wrapper(num_classes)

    ext = os.path.splitext(path)[1].lower()
    loaders = {".hef": (True, _load_hef), ".pt": (_HAS_TORCH, _load_torch),
               ".tflite": (_HAS_TF, _load_tflite), ".onnx": (_HAS_ONNX, _load_onnx)}
    available, loader = loaders.get(ext, (False, None))
    if available:
        try:
            wrapper = loader(path)
            wrapper.path = path
            print(f"[model_loader] {os.path.basename(path)} on {wrapper.backend}")
            return wrapper
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[model_loader] WARNING: failed to load {path}: {exc}; "
                  f"falling back to RANDOM MOCK predictions")
            return _mock_wrapper(num_classes)

    print(f"[model_loader] WARNING: no backend available for {path!r} "
          f"(ext {ext}) -- falling back to RANDOM MOCK predictions")
    return _mock_wrapper(num_classes)


def probs_in_config_order(logits, model_names, classes=CLASSES):
    """Softmax the logits and return ``{class: prob}`` for ``classes``.

    Outputs the model was not trained on are dropped; config classes the
    model does not know get probability 0. The result is renormalised.
    """
    z = np.asarray(logits, dtype=np.float64).ravel()
    e = np.exp(z - z.max())
    p = e / e.sum()
    by_name = dict(zip(model_names, p))
    out = np.array([by_name.get(c, 0.0) for c in classes])
    total = out.sum()
    out = out / total if total > 0 else np.full(len(classes), 1.0 / len(classes))
    return {c: float(v) for c, v in zip(classes, out)}


if __name__ == "__main__":
    wrapper = load_model("nonexistent.pt")
    dummy = np.zeros((1, 3, 224, 224), dtype=np.float32)
    print("backend:", wrapper.backend)
    print("logits:", wrapper(dummy))
