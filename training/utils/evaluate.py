"""Evaluation metrics and confusion-matrix plotting.

Heavy imports (torch, sklearn, matplotlib) are performed inside functions so
this module can be imported in lightweight environments.
"""

from . import CLASS_NAMES


def evaluate(model, loader, device="cpu"):
    """Run the model over a loader and return metrics + raw predictions.

    Returns a dict with accuracy, precision, recall, f1 (macro), the
    confusion matrix, and the flat lists of true/predicted labels.
    """
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

    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": confusion_matrix(
            y_true, y_pred, labels=list(range(len(CLASS_NAMES)))),
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


if __name__ == "__main__":
    print("Evaluation utilities. Import evaluate() and plot_confusion_matrix().")
