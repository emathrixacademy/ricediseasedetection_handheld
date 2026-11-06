"""Build the biosensor calibration from readings of plants of confirmed condition.

The biosensor joins the fused diagnosis only after this calibration exists
(Development Methods, 9.7). For each analyte and class it stores the mean and
spread of the DPV features; pi5/ai/biosensor_model.py turns a new reading
into class probabilities against them.

Readings come from either source:

* ``--csv readings.csv``: columns ``class,analyte`` plus the feature columns
  (peak_height_ua, peak_voltage_v, ...), one row per valid reading.
* ``--db``: the scanner's database. A scan counts when its session's
  ``plant_condition`` is set to the confirmed class and the reading's status
  is OK.

Usage::

    python calibrate_biosensor.py --db --output ../pi5/models/biosensor_calibration.json
    python calibrate_biosensor.py --csv readings.csv --output ...
"""

import argparse
import csv
import datetime
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pi5.ai.dpv_features import FEATURE_NAMES  # noqa: E402
from pi5.config import CLASSES  # noqa: E402

# n_peaks is a count, not a measurement with a spread: leave it out.
DEFAULT_FEATURES = [f for f in FEATURE_NAMES if f != "n_peaks"]
MIN_PER_CLASS = 5


def rows_from_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            yield r["class"], r["analyte"], {k: r[k] for k in FEATURE_NAMES if k in r}


def rows_from_db():
    from pi5 import db

    with db.get_session() as s:
        q = (s.query(db.ScanSession.plant_condition, db.BiosensorReading)
             .join(db.BiosensorReading, db.BiosensorReading.session_id == db.ScanSession.id)
             .filter(db.ScanSession.plant_condition.isnot(None))
             .filter(db.BiosensorReading.status == "OK"))
        for cls, reading in q:
            if reading.features:
                yield cls, reading.analyte, reading.features


def build(rows, features=DEFAULT_FEATURES):
    data = {}
    for cls, analyte, feats in rows:
        if cls not in CLASSES:
            print(f"[calibrate] skipping unknown class {cls!r}")
            continue
        try:
            x = [float(feats[k]) for k in features]
        except (KeyError, TypeError, ValueError):
            continue
        data.setdefault(analyte, {}).setdefault(cls, []).append(x)

    out = {"created": datetime.datetime.now().isoformat(timespec="seconds"),
           "n_readings": 0, "analytes": {}}
    for analyte, by_class in data.items():
        classes = {}
        for cls, xs in by_class.items():
            if len(xs) < MIN_PER_CLASS:
                print(f"[calibrate] {analyte}/{cls}: only {len(xs)} reading(s), "
                      f"need {MIN_PER_CLASS}; left out")
                continue
            arr = np.asarray(xs)
            classes[cls] = {"mean": arr.mean(0).round(6).tolist(),
                            "std": arr.std(0, ddof=1).round(6).tolist(),
                            "n": len(xs)}
            out["n_readings"] += len(xs)
        if classes:
            out["analytes"][analyte] = {"features": list(features), "classes": classes}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="readings CSV (class, analyte, feature columns)")
    src.add_argument("--db", action="store_true", help="read from the scanner database")
    parser.add_argument("--output", required=True, help="calibration JSON to write")
    args = parser.parse_args()

    cal = build(rows_from_csv(args.csv) if args.csv else rows_from_db())
    if not cal["analytes"]:
        raise SystemExit("[calibrate] no class had enough readings; nothing written")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(cal, f, indent=2)
    for analyte, a in cal["analytes"].items():
        print(f"[calibrate] {analyte}: " + ", ".join(
            f"{c} (n={v['n']})" for c, v in a["classes"].items()))
    print(f"[calibrate] wrote {args.output}")


if __name__ == "__main__":
    main()
