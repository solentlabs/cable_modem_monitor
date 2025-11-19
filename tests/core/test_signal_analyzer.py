"""Tests for Signal Quality Analyzer."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from custom_components.cable_modem_monitor.core.signal_analyzer import SignalQualityAnalyzer


@pytest.fixture
def analyzer():
    """Create a signal analyzer instance."""
    return SignalQualityAnalyzer()


@pytest.fixture
def stable_sample():
    """Create a sample with stable signal quality."""
    return {
        "downstream_channels": [
            {"channel_id": 1, "snr": 40.0, "power": 5.0},
            {"channel_id": 2, "snr": 40.5, "power": 5.1},
            {"channel_id": 3, "snr": 39.8, "power": 4.9},
        ],
        "total_uncorrected_errors": 0,
    }


@pytest.fixture
def fluctuating_sample():
    """Create a sample with fluctuating signal quality."""
    return {
        "downstream_channels": [
            {"channel_id": 1, "snr": 35.0, "power": 3.0},
            {"channel_id": 2, "snr": 42.0, "power": 7.0},
            {"channel_id": 3, "snr": 28.0, "power": 2.0},
        ],
        "total_uncorrected_errors": 100,
    }


@pytest.fixture
def problematic_sample():
    """Create a sample with problematic signal quality."""
    return {
        "downstream_channels": [
            {"channel_id": 1, "snr": 25.0, "power": 10.0},
            {"channel_id": 2, "snr": 18.0, "power": -2.0},
            {"channel_id": 3, "snr": 32.0, "power": 8.0},
        ],
        "total_uncorrected_errors": 5000,
    }


class TestSignalAnalyzerBasics:
    """Test basic signal analyzer functionality."""

    def test_initialization(self, analyzer):
        """Test analyzer initializes with empty history."""
        assert len(analyzer._history) == 0
        assert analyzer._max_history_hours == 48

    def test_add_sample(self, analyzer, stable_sample):
        """Test adding a sample to history."""
        analyzer.add_sample(stable_sample)

        assert len(analyzer._history) == 1
        assert analyzer._history[0]["data"] == stable_sample
        assert isinstance(analyzer._history[0]["timestamp"], datetime)

    def test_add_multiple_samples(self, analyzer, stable_sample):
        """Test adding multiple samples."""
        for _ in range(5):
            analyzer.add_sample(stable_sample)

        assert len(analyzer._history) == 5

    @patch("custom_components.cable_modem_monitor.core.signal_analyzer.datetime")
    def test_old_samples_removed(self, mock_datetime, analyzer, stable_sample):
        """Test that samples older than 48 hours are removed."""
        # Set initial time
        base_time = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = base_time

        # Add sample at base time
        analyzer.add_sample(stable_sample)

        # Advance time by 49 hours (past the 48-hour threshold)
        future_time = base_time + timedelta(hours=49)
        mock_datetime.now.return_value = future_time

        # Add new sample - should trigger cleanup
        analyzer.add_sample(stable_sample)

        # First sample should be removed, only second remains
        assert len(analyzer._history) == 1
        assert analyzer._history[0]["timestamp"] == future_time


class TestSignalMetricExtraction:
    """Test SNR, power, and error extraction."""

    def test_extract_snr_values(self, analyzer, stable_sample):
        """Test SNR value extraction."""
        sample = {"timestamp": datetime.now(), "data": stable_sample}
        snr_values = analyzer._extract_snr_values([sample])

        assert len(snr_values) == 3
        assert 39.8 in snr_values
        assert 40.0 in snr_values
        assert 40.5 in snr_values

    def test_extract_power_values(self, analyzer, stable_sample):
        """Test power value extraction."""
        sample = {"timestamp": datetime.now(), "data": stable_sample}
        power_values = analyzer._extract_power_values([sample])

        assert len(power_values) == 3
        assert 4.9 in power_values
        assert 5.0 in power_values
        assert 5.1 in power_values

    def test_extract_snr_handles_none_values(self, analyzer):
        """Test that None SNR values are filtered out."""
        sample_with_none = {
            "timestamp": datetime.now(),
            "data": {
                "downstream_channels": [
                    {"channel_id": 1, "snr": 40.0, "power": 5.0},
                    {"channel_id": 2, "snr": None, "power": 5.1},  # None SNR
                    {"channel_id": 3, "snr": 39.8, "power": 4.9},
                ]
            },
        }

        snr_values = analyzer._extract_snr_values([sample_with_none])

        assert len(snr_values) == 2  # Only 2 valid SNR values
        assert None not in snr_values

    def test_extract_power_handles_none_values(self, analyzer):
        """Test that None power values are filtered out."""
        sample_with_none = {
            "timestamp": datetime.now(),
            "data": {
                "downstream_channels": [
                    {"channel_id": 1, "snr": 40.0, "power": 5.0},
                    {"channel_id": 2, "snr": 40.5, "power": None},  # None power
                    {"channel_id": 3, "snr": 39.8, "power": 4.9},
                ]
            },
        }

        power_values = analyzer._extract_power_values([sample_with_none])

        assert len(power_values) == 2  # Only 2 valid power values
        assert None not in power_values

    def test_calculate_error_rates(self, analyzer):
        """Test error rate calculation."""
        samples = [
            {"timestamp": datetime.now(), "data": {"total_uncorrected_errors": 0}},
            {"timestamp": datetime.now(), "data": {"total_uncorrected_errors": 10}},
            {"timestamp": datetime.now(), "data": {"total_uncorrected_errors": 25}},
        ]

        error_rates = analyzer._calculate_error_rates(samples)

        assert error_rates == [0, 10, 25]


class TestErrorTrendAnalysis:
    """Test error trend calculation."""

    def test_error_trend_increasing(self, analyzer):
        """Test detection of increasing error trend."""
        # Recent errors (50-100) are > 1.5x older errors (0-10)
        error_rates = [0, 5, 10, 50, 75, 100]
        trend = analyzer._calculate_error_trend(error_rates)

        assert trend == "increasing"

    def test_error_trend_decreasing(self, analyzer):
        """Test detection of decreasing error trend."""
        # Recent errors (0-5) are < 0.5x older errors (100-150)
        error_rates = [100, 125, 150, 0, 2, 5]
        trend = analyzer._calculate_error_trend(error_rates)

        assert trend == "decreasing"

    def test_error_trend_stable(self, analyzer):
        """Test detection of stable error trend."""
        # Recent and older errors are similar
        error_rates = [10, 12, 15, 11, 13, 14]
        trend = analyzer._calculate_error_trend(error_rates)

        assert trend == "stable"

    def test_error_trend_insufficient_data(self, analyzer):
        """Test error trend with insufficient data."""
        error_rates = [10]  # Only one sample
        trend = analyzer._calculate_error_trend(error_rates)

        assert trend == "stable"  # Default to stable


class TestRecommendations:
    """Test polling interval recommendations."""

    @patch("custom_components.cable_modem_monitor.core.signal_analyzer.datetime")
    def test_insufficient_samples(self, mock_datetime, analyzer, stable_sample):
        """Test recommendation with insufficient samples."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = base_time

        # Add only 2 samples (need at least 3)
        analyzer.add_sample(stable_sample)
        analyzer.add_sample(stable_sample)

        recommendation = analyzer.get_recommended_interval(300)

        assert recommendation["recommended_seconds"] == 300  # Keep current
        assert recommendation["confidence"] == "low"
        assert "Insufficient data" in recommendation["reason"]
        assert recommendation["signal_status"] == "unknown"

    @patch("custom_components.cable_modem_monitor.core.signal_analyzer.datetime")
    def test_stable_signal_recommendation(self, mock_datetime, analyzer, stable_sample):
        """Test recommendation for very stable signal."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        # Add 10 stable samples over 24 hours
        for i in range(10):
            mock_datetime.now.return_value = base_time + timedelta(hours=i * 2.4)
            analyzer.add_sample(stable_sample)

        # Get recommendation
        mock_datetime.now.return_value = base_time + timedelta(hours=24)
        recommendation = analyzer.get_recommended_interval(300)

        assert recommendation["signal_status"] == "very_stable"
        assert recommendation["recommended_seconds"] == 600  # Increased from 300 (gradual 2x)
        assert recommendation["confidence"] in ["medium", "high"]
        assert "stable" in recommendation["reason"].lower()

    @patch("custom_components.cable_modem_monitor.core.signal_analyzer.datetime")
    def test_problematic_signal_recommendation(self, mock_datetime, analyzer, problematic_sample):
        """Test recommendation for problematic signal."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        # Add problematic samples with increasing errors
        for i in range(10):
            mock_datetime.now.return_value = base_time + timedelta(hours=i * 2.4)
            sample = {
                "downstream_channels": [
                    {"channel_id": 1, "snr": 25.0 - i, "power": 10.0 + i},  # Degrading SNR
                    {"channel_id": 2, "snr": 18.0 - i, "power": -2.0},
                ],
                "total_uncorrected_errors": i * 1000,  # Increasing errors
            }
            analyzer.add_sample(sample)

        mock_datetime.now.return_value = base_time + timedelta(hours=24)
        recommendation = analyzer.get_recommended_interval(300)

        assert recommendation["signal_status"] == "problematic"
        assert recommendation["recommended_seconds"] == 60  # Frequent monitoring
        assert recommendation["confidence"] == "high"
        assert "degrading" in recommendation["reason"].lower() or "problematic" in recommendation["reason"].lower()

    @patch("custom_components.cable_modem_monitor.core.signal_analyzer.datetime")
    def test_fluctuating_signal_recommendation(self, mock_datetime, analyzer):
        """Test recommendation for fluctuating signal."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        # Add samples with moderate SNR variance (5-10 dB)
        # Using 32-44 dB range creates ~6.3 dB variance, which is in the fluctuating range
        for i in range(10):
            mock_datetime.now.return_value = base_time + timedelta(hours=i * 2.4)
            sample = {
                "downstream_channels": [
                    {"channel_id": 1, "snr": 32.0 + (i % 2) * 12, "power": 5.0},  # SNR varies 32-44 (~6 dB stdev)
                ],
                "total_uncorrected_errors": 50,
            }
            analyzer.add_sample(sample)

        mock_datetime.now.return_value = base_time + timedelta(hours=24)
        recommendation = analyzer.get_recommended_interval(300)

        assert recommendation["signal_status"] == "fluctuating"
        assert recommendation["recommended_seconds"] == 180  # More frequent than stable
        assert "fluctuating" in recommendation["reason"].lower()

    @patch("custom_components.cable_modem_monitor.core.signal_analyzer.datetime")
    def test_gradual_adjustment_prevents_drastic_changes(self, mock_datetime, analyzer, stable_sample):
        """Test that recommendations don't change too drastically."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        # Add very stable samples
        for i in range(10):
            mock_datetime.now.return_value = base_time + timedelta(hours=i * 2.4)
            analyzer.add_sample(stable_sample)

        mock_datetime.now.return_value = base_time + timedelta(hours=24)

        # Current interval is 100 seconds
        # Recommendation would be 900 (very_stable), but should be clamped to 200 (2x current)
        recommendation = analyzer.get_recommended_interval(100)

        assert recommendation["recommended_seconds"] == 200  # 2x current, not full 900
        assert "gradual" in recommendation["reason"]

    @patch("custom_components.cable_modem_monitor.core.signal_analyzer.datetime")
    def test_clamping_to_valid_range(self, mock_datetime, analyzer, stable_sample):
        """Test that recommendations are clamped to 60-1800 second range."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        for i in range(10):
            mock_datetime.now.return_value = base_time + timedelta(hours=i * 2.4)
            analyzer.add_sample(stable_sample)

        mock_datetime.now.return_value = base_time + timedelta(hours=24)

        # Even with 30-second current interval, should not go below 60
        recommendation = analyzer.get_recommended_interval(30)

        assert recommendation["recommended_seconds"] >= 60
        assert recommendation["recommended_seconds"] <= 1800


class TestHistorySummary:
    """Test history summary functionality."""

    def test_summary_empty_history(self, analyzer):
        """Test summary with no samples."""
        summary = analyzer.get_history_summary()

        assert summary["sample_count"] == 0
        assert summary["oldest_sample"] is None
        assert summary["newest_sample"] is None

    @patch("custom_components.cable_modem_monitor.core.signal_analyzer.datetime")
    def test_summary_with_samples(self, mock_datetime, analyzer, stable_sample):
        """Test summary with multiple samples."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        # Add 5 samples over 10 hours
        for i in range(5):
            mock_datetime.now.return_value = base_time + timedelta(hours=i * 2)
            analyzer.add_sample(stable_sample)

        summary = analyzer.get_history_summary()

        assert summary["sample_count"] == 5
        assert summary["oldest_sample"] == base_time.isoformat()
        assert summary["newest_sample"] == (base_time + timedelta(hours=8)).isoformat()
        assert summary["hours_covered"] == 8.0


class TestMetricsInRecommendation:
    """Test that metrics are included in recommendations."""

    @patch("custom_components.cable_modem_monitor.core.signal_analyzer.datetime")
    def test_metrics_included(self, mock_datetime, analyzer, stable_sample):
        """Test that recommendation includes detailed metrics."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        for i in range(10):
            mock_datetime.now.return_value = base_time + timedelta(hours=i * 2.4)
            analyzer.add_sample(stable_sample)

        mock_datetime.now.return_value = base_time + timedelta(hours=24)
        recommendation = analyzer.get_recommended_interval(300)

        assert "metrics" in recommendation
        assert "snr_variance" in recommendation["metrics"]
        assert "power_variance" in recommendation["metrics"]
        assert "error_trend" in recommendation["metrics"]
        assert "sample_count" in recommendation["metrics"]

        # Verify metrics are reasonable
        assert isinstance(recommendation["metrics"]["snr_variance"], (int, float))
        assert isinstance(recommendation["metrics"]["power_variance"], (int, float))
        assert recommendation["metrics"]["error_trend"] in ["increasing", "stable", "decreasing"]
        # Sample count is 9, not 10, because filter uses > not >= (sample at exactly 24h cutoff is excluded)
        assert recommendation["metrics"]["sample_count"] == 9
