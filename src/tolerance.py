```python
"""
tolerance_tracker.py

A lightweight, pure‑standard‑library module for tracking the tolerance between
simulation predictions and real measurements.

Classes
-------
Measurement
    Holds a single prediction/measurement pair together with metadata and the
    computed error percentage.

ToleranceTracker
    Collects measurements, computes statistics, detects drift, suggests
    adjustments and can persist/restore its state to/from JSON files.
"""

import json
import math
from datetime import datetime
from statistics import mean
from typing import List, Dict, Any, Optional


class Measurement:
    """
    Represents a single measurement.

    Attributes
    ----------
    variable_name : str
        Name of the variable being measured.
    predicted : float
        Predicted value from the simulation.
    actual : float
        Real measured value.
    timestamp : datetime
        Time the measurement was recorded.
    unit : str
        Unit of the measurement (e.g., "V", "°C").
    source : str
        Identifier of the data source.
    error_pct : float
        Relative error expressed as a percentage.
    """

    __slots__ = (
        "variable_name",
        "predicted",
        "actual",
        "timestamp",
        "unit",
        "source",
        "error_pct",
    )

    def __init__(
        self,
        variable_name: str,
        predicted: float,
        actual: float,
        timestamp: Optional[datetime] = None,
        unit: str = "",
        source: str = "",
    ) -> None:
        self.variable_name = variable_name
        self.predicted = float(predicted)
        self.actual = float(actual)
        self.timestamp = timestamp or datetime.now()
        self.unit = unit
        self.source = source
        self.error_pct = self._calc_error_pct()

    def _calc_error_pct(self) -> float:
        """Calculate relative error in percent."""
        if self.predicted == 0:
            return 0.0 if self.actual == 0 else math.inf
        return ((self.actual - self.predicted) / self.predicted) * 100.0

    # --------------------------------------------------------------------- #
    # JSON (de)serialization helpers
    # --------------------------------------------------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON‑serialisable representation."""
        return {
            "variable_name": self.variable_name,
            "predicted": self.predicted,
            "actual": self.actual,
            "timestamp": self.timestamp.isoformat(),
            "unit": self.unit,
            "source": self.source,
            "error_pct": self.error_pct,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Measurement":
        """Re‑create a Measurement from a dict produced by ``to_dict``."""
        ts = datetime.fromisoformat(data["timestamp"])
        return cls(
            variable_name=data["variable_name"],
            predicted=data["predicted"],
            actual=data["actual"],
            timestamp=ts,
            unit=data.get("unit", ""),
            source=data.get("source", ""),
        )


class ToleranceTracker:
    """
    Tracks measurements for many variables and provides tolerance‑related
    analytics.

    Public API
    ----------
    record(variable, predicted, actual, unit='', source='') -> Measurement
    get_tolerance(variable) -> float
    get_curve(variable) -> List[float]
    is_within_tolerance(variable, threshold_pct) -> bool
    calibrate(variable) -> float
    detect_drift(variable) -> bool
    confidence(variable) -> float
    report() -> dict
    suggest_adjustments() -> List[str]
    save(path) -> None
    load(path) -> None
    """

    def __init__(self) -> None:
        # Mapping variable name -> list[Measurement]
        self._data: Dict[str, List[Measurement]] = {}

    # --------------------------------------------------------------------- #
    # Recording
    # --------------------------------------------------------------------- #
    def record(
        self,
        variable: str,
        predicted: float,
        actual: float,
        unit: str = "",
        source: str = "",
    ) -> Measurement:
        """Create a Measurement, store it and return the instance."""
        m = Measurement(variable, predicted, actual, unit=unit, source=source)
        self._data.setdefault(variable, []).append(m)
        return m

    # --------------------------------------------------------------------- #
    # Basic statistics
    # --------------------------------------------------------------------- #
    def get_tolerance(self, variable: str) -> float:
        """Average error percentage for *variable* (0 if no data)."""
        errors = self._errors(variable)
        return mean(errors) if errors else 0.0

    def get_curve(self, variable: str) -> List[float]:
        """Chronological list of error percentages for *variable*."""
        return [m.error_pct for m in self._data.get(variable, [])]

    # --------------------------------------------------------------------- #
    # Decision helpers
    # --------------------------------------------------------------------- #
    def is_within_tolerance(self, variable: str, threshold_pct: float) -> bool:
        """True if the absolute average error is ≤ *threshold_pct*."""
        return abs(self.get_tolerance(variable)) <= threshold_pct

    def calibrate(self, variable: str) -> float:
        """
        Return a multiplicative correction factor that would bring the
        predictions closer to reality.

        factor = 1 + (average_error / 100)
        """
        return 1.0 + (self.get_tolerance(variable) / 100.0)

    def detect_drift(self, variable: str) -> bool:
        """
        Simple drift detection: returns True if the latest error is larger
        than the earliest error (i.e., error is trending upward).
        """
        curve = self.get_curve(variable)
        if len(curve) < 2:
            return False
        return curve[-1] > curve[0]

    def confidence(self, variable: str) -> float:
        """
        Heuristic confidence score in the range [0, 1] where 1 means
        zero error and 0 means 100 % error.
        """
        avg_err = abs(self.get_tolerance(variable))
        return max(0.0, 1.0 - (avg_err / 100.0))

    # --------------------------------------------------------------------- #
    # Reporting
    # --------------------------------------------------------------------- #
    def report(self) -> Dict[str, Dict[str, Any]]:
        """
        Produce a summary dictionary keyed by variable name.
        Each entry contains tolerance, curve, drift flag, calibration factor,
        confidence and a boolean indicating whether the default 10 % threshold
        is satisfied.
        """
        summary: Dict[str, Dict[str, Any]] = {}
        for var in self._data:
            summary[var] = {
                "tolerance_pct": self.get_tolerance(var),
                "error_curve": self.get_curve(var),
                "within_10pct": self.is_within_tolerance(var, 10.0),
                "calibration_factor": self.calibrate(var),
                "drift_detected": self.detect_drift(var),
                "confidence": self.confidence(var),
            }
        return summary

    def suggest_adjustments(self) -> List[str]:
        """
        Generate human‑readable suggestions for variables that exceed the
        default 10 % tolerance.
        """
        suggestions = []
        for var, info in self.report().items():
            if not info["within_10pct"]:
                factor = info["calibration_factor"]
                suggestions.append(
                    f"Variable '{var}': apply correction factor {factor:.4f}"
                )
        return suggestions

    # --------------------------------------------------------------------- #
    # Persistence
    # --------------------------------------------------------------------- #
    def save(self, path: str) -> None:
        """Serialise all measurements to *path* as JSON."""
        serialisable = {
            var: [m.to_dict() for m in measurements]
            for var, measurements in self._data.items()
        }
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(serialisable, fp, indent=2)

    def load(self, path: str) -> None:
        """Load measurements from a JSON file written by ``save``."""
        with open(path, "r", encoding="utf-8") as fp:
            raw = json.load(fp)
        self._data = {
            var: [Measurement.from_dict(m_dict) for m_dict in lst]
            for var, lst in raw.items()
        }

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _errors(self, variable: str) -> List[float]:
        """Return a list of error percentages for *variable*."""
        return [m.error_pct for m in self._data.get(variable, [])]


# Exported symbols when ``from tolerance_tracker import *`` is used
__all__ = ["Measurement", "ToleranceTracker"]
```