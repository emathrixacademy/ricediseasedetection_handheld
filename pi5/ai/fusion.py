"""Weighted late fusion of RGB, NIR and biosensor class evidence."""

import numpy as np

try:
    from config import CLASSES, FUSION_WEIGHTS
except ImportError:  # pragma: no cover
    from pi5.config import CLASSES, FUSION_WEIGHTS


class DecisionFusion:
    """Weighted late fusion over per-modality class-probability vectors.

    Every modality that is present contributes ``weight x probabilities``; the
    sum is divided by the total weight of the modalities present. RGB and NIR
    come from the image models; the biosensor comes from
    ``BiosensorClassifier`` and is present only once it has been calibrated
    (otherwise pass ``biosensor_result=None`` and imaging decides alone).
    Because the biosensor carries its own class distribution, a strong,
    calibrated reading can change the diagnosed class.
    """

    def __init__(self, weights=None, classes=None):
        self.weights = dict(weights or FUSION_WEIGHTS)
        self.classes = list(classes or CLASSES)

    def _probs_vector(self, result):
        """Extract an ordered probability vector from a classifier result."""
        if not result:
            return None
        probs = result.get("probs")
        if not probs:
            return None
        return np.array([probs.get(c, 0.0) for c in self.classes], dtype=np.float64)

    def fuse(self, rgb_result, nir_result, biosensor_result=None):
        """Combine modality outputs into a final diagnosis dict."""
        combined = np.zeros(len(self.classes))
        used = {}
        for name, result in (("rgb", rgb_result), ("nir", nir_result),
                             ("biosensor", biosensor_result)):
            vec = self._probs_vector(result)
            if vec is None:
                continue
            w = float(self.weights.get(name, 0.0))
            if w <= 0:
                continue
            combined += w * vec
            used[name] = w

        total = sum(used.values())
        if total == 0:
            fused = np.full(len(self.classes), 1.0 / len(self.classes))
        else:
            fused = combined / total
            fused = fused / fused.sum()
        idx = int(np.argmax(fused))

        return {
            "final_diagnosis": self.classes[idx],
            "final_confidence": float(fused[idx]),
            "fused_probs": {c: float(p) for c, p in zip(self.classes, fused)},
            "modalities": sorted(used),
            "weights_used": {k: round(v / total, 4) for k, v in used.items()} if total else {},
        }


if __name__ == "__main__":
    rgb = {"probs": {c: (0.6 if c == "rice_blast" else 0.08) for c in CLASSES}}
    nir = {"probs": {c: (0.5 if c == "rice_blast" else 0.1) for c in CLASSES}}
    bio = {"probs": {c: (0.7 if c == "bacterial_leaf_blight" else 0.06) for c in CLASSES}}
    fusion = DecisionFusion()
    print(fusion.fuse(rgb, nir))
    print(fusion.fuse(rgb, nir, bio))
