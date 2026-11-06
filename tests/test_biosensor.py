"""DPV features, the analyte-aware UART protocol, model class order, and the
scan pipeline writing every database table."""

import json
import random

import numpy as np
import pytest

from pi5.ai.dpv_features import FEATURE_NAMES, extract_features
from pi5.ai.model_loader import probs_in_config_order
from pi5.comms.uart_bridge import UARTBridge
from pi5.config import CLASSES


def _curve(centre=0.25, height=2.5, width=0.05, slope=0.4, noise=0.01,
           start=-0.2, end=0.6, step=0.004, sign=1, seed=1):
    rng = np.random.default_rng(seed)
    v = np.arange(start, end + step / 2, step) if step > 0 else \
        np.arange(start, end + step / 2, step)
    i = slope * v + height * np.exp(-((v - centre) / width) ** 2)
    i = sign * (i + rng.normal(0, noise, v.size))
    return [{"v": float(a), "i": float(b)} for a, b in zip(v, i)]


# -- features ----------------------------------------------------------------

def test_features_of_a_gaussian_peak():
    f = extract_features(_curve())
    assert set(f) == set(FEATURE_NAMES)
    assert f["peak_height_ua"] == pytest.approx(2.5, rel=0.03)
    assert f["peak_voltage_v"] == pytest.approx(0.25, abs=0.005)
    # FWHM of exp(-(x/w)^2) is 2 w sqrt(ln 2); area is h w sqrt(pi).
    assert f["peak_width_v"] == pytest.approx(2 * 0.05 * np.sqrt(np.log(2)), rel=0.05)
    assert f["peak_area_uav"] == pytest.approx(2.5 * 0.05 * np.sqrt(np.pi), rel=0.05)
    assert f["background_slope"] == pytest.approx(0.4, rel=0.1)
    assert f["n_peaks"] == 1
    assert f["snr"] > 50


def test_two_peaks_counted():
    a = _curve(centre=0.1, height=2.0)
    b = _curve(centre=0.4, height=1.5, slope=0.0, noise=0.0)
    both = [{"v": p["v"], "i": p["i"] + q["i"]} for p, q in zip(a, b)]
    assert extract_features(both)["n_peaks"] == 2


def test_reduction_curve_with_negative_polarity():
    curve = _curve(centre=-0.45, start=0.0, end=-0.8, step=-0.004, sign=-1, slope=0.2)
    f = extract_features(curve, polarity=-1)
    assert f["peak_height_ua"] == pytest.approx(2.5, rel=0.05)
    assert f["peak_voltage_v"] == pytest.approx(-0.45, abs=0.005)


def test_too_short_curve():
    assert extract_features([{"v": 0, "i": 0}] * 5) is None


# -- protocol ------------------------------------------------------------------

def test_parse_analyte_and_status():
    curve = json.dumps([{"v": 0.1, "i": 1.0}, {"v": 0.2, "i": 2.0}])
    msg = UARTBridge.parse_line(f"DATA:BIOSENSOR:NO3:SATURATED:-15.9,-0.45,1.2,{curve}")
    assert msg["analyte"] == "NO3"
    assert msg["status"] == "SATURATED"
    assert msg["valid"] is False
    assert msg["peak_current_ua"] == pytest.approx(-15.9)
    assert len(msg["raw_json"]) == 2


def test_parse_legacy_biosensor_line():
    msg = UARTBridge.parse_line('DATA:BIOSENSOR:12.5,0.35,0.20,[{"v":0.1,"i":1}]')
    assert msg["analyte"] == "H2O2" and msg["status"] == "OK" and msg["valid"]


def test_mock_scan_returns_requested_analyte():
    bridge = UARTBridge(port="/dev/does-not-exist")
    r = bridge.trigger_scan("NO3")
    assert r["analyte"] == "NO3" and r["mock"] is True
    f = extract_features(r["raw_json"], polarity=-1)
    assert f["peak_height_ua"] > 0.3


def test_button_during_battery_poll_is_kept():
    bridge = UARTBridge(port="/dev/does-not-exist")
    lines = iter(["DATA:BUTTON:1", "DATA:BATTERY:3.912"])
    bridge.read_response = lambda timeout=None: UARTBridge.parse_line(next(lines))
    bridge.send_command = lambda cmd: None
    assert bridge.get_battery() == pytest.approx(3.912)
    assert bridge.read_event()["button"] == 1


# -- model class order ---------------------------------------------------------

def test_alphabetical_model_outputs_are_remapped():
    alphabetical = sorted(CLASSES)          # what ImageFolder trains
    logits = np.full(len(CLASSES), -5.0)
    logits[alphabetical.index("rice_blast")] = 5.0
    probs = probs_in_config_order(logits, alphabetical)
    assert max(probs, key=probs.get) == "rice_blast"
    assert list(probs) == list(CLASSES)


def test_unknown_model_classes_are_dropped():
    names = ["brown_spot", "healthy", "rice_blast"]
    probs = probs_in_config_order([0.0, 1.0, 2.0], names)
    assert set(probs) == set(CLASSES)
    assert sum(probs.values()) == pytest.approx(1.0)
    assert probs["heat_stress"] == 0.0


# -- pipeline + database -------------------------------------------------------

def test_scan_writes_every_table(tmp_path, monkeypatch):
    sqlalchemy = pytest.importorskip("sqlalchemy")
    from contextlib import contextmanager

    from sqlalchemy.orm import sessionmaker

    from pi5 import config
    from pi5 import db as db_pkg
    from pi5 import main as main_mod

    monkeypatch.setattr(config, "IMAGE_DIR", str(tmp_path / "img"))
    monkeypatch.setattr(config, "LCD_PREVIEW_PATH", str(tmp_path / "lcd.png"))
    random.seed(3)
    engine = sqlalchemy.create_engine("sqlite:///:memory:")
    db_pkg.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def factory():
        s = Session()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    scanner = main_mod.RiceScanner(use_db=True, session_factory=factory)
    scanner.mode_index = config.ANALYTE_MODES.index(("H2O2", "NO3"))
    result = scanner.run_scan(session_notes="test")
    scanner.close()

    assert result["mock"] is True
    assert [r["analyte"] for r in result["biosensor"]] == ["H2O2", "NO3"]
    with Session() as s:
        for model in (db_pkg.ScanSession, db_pkg.RGBScan, db_pkg.NIRScan,
                      db_pkg.FusedDiagnosis):
            assert s.query(model).count() == 1, model.__tablename__
        rows = s.query(db_pkg.BiosensorReading).all()
        assert sorted(r.analyte for r in rows) == ["H2O2", "NO3"]
        assert all(r.features and len(r.raw_adc_values["curve"]) > 100 for r in rows)
        assert s.query(db_pkg.FusedDiagnosis).one().mock is True
