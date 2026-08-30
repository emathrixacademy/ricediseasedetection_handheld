"""Evaluation metrics and confusion-matrix plotting.

Heavy imports (torch, sklearn, matplotlib) are performed inside functions so
this module can be imported in lightweight environments.
"""

from . import CLASS_NAMES


def evaluate(model, loader, device="cpu", class_names=None):
    """Run the model over a loader and return metrics + raw predictions.

    Returns a dict with accuracy, precision, recall, f1 (macro), the
    confusion matrix, and the flat lists of true/predicted labels.

    ``class_names`` must be the label space the model was TRAINED on (the
    dataset's own order). Defaulting to the package-level CLASS_NAMES sizes
    the confusion matrix for six classes even when the model has three.
    """
    class_names = list(class_names or CLASS_NAMES)
    import torch
    from sklearn.metrics import (accuracy_score, confusion_matrix,
                                 precision_recall_fscore_support)

    model.eval()
    model.to(device)

    y_true, y_pred = [], []
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            outputs = model(images)
            preds = outputs.argmax(dim=1).cpu().tolist()
            y_pred.extend(preds)
            y_true.extend(labels.cpu().tolist())

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0)

    per_class = precision_recall_fscore_support(
        y_true, y_pred, average=None,
        labels=list(range(len(class_names))), zero_division=0)

    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": confusion_matrix(
            y_true, y_pred, labels=list(range(len(class_names)))),
        "per_class": {
            name: {"precision": float(per_class[0][i]),
                   "recall": float(per_class[1][i]),
                   "f1": float(per_class[2][i]),
                   "support": int(per_class[3][i])}
            for i, name in enumerate(class_names)
        },
        "class_names": class_names,
        "y_true": y_true,
        "y_pred": y_pred,
    }


def plot_confusion_matrix(cm, class_names=None, output_path=None):
    """Render a confusion matrix; save to output_path when provided."""
    import matplotlib
    if output_path:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    class_names = class_names or CLASS_NAMES
    fig, ax = plt.subplots(figsize=(8, 7))

    try:
        import seaborn as sns
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                    xticklabels=class_names, yticklabels=class_names, ax=ax)
    except ImportError:
        im = ax.imshow(cm, cmap="Blues")
        fig.colorbar(im, ax=ax)
        ax.set_xticks(range(len(class_names)))
        ax.set_yticks(range(len(class_names)))
        ax.set_xticklabels(class_names, rotation=45, ha="right")
        ax.set_yticklabels(class_names)
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, cm[i, j], ha="center", va="center")

    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Confusion Matrix")
    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return output_path
    plt.show()
    return None


def main():
    """CLI: evaluate a trained checkpoint against a held-out split.

    Run as a module from the project root:
        python -m training.utils.evaluate --checkpoint models/rgb_classifier_best.pt \
                                          --data-root training/dataset/split
    """
    import argparse
    import os

    import torch
    from torchvision import datasets, transforms

    from training.train_rgb import build_model
    from training.utils.preprocess import IMAGENET_MEAN, IMAGENET_STD

    ap = argparse.ArgumentParser(description="Evaluate a trained classifier.")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--data-root", required=True,
                    help="folder containing the split subset directories")
    ap.add_argument("--subset", default="test")
    ap.add_argument("--image-size", type=int, default=224)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--plot", default=None, help="path for confusion-matrix PNG")
    args = ap.parse_args()

    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    # The checkpoint's own label space -- never the package default.
    class_names = list(ckpt.get("class_names") or CLASS_NAMES)

    model = build_model(ckpt["backbone"], ckpt["num_classes"],
                        ckpt.get("in_channels", 3))
    model.load_state_dict(ckpt["model_state"])

    tf = transforms.Compose([
        transforms.Resize((args.image_size, args.image_size)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    ds = datasets.ImageFolder(os.path.join(args.data_root, args.subset), tf)

    if ds.classes != class_names:
        raise SystemExit(
            f"[evaluate] FATAL: label space mismatch.\n"
            f"  checkpoint: {class_names}\n"
            f"  {args.subset} set: {ds.classes}\n"
            f"Evaluating across mismatched label orders silently reports "
            f"wrong per-class metrics.")

    loader = torch.utils.data.DataLoader(ds, batch_size=args.batch_size,
                                         shuffle=False, num_workers=0)
    metrics = evaluate(model, loader, class_names=class_names)

    print(f"\nEvaluated {len(ds)} image(s) from '{args.subset}' "
          f"over {len(class_names)} class(es)\n")
    print("Overall (macro):")
    print(f"  accuracy : {metrics['accuracy']:.4f}")
    print(f"  precision: {metrics['precision']:.4f}")
    print(f"  recall   : {metrics['recall']:.4f}")
    print(f"  f1       : {metrics['f1']:.4f}")

    print("\nPer-class metrics:")
    width = max(len(c) for c in class_names)
    print(f"  {'class'.ljust(width)}  {'prec':>6} {'recall':>7} "
          f"{'f1':>6} {'support':>8}")
    for name, m in metrics["per_class"].items():
        print(f"  {name.ljust(width)}  {m['precision']:6.3f} {m['recall']:7.3f} "
              f"{m['f1']:6.3f} {m['support']:8d}")

    print("\nConfusion matrix (rows = true, cols = predicted):")
    cm = metrics["confusion_matrix"]
    print(f"  {''.ljust(width)}  " +
          " ".join(n[:6].rjust(6) for n in class_names))
    for i, name in enumerate(class_names):
        print(f"  {name.ljust(width)}  " +
              " ".join(f"{v:6d}" for v in cm[i]))

    if args.plot:
        path = plot_confusion_matrix(cm, class_names, output_path=args.plot)
        print(f"\nConfusion matrix written to {path}")

    return metrics


if __name__ == "__main__":
    main()
