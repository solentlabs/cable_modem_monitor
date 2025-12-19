"""Tests for __init__.py helper functions."""

from custom_components.cable_modem_monitor import _normalize_channel_type


class TestNormalizeChannelType:
    """Tests for _normalize_channel_type function."""

    # Downstream QAM cases
    def test_downstream_qam_from_channel_type(self):
        """QAM downstream with explicit channel_type."""
        channel = {"channel_type": "qam", "modulation": "QAM256"}
        assert _normalize_channel_type(channel, "downstream") == "qam"

    def test_downstream_qam_from_modulation_only(self):
        """QAM downstream with only modulation field."""
        channel = {"modulation": "QAM256"}
        assert _normalize_channel_type(channel, "downstream") == "qam"

    def test_downstream_qam_default(self):
        """QAM downstream when no type info provided."""
        channel = {"frequency": 765000000}
        assert _normalize_channel_type(channel, "downstream") == "qam"

    # Downstream OFDM cases
    def test_downstream_ofdm_from_channel_type(self):
        """OFDM downstream with explicit channel_type."""
        channel = {"channel_type": "ofdm", "modulation": "OFDM"}
        assert _normalize_channel_type(channel, "downstream") == "ofdm"

    def test_downstream_ofdm_from_modulation(self):
        """OFDM downstream detected from modulation field."""
        channel = {"modulation": "OFDM"}
        assert _normalize_channel_type(channel, "downstream") == "ofdm"

    def test_downstream_ofdm_from_is_ofdm_flag(self):
        """OFDM downstream detected from is_ofdm flag."""
        channel = {"is_ofdm": True}
        assert _normalize_channel_type(channel, "downstream") == "ofdm"

    # Upstream ATDMA cases
    def test_upstream_atdma_from_channel_type(self):
        """ATDMA upstream with explicit channel_type (CM1200 format)."""
        channel = {"channel_type": "ATDMA", "symbol_rate": 5120}
        assert _normalize_channel_type(channel, "upstream") == "atdma"

    def test_upstream_atdma_from_channel_type_lowercase(self):
        """ATDMA upstream with lowercase channel_type."""
        channel = {"channel_type": "atdma"}
        assert _normalize_channel_type(channel, "upstream") == "atdma"

    def test_upstream_atdma_default(self):
        """ATDMA upstream when no type info provided."""
        channel = {"frequency": 13200000}
        assert _normalize_channel_type(channel, "upstream") == "atdma"

    # Upstream OFDMA cases - these were failing before the fix!
    def test_upstream_ofdma_from_channel_type(self):
        """OFDMA upstream with explicit channel_type (CM1200 format).

        This was the bug: CM1200 outputs channel_type='OFDMA' but the old
        code only checked modulation field, causing OFDMA to be classified as ATDMA.
        """
        channel = {"channel_type": "OFDMA", "is_ofdm": True}
        assert _normalize_channel_type(channel, "upstream") == "ofdma"

    def test_upstream_ofdma_from_channel_type_lowercase(self):
        """OFDMA upstream with lowercase channel_type."""
        channel = {"channel_type": "ofdma"}
        assert _normalize_channel_type(channel, "upstream") == "ofdma"

    def test_upstream_ofdma_from_modulation(self):
        """OFDMA upstream detected from modulation field."""
        channel = {"modulation": "OFDMA"}
        assert _normalize_channel_type(channel, "upstream") == "ofdma"

    def test_upstream_ofdma_from_is_ofdm_flag(self):
        """OFDMA upstream detected from is_ofdm flag."""
        channel = {"is_ofdm": True}
        assert _normalize_channel_type(channel, "upstream") == "ofdma"

    # Edge cases
    def test_empty_channel(self):
        """Empty channel defaults correctly."""
        assert _normalize_channel_type({}, "downstream") == "qam"
        assert _normalize_channel_type({}, "upstream") == "atdma"

    def test_case_insensitivity(self):
        """Channel type matching is case-insensitive."""
        assert _normalize_channel_type({"channel_type": "OFDM"}, "downstream") == "ofdm"
        assert _normalize_channel_type({"channel_type": "Ofdma"}, "upstream") == "ofdma"
