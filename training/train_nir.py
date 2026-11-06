"""Train the NIR rice disease classifier.

NIR captures are single-channel. We adapt the backbone's first conv to accept
1 input channel (weights averaged from the pretrained RGB kernels). Reuses the
shared training loop from ``train_rgb``. Grayscale images are loaded and the
transform keeps a single channel.

Usage::

    python train_nir.py --config configs/train_config.yaml --data-root ...
"""

import argparse

from train_rgb import load_config, train


def train_nir(cfg, data_root, init_from=None):
    """Train the single-channel NIR model with the shared training loop.

    Same loop, augmentations and checkpoint format as the RGB model; the
    checkpoint records the dataset's (alphabetical) class order.
    """
    return train(cfg, data_root=data_root, in_channels=1,
                 model_name="nir_classifier", init_from=init_from)


def main():
    parser = argparse.ArgumentParser(description="Train NIR rice classifier.")
    parser.add_argument("--config", default="configs/train_config.yaml")
    parser.add_argument("--data-root", required=True,
                        help="folder containing train/ and val/ NIR subsets")
    parser.add_argument("--init-from", default=None,
                        help="checkpoint to fine-tune from (e.g. the phone-photo run)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    train_nir(cfg, args.data_root, init_from=args.init_from)


if __name__ == "__main__":
    main()
