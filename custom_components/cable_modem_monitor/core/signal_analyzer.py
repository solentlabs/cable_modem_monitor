"""Signal quality analyzer for adaptive polling recommendations."""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta
from typing import Any

_LOGGER = logging.getLogger(__name__)


class SignalQualityAnalyzer:
    """Analyze signal quality trends to recommend polling intervals."""

    def __init__(self):
        """Initialize the signal analyzer."""
        self._history: list[dict[str, Any]] = []
        self._max_history_hours = 48  ***REMOVED*** Keep 48 hours of data for analysis

    def add_sample(self, data: dict[str, Any]) -> None:
        """
        Add a new data sample to history.

        Args:
            data: Modem data dict with downstream_channels, upstream_channels, etc.
        """
        sample = {
            "timestamp": datetime.now(),
            "data": data,
        }
        self._history.append(sample)

        ***REMOVED*** Clean old data (older than max_history_hours)
        cutoff = datetime.now() - timedelta(hours=self._max_history_hours)
        self._history = [s for s in self._history if s["timestamp"] > cutoff]

    def get_recommended_interval(self, current_interval: int) -> dict[str, Any]:
        """
        Calculate recommended polling interval based on signal trends.

        Algorithm:
        - Analyzes SNR stability (standard deviation)
        - Monitors power level changes
        - Tracks error rate trends
        - Considers current interval

        Returns dict with:
            - recommended_seconds: int
            - confidence: str (low/medium/high)
            - reason: str (explanation)
            - signal_status: str (stable/fluctuating/problematic)

        Based on research:
        - DOCSIS specifications for acceptable signal ranges
        - Network monitoring best practices
        - Cable modem health indicators
        """
        if len(self._history) < 3:
            return {
                "recommended_seconds": current_interval,
                "confidence": "low",
                "reason": "Insufficient data for analysis (need at least 3 samples)",
                "signal_status": "unknown",
            }

        ***REMOVED*** Extract recent samples (last 24 hours)
        cutoff_24h = datetime.now() - timedelta(hours=24)
        recent_samples = [s for s in self._history if s["timestamp"] > cutoff_24h]

        if len(recent_samples) < 3:
            return {
                "recommended_seconds": current_interval,
                "confidence": "low",
                "reason": "Insufficient recent data (need 24 hours of samples)",
                "signal_status": "unknown",
            }

        ***REMOVED*** Analyze signal stability
        snr_values = self._extract_snr_values(recent_samples)
        power_values = self._extract_power_values(recent_samples)
        error_rates = self._calculate_error_rates(recent_samples)

        ***REMOVED*** Calculate stability metrics
        snr_variance = statistics.stdev(snr_values) if len(snr_values) > 1 else 0
        power_variance = statistics.stdev(power_values) if len(power_values) > 1 else 0
        error_trend = self._calculate_error_trend(error_rates)

        ***REMOVED*** Determine signal status and recommendation
        return self._calculate_recommendation(
            current_interval=current_interval,
            snr_variance=snr_variance,
            power_variance=power_variance,
            error_trend=error_trend,
            sample_count=len(recent_samples),
        )

    def _extract_snr_values(self, samples: list[dict]) -> list[float]:
        """Extract SNR values from downstream channels."""
        snr_values = []
        for sample in samples:
            channels = sample["data"].get("downstream_channels", [])
            for channel in channels:
                if "snr" in channel and channel["snr"] is not None:
                    snr_values.append(channel["snr"])
        return snr_values

    def _extract_power_values(self, samples: list[dict]) -> list[float]:
        """Extract power level values from downstream channels."""
        power_values = []
        for sample in samples:
            channels = sample["data"].get("downstream_channels", [])
            for channel in channels:
                if "power" in channel and channel["power"] is not None:
                    power_values.append(channel["power"])
        return power_values

    def _calculate_error_rates(self, samples: list[dict]) -> list[int]:
        """Calculate total error counts over time."""
        error_rates = []
        for sample in samples:
            total_errors = sample["data"].get("total_uncorrected_errors", 0)
            error_rates.append(total_errors)
        return error_rates

    def _calculate_error_trend(self, error_rates: list[int]) -> str:
        """
        Determine if errors are increasing, stable, or decreasing.

        Returns: "increasing", "stable", or "decreasing"
        """
        if len(error_rates) < 2:
            return "stable"

        ***REMOVED*** Compare recent half to older half
        mid = len(error_rates) // 2
        older_avg = statistics.mean(error_rates[:mid])
        recent_avg = statistics.mean(error_rates[mid:])

        ***REMOVED*** If recent errors are 50% higher, consider increasing
        if recent_avg > older_avg * 1.5:
            return "increasing"
        ***REMOVED*** If recent errors are significantly lower
        elif recent_avg < older_avg * 0.5:
            return "decreasing"
        else:
            return "stable"

    def _calculate_recommendation(
        self,
        current_interval: int,
        snr_variance: float,
        power_variance: float,
        error_trend: str,
        sample_count: int,
    ) -> dict[str, Any]:
        """
        Calculate final recommendation based on all metrics.

        Signal Quality Thresholds (based on DOCSIS specs):
        - SNR variance < 2 dB: Very stable
        - SNR variance 2-5 dB: Stable
        - SNR variance 5-10 dB: Fluctuating
        - SNR variance > 10 dB: Problematic

        Power variance threshold: 3 dBmV
        """
        ***REMOVED*** Determine signal status
        if error_trend == "increasing" or snr_variance > 10:
            signal_status = "problematic"
            recommended = 60  ***REMOVED*** 1 minute - frequent monitoring
            confidence = "high"
            reason = "Signal quality degrading - recommend frequent monitoring"

        elif snr_variance > 5 or power_variance > 3:
            signal_status = "fluctuating"
            recommended = 180  ***REMOVED*** 3 minutes
            confidence = "medium"
            reason = "Signal fluctuating - moderate monitoring recommended"

        elif snr_variance < 2 and power_variance < 2 and error_trend != "increasing":
            signal_status = "very_stable"
            recommended = 900  ***REMOVED*** 15 minutes
            confidence = "high"
            reason = "Signal very stable - can reduce polling frequency"

        else:  ***REMOVED*** Stable
            signal_status = "stable"
            recommended = 300  ***REMOVED*** 5 minutes (standard)
            confidence = "medium"
            reason = "Signal stable - standard polling interval recommended"

        ***REMOVED*** Consider sample count for confidence
        if sample_count < 12:  ***REMOVED*** Less than half a day of 30-min samples
            confidence = "low"

        ***REMOVED*** Don't recommend drastic changes from current
        ***REMOVED*** Max 2x increase or 50% decrease at once
        if recommended > current_interval * 2:
            recommended = current_interval * 2
            reason += " (gradual adjustment)"
        elif recommended < current_interval * 0.5:
            recommended = int(current_interval * 0.5)
            reason += " (gradual adjustment)"

        ***REMOVED*** Clamp to valid range (60-1800 seconds)
        recommended = max(60, min(1800, recommended))

        return {
            "recommended_seconds": recommended,
            "confidence": confidence,
            "reason": reason,
            "signal_status": signal_status,
            "metrics": {
                "snr_variance": round(snr_variance, 2),
                "power_variance": round(power_variance, 2),
                "error_trend": error_trend,
                "sample_count": sample_count,
            },
        }

    def get_history_summary(self) -> dict[str, Any]:
        """Get summary of collected history."""
        if not self._history:
            return {
                "sample_count": 0,
                "oldest_sample": None,
                "newest_sample": None,
            }

        return {
            "sample_count": len(self._history),
            "oldest_sample": self._history[0]["timestamp"].isoformat(),
            "newest_sample": self._history[-1]["timestamp"].isoformat(),
            "hours_covered": (
                self._history[-1]["timestamp"] - self._history[0]["timestamp"]
            ).total_seconds()
            / 3600,
        }
