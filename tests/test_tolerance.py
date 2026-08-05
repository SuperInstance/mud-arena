"""Tests for the ToleranceTracker module."""

import json
import math
import os
import tempfile
from datetime import datetime

import pytest

from tolerance import Measurement, ToleranceTracker


class TestMeasurement:
    def test_basic_measurement(self):
        m = Measurement("voltage", predicted=12.0, actual=12.6)
        assert m.variable_name == "voltage"
        assert m.predicted == 12.0
        assert m.actual == 12.6
        assert m.error_pct == pytest.approx(5.0)

    def test_zero_prediction_zero_actual(self):
        m = Measurement("temp", predicted=0, actual=0)
        assert m.error_pct == 0.0

    def test_zero_prediction_nonzero_actual(self):
        m = Measurement("temp", predicted=0, actual=5)
        assert m.error_pct == math.inf

    def test_negative_error(self):
        m = Measurement("rpm", predicted=2000, actual=1900)
        assert m.error_pct == pytest.approx(-5.0)

    def test_timestamp_defaults_to_now(self):
        before = datetime.now()
        m = Measurement("x", 1.0, 1.0)
        after = datetime.now()
        assert before <= m.timestamp <= after

    def test_custom_timestamp(self):
        ts = datetime(2025, 1, 1, 12, 0, 0)
        m = Measurement("x", 1.0, 1.0, timestamp=ts)
        assert m.timestamp == ts

    def test_to_dict_and_from_dict_roundtrip(self):
        ts = datetime(2025, 6, 15, 10, 30, 0)
        m = Measurement(
            "pressure",
            predicted=101.3,
            actual=99.8,
            timestamp=ts,
            unit="kPa",
            source="sensor_01",
        )
        d = m.to_dict()
        assert d["variable_name"] == "pressure"
        assert d["unit"] == "kPa"
        assert d["source"] == "sensor_01"

        m2 = Measurement.from_dict(d)
        assert m2.variable_name == m.variable_name
        assert m2.predicted == m.predicted
        assert m2.actual == m.actual
        assert m2.timestamp == m.timestamp
        assert m2.unit == m.unit
        assert m2.source == m.source
        assert m2.error_pct == pytest.approx(m.error_pct)

    def test_slots_prevents_arbitrary_attributes(self):
        m = Measurement("x", 1.0, 2.0)
        with pytest.raises(AttributeError):
            m.foo = "bar"


class TestToleranceTracker:
    def test_record_returns_measurement(self):
        tracker = ToleranceTracker()
        m = tracker.record("voltage", 12.0, 12.6, unit="V")
        assert isinstance(m, Measurement)
        assert m.variable_name == "voltage"

    def test_get_tolerance_empty(self):
        tracker = ToleranceTracker()
        assert tracker.get_tolerance("nonexistent") == 0.0

    def test_get_tolerance_average(self):
        tracker = ToleranceTracker()
        tracker.record("temp", 100, 105)  # +5%
        tracker.record("temp", 100, 95)   # -5%
        assert tracker.get_tolerance("temp") == pytest.approx(0.0)

    def test_get_tolerance_all_positive(self):
        tracker = ToleranceTracker()
        tracker.record("v", 10, 11)  # +10%
        tracker.record("v", 10, 12)  # +20%
        assert tracker.get_tolerance("v") == pytest.approx(15.0)

    def test_get_curve(self):
        tracker = ToleranceTracker()
        tracker.record("x", 100, 110)
        tracker.record("x", 100, 120)
        tracker.record("x", 100, 90)
        curve = tracker.get_curve("x")
        assert len(curve) == 3
        assert curve[0] == pytest.approx(10.0)
        assert curve[1] == pytest.approx(20.0)
        assert curve[2] == pytest.approx(-10.0)

    def test_get_curve_empty(self):
        tracker = ToleranceTracker()
        assert tracker.get_curve("nope") == []

    def test_is_within_tolerance_true(self):
        tracker = ToleranceTracker()
        tracker.record("v", 100, 103)  # 3%
        assert tracker.is_within_tolerance("v", 5.0) is True

    def test_is_within_tolerance_false(self):
        tracker = ToleranceTracker()
        tracker.record("v", 100, 120)  # 20%
        assert tracker.is_within_tolerance("v", 5.0) is False

    def test_is_within_tolerance_negative_error(self):
        tracker = ToleranceTracker()
        tracker.record("v", 100, 80)  # -20%
        assert tracker.is_within_tolerance("v", 5.0) is False

    def test_calibrate(self):
        tracker = ToleranceTracker()
        tracker.record("v", 100, 110)  # +10%
        factor = tracker.calibrate("v")
        assert factor == pytest.approx(1.1)

    def test_calibrate_no_data(self):
        tracker = ToleranceTracker()
        assert tracker.calibrate("nope") == pytest.approx(1.0)

    def test_detect_drift_true(self):
        tracker = ToleranceTracker()
        tracker.record("v", 100, 101)  # 1% error
        tracker.record("v", 100, 110)  # 10% error
        assert tracker.detect_drift("v") is True

    def test_detect_drift_false(self):
        tracker = ToleranceTracker()
        tracker.record("v", 100, 110)  # 10% error
        tracker.record("v", 100, 101)  # 1% error
        assert tracker.detect_drift("v") is False

    def test_detect_drift_insufficient_data(self):
        tracker = ToleranceTracker()
        tracker.record("v", 100, 110)
        assert tracker.detect_drift("v") is False

    def test_detect_drift_no_data(self):
        tracker = ToleranceTracker()
        assert tracker.detect_drift("nope") is False

    def test_confidence_perfect(self):
        tracker = ToleranceTracker()
        tracker.record("v", 100, 100)
        assert tracker.confidence("v") == pytest.approx(1.0)

    def test_confidence_zero(self):
        tracker = ToleranceTracker()
        tracker.record("v", 100, 200)  # 100% error
        assert tracker.confidence("v") == pytest.approx(0.0)

    def test_confidence_no_data(self):
        tracker = ToleranceTracker()
        assert tracker.confidence("nope") == pytest.approx(1.0)

    def test_report_structure(self):
        tracker = ToleranceTracker()
        tracker.record("v", 100, 110, unit="V")
        tracker.record("t", 50, 48, unit="°C")
        report = tracker.report()
        assert "v" in report
        assert "t" in report
        assert "tolerance_pct" in report["v"]
        assert "error_curve" in report["v"]
        assert "within_10pct" in report["v"]
        assert "calibration_factor" in report["v"]
        assert "drift_detected" in report["v"]
        assert "confidence" in report["v"]

    def test_suggest_adjustments_within_tolerance(self):
        tracker = ToleranceTracker()
        tracker.record("good", 100, 101)  # 1%
        suggestions = tracker.suggest_adjustments()
        assert len(suggestions) == 0

    def test_suggest_adjustments_out_of_tolerance(self):
        tracker = ToleranceTracker()
        tracker.record("bad", 100, 130)  # 30%
        suggestions = tracker.suggest_adjustments()
        assert len(suggestions) == 1
        assert "bad" in suggestions[0]

    def test_save_and_load_roundtrip(self):
        tracker = ToleranceTracker()
        tracker.record("v", 100, 110, unit="V", source="s1")
        tracker.record("v", 100, 105, unit="V", source="s2")
        tracker.record("t", 50, 48, unit="°C", source="s3")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            tracker.save(path)
            tracker2 = ToleranceTracker()
            tracker2.load(path)
            assert len(tracker2.get_curve("v")) == 2
            assert len(tracker2.get_curve("t")) == 1
            assert tracker2.get_tolerance("v") == pytest.approx(tracker.get_tolerance("v"))
        finally:
            os.unlink(path)

    def test_multiple_variables_independent(self):
        tracker = ToleranceTracker()
        tracker.record("a", 100, 110)
        tracker.record("b", 100, 90)
        assert tracker.get_tolerance("a") == pytest.approx(10.0)
        assert tracker.get_tolerance("b") == pytest.approx(-10.0)
