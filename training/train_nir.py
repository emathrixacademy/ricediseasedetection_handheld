"""Train the NIR rice disease classifier.

NIR captures are single-channel. We adapt the backbone's first conv to accept
1 input channel (weights averaged from the pretrained RGB kernels). Reuses the
shared training loop from ``train_rgb``. Grayscale images are loaded and the
transform keeps a single channel.

Usage::

    python train_nir.py --config configs/train_config.yaml --data-root ...
"""

import argparse
import os

from train_rgb import build_model, build_optimizer, load_config, run_epoch


def build_nir_dataloaders(cfg, data_root):
    """Loaders that yield single-channel (NIR) tensors from an ImageFolder."""
    import torch
    from torchvision import datasets, transforms

    size = cfg["image_size"]
    # NIR normalization: single-channel mean/std (approximate ImageNet grey).
    mean, std = (0.45,), (0.225,)

    common = [transforms.Grayscale(num_output_channels=1),
              transforms.Resize((size, size))]
    train_tf = transforms.Compose(common + [
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])
    val_tf = transforms.Compose(common + [
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])

    train_ds = datasets.ImageFolder(os.path.join(data_root, "train"), train_tf)
    val_ds = datasets.ImageFolder(os.path.join(data_root, "val"), val_tf)

    train_loader = torch.utils.data.DataLoader(
        train_ds, batch_size=cfg["batch_size"], shuffle=True,
        num_workers=cfg.get("num_workers", 4))
    val_loader = torch.utils.data.DataLoader(
        val_ds, batch_size=cfg["batch_size"], shuffle=False,
        num_workers=cfg.get("num_workers", 4))
    return train_loader, val_loader


def train_nir(cfg, data_root):
    import torch
    import torch.nn as nn
    from torch.utils.tensorboard import SummaryWriter

    torch.manual_seed(cfg.get("seed", 42))
    device = "cuda" if torch.cuda.is_available() else "cpu"

    paths = cfg["paths"]
    models_dir = paths["models_dir"]
    os.makedirs(models_dir, exist_ok=True)

    # in_channels=1 triggers first-conv adaptation inside build_model.
    model = build_model(cfg["backbone"], cfg["num_classes"], in_channels=1)
    model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = build_optimizer(cfg["optimizer"], model.parameters(),
                                cfg["lr"], cfg["weight_decay"])
    train_loader, val_loader = build_nir_dataloaders(cfg, data_root)

    writer = SummaryWriter(os.path.join(paths.get("tensorboard_dir", "runs"),
                                        "nir_classifier"))
    best_acc = 0.0
    best_path = os.path.join(models_dir, "nir_classifier_best.pt")

    for epoch in range(cfg["epochs"]):
        tr_loss, tr_acc = run_epoch(model, train_loader, criterion, device,
                                    optimizer)
        val_loss, val_acc = run_epoch(model, val_loader, criterion, device)

        writer.add_scalar("loss/train", tr_loss, epoch)
        writer.add_scalar("loss/val", val_loss, epoch)
        writer.add_scalar("acc/val", val_acc, epoch)
        print(f"[{epoch + 1}/{cfg['epochs']}] "
              f"train_acc={tr_acc:.4f} val_acc={val_acc:.4f}")

        if val_acc >= best_acc:
            best_acc = val_acc
            torch.save({"model_state": model.state_dict(),
                        "backbone": cfg["backbone"],
                        "num_classes": cfg["num_classes"],
                        "in_channels": 1,
                        "class_names": cfg["class_names"]}, best_path)

    writer.close()
    print(f"Best NIR val acc={best_acc:.4f}; saved to {best_path}")
    return best_path


def main():
    parser = argparse.ArgumentParser(description="Train NIR rice classifier.")
    parser.add_argument("--config", default="configs/train_config.yaml")
    parser.add_argument("--data-root", required=True,
                        help="folder containing train/ and val/ NIR subsets")
    args = parser.parse_args()

    cfg = load_config(args.config)
    train_nir(cfg, args.data_root)


if __name__ == "__main__":
    main()
