"""Biosensor class evidence from calibrated DPV features.

The biosensor joins the fused diagnosis only after it has been calibrated
with readings from plants of confirmed condition (Development Methods, 9.7).
Calibration is a JSON file written by ``training/calibrate_biosensor.py``::

    {"created": "...", "n_readings": 120,
     "analytes": {
        "H2O2": {"features": ["peak_height_ua", ...],
                 "classes": {"healthy": {"mean": [...], "std": [...], "n": 20},
                             ...}},
        "NO3":  {...}}}

For each analyte measured in a scan, every calibrated class gets a Gaussian
log-likelihood of the observed features (naive Bayes, one diagonal Gaussian
per class); analytes add up. Classes with no calibration data share the
lowest likelihood seen. Without a calibration file, ``predict`` returns None
and fusion uses imaging alone.
"""

import json
import os

import numpy as np

try:
    from config import BIOSENSOR_CALIBRATION_PATH, CLASSES
except ImportError:  # pragma: no cover
    from pi5.config import BIOSENSOR_CALIBRATION_PATH, CLASSES

_MIN_STD = 1e-3


class BiosensorClassifier:
    def __init__(self, path=BIOSENSOR_CALIBRATION_PATH, classes=None):
        self.path = path
        self.classes = list(classes or CLASSES)
        self.calibration = None
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.calibration = json.load(f)
            except (OSError, ValueError) as exc:
                print(f"[biosensor] calibration unreadable ({exc}); "
                      f"biosensor left out of fusion")
        else:
            print(f"[biosensor] no calibration at {path!r}: biosensor is "
                  f"recorded but left out of fusion until calibrated")

    @property
    def calibrated(self):
        return bool(self.calibration and self.calibration.get("analytes"))

    def predict(self, readings):
        """Class probabilities from ``{analyte: features}``, or None.

        Only valid readings should be passed (status OK, features present).
        """
        if not self.calibrated or not readings:
            return None
        loglik = np.zeros(len(self.classes))
        used = []
        for analyte, feats in readings.items():
            cal = self.calibration["analytes"].get(analyte)
            if not cal or not feats:
                continue
            names = cal["features"]
            x = np.array([float(feats[k]) for k in names])
            ll = np.full(len(self.classes), np.nan)
            for ci, cls in enumerate(self.classes):
                c = cal["classes"].get(cls)
                if not c:
                    continue
                mu = np.asarray(c["mean"], dtype=float)
                sd = np.maximum(np.asarray(c["std"], dtype=float), _MIN_STD)
                ll[ci] = float(np.sum(-0.5 * ((x - mu) / sd) ** 2 - np.log(sd)))
            if np.all(np.isnan(ll)):
                continue
            ll[np.isnan(ll)] = np.nanmin(ll)
            loglik += ll
            used.append(analyte)
        if not used:
            return None
        p = np.exp(loglik - loglik.max())
        p /= p.sum()
        idx = int(np.argmax(p))
        return {
            "prediction": self.classes[idx],
            "confidence": float(p[idx]),
            "probs": {c: float(v) for c, v in zip(self.classes, p)},
            "analytes": used,
        }
