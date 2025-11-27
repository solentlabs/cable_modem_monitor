"""Tests for capture_modem.py filtering and compression."""

from __future__ import annotations

import gzip
import json

# Import the module components we want to test
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


class TestBloatFiltering:
    """Tests for BLOAT_EXTENSIONS filtering."""

    def test_font_extensions_defined(self):
        """Verify font extensions are in bloat list."""
        from capture_modem import BLOAT_EXTENSIONS

        font_exts = {".woff", ".woff2", ".ttf", ".otf", ".eot"}
        assert font_exts.issubset(BLOAT_EXTENSIONS)

    def test_image_extensions_defined(self):
        """Verify image extensions are in bloat list."""
        from capture_modem import BLOAT_EXTENSIONS

        image_exts = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp"}
        assert image_exts.issubset(BLOAT_EXTENSIONS)

    def test_media_extensions_defined(self):
        """Verify media extensions are in bloat list."""
        from capture_modem import BLOAT_EXTENSIONS

        media_exts = {".mp3", ".mp4", ".wav", ".webm", ".ogg"}
        assert media_exts.issubset(BLOAT_EXTENSIONS)


class TestFilterAndCompressHar:
    """Tests for filter_and_compress_har function."""

    def _create_har_entry(self, url: str, content: str = "test") -> dict:
        """Helper to create a HAR entry."""
        return {
            "request": {"url": url},
            "response": {"content": {"text": content, "mimeType": "text/html"}},
        }

    def _create_har(self, entries: list[dict]) -> dict:
        """Helper to create a HAR structure."""
        return {"log": {"entries": entries}}

    def _write_har(self, har: dict, path: Path) -> None:
        """Helper to write HAR to file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(har, f)

    def test_filters_font_files(self):
        """Font files should be removed."""
        from capture_modem import filter_and_compress_har

        har = self._create_har(
            [
                self._create_har_entry("http://modem/index.html", "<html>test</html>"),
                self._create_har_entry("http://modem/font.woff", "binary font data"),
                self._create_har_entry("http://modem/font.woff2", "binary font data"),
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".har", delete=False) as f:
            self._write_har(har, Path(f.name))
            _, stats = filter_and_compress_har(Path(f.name))

        assert stats["original_entries"] == 3
        assert stats["filtered_entries"] == 1
        assert stats["removed_entries"] == 2

    def test_filters_image_files(self):
        """Image files should be removed."""
        from capture_modem import filter_and_compress_har

        har = self._create_har(
            [
                self._create_har_entry("http://modem/index.html", "<html>test</html>"),
                self._create_har_entry("http://modem/logo.png", "binary image"),
                self._create_har_entry("http://modem/icon.ico", "binary icon"),
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".har", delete=False) as f:
            self._write_har(har, Path(f.name))
            _, stats = filter_and_compress_har(Path(f.name))

        assert stats["filtered_entries"] == 1
        assert stats["removed_entries"] == 2

    def test_removes_duplicate_urls(self):
        """Duplicate URLs should be removed (keep first)."""
        from capture_modem import filter_and_compress_har

        har = self._create_har(
            [
                self._create_har_entry("http://modem/page.html", "first"),
                self._create_har_entry("http://modem/page.html", "second"),
                self._create_har_entry("http://modem/page.html", "third"),
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".har", delete=False) as f:
            self._write_har(har, Path(f.name))
            _, stats = filter_and_compress_har(Path(f.name))

        assert stats["original_entries"] == 3
        assert stats["filtered_entries"] == 1

    def test_preserves_html_pages(self):
        """HTML pages should be preserved."""
        from capture_modem import filter_and_compress_har

        har = self._create_har(
            [
                self._create_har_entry("http://modem/index.html", "<html>index</html>"),
                self._create_har_entry("http://modem/status.htm", "<html>status</html>"),
                self._create_har_entry("http://modem/login", "<html>login</html>"),
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".har", delete=False) as f:
            self._write_har(har, Path(f.name))
            _, stats = filter_and_compress_har(Path(f.name))

        assert stats["filtered_entries"] == 3
        assert stats["removed_entries"] == 0

    def test_creates_compressed_file(self):
        """Should create a .har.gz file."""
        from capture_modem import filter_and_compress_har

        har = self._create_har(
            [
                self._create_har_entry("http://modem/index.html", "<html>test</html>"),
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".har", delete=False) as f:
            har_path = Path(f.name)
            self._write_har(har, har_path)
            compressed_path, _ = filter_and_compress_har(har_path)

        assert compressed_path.suffix == ".gz"
        assert compressed_path.exists()

        # Verify it's valid gzip
        with gzip.open(compressed_path, "rt") as f:
            data = json.load(f)
            assert "log" in data

    def test_compression_reduces_size(self):
        """Compressed file should be smaller than original."""
        from capture_modem import filter_and_compress_har

        # Create a HAR with repetitive content (compresses well)
        large_content = "<html>" + "test " * 10000 + "</html>"
        har = self._create_har(
            [
                self._create_har_entry("http://modem/index.html", large_content),
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".har", delete=False) as f:
            har_path = Path(f.name)
            self._write_har(har, har_path)
            compressed_path, stats = filter_and_compress_har(har_path)

        assert stats["compressed_size"] < stats["filtered_size"]

    def test_handles_query_params_in_urls(self):
        """Should handle URLs with query parameters correctly."""
        from capture_modem import filter_and_compress_har

        har = self._create_har(
            [
                self._create_har_entry("http://modem/image.png?v=123", "image"),
                self._create_har_entry("http://modem/page.html?id=456", "page"),
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".har", delete=False) as f:
            self._write_har(har, Path(f.name))
            _, stats = filter_and_compress_har(Path(f.name))

        # image.png should be filtered even with query params
        assert stats["filtered_entries"] == 1

    def test_stats_contain_all_fields(self):
        """Stats dict should contain all expected fields."""
        from capture_modem import filter_and_compress_har

        har = self._create_har(
            [
                self._create_har_entry("http://modem/index.html", "test"),
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".har", delete=False) as f:
            self._write_har(har, Path(f.name))
            _, stats = filter_and_compress_har(Path(f.name))

        assert "original_entries" in stats
        assert "filtered_entries" in stats
        assert "removed_entries" in stats
        assert "original_size" in stats
        assert "filtered_size" in stats
        assert "compressed_size" in stats
