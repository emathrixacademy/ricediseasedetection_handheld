"""Train the RGB rice disease classifier.

Backbone: MobileNetV3-Small (default) or EfficientNet-B0 from torchvision.
Reads hyperparameters from configs/train_config.yaml. Saves the best model
by validation accuracy to the configured models directory and logs scalars
to TensorBoard.

Usage::

    python train_rgb.py --config configs/train_config.yaml
"""

import argparse
import os


def load_config(path):
    import yaml
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_model(backbone, num_classes, in_channels=3):
    """Build a torchvision backbone with a fresh num_classes head.

    ``in_channels`` allows adapting the first conv (used by the NIR script).
    """
    import torch.nn as nn
    from torchvision import models

    backbone = backbone.lower()
    # Reject unknown names rather than silently defaulting. A typo such as
    # "mobilen_v3_small" previously fell through to the else-branch and
    # trained a different architecture than the config asked for.
    valid = {"mobilenet_v3_small", "efficientnet_b0"}
    if backbone not in valid:
        raise ValueError(
            f"unknown backbone {backbone!r}; expected one of {sorted(valid)}")

    if backbone == "efficientnet_b0":
        model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
        if in_channels != 3:
            _adapt_first_conv(model.features[0][0], in_channels)
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)
    else:  # default: mobilenet_v3_small
        model = models.mobilenet_v3_small(
            weights=models.MobileNet_V3_Small_Weights.DEFAULT)
        if in_channels != 3:
            _adapt_first_conv(model.features[0][0], in_channels)
        in_features = model.classifier[3].in_features
        model.classifier[3] = nn.Linear(in_features, num_classes)
    return model


def _adapt_first_conv(conv, in_channels):
    """Replace a Conv2d's input channels, averaging pretrained weights."""
    import torch
    import torch.nn as nn

    new_conv = nn.Conv2d(in_channels, conv.out_channels,
                         kernel_size=conv.kernel_size, stride=conv.stride,
                         padding=conv.padding, bias=conv.bias is not None)
    with torch.no_grad():
        mean_w = conv.weight.mean(dim=1, keepdim=True)
        new_conv.weight.copy_(mean_w.repeat(1, in_channels, 1, 1))
    # Mutate in place so the parent module reference is updated.
    conv.__dict__.update(new_conv.__dict__)


def build_optimizer(name, params, lr, weight_decay):
    import torch.optim as optim
    if name.lower() == "sgd":
        return optim.SGD(params, lr=lr, momentum=0.9, weight_decay=weight_decay)
    return optim.Adam(params, lr=lr, weight_decay=weight_decay)


def build_dataloaders(cfg, data_root):
    """Build train/val loaders from an ImageFolder split (train/ val/)."""
    import torch
    from torchvision import datasets, transforms

    from utils.preprocess import IMAGENET_MEAN, IMAGENET_STD

    size = cfg["image_size"]
    train_tf = transforms.Compose([
        transforms.Resize((size, size)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((size, size)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])

    train_ds = datasets.ImageFolder(os.path.join(data_root, "train"), train_tf)
    val_ds = datasets.ImageFolder(os.path.join(data_root, "val"), val_tf)

    if train_ds.classes != val_ds.classes:
        raise ValueError(
            f"train/val class mismatch: {train_ds.classes} vs {val_ds.classes}")

    train_loader = torch.utils.data.DataLoader(
        train_ds, batch_size=cfg["batch_size"], shuffle=True,
        num_workers=cfg.get("num_workers", 4))
    val_loader = torch.utils.data.DataLoader(
        val_ds, batch_size=cfg["batch_size"], shuffle=False,
        num_workers=cfg.get("num_workers", 4))
    # Return the dataset's own class order. ImageFolder assigns label indices
    # alphabetically, which is NOT the order in the config file -- the caller
    # must record these names, not the config's, or every prediction is
    # mislabelled at inference time.
    return train_loader, val_loader, train_ds.classes


def run_epoch(model, loader, criterion, device, optimizer=None):
    import torch

    train = optimizer is not None
    model.train() if train else model.eval()
    total_loss, correct, total = 0.0, 0, 0

    with torch.set_grad_enabled(train):
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            if train:
                optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            if train:
                loss.backward()
                optimizer.step()
            total_loss += loss.item() * images.size(0)
            correct += (outputs.argmax(1) == labels).sum().item()
            total += images.size(0)

    return total_loss / max(total, 1), correct / max(total, 1)


def train(cfg, data_root=None, in_channels=3, model_name="rgb_classifier"):
    """Full training loop. Returns the path of the best saved checkpoint."""
    import torch
    import torch.nn as nn

    # TensorBoard is optional monitoring, not a training dependency. Its
    # absence must not abort a run -- log to stdout instead.
    try:
        from torch.utils.tensorboard import SummaryWriter
    except ImportError:
        SummaryWriter = None
        print("[train] tensorboard unavailable -- scalar logging disabled "
              "(pip install tensorboard to enable)")

    torch.manual_seed(cfg.get("seed", 42))
    device = "cuda" if torch.cuda.is_available() else "cpu"

    paths = cfg["paths"]
    data_root = data_root or paths["dataset_annotated"]
    models_dir = paths["models_dir"]
    os.makedirs(models_dir, exist_ok=True)

    # Build loaders first: the dataset decides the label space, not the config.
    train_loader, val_loader, class_names = build_dataloaders(cfg, data_root)

    num_classes = len(class_names)
    if num_classes != cfg["num_classes"]:
        print(f"[train] WARNING: config declares num_classes="
              f"{cfg['num_classes']} but the dataset contains {num_classes} "
              f"class(es): {class_names}")
        print(f"[train] using the dataset's {num_classes} -- a head sized for "
              f"absent classes would train dead outputs")
    if class_names != list(cfg.get("class_names", [])):
        print(f"[train] NOTE: label order comes from the dataset "
              f"(alphabetical), not the config file.")
        print(f"[train]   dataset: {class_names}")
        print(f"[train]   config : {list(cfg.get('class_names', []))}")

    model = build_model(cfg["backbone"], num_classes, in_channels)
    model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = build_optimizer(cfg["optimizer"], model.parameters(),
                                cfg["lr"], cfg["weight_decay"])

    writer = None
    if SummaryWriter is not None:
        writer = SummaryWriter(os.path.join(paths.get("tensorboard_dir", "runs"),
                                            model_name))
    best_acc, best_path = 0.0, os.path.join(models_dir, f"{model_name}_best.pt")

    for epoch in range(cfg["epochs"]):
        tr_loss, tr_acc = run_epoch(model, train_loader, criterion, device,
                                    optimizer)
        val_loss, val_acc = run_epoch(model, val_loader, criterion, device)

        if writer is not None:
            writer.add_scalar("loss/train", tr_loss, epoch)
            writer.add_scalar("loss/val", val_loss, epoch)
            writer.add_scalar("acc/train", tr_acc, epoch)
            writer.add_scalar("acc/val", val_acc, epoch)
        print(f"[{epoch + 1}/{cfg['epochs']}] "
              f"train_loss={tr_loss:.4f} train_acc={tr_acc:.4f} "
              f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}")

        if val_acc >= best_acc:
            best_acc = val_acc
            torch.save({"model_state": model.state_dict(),
                        "backbone": cfg["backbone"],
                        "num_classes": num_classes,
                        "in_channels": in_channels,
                        # The dataset's order, matching the trained label
                        # indices. Using cfg["class_names"] here permutes
                        # every prediction at inference time.
                        "class_names": class_names}, best_path)

    if writer is not None:
        writer.close()
    print(f"Best val acc={best_acc:.4f}; saved to {best_path}")
    return best_path


def main():
    parser = argparse.ArgumentParser(description="Train RGB rice classifier.")
    parser.add_argument("--config", default="configs/train_config.yaml")
    parser.add_argument("--data-root", default=None,
                        help="folder containing train/ and val/ subsets")
    args = parser.parse_args()

    cfg = load_config(args.config)
    train(cfg, data_root=args.data_root, in_channels=3,
          model_name="rgb_classifier")


if __name__ == "__main__":
    main()
