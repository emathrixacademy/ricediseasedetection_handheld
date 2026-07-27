"""test_potentiostat.py — DPV parameter math and ADC->current conversion.

Pure math tests documenting the analog front-end behavior:
  - Transimpedance amplifier (TIA): Vout = Vgnd - I_we * Rf
    => I_we = (Vgnd - Vout) / Rf
  - Virtual ground = 1.65V (2x10k divider from 3.3V) enables bidirectional
    current on a single supply.
  - ADS1115 16-bit ADC; here we model the standard ±4.096V full-scale range.
"""
import pytest

RF_OHMS = 100_000.0        # feedback resistor, 100 kΩ
VGND = 1.65                # virtual ground (V)
ADS_FS_VOLTS = 4.096       # ADS1115 PGA full scale for GAIN=1 (±4.096V)
ADS_FS_COUNTS = 32767      # 16-bit signed full-scale


def adc_counts_to_volts(counts, fs_volts=ADS_FS_VOLTS, fs_counts=ADS_FS_COUNTS):
    """Convert signed ADS1115 counts to volts."""
    return counts / fs_counts * fs_volts


def tia_output_to_current_ua(vout, vgnd=VGND, rf=RF_OHMS):
    """Convert TIA output voltage to working-electrode current in microamps."""
    i_amps = (vgnd - vout) / rf
    return i_amps * 1e6


def test_adc_full_scale():
    assert adc_counts_to_volts(ADS_FS_COUNTS) == pytest.approx(ADS_FS_VOLTS, rel=1e-4)


def test_adc_zero():
    assert adc_counts_to_volts(0) == 0.0


def test_zero_current_at_virtual_ground():
    # When Vout == Vgnd, no current flows through Rf.
    assert tia_output_to_current_ua(VGND) == pytest.approx(0.0, abs=1e-9)


def test_positive_current_conversion():
    # Vout below Vgnd => positive (oxidation) current.
    # 0.65V below 1.65V across 100k => 10 µA.
    i_ua = tia_output_to_current_ua(VGND - 1.0)
    assert i_ua == pytest.approx(10.0, rel=1e-6)


def test_negative_current_sign():
    # Vout above Vgnd => negative current.
    i_ua = tia_output_to_current_ua(VGND + 0.5)
    assert i_ua < 0
    assert i_ua == pytest.approx(-5.0, rel=1e-6)


def test_roundtrip_counts_to_current():
    # A raw ADC reading corresponding to ~0.65V below Vgnd.
    target_vout = VGND - 1.0
    counts = round(target_vout / ADS_FS_VOLTS * ADS_FS_COUNTS)
    vout = adc_counts_to_volts(counts)
    i_ua = tia_output_to_current_ua(vout)
    assert i_ua == pytest.approx(10.0, rel=1e-3)


def test_virtual_ground_divider():
    # 2x10k divider from 3.3V yields 1.65V.
    r_top = r_bot = 10_000.0
    vgnd = 3.3 * r_bot / (r_top + r_bot)
    assert vgnd == pytest.approx(VGND, rel=1e-6)


def dpv_step_voltages(v_start, v_end, step_mv):
    """Generate DPV staircase base potentials (V)."""
    step_v = step_mv / 1000.0
    n = int(round((v_end - v_start) / step_v)) + 1
    return [round(v_start + i * step_v, 6) for i in range(n)]


def test_dpv_staircase():
    steps = dpv_step_voltages(-0.2, 0.6, 5)  # 5 mV steps
    assert steps[0] == pytest.approx(-0.2)
    assert steps[-1] == pytest.approx(0.6)
    assert len(steps) == 161
