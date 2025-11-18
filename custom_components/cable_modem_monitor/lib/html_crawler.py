"""Reusable HTML link discovery and crawling utilities.

This module provides functions for discovering and crawling links from HTML pages,
useful for modem diagnostics capture and exploration.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


# Default seed patterns for modem page discovery
DEFAULT_SEED_BASES = ["", "index", "status", "connection"]
DEFAULT_EXTENSIONS = ["", ".html", ".htm", ".asp", ".php", ".jsp", ".cgi"]


def generate_seed_urls(
    bases: list[str] | None = None,
    extensions: list[str] | None = None,
) -> list[str]:
    """Generate seed URLs from base names and extensions.

    Combines base page names with file extensions to create a comprehensive
    list of URLs to try. Generic patterns, not manufacturer-specific.

    Args:
        bases: List of base page names (default: ["", "index", "status", "connection"])
        extensions: List of file extensions (default: ["", ".html", ".htm", ".asp", ...])

    Returns:
        List of URL paths (e.g., ["/", "/index.html", "/status.asp", ...])

    Example:
        >>> generate_seed_urls(["index", "status"], [".html", ".asp"])
        ["/index.html", "/index.asp", "/status.html", "/status.asp"]
    """
    if bases is None:
        bases = DEFAULT_SEED_BASES
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS

    urls = []

    for base in bases:
        for ext in extensions:
            # Root path - only add once without extension
            if base == "":
                if ext == "":
                    urls.append("/")
                # Skip empty base with extensions (would create "/.html")
                continue
            else:
                # Regular pages - combine base + extension
                urls.append(f"/{base}{ext}")

    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return unique_urls


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication.

    Removes fragments and normalizes trailing slashes.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL string
    """
    parsed = urlparse(url)
    # Remove fragment, normalize path (remove trailing slash unless it's root)
    path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
    # Reconstruct without fragment
    normalized = urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))
    return normalized


def extract_links_from_html(html: str, base_url: str) -> set[str]:
    """Extract all valid links from HTML content.

    Args:
        html: HTML content to parse
        base_url: Base URL for resolving relative links

    Returns:
        Set of absolute URLs found in the HTML
    """
    links = set()
    base_host = urlparse(base_url).netloc

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Find all <a> tags with href attributes
        for link_tag in soup.find_all("a", href=True):
            href = link_tag["href"]

            # Skip anchors, javascript, mailto, etc.
            if href.startswith(("#", "javascript:", "mailto:")):
                continue

            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)

            # Only include same-host links
            parsed = urlparse(absolute_url)
            if parsed.netloc != base_host:
                continue

            # Skip binary/non-useful file extensions
            # Note: .js and .css are NOT skipped - they may contain useful data or API info
            skip_extensions = [".jpg", ".png", ".gif", ".ico", ".pdf", ".zip", ".svg", ".woff", ".woff2", ".ttf"]
            if any(absolute_url.lower().endswith(ext) for ext in skip_extensions):
                continue

            links.add(absolute_url)

    except Exception as e:
        _LOGGER.debug("Error extracting links from HTML: %s", e)

    return links


def discover_links_from_pages(captured_pages: list[dict], base_url: str) -> set[str]:
    """Discover all links from a list of captured pages.

    Args:
        captured_pages: List of dicts with 'url' and 'html' keys
        base_url: Base URL for the site

    Returns:
        Set of discovered URLs (normalized, deduplicated)
    """
    all_links = set()

    for page in captured_pages:
        try:
            html = page.get("html", "")
            if html:
                links = extract_links_from_html(html, base_url)
                all_links.update(links)
        except Exception as e:
            _LOGGER.debug("Error discovering links from %s: %s", page.get("url", "unknown"), e)

    # Normalize all discovered links
    normalized_links = {normalize_url(url) for url in all_links}

    _LOGGER.debug("Discovered %d unique links from %d pages", len(normalized_links), len(captured_pages))

    return normalized_links


def get_new_links_to_crawl(
    discovered_links: set[str], already_captured_urls: set[str], max_new_links: int = 20
) -> list[str]:
    """Get list of new links to crawl that haven't been captured yet.

    Args:
        discovered_links: Set of discovered link URLs
        already_captured_urls: Set of URLs already captured (normalized)
        max_new_links: Maximum number of new links to return

    Returns:
        List of new URLs to crawl (up to max_new_links)
    """
    # Find links not yet captured
    new_links = discovered_links - already_captured_urls

    _LOGGER.debug("Found %d new links to crawl (already have %d pages)", len(new_links), len(already_captured_urls))

    # Return up to max_new_links
    return list(new_links)[:max_new_links]
