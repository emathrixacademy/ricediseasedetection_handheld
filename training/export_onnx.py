"""Export a trained .pt checkpoint to ONNX (opset 13).

The checkpoint is expected to contain the keys produced by the training
scripts: ``model_state``, ``backbone``, ``num_classes``, ``in_channels``.

Usage::

    python export_onnx.py --model models/rgb_classifier_best.pt \
        --output models/rgb_classifier.onnx
"""

import argparse


def export(model_path, output_path, image_size=224, opset=13):
    import torch

    from train_rgb import build_model

    ckpt = torch.load(model_path, map_location="cpu")
    backbone = ckpt.get("backbone", "mobilenet_v3_small")
    num_classes = ckpt.get("num_classes", 6)
    in_channels = ckpt.get("in_channels", 3)

    model = build_model(backbone, num_classes, in_channels)
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    dummy = torch.randn(1, in_channels, image_size, image_size)
    torch.onnx.export(
        model, dummy, output_path,
        input_names=["input"], output_names=["logits"],
        opset_version=opset,
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
    )
    print(f"Exported ONNX (opset {opset}) to {output_path}")
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
