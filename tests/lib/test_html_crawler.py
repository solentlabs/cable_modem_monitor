"""Tests for HTML crawler utility functions."""

from __future__ import annotations

from custom_components.cable_modem_monitor.lib.html_crawler import (
    DEFAULT_EXTENSIONS,
    DEFAULT_SEED_BASES,
    RESOURCE_TYPE_CSS,
    RESOURCE_TYPE_FRAGMENT,
    RESOURCE_TYPE_HTML,
    RESOURCE_TYPE_JS,
    discover_links_from_pages,
    extract_all_resources_from_html,
    extract_links_from_html,
    generate_seed_urls,
    get_new_links_to_crawl,
    normalize_url,
)


class TestGenerateSeedUrls:
    """Tests for generate_seed_urls function."""

    def test_default_seeds(self):
        """Test default seed URL generation."""
        urls = generate_seed_urls()

        # Should include root
        assert "/" in urls
        # Should include index variations
        assert "/index" in urls
        assert "/index.html" in urls
        assert "/index.htm" in urls
        assert "/index.asp" in urls
        # Should include status variations
        assert "/status" in urls
        assert "/status.html" in urls

    def test_custom_bases_and_extensions(self):
        """Test with custom bases and extensions."""
        urls = generate_seed_urls(
            bases=["test", "admin"],
            extensions=[".html", ".php"],
        )

        assert "/test.html" in urls
        assert "/test.php" in urls
        assert "/admin.html" in urls
        assert "/admin.php" in urls
        # Root should not be included when not in bases
        assert "/" not in urls

    def test_empty_base_with_empty_extension_adds_root(self):
        """Test that empty base with empty extension adds root path."""
        urls = generate_seed_urls(bases=[""], extensions=[""])

        # Empty base with empty extension produces root
        assert "/" in urls

    def test_empty_base_with_extensions_skipped(self):
        """Test that empty base with extensions is skipped (no /.html)."""
        urls = generate_seed_urls(bases=[""], extensions=[".html", ".htm"])

        # Empty base + extensions would create invalid paths like "/.html", so skipped
        assert "/.html" not in urls
        assert "/.htm" not in urls

    def test_no_duplicates(self):
        """Test that duplicate URLs are removed."""
        urls = generate_seed_urls(
            bases=["index", "index"],
            extensions=[".html", ".html"],
        )

        # Count occurrences of /index.html
        count = sum(1 for u in urls if u == "/index.html")
        assert count == 1

    def test_default_constants(self):
        """Test that default constants are defined correctly."""
        assert "" in DEFAULT_SEED_BASES
        assert "index" in DEFAULT_SEED_BASES
        assert "status" in DEFAULT_SEED_BASES

        assert "" in DEFAULT_EXTENSIONS
        assert ".html" in DEFAULT_EXTENSIONS
        assert ".htm" in DEFAULT_EXTENSIONS
        assert ".asp" in DEFAULT_EXTENSIONS


class TestNormalizeUrl:
    """Tests for normalize_url function."""

    def test_removes_fragment(self):
        """Test that URL fragments are removed."""
        url = "http://192.168.100.1/status.html#section1"
        normalized = normalize_url(url)

        assert "#section1" not in normalized
        assert normalized == "http://192.168.100.1/status.html"

    def test_removes_trailing_slash(self):
        """Test that trailing slashes are removed."""
        url = "http://192.168.100.1/status/"
        normalized = normalize_url(url)

        assert normalized == "http://192.168.100.1/status"

    def test_preserves_root_slash(self):
        """Test that root path slash is preserved."""
        url = "http://192.168.100.1/"
        normalized = normalize_url(url)

        assert normalized == "http://192.168.100.1/"

    def test_preserves_query_string(self):
        """Test that query strings are preserved."""
        url = "http://192.168.100.1/status.html?page=1"
        normalized = normalize_url(url)

        assert "?page=1" in normalized

    def test_handles_complex_url(self):
        """Test normalization of complex URL."""
        url = "http://192.168.100.1/path/to/page.html?foo=bar#anchor"
        normalized = normalize_url(url)

        assert normalized == "http://192.168.100.1/path/to/page.html?foo=bar"


class TestExtractLinksFromHtml:
    """Tests for extract_links_from_html function."""

    def test_extracts_absolute_links(self):
        """Test extraction of absolute links."""
        html = """
        <html>
            <a href="http://192.168.100.1/status.html">Status</a>
            <a href="http://192.168.100.1/config.html">Config</a>
        </html>
        """
        links = extract_links_from_html(html, "http://192.168.100.1")

        assert "http://192.168.100.1/status.html" in links
        assert "http://192.168.100.1/config.html" in links

    def test_converts_relative_links(self):
        """Test that relative links are converted to absolute."""
        html = """
        <html>
            <a href="/status.html">Status</a>
            <a href="config.html">Config</a>
        </html>
        """
        links = extract_links_from_html(html, "http://192.168.100.1")

        assert "http://192.168.100.1/status.html" in links
        assert "http://192.168.100.1/config.html" in links

    def test_ignores_external_links(self):
        """Test that external domain links are ignored."""
        html = """
        <html>
            <a href="http://192.168.100.1/status.html">Internal</a>
            <a href="http://example.com/page.html">External</a>
        </html>
        """
        links = extract_links_from_html(html, "http://192.168.100.1")

        assert "http://192.168.100.1/status.html" in links
        assert "http://example.com/page.html" not in links

    def test_ignores_anchors(self):
        """Test that anchor-only links are ignored."""
        html = '<a href="#section1">Jump to section</a>'
        links = extract_links_from_html(html, "http://192.168.100.1")

        assert len(links) == 0

    def test_ignores_javascript_links(self):
        """Test that javascript: links are ignored."""
        html = '<a href="javascript:void(0)">Click</a>'
        links = extract_links_from_html(html, "http://192.168.100.1")

        assert len(links) == 0

    def test_ignores_mailto_links(self):
        """Test that mailto: links are ignored."""
        html = '<a href="mailto:admin@example.com">Email</a>'
        links = extract_links_from_html(html, "http://192.168.100.1")

        assert len(links) == 0

    def test_ignores_binary_files(self):
        """Test that binary file links are ignored."""
        html = """
        <html>
            <a href="/image.jpg">Image</a>
            <a href="/document.pdf">PDF</a>
            <a href="/archive.zip">ZIP</a>
            <a href="/status.html">Status</a>
        </html>
        """
        links = extract_links_from_html(html, "http://192.168.100.1")

        assert "http://192.168.100.1/status.html" in links
        assert not any("jpg" in link for link in links)
        assert not any("pdf" in link for link in links)
        assert not any("zip" in link for link in links)

    def test_handles_empty_html(self):
        """Test handling of empty HTML."""
        links = extract_links_from_html("", "http://192.168.100.1")

        assert len(links) == 0

    def test_handles_malformed_html(self):
        """Test handling of malformed HTML."""
        html = "<a href='/status.html'>Unclosed tag"
        links = extract_links_from_html(html, "http://192.168.100.1")

        # Should still extract the link
        assert "http://192.168.100.1/status.html" in links


class TestDiscoverLinksFromPages:
    """Tests for discover_links_from_pages function."""

    def test_discovers_from_multiple_pages(self):
        """Test link discovery from multiple pages."""
        pages = [
            {
                "url": "http://192.168.100.1/",
                "content": '<a href="/status.html">Status</a>',
            },
            {
                "url": "http://192.168.100.1/status.html",
                "content": '<a href="/config.html">Config</a>',
            },
        ]
        links = discover_links_from_pages(pages, "http://192.168.100.1")

        assert "http://192.168.100.1/status.html" in links
        assert "http://192.168.100.1/config.html" in links

    def test_deduplicates_links(self):
        """Test that duplicate links are deduplicated."""
        pages = [
            {
                "url": "http://192.168.100.1/",
                "content": '<a href="/status.html">Status</a>',
            },
            {
                "url": "http://192.168.100.1/other.html",
                "content": '<a href="/status.html">Status Again</a>',
            },
        ]
        links = discover_links_from_pages(pages, "http://192.168.100.1")

        # Count occurrences
        count = sum(1 for link in links if "status.html" in link)
        assert count == 1

    def test_handles_empty_content(self):
        """Test handling of pages with empty content."""
        pages: list[dict[str, str | None]] = [
            {"url": "http://192.168.100.1/", "content": ""},
            {"url": "http://192.168.100.1/status.html", "content": None},
        ]
        links = discover_links_from_pages(pages, "http://192.168.100.1")

        assert len(links) == 0


class TestGetNewLinksToCrawl:
    """Tests for get_new_links_to_crawl function."""

    def test_returns_uncaptured_links(self):
        """Test that only uncaptured links are returned."""
        discovered = {
            "http://192.168.100.1/page1.html",
            "http://192.168.100.1/page2.html",
            "http://192.168.100.1/page3.html",
        }
        already_captured = {"http://192.168.100.1/page1.html"}

        new_links = get_new_links_to_crawl(discovered, already_captured)

        assert "http://192.168.100.1/page1.html" not in new_links
        assert "http://192.168.100.1/page2.html" in new_links
        assert "http://192.168.100.1/page3.html" in new_links

    def test_respects_max_limit(self):
        """Test that max_new_links limit is respected."""
        discovered = {f"http://192.168.100.1/page{i}.html" for i in range(50)}
        already_captured: set[str] = set()

        new_links = get_new_links_to_crawl(discovered, already_captured, max_new_links=10)

        assert len(new_links) == 10

    def test_returns_empty_when_all_captured(self):
        """Test empty result when all links already captured."""
        discovered = {"http://192.168.100.1/page1.html"}
        already_captured = {"http://192.168.100.1/page1.html"}

        new_links = get_new_links_to_crawl(discovered, already_captured)

        assert len(new_links) == 0


class TestExtractAllResourcesFromHtml:
    """Tests for extract_all_resources_from_html function."""

    def test_extracts_javascript_files(self):
        """Test extraction of JavaScript file references."""
        html = """
        <html>
            <script src="/js/main.js"></script>
            <script src="scripts/util.js"></script>
        </html>
        """
        resources = extract_all_resources_from_html(html, "http://192.168.100.1")

        assert "http://192.168.100.1/js/main.js" in resources[RESOURCE_TYPE_JS]
        assert "http://192.168.100.1/scripts/util.js" in resources[RESOURCE_TYPE_JS]

    def test_extracts_css_files(self):
        """Test extraction of CSS file references."""
        html = """
        <html>
            <link rel="stylesheet" href="/css/style.css">
            <link href="theme.css" rel="stylesheet">
        </html>
        """
        resources = extract_all_resources_from_html(html, "http://192.168.100.1")

        assert "http://192.168.100.1/css/style.css" in resources[RESOURCE_TYPE_CSS]
        assert "http://192.168.100.1/theme.css" in resources[RESOURCE_TYPE_CSS]

    def test_extracts_html_links(self):
        """Test extraction of HTML page links."""
        html = """
        <html>
            <a href="/status.html">Status</a>
            <a href="config.htm">Config</a>
        </html>
        """
        resources = extract_all_resources_from_html(html, "http://192.168.100.1")

        assert "http://192.168.100.1/status.html" in resources[RESOURCE_TYPE_HTML]
        assert "http://192.168.100.1/config.htm" in resources[RESOURCE_TYPE_HTML]

    def test_extracts_jquery_load_fragments(self):
        """Test extraction of jQuery .load() fragment URLs."""
        html = """
        <html>
            <script>
                $('#header').load('header.htm');
                $(".content").load('/fragments/menu.html');
            </script>
        </html>
        """
        resources = extract_all_resources_from_html(html, "http://192.168.100.1")

        assert "http://192.168.100.1/header.htm" in resources[RESOURCE_TYPE_FRAGMENT]
        assert "http://192.168.100.1/fragments/menu.html" in resources[RESOURCE_TYPE_FRAGMENT]

    def test_returns_all_resource_types(self):
        """Test that all resource type keys are present."""
        html = "<html></html>"
        resources = extract_all_resources_from_html(html, "http://192.168.100.1")

        assert RESOURCE_TYPE_JS in resources
        assert RESOURCE_TYPE_CSS in resources
        assert RESOURCE_TYPE_HTML in resources
        assert RESOURCE_TYPE_FRAGMENT in resources

    def test_ignores_external_resources(self):
        """Test that external domain resources are ignored."""
        html = """
        <html>
            <script src="http://192.168.100.1/local.js"></script>
            <script src="http://cdn.example.com/external.js"></script>
        </html>
        """
        resources = extract_all_resources_from_html(html, "http://192.168.100.1")

        assert "http://192.168.100.1/local.js" in resources[RESOURCE_TYPE_JS]
        assert "http://cdn.example.com/external.js" not in resources[RESOURCE_TYPE_JS]

    def test_handles_inline_scripts(self):
        """Test that inline scripts without src are handled."""
        html = """
        <html>
            <script>console.log('inline');</script>
            <script src="/app.js"></script>
        </html>
        """
        resources = extract_all_resources_from_html(html, "http://192.168.100.1")

        # Should only have the external script
        assert "http://192.168.100.1/app.js" in resources[RESOURCE_TYPE_JS]
        assert len(resources[RESOURCE_TYPE_JS]) == 1

    def test_handles_css_link_without_rel(self):
        """Test CSS detection by file extension when rel is missing."""
        html = '<link href="/styles.css">'
        resources = extract_all_resources_from_html(html, "http://192.168.100.1")

        assert "http://192.168.100.1/styles.css" in resources[RESOURCE_TYPE_CSS]


class TestResourceTypeConstants:
    """Tests for resource type constants."""

    def test_constants_defined(self):
        """Test that resource type constants are properly defined."""
        assert RESOURCE_TYPE_HTML == "html"
        assert RESOURCE_TYPE_JS == "javascript"
        assert RESOURCE_TYPE_CSS == "stylesheet"
        assert RESOURCE_TYPE_FRAGMENT == "fragment"
