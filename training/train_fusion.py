"""Train the late-fusion head.

The fusion model takes concatenated features:
    - RGB branch softmax probabilities   (num_classes)
    - NIR branch softmax probabilities   (num_classes)
    - biosensor scalar(s)                (n_bio)
and learns a small MLP that outputs final class logits.

A synthetic data loader is provided so the script runs end-to-end even when
real per-sample feature vectors are unavailable.

Usage::

    python train_fusion.py --config configs/train_config.yaml [--synthetic]
"""

import argparse
import os

from train_rgb import load_config


def build_fusion_model(num_classes, n_bio=1, hidden=64):
    """Small MLP fusion head over [rgb_probs, nir_probs, biosensor]."""
    import torch.nn as nn

    in_dim = num_classes * 2 + n_bio
    return nn.Sequential(
        nn.Linear(in_dim, hidden),
        nn.ReLU(inplace=True),
        nn.Dropout(0.3),
        nn.Linear(hidden, num_classes),
    )


class SyntheticFusionDataset:
    """Placeholder dataset generating plausible fusion feature vectors.

    Each sample: softmax-like RGB and NIR vectors biased toward the true
    label, plus a random biosensor scalar. Replace with a real loader that
    reads exported branch features when available.
    """

    def __init__(self, num_classes, n_bio=1, n_samples=1024, seed=42):
        import numpy as np
        rng = np.random.default_rng(seed)
        self.num_classes = num_classes
        labels = rng.integers(0, num_classes, size=n_samples)

        def soft(bias_labels):
            logits = rng.normal(0, 1, size=(n_samples, num_classes))
            logits[np.arange(n_samples), bias_labels] += 2.5
            e = np.exp(logits - logits.max(axis=1, keepdims=True))
            return e / e.sum(axis=1, keepdims=True)

        rgb = soft(labels)
        nir = soft(labels)
        bio = rng.normal(0.5, 0.2, size=(n_samples, n_bio))
        self.x = np.concatenate([rgb, nir, bio], axis=1).astype("float32")
        self.y = labels.astype("int64")

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        import torch
        return torch.from_numpy(self.x[idx]), int(self.y[idx])


def build_loaders(cfg, synthetic, features_path, n_bio):
    import torch

    num_classes = cfg["num_classes"]
    if synthetic or not features_path:
        train_ds = SyntheticFusionDataset(num_classes, n_bio, 1024, seed=1)
        val_ds = SyntheticFusionDataset(num_classes, n_bio, 256, seed=2)
    else:
        # Expect an .npz with arrays x (features) and y (labels).
        import numpy as np
        data = np.load(features_path)
        x, y = data["x"].astype("float32"), data["y"].astype("int64")
        n_val = int(len(y) * 0.2)
        train_ds = list(zip(torch.from_numpy(x[n_val:]), y[n_val:].tolist()))
        val_ds = list(zip(torch.from_numpy(x[:n_val]), y[:n_val].tolist()))

    bs = cfg["batch_size"]
    return (torch.utils.data.DataLoader(train_ds, batch_size=bs, shuffle=True),
            torch.utils.data.DataLoader(val_ds, batch_size=bs, shuffle=False))


def train_fusion(cfg, synthetic=True, features_path=None, n_bio=1):
    import torch
    import torch.nn as nn
    from torch.utils.tensorboard import SummaryWriter

    torch.manual_seed(cfg.get("seed", 42))
    device = "cuda" if torch.cuda.is_available() else "cpu"

    paths = cfg["paths"]
    models_dir = paths["models_dir"]
    os.makedirs(models_dir, exist_ok=True)

    model = build_fusion_model(cfg["num_classes"], n_bio).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["lr"],
                                 weight_decay=cfg["weight_decay"])
    train_loader, val_loader = build_loaders(cfg, synthetic, features_path, n_bio)

    writer = SummaryWriter(os.path.join(paths.get("tensorboard_dir", "runs"),
                                        "fusion_head"))
    best_acc = 0.0
    best_path = os.path.join(models_dir, "fusion_head_best.pt")

    for epoch in range(cfg["epochs"]):
        model.train()
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()

        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                correct += (model(x).argmax(1) == y).sum().item()
                total += y.size(0)
        val_acc = correct / max(total, 1)
        writer.add_scalar("acc/val", val_acc, epoch)
        print(f"[{epoch + 1}/{cfg['epochs']}] val_acc={val_acc:.4f}")

        if val_acc >= best_acc:
            best_acc = val_acc
            torch.save({"model_state": model.state_dict(),
                        "num_classes": cfg["num_classes"],
                        "n_bio": n_bio,
                        "class_names": cfg["class_names"]}, best_path)

    writer.close()
    print(f"Best fusion val acc={best_acc:.4f}; saved to {best_path}")
    return best_path


def main():
    parser = argparse.ArgumentParser(description="Train late-fusion head.")
    parser.add_argument("--config", default="configs/train_config.yaml")
    parser.add_argument("--synthetic", action="store_true",
                        help="use synthetic placeholder features")
    parser.add_argument("--features", default=None,
                        help=".npz with real x/y fusion features")
    parser.add_argument("--n-bio", type=int, default=1,
                        help="number of biosensor scalar features")
    args = parser.parse_args()

    cfg = load_config(args.config)
    train_fusion(cfg, synthetic=args.synthetic or not args.features,
                 features_path=args.features, n_bio=args.n_bio)


if __name__ == "__main__":
    main()
