"""Export a trained .pt checkpoint to ONNX (opset 13).

The checkpoint is expected to contain the keys produced by the training
scripts: ``model_state``, ``backbone``, ``num_classes``, ``in_channels``.

Usage::

    python export_onnx.py --model models/rgb_classifier_best.pt \
        --output models/rgb_classifier.onnx
"""

import argparse
import os
import sys


def _force_utf8_stdout():
    """Make stdout/stderr UTF-8 tolerant.

    torch.onnx's exporter prints status lines containing emoji. On a Windows
    console defaulting to cp1252 that raises UnicodeEncodeError mid-export and
    aborts an otherwise successful conversion.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass


def sidecar_path(model_path):
    """``models/rgb_model.onnx`` -> ``models/rgb_model.classes.json``."""
    return os.path.splitext(model_path)[0] + ".classes.json"


def write_sidecar(output_path, class_names, in_channels, image_size):
    """Record the output order next to the model.

    ImageFolder numbers classes alphabetically, so output i of the network is
    class_names[i] -- not the order in pi5/config.py. ONNX and HEF files do not
    carry the names, so the Pi reads them from this file.
    """
    import json

    with open(sidecar_path(output_path), "w", encoding="utf-8") as f:
        json.dump({"class_names": list(class_names), "in_channels": in_channels,
                   "image_size": image_size}, f, indent=2)


def export(model_path, output_path, image_size=224, opset=13):
    import torch

    from train_rgb import build_model

    _force_utf8_stdout()
    ckpt = torch.load(model_path, map_location="cpu", weights_only=False)
    backbone = ckpt.get("backbone", "mobilenet_v3_small")
    num_classes = ckpt.get("num_classes", 6)
    in_channels = ckpt.get("in_channels", 3)

    model = build_model(backbone, num_classes, in_channels)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    if ckpt.get("class_names"):
        write_sidecar(output_path, ckpt["class_names"], in_channels, image_size)
    else:
        print("[export] WARNING: checkpoint has no class_names; the Pi will "
              "assume alphabetical (ImageFolder) order")

    dummy = torch.randn(1, in_channels, image_size, image_size)
    torch.onnx.export(
        model, dummy, output_path,
        input_names=["input"], output_names=["logits"],
        opset_version=opset,
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
    )
    # Report the opset the file ACTUALLY carries. torch may fail to downgrade
    # to the requested version and emit a newer one anyway; printing the
    # requested number would misreport the artifact, and the Hailo compiler
    # is opset-sensitive.
    actual = opset
    try:
        import onnx

        loaded = onnx.load(output_path)
        onnx.checker.check_model(loaded)
        for imp in loaded.opset_import:
            if imp.domain in ("", "ai.onnx"):
                actual = imp.version
                break
    except ImportError:
        print("[export] onnx not installed -- cannot verify the written file")
        print(f"Exported ONNX (opset requested {opset}) to {output_path}")
        return output_path

    if actual != opset:
        print(f"[export] WARNING: requested opset {opset} but the exported "
              f"model declares opset {actual}. torch could not downgrade the "
              f"graph. Verify this opset is accepted by the Hailo compiler.")
    print(f"Exported ONNX (opset {actual}) to {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Export .pt to ONNX.")
    parser.add_argument("--model", required=True, help="trained .pt checkpoint")
    parser.add_argument("--output", required=True, help="output .onnx path")
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--opset", type=int, default=13)
    args = parser.parse_args()

    export(args.model, args.output, args.image_size, args.opset)


if __name__ == "__main__":
    main()
