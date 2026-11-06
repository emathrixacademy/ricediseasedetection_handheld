"""Feature extraction from one differential pulse voltammetry (DPV) curve.

The ESP32 sends the full curve as ``[{"v": volts, "i": microamps}, ...]``.
These are the seven features of the Development Methods (section 7.2):

    peak_height_ua    baseline-corrected height of the main peak
    peak_voltage_v    potential of the main peak
    peak_area_uav     area of the main peak above the baseline (uA x V)
    peak_width_v      full width at half maximum of the main peak
    background_slope  slope of the baseline (uA per V)
    n_peaks           peaks standing above the noise (3 x noise, 3 x step wide)
    snr               peak height / baseline noise

The baseline is a straight line fitted to the first and last 15 % of the
curve, where no faradaic peak is expected. A reduction sweep (nitrate) has
negative peaks: pass ``polarity=-1`` and the curve is flipped before the
analysis, so every height is reported positive.
"""

import numpy as np

FEATURE_NAMES = (
    "peak_height_ua",
    "peak_voltage_v",
    "peak_area_uav",
    "peak_width_v",
    "background_slope",
    "n_peaks",
    "snr",
)

_EDGE = 0.15       # fraction of the curve at each end used for the baseline
_MIN_POINTS = 12


def _curve_arrays(curve):
    v = np.array([float(p["v"]) for p in curve], dtype=np.float64)
    i = np.array([float(p["i"]) for p in curve], dtype=np.float64)
    order = np.argsort(v)            # cathodic sweeps arrive high -> low
    return v[order], i[order]


def extract_features(curve, polarity=1):
    """Return the feature dict for ``curve``, or None if it is too short."""
    if not curve or len(curve) < _MIN_POINTS:
        return None
    v, i = _curve_arrays(curve)
    i = i * (1 if polarity >= 0 else -1)
    n = len(v)

    # Baseline: least squares line through both ends.
    k = max(3, int(n * _EDGE))
    edge = np.r_[0:k, n - k:n]
    slope, intercept = np.polyfit(v[edge], i[edge], 1)
    base = slope * v + intercept
    resid = i - base
    noise = float(np.std(resid[edge])) or 1e-9

    # Main peak.
    p = int(np.argmax(resid))
    height = float(resid[p])

    # Full width at half maximum, interpolated on both flanks.
    half = height / 2.0
    lo = p
    while lo > 0 and resid[lo] > half:
        lo -= 1
    hi = p
    while hi < n - 1 and resid[hi] > half:
        hi += 1

    def _cross(a, b):
        if resid[a] == resid[b]:
            return v[a]
        return v[a] + (half - resid[a]) * (v[b] - v[a]) / (resid[b] - resid[a])

    width = float(_cross(hi - 1, hi) - _cross(lo + 1, lo)) if height > 0 else 0.0

    # Area of the main peak above the baseline, between its half-height points
    # widened to where the residual returns to zero.
    a = lo
    while a > 0 and resid[a] > 0:
        a -= 1
    b = hi
    while b < n - 1 and resid[b] > 0:
        b += 1
    seg = slice(a, b + 1)
    area = float(np.trapezoid(np.clip(resid[seg], 0, None), v[seg])) \
        if hasattr(np, "trapezoid") else \
        float(np.trapz(np.clip(resid[seg], 0, None), v[seg]))

    # Number of peaks: local maxima above 3 x noise, at least 3 steps apart.
    thresh = 3.0 * noise
    peaks = []
    for j in range(1, n - 1):
        if resid[j] > thresh and resid[j] >= resid[j - 1] and resid[j] > resid[j + 1]:
            if peaks and j - peaks[-1] < 3:
                if resid[j] > resid[peaks[-1]]:
                    peaks[-1] = j
                continue
            peaks.append(j)

    return {
        "peak_height_ua": round(height, 5),
        "peak_voltage_v": round(float(v[p]), 4),
        "peak_area_uav": round(area, 6),
        "peak_width_v": round(max(width, 0.0), 4),
        "background_slope": round(float(slope) * (1 if polarity >= 0 else -1), 5),
        "n_peaks": len(peaks),
        "snr": round(height / noise, 2),
    }


def feature_vector(features):
    """The features as a float array in FEATURE_NAMES order."""
    return np.array([float(features[k]) for k in FEATURE_NAMES], dtype=np.float32)


if __name__ == "__main__":
    vs = np.arange(-0.2, 0.6001, 0.004)
    cur = 0.4 * vs + 2.5 * np.exp(-((vs - 0.25) / 0.05) ** 2)
    cur += np.random.default_rng(1).normal(0, 0.01, vs.size)
    print(extract_features([{"v": a, "i": b} for a, b in zip(vs, cur)]))
