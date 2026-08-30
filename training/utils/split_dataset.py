"""Split a class-organized image folder into train/val/test subsets.

Input layout::

    input/
        healthy/*.jpg
        rice_blast/*.jpg
        ...

Output layout::

    output/
        train/<class>/...
        val/<class>/...
        test/<class>/...
"""

import argparse
import os
import random
import shutil

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def _list_images(class_dir):
    return [f for f in os.listdir(class_dir)
            if os.path.splitext(f)[1].lower() in IMG_EXTS]


def split_dataset(input_dir, output_dir, ratios=(0.70, 0.15, 0.15),
                  seed=42, copy=True):
    """Split each class folder into train/val/test by the given ratios."""
    assert abs(sum(ratios) - 1.0) < 1e-6, "ratios must sum to 1.0"
    rng = random.Random(seed)
    train_r, val_r, _ = ratios

    classes = [d for d in os.listdir(input_dir)
               if os.path.isdir(os.path.join(input_dir, d))]

    counts = {}
    skipped = []
    for cls in classes:
        src_cls = os.path.join(input_dir, cls)
        images = _list_images(src_cls)

        # Skip classes with no images. The repo ships empty placeholder
        # directories for every configured class; propagating them into the
        # split makes torchvision's ImageFolder raise
        # "Found no valid file for the classes ..." and abort training.
        if not images:
            skipped.append(cls)
            continue

        rng.shuffle(images)

        n = len(images)
        n_train = int(n * train_r)
        n_val = int(n * val_r)
        subsets = {
            "train": images[:n_train],
            "val": images[n_train:n_train + n_val],
            "test": images[n_train + n_val:],
        }

        for subset, files in subsets.items():
            dst_cls = os.path.join(output_dir, subset, cls)
            os.makedirs(dst_cls, exist_ok=True)
            for f in files:
                src = os.path.join(src_cls, f)
                dst = os.path.join(dst_cls, f)
                if copy:
                    shutil.copy2(src, dst)
                else:
                    shutil.move(src, dst)

        counts[cls] = {k: len(v) for k, v in subsets.items()}

    if skipped:
        print(f"[split] WARNING: skipped {len(skipped)} class(es) with no "
              f"images: {', '.join(sorted(skipped))}")
    if not counts:
        raise SystemExit(
            f"[split] FATAL: no images found under {input_dir!r}. "
            f"Populate training/dataset/raw/<class_name>/ first.")

    return counts


def main():
    parser = argparse.ArgumentParser(description="Split dataset 70/15/15.")
    parser.add_argument("--input", required=True, help="class-organized folder")
    parser.add_argument("--output", required=True, help="output root folder")
    parser.add_argument("--train", type=float, default=0.70)
    parser.add_argument("--val", type=float, default=0.15)
    parser.add_argument("--test", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--move", action="store_true",
                        help="move files instead of copying")
    args = parser.parse_args()

    counts = split_dataset(
        args.input, args.output,
        ratios=(args.train, args.val, args.test),
        seed=args.seed, copy=not args.move,
    )
    for cls, c in counts.items():
        print(f"{cls}: {c}")


if __name__ == "__main__":
    main()
