"""Split a class-organized image folder into train/val/test subsets BY SESSION.

Images of the same leaf on the same day must never sit in both training and
testing, or the test score measures memory, not diagnosis. So whole sessions
are assigned to a subset, never single images.

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

How an image's session is found, first match wins:

1. ``--sessions sessions.csv`` with columns ``filename,session``.
2. The capture-guide file name ``<class>_<site>_<YYYYMMDD>_<index>_<rgb|nir>.<ext>``
   (docs/CAPTURE_GUIDE.md): session = ``<site>_<YYYYMMDD>``.
3. The photo's EXIF date (DateTimeOriginal): session = that day.
4. The file's modification date (with a warning: this is a weak guess).

RGB and NIR pictures of one leaf share a session by construction, so a pair
always lands in the same subset.
"""

import argparse
import csv
import datetime
import os
import random
import re
import shutil

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
GUIDE_NAME = re.compile(r"^(?P<cls>.+?)_(?P<site>[^_]+)_(?P<date>\d{8})_\d+(?:_(?:rgb|nir))?$",
                        re.IGNORECASE)


def _list_images(class_dir):
    return sorted(f for f in os.listdir(class_dir)
                  if os.path.splitext(f)[1].lower() in IMG_EXTS)


def _exif_day(path):
    try:
        from PIL import Image

        with Image.open(path) as im:
            exif = im.getexif()
            raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)  # DateTimeOriginal / DateTime
        if raw:
            return str(raw)[:10].replace(":", "")
    except Exception:
        pass
    return None


def session_of(path, overrides=None):
    """Return ``(session, source)`` for one image file."""
    name = os.path.basename(path)
    if overrides and name in overrides:
        return overrides[name], "csv"
    m = GUIDE_NAME.match(os.path.splitext(name)[0])
    if m:
        return f"{m['site']}_{m['date']}", "filename"
    day = _exif_day(path)
    if day:
        return f"exif_{day}", "exif"
    mtime = datetime.date.fromtimestamp(os.path.getmtime(path)).strftime("%Y%m%d")
    return f"mtime_{mtime}", "mtime"


def assign_groups(groups, ratios, rng):
    """Assign whole groups to subsets so image counts approach ``ratios``.

    ``groups`` maps session -> list of files. Largest sessions are placed
    first, each into the subset furthest below its target.
    """
    names = list(groups)
    rng.shuffle(names)
    names.sort(key=lambda g: -len(groups[g]))
    total = sum(len(v) for v in groups.values())
    targets = dict(zip(("train", "val", "test"), (r * total for r in ratios)))
    filled = {k: 0 for k in targets}
    out = {k: [] for k in targets}
    for g in names:
        subset = max(targets, key=lambda k: (targets[k] - filled[k]) / max(targets[k], 1e-9))
        out[subset].extend(groups[g])
        filled[subset] += len(groups[g])
    return out


def split_dataset(input_dir, output_dir, ratios=(0.70, 0.15, 0.15),
                  seed=42, copy=True, sessions_csv=None):
    """Split each class folder into train/val/test by session."""
    assert abs(sum(ratios) - 1.0) < 1e-6, "ratios must sum to 1.0"
    rng = random.Random(seed)

    overrides = {}
    if sessions_csv:
        with open(sessions_csv, newline="", encoding="utf-8") as f:
            overrides = {r["filename"]: r["session"] for r in csv.DictReader(f)}

    classes = sorted(d for d in os.listdir(input_dir)
                     if os.path.isdir(os.path.join(input_dir, d)))

    counts, skipped, sources = {}, [], {}
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

        groups = {}
        for f in images:
            session, source = session_of(os.path.join(src_cls, f), overrides)
            groups.setdefault(session, []).append(f)
            sources[source] = sources.get(source, 0) + 1
        subsets = assign_groups(groups, ratios, rng)
        if len(groups) < 3:
            print(f"[split] WARNING: {cls} has only {len(groups)} session(s); "
                  f"val/test cannot all get one. Collect more sessions.")

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
        counts[cls]["sessions"] = len(groups)

    if skipped:
        print(f"[split] WARNING: skipped {len(skipped)} class(es) with no "
              f"images: {', '.join(sorted(skipped))}")
    if not counts:
        raise SystemExit(
            f"[split] FATAL: no images found under {input_dir!r}. "
            f"Populate training/dataset/raw/<class_name>/ first.")
    print(f"[split] session found by: {sources}")
    if sources.get("mtime"):
        print(f"[split] WARNING: {sources['mtime']} image(s) had no session in the "
              f"name or EXIF; grouped by file date. Name files as in "
              f"docs/CAPTURE_GUIDE.md or pass --sessions.")

    return counts


def main():
    parser = argparse.ArgumentParser(description="Split dataset 70/15/15 by session.")
    parser.add_argument("--input", required=True, help="class-organized folder")
    parser.add_argument("--output", required=True, help="output root folder")
    parser.add_argument("--train", type=float, default=0.70)
    parser.add_argument("--val", type=float, default=0.15)
    parser.add_argument("--test", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sessions", help="CSV with columns filename,session")
    parser.add_argument("--move", action="store_true",
                        help="move files instead of copying")
    args = parser.parse_args()

    counts = split_dataset(
        args.input, args.output,
        ratios=(args.train, args.val, args.test),
        seed=args.seed, copy=not args.move, sessions_csv=args.sessions,
    )
    for cls, c in counts.items():
        print(f"{cls}: {c}")


if __name__ == "__main__":
    main()
