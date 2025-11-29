"""Reusable HTML link discovery and crawling utilities.

This module provides functions for discovering and crawling links from HTML pages,
useful for modem diagnostics capture and exploration.

Comprehensive Resource Discovery
================================
Modern cable modem UIs use JavaScript to dynamically load navigation menus and content.
Simple <a href> extraction misses most pages because:
- Navigation is built by JavaScript (e.g., main_arris.js defines menu structure)
- Content is loaded via jQuery .load() calls (e.g., pageheaderA.htm)
- API endpoints are defined in JS files

To capture everything, we need to:
1. Extract static resources: <script src>, <link href>, <a href>
2. Parse JavaScript files for URL patterns (linkUrl, .htm references)
3. Parse jQuery .load() calls in HTML
4. Recursively crawl discovered pages

This enables building a comprehensive fixture database from user-submitted captures.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


***REMOVED*** Resource types for categorization
RESOURCE_TYPE_HTML = "html"
RESOURCE_TYPE_JS = "javascript"
RESOURCE_TYPE_CSS = "stylesheet"
RESOURCE_TYPE_FRAGMENT = "fragment"
RESOURCE_TYPE_API = "api"


***REMOVED*** Default seed patterns for modem page discovery
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
            ***REMOVED*** Root path - only add once without extension
            if base == "":
                if ext == "":
                    urls.append("/")
                ***REMOVED*** Skip empty base with extensions (would create "/.html")
                continue
            else:
                ***REMOVED*** Regular pages - combine base + extension
                urls.append(f"/{base}{ext}")

    ***REMOVED*** Remove duplicates while preserving order
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
    ***REMOVED*** Remove fragment, normalize path (remove trailing slash unless it's root)
    path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
    ***REMOVED*** Reconstruct without fragment
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

        ***REMOVED*** Find all <a> tags with href attributes
        for link_tag in soup.find_all("a", href=True):
            href = link_tag["href"]

            ***REMOVED*** Ensure href is a string (BeautifulSoup can return list for multi-value attrs)
            if not isinstance(href, str):
                continue

            ***REMOVED*** Skip anchors, javascript, mailto, etc.
            if href.startswith(("***REMOVED***", "javascript:", "mailto:")):
                continue

            ***REMOVED*** Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)

            ***REMOVED*** Only include same-host links
            parsed = urlparse(absolute_url)
            if parsed.netloc != base_host:
                continue

            ***REMOVED*** Skip binary/non-useful file extensions
            ***REMOVED*** Note: .js and .css are NOT skipped - they may contain useful data or API info
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
        captured_pages: List of dicts with 'url' and 'content' keys
        base_url: Base URL for the site

    Returns:
        Set of discovered URLs (normalized, deduplicated)
    """
    all_links = set()

    for page in captured_pages:
        try:
            html = page.get("content", "")
            if html:
                links = extract_links_from_html(html, base_url)
                all_links.update(links)
        except Exception as e:
            _LOGGER.debug("Error discovering links from %s: %s", page.get("url", "unknown"), e)

    ***REMOVED*** Normalize all discovered links
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
    ***REMOVED*** Find links not yet captured
    new_links = discovered_links - already_captured_urls

    _LOGGER.debug("Found %d new links to crawl (already have %d pages)", len(new_links), len(already_captured_urls))

    ***REMOVED*** Return up to max_new_links
    return list(new_links)[:max_new_links]


def extract_all_resources_from_html(html: str, base_url: str) -> dict[str, set[str]]:  ***REMOVED*** noqa: C901
    """Extract ALL resources from HTML content for comprehensive capture.

    This goes beyond simple <a href> extraction to find:
    - JavaScript files (<script src>)
    - CSS files (<link href>)
    - jQuery .load() fragment URLs
    - Standard page links (<a href>)

    Args:
        html: HTML content to parse
        base_url: Base URL for resolving relative links

    Returns:
        Dict with keys for each resource type, values are sets of absolute URLs:
        {
            "javascript": {"http://192.168.100.1/main.js", ...},
            "stylesheet": {"http://192.168.100.1/styles.css", ...},
            "fragment": {"http://192.168.100.1/header.htm", ...},
            "html": {"http://192.168.100.1/status.html", ...},
        }
    """
    resources: dict[str, set[str]] = {
        RESOURCE_TYPE_JS: set(),
        RESOURCE_TYPE_CSS: set(),
        RESOURCE_TYPE_FRAGMENT: set(),
        RESOURCE_TYPE_HTML: set(),
    }

    base_host = urlparse(base_url).netloc

    def is_same_host(url: str) -> bool:
        """Check if URL is on the same host."""
        parsed = urlparse(url)
        return parsed.netloc == base_host or parsed.netloc == ""

    def make_absolute(url: str) -> str:
        """Convert relative URL to absolute."""
        return urljoin(base_url, url)

    try:
        soup = BeautifulSoup(html, "html.parser")

        ***REMOVED*** 1. Extract JavaScript files: <script src="...">
        for script in soup.find_all("script", src=True):
            src = script.get("src", "")
            if isinstance(src, str) and src:
                absolute = make_absolute(src)
                if is_same_host(absolute):
                    resources[RESOURCE_TYPE_JS].add(absolute)
                    _LOGGER.debug("Found JS: %s", absolute)

        ***REMOVED*** 2. Extract CSS files: <link rel="stylesheet" href="...">
        for link in soup.find_all("link", href=True):
            href = link.get("href", "")
            rel = link.get("rel", [])
            ***REMOVED*** Check if it's a stylesheet or ends with .css
            is_css = "stylesheet" in rel or (isinstance(href, str) and href.endswith(".css"))
            if isinstance(href, str) and href and is_css:
                absolute = make_absolute(href)
                if is_same_host(absolute):
                    resources[RESOURCE_TYPE_CSS].add(absolute)
                    _LOGGER.debug("Found CSS: %s", absolute)

        ***REMOVED*** 3. Extract jQuery .load() fragment URLs from inline scripts
        ***REMOVED*** Pattern: .load("something.htm") or .load('something.htm')
        load_pattern = r'\.load\s*\(\s*["\']([^"\']+)["\']'
        for match in re.finditer(load_pattern, html):
            fragment_url = match.group(1)
            if fragment_url and not fragment_url.startswith(("http://", "https://", "//")):
                absolute = make_absolute(fragment_url)
                if is_same_host(absolute):
                    resources[RESOURCE_TYPE_FRAGMENT].add(absolute)
                    _LOGGER.debug("Found jQuery .load() fragment: %s", absolute)

        ***REMOVED*** 4. Extract standard page links: <a href="...">
        for link_tag in soup.find_all("a", href=True):
            href = link_tag.get("href", "")
            if not isinstance(href, str):
                continue
            ***REMOVED*** Skip anchors, javascript, mailto
            if href.startswith(("***REMOVED***", "javascript:", "mailto:")):
                continue
            absolute = make_absolute(href)
            if not is_same_host(absolute):
                continue
            ***REMOVED*** Skip binary files
            skip_ext = [".jpg", ".png", ".gif", ".ico", ".pdf", ".zip", ".svg", ".woff", ".woff2", ".ttf"]
            if any(absolute.lower().endswith(ext) for ext in skip_ext):
                continue
            resources[RESOURCE_TYPE_HTML].add(absolute)

    except Exception as e:
        _LOGGER.debug("Error extracting resources from HTML: %s", e)

    total = sum(len(urls) for urls in resources.values())
    _LOGGER.debug(
        "Extracted %d total resources: %d JS, %d CSS, %d fragments, %d HTML pages",
        total,
        len(resources[RESOURCE_TYPE_JS]),
        len(resources[RESOURCE_TYPE_CSS]),
        len(resources[RESOURCE_TYPE_FRAGMENT]),
        len(resources[RESOURCE_TYPE_HTML]),
    )

    return resources


def extract_urls_from_javascript(js_content: str, base_url: str) -> set[str]:  ***REMOVED*** noqa: C901
    """Extract page URLs from JavaScript content.

    Parses JS files to find URL references that wouldn't be visible in HTML.
    This is critical for modems like ARRIS SB8200 where navigation menus
    are defined in JS (e.g., main_arris.js contains linkUrl definitions).

    Patterns detected:
    - linkUrl: 'page.html' (menu definitions)
    - href: 'page.html' (link references)
    - url: 'page.html' (AJAX calls)
    - Generic .htm/.html string references
    - window.location assignments

    Args:
        js_content: JavaScript file content
        base_url: Base URL for resolving relative paths

    Returns:
        Set of absolute URLs discovered in the JavaScript
    """
    urls = set()
    base_host = urlparse(base_url).netloc

    def make_absolute(path: str) -> str:
        """Convert path to absolute URL."""
        if path.startswith(("http://", "https://")):
            return path
        return urljoin(base_url, path)

    def is_valid_url(url: str) -> bool:
        """Check if URL is valid and on same host."""
        parsed = urlparse(url)
        ***REMOVED*** Same host or relative path
        return parsed.netloc == base_host or parsed.netloc == ""

    ***REMOVED*** Pattern 1: linkUrl: 'page.html' or linkUrl:'page.html' (menu configs)
    for match in re.finditer(r"linkUrl\s*:\s*['\"]([^'\"]+)['\"]", js_content):
        path = match.group(1)
        if path:
            absolute = make_absolute(path)
            if is_valid_url(absolute):
                urls.add(absolute)
                _LOGGER.debug("Found linkUrl in JS: %s", absolute)

    ***REMOVED*** Pattern 2: href: 'page.html' or href='page.html'
    for match in re.finditer(r"href\s*[=:]\s*['\"]([^'\"]+\.html?)['\"]", js_content, re.IGNORECASE):
        path = match.group(1)
        if path:
            absolute = make_absolute(path)
            if is_valid_url(absolute):
                urls.add(absolute)

    ***REMOVED*** Pattern 3: url: 'page.html' (AJAX/fetch calls)
    for match in re.finditer(r"url\s*:\s*['\"]([^'\"]+\.(?:html?|asp|php|cgi))['\"]", js_content, re.IGNORECASE):
        path = match.group(1)
        if path:
            absolute = make_absolute(path)
            if is_valid_url(absolute):
                urls.add(absolute)

    ***REMOVED*** Pattern 4: Generic .htm/.html string references (catches menu arrays etc.)
    for match in re.finditer(r"['\"]([a-zA-Z0-9_/-]+\.html?)['\"]", js_content, re.IGNORECASE):
        path = match.group(1)
        ***REMOVED*** Skip obvious non-URLs (like file.html.template)
        if path and not path.endswith(".html."):
            absolute = make_absolute(path)
            if is_valid_url(absolute):
                urls.add(absolute)

    ***REMOVED*** Pattern 5: window.location = 'page.html'
    for match in re.finditer(r"(?:window\.)?location\s*=\s*['\"]([^'\"]+)['\"]", js_content):
        path = match.group(1)
        if path and not path.startswith("javascript:"):
            absolute = make_absolute(path)
            if is_valid_url(absolute):
                urls.add(absolute)

    _LOGGER.debug("Extracted %d URLs from JavaScript", len(urls))
    return urls


def extract_api_endpoints_from_javascript(js_content: str, base_url: str) -> set[str]:
    """Extract potential API endpoints from JavaScript content.

    Looks for AJAX/fetch patterns that might indicate REST APIs or
    data endpoints that could provide modem information.

    Args:
        js_content: JavaScript file content
        base_url: Base URL for resolving relative paths

    Returns:
        Set of potential API endpoint URLs
    """
    endpoints = set()

    def make_absolute(path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return urljoin(base_url, path)

    ***REMOVED*** Pattern 1: $.ajax({ url: '...' })
    for match in re.finditer(r"\$\.ajax\s*\(\s*\{[^}]*url\s*:\s*['\"]([^'\"]+)['\"]", js_content, re.DOTALL):
        endpoints.add(make_absolute(match.group(1)))

    ***REMOVED*** Pattern 2: $.get('...') or $.post('...')
    for match in re.finditer(r"\$\.(?:get|post)\s*\(\s*['\"]([^'\"]+)['\"]", js_content):
        endpoints.add(make_absolute(match.group(1)))

    ***REMOVED*** Pattern 3: fetch('...')
    for match in re.finditer(r"fetch\s*\(\s*['\"]([^'\"]+)['\"]", js_content):
        endpoints.add(make_absolute(match.group(1)))

    ***REMOVED*** Pattern 4: XMLHttpRequest .open('GET', '...')
    for match in re.finditer(r"\.open\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]", js_content):
        endpoints.add(make_absolute(match.group(1)))

    ***REMOVED*** Pattern 5: Common API path patterns
    for match in re.finditer(r"['\"](/(?:api|cgi-bin|data|json|xml)[^'\"]*)['\"]", js_content, re.IGNORECASE):
        endpoints.add(make_absolute(match.group(1)))

    _LOGGER.debug("Found %d potential API endpoints in JavaScript", len(endpoints))
    return endpoints


def discover_all_resources(
    captured_pages: list[dict],
    base_url: str,
    include_js_content: bool = True,
) -> dict[str, set[str]]:
    """Comprehensive resource discovery from captured pages.

    Combines all extraction methods to build a complete picture of
    available resources on the modem. This is the main entry point
    for comprehensive capture.

    Args:
        captured_pages: List of dicts with 'url', 'content', and optionally 'content_type' keys
        base_url: Base URL for the modem
        include_js_content: If True, also parse captured JS files for URLs

    Returns:
        Dict with all discovered resources by type
    """
    all_resources: dict[str, set[str]] = {
        RESOURCE_TYPE_JS: set(),
        RESOURCE_TYPE_CSS: set(),
        RESOURCE_TYPE_FRAGMENT: set(),
        RESOURCE_TYPE_HTML: set(),
        RESOURCE_TYPE_API: set(),
    }

    for page in captured_pages:
        url = page.get("url", "")
        content = page.get("content", "")
        content_type = page.get("content_type", "").lower()

        if not content:
            continue

        ***REMOVED*** Determine if this is HTML or JS based on content-type or URL
        is_javascript = "javascript" in content_type or url.endswith(".js") or content_type == "application/javascript"

        if is_javascript and include_js_content:
            ***REMOVED*** Parse JavaScript for URLs and API endpoints
            js_urls = extract_urls_from_javascript(content, base_url)
            all_resources[RESOURCE_TYPE_HTML].update(js_urls)

            api_endpoints = extract_api_endpoints_from_javascript(content, base_url)
            all_resources[RESOURCE_TYPE_API].update(api_endpoints)
        else:
            ***REMOVED*** Parse HTML for all resource types
            html_resources = extract_all_resources_from_html(content, base_url)
            for resource_type, urls in html_resources.items():
                all_resources[resource_type].update(urls)

    ***REMOVED*** Log summary
    total = sum(len(urls) for urls in all_resources.values())
    _LOGGER.info(
        "Comprehensive discovery found %d resources: %d HTML, %d JS, %d CSS, %d fragments, %d API endpoints",
        total,
        len(all_resources[RESOURCE_TYPE_HTML]),
        len(all_resources[RESOURCE_TYPE_JS]),
        len(all_resources[RESOURCE_TYPE_CSS]),
        len(all_resources[RESOURCE_TYPE_FRAGMENT]),
        len(all_resources[RESOURCE_TYPE_API]),
    )

    return all_resources
