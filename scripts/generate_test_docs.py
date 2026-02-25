#!/usr/bin/env python3
"""Generate test documentation from test files.

Data sources:
1. Test files - docstrings, class names, test function names
2. conftest.py - fixtures definitions
3. .github/codeql/ - CodeQL configuration for security docs

This separation allows:
- Single source of truth for test documentation
- Auto-regeneration on commit
- Consistent documentation across test categories

Usage:
    python scripts/generate_test_docs.py
    python scripts/generate_test_docs.py --print
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Any

# Add project root to path
script_dir = Path(__file__).parent
repo_root = script_dir.parent
sys.path.insert(0, str(repo_root))

# Test category configurations
TEST_CATEGORIES: dict[str, dict[str, Any]] = {
    "core": {
        "path": "tests/core",
        "title": "Core Module Tests",
        "description": (
            "Unit tests for core functionality including signal analysis, "
            "health monitoring, HNAP builders, authentication, and discovery helpers."
        ),
        "output": "tests/core/README.md",
    },
    "components": {
        "path": "tests/components",
        "title": "Component Tests",
        "description": (
            "Tests for Home Assistant components including config flow, "
            "coordinator, sensors, buttons, diagnostics, and the modem scraper."
        ),
        "output": "tests/components/README.md",
    },
    "integration": {
        "path": "tests/integration",
        "title": "Integration Tests",
        "description": (
            "End-to-end integration tests using mock HTTP/HTTPS servers with fixture data. "
            "Tests real SSL/TLS handling, authentication flows, and modem communication patterns."
        ),
        "output": "tests/integration/README.md",
    },
    "parsers": {
        "path": "tests/parsers",
        "title": "Parser Tests",
        "description": "Tests for modem-specific parsers, parser contracts, and fixture validation.",
        "output": None,  # Parsers have FIXTURES.md, skip README generation
    },
    "utils": {
        "path": "tests/utils",
        "title": "Utility Tests",
        "description": (
            "Tests for utility functions including HTML helpers, "
            "HAR sanitization, entity migration, and host validation."
        ),
        "output": "tests/utils/README.md",
    },
    "lib": {
        "path": "tests/lib",
        "title": "Library Tests",
        "description": "Tests for library modules including the HTML crawler and general utilities.",
        "output": "tests/lib/README.md",
    },
}


def extract_test_info(file_path: Path) -> dict:
    """Extract test information from a Python test file.

    Returns:
        Dict with keys: module_docstring, classes, functions, test_count
    """
    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return {"module_docstring": None, "classes": [], "functions": [], "test_count": 0}

    info: dict = {
        "module_docstring": ast.get_docstring(tree),
        "classes": [],
        "functions": [],
        "test_count": 0,
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name.startswith("Test"):
                methods: list[dict[str, Any]] = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                        methods.append(
                            {
                                "name": item.name,
                                "docstring": ast.get_docstring(item),
                            }
                        )
                        info["test_count"] += 1
                info["classes"].append(
                    {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "methods": methods,
                    }
                )

        elif (
            isinstance(node, ast.FunctionDef)
            and node.name.startswith("test_")
            and not any(
                isinstance(parent, ast.ClassDef)
                for parent in ast.walk(tree)
                if hasattr(parent, "body") and node in getattr(parent, "body", [])
            )
        ):
            # Top-level test function
            info["functions"].append(
                {
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                }
            )
            info["test_count"] += 1

    return info


def _get_decorator_name(decorator: ast.expr) -> str:
    """Extract the name from a decorator node."""
    if isinstance(decorator, ast.Name):
        return decorator.id
    if isinstance(decorator, ast.Attribute):
        return decorator.attr
    if isinstance(decorator, ast.Call):
        func = decorator.func
        if isinstance(func, ast.Attribute):
            return func.attr
        if isinstance(func, ast.Name):
            return func.id
    return ""


def _is_fixture(node: ast.FunctionDef) -> bool:
    """Check if a function has a @pytest.fixture decorator."""
    return any(_get_decorator_name(d) == "fixture" for d in node.decorator_list)


def extract_fixtures(conftest_path: Path) -> list[dict]:
    """Extract pytest fixtures from conftest.py."""
    if not conftest_path.exists():
        return []

    try:
        content = conftest_path.read_text()
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return []

    return [
        {"name": node.name, "docstring": ast.get_docstring(node)}
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and _is_fixture(node)
    ]


def _truncate(text: str, max_len: int = 60) -> str:
    """Truncate text to max length, adding ellipsis if needed."""
    if not text:
        return ""
    first_line = text.split("\n", maxsplit=1)[0].strip()
    if len(first_line) <= max_len:
        return first_line
    return first_line[: max_len - 3] + "..."


def _format_test_item(name: str, docstring: str | None) -> str:
    """Format a test function/method as a markdown bullet."""
    if docstring:
        return f"- `{name}`: {docstring.split(chr(10))[0].strip()}"
    return f"- `{name}`"


def _build_class_section(class_info: dict) -> list[str]:
    """Build markdown section for a test class."""
    lines = []
    class_name = class_info["name"]
    class_doc = class_info.get("docstring", "")
    methods = class_info.get("methods", [])

    lines.append(f"**{class_name}** ({len(methods)} tests)")
    if class_doc:
        lines.append(f": {class_doc.split(chr(10))[0]}")
    lines.append("")

    for method in methods:
        lines.append(_format_test_item(method["name"], method.get("docstring")))
    lines.append("")
    return lines


def _build_test_details(all_tests: list[dict]) -> list[str]:
    """Build the detailed test breakdown section."""
    lines = ["## Test Details", ""]

    for test_info in all_tests:
        lines.append(f"### {test_info['file_name']}")
        lines.append("")

        if test_info.get("module_docstring"):
            lines.append(test_info["module_docstring"])
            lines.append("")

        for class_info in test_info.get("classes", []):
            lines.extend(_build_class_section(class_info))

        if test_info.get("functions"):
            lines.append("**Standalone Tests:**")
            lines.append("")
            for func in test_info["functions"]:
                lines.append(_format_test_item(func["name"], func.get("docstring")))
            lines.append("")

    return lines


def _build_fixtures_section(fixtures: list[dict]) -> list[str]:
    """Build the fixtures table section."""
    if not fixtures:
        return []

    lines = [
        "## Fixtures",
        "",
        "| Fixture | Description |",
        "|---------|-------------|",
    ]
    for fixture in fixtures:
        doc = _truncate(fixture.get("docstring", "") or "")
        lines.append(f"| `{fixture['name']}` | {doc} |")
    lines.append("")
    return lines


def _collect_test_info(category_path: Path) -> tuple[list[dict], int]:
    """Collect test info from all test files in a category."""
    test_files = sorted(category_path.glob("test_*.py"))
    all_tests: list[dict] = []
    total_count = 0

    for test_file in test_files:
        info = extract_test_info(test_file)
        info["file_name"] = test_file.name
        info["relative_path"] = test_file.relative_to(repo_root)
        all_tests.append(info)
        total_count += info["test_count"]

    return all_tests, total_count


def _collect_fixtures(category_path: Path) -> list[dict]:
    """Collect fixtures from conftest.py files."""
    fixtures = extract_fixtures(category_path / "conftest.py")
    parent_conftest = category_path.parent / "conftest.py"
    if parent_conftest.exists():
        fixtures.extend(extract_fixtures(parent_conftest))
    return fixtures


def generate_category_docs(category: str, config: dict) -> str | None:
    """Generate documentation for a test category."""
    if config.get("output") is None:
        return None

    category_path = repo_root / config["path"]
    if not category_path.exists():
        return None

    all_tests, total_count = _collect_test_info(category_path)
    if not all_tests:
        return None

    fixtures = _collect_fixtures(category_path)

    # Build header
    lines = [
        f"# {config['title']}",
        "",
        "> Auto-generated from test files. Do not edit manually.",
        "",
        config["description"],
        "",
        f"**Total Tests:** {total_count}",
        "",
        "## Test Files",
        "",
        "| File | Tests | Description |",
        "|------|-------|-------------|",
    ]

    # Add summary table rows
    for test_info in all_tests:
        desc = _truncate(test_info.get("module_docstring", "") or "")
        lines.append(
            f"| [{test_info['file_name']}]({test_info['file_name']}) | " f"{test_info['test_count']} | {desc} |"
        )
    lines.append("")

    # Add sections
    lines.extend(_build_test_details(all_tests))
    lines.extend(_build_fixtures_section(fixtures))
    lines.extend(["---", "*Generated by `scripts/generate_test_docs.py`*"])

    return "\n".join(lines) + "\n"


def _find_rationale(comments: list[str]) -> str:
    """Find the rationale line in a list of comment lines."""
    for comment in comments:
        if comment.lower().startswith("rationale:"):
            return comment.split(":", 1)[-1].strip()
    return ""


def _should_reset_comments(line: str) -> bool:
    """Check if a line should reset the comment collection."""
    return bool(line) and not line.startswith("#") and "exclude:" not in line


def _extract_codeql_rationales(config_content: str) -> dict[str, str]:
    """Extract rationales from YAML comments in CodeQL config."""
    rationales: dict[str, str] = {}
    current_comments: list[str] = []

    for line in config_content.split("\n"):
        stripped = line.strip()

        if stripped.startswith("#"):
            comment_text = stripped.lstrip("#").strip()
            if comment_text and not comment_text.startswith("---"):
                current_comments.append(comment_text)
            continue

        if "id:" in stripped and "py/" in stripped and current_comments:
            rule_id = stripped.split("id:")[-1].strip()
            rationale = _find_rationale(current_comments)
            if rationale:
                rationales[rule_id] = rationale
            current_comments = []
        elif _should_reset_comments(stripped):
            current_comments = []

    return rationales


def generate_codeql_docs() -> str:
    """Generate CodeQL security documentation from .github/codeql/ files."""
    codeql_dir = repo_root / ".github" / "codeql"
    codeql_config = codeql_dir / "codeql-config.yml"

    lines = [
        "# CodeQL Security Tests",
        "",
        "> Auto-generated from `.github/codeql/` configuration. Do not edit manually.",
        "",
        "This document describes the CodeQL security scanning configuration for the Cable Modem Monitor project.",
        "",
    ]

    # Overview section
    lines.extend(
        [
            "## Overview",
            "",
            "CodeQL is GitHub's code analysis engine that finds security vulnerabilities automatically. "
            "It performs data flow analysis across the entire codebase to detect issues that simpler tools miss.",
            "",
            "### Scan Schedule",
            "",
            "- **On Push:** Every push to `main` branch",
            "- **On PR:** Every pull request to `main`",
            "- **Scheduled:** Weekly (Monday 9:00 AM UTC)",
            "",
        ]
    )

    # Extract exclusions from codeql-config.yml
    if codeql_config.exists():
        import yaml

        config_content = codeql_config.read_text()
        try:
            config = yaml.safe_load(config_content)
        except Exception:
            config = {}

        # Extract rationales from comments
        rationales = _extract_codeql_rationales(config_content)

        # Paths ignored
        paths_ignore = config.get("paths-ignore", [])
        if paths_ignore:
            lines.extend(
                [
                    "## Excluded Paths",
                    "",
                    "The following paths are excluded from CodeQL scanning:",
                    "",
                ]
            )
            for path in paths_ignore:
                lines.append(f"- `{path}`")
            lines.append("")

        # Query filters (exclusions)
        query_filters = config.get("query-filters", [])
        exclusions = [f for f in query_filters if "exclude" in f]
        if exclusions:
            lines.extend(
                [
                    "## Suppressed Rules",
                    "",
                    "The following CodeQL rules are suppressed due to intentional design decisions:",
                    "",
                ]
            )

            for exc in exclusions:
                exclude = exc.get("exclude", {})
                rule_id = exclude.get("id", "Unknown")
                rationale = rationales.get(rule_id, "See `.github/codeql/codeql-config.yml` for details")

                lines.append(f"### `{rule_id}`")
                lines.append("")
                lines.append(rationale)
                lines.append("")

    # How to use section
    lines.extend(
        [
            "## Viewing Results",
            "",
            "1. Go to the GitHub repository",
            "2. Click **Security** tab",
            "3. Click **Code scanning alerts**",
            "4. Filter by severity, category, or query",
            "",
            "## Suppressing False Positives",
            "",
            "**In code:**",
            "```python",
            "# Justification comment explaining why this is safe",
            "potentially_flagged_code()  # nosec B501",
            "```",
            "",
            "**In config file:**",
            "Edit `.github/codeql/codeql-config.yml` and add to `query-filters`.",
            "",
            "## Local Testing",
            "",
            "```bash",
            "# Quick syntax check",
            "bash scripts/dev/test-codeql.sh",
            "```",
            "",
            "## Related Documentation",
            "",
            "- [CodeQL Overview](.github/codeql/README.md)",
            "- [Query Documentation](.github/codeql/queries/README.md)",
            "- [GitHub CodeQL Docs](https://codeql.github.com/docs/)",
            "",
            "---",
            "*Generated by `scripts/generate_test_docs.py`*",
        ]
    )

    return "\n".join(lines) + "\n"


def _collect_category_stats() -> tuple[list[dict[str, Any]], int, int]:
    """Collect test statistics for all categories."""
    total_tests = 0
    total_files = 0
    category_stats: list[dict[str, Any]] = []

    for category, config in TEST_CATEGORIES.items():
        category_path = repo_root / config["path"]
        if not category_path.exists():
            continue

        test_files = list(category_path.glob("test_*.py"))
        if category == "parsers":
            test_files.extend(category_path.glob("*/test_*.py"))
            test_files.extend(category_path.glob("*/*/test_*.py"))

        test_count = sum(extract_test_info(f)["test_count"] for f in test_files)
        total_tests += test_count
        total_files += len(test_files)

        category_stats.append(
            {
                "category": category,
                "title": config["title"],
                "path": config["path"],
                "output": config.get("output"),
                "files": len(test_files),
                "tests": test_count,
                "description": config["description"],
            }
        )

    return category_stats, total_tests, total_files


def _format_category_link(stat: dict[str, Any]) -> str:
    """Format a category name as a markdown link."""
    title: str = stat["title"]
    if stat.get("output"):
        return f"[{title}]({stat['output']})"
    if stat["category"] == "parsers":
        return f"[{title}](tests/parsers/FIXTURES.md)"
    return title


def _build_category_table(category_stats: list[dict[str, Any]]) -> list[str]:
    """Build the category summary table."""
    lines = [
        "| Category | Tests | Files | Description |",
        "|----------|-------|-------|-------------|",
    ]
    for stat in category_stats:
        name = _format_category_link(stat)
        desc = _truncate(stat["description"], 50)
        lines.append(f"| {name} | {stat['tests']} | {stat['files']} | {desc} |")
    lines.append("")
    return lines


def _build_category_details(category_stats: list[dict[str, Any]]) -> list[str]:
    """Build the detailed category breakdown section."""
    lines = ["## Category Details", ""]
    for stat in category_stats:
        lines.extend(
            [
                f"### {stat['title']}",
                "",
                stat["description"],
                "",
                f"- **Path:** `{stat['path']}/`",
                f"- **Tests:** {stat['tests']}",
                f"- **Files:** {stat['files']}",
            ]
        )
        if stat.get("output"):
            lines.append(f"- **Documentation:** [{stat['output']}]({stat['output']})")
        lines.append("")
    return lines


def generate_main_index() -> str:
    """Generate the main test index (tests/TESTS.md)."""
    category_stats, total_tests, total_files = _collect_category_stats()

    lines = [
        "# Test Suite Documentation",
        "",
        "> Auto-generated test documentation. Do not edit manually.",
        "",
        "This document provides an overview of the Cable Modem Monitor test suite.",
        "",
        f"**Total Tests:** {total_tests} across {total_files} test files",
        "",
        "## Test Categories",
        "",
    ]

    lines.extend(_build_category_table(category_stats))

    # Static content sections
    lines.extend(
        [
            "## Running Tests",
            "",
            "### Quick Start",
            "",
            "```bash",
            "# Run all tests with setup",
            "./scripts/dev/run_tests_local.sh",
            "",
            "# Quick test during development",
            "./scripts/dev/quick_test.sh",
            "",
            "# Run specific category",
            "pytest tests/core/ -v",
            "pytest tests/components/ -v",
            "```",
            "",
            "### Test Commands",
            "",
            "```bash",
            "# Run with coverage",
            "pytest tests/ --cov=custom_components/cable_modem_monitor --cov-report=term",
            "",
            "# Run specific test file",
            "pytest tests/core/test_signal_analyzer.py -v",
            "",
            "# Run specific test",
            "pytest tests/core/test_signal_analyzer.py::TestSignalAnalyzerBasics::test_initialization -v",
            "```",
            "",
            "## Coverage",
            "",
            "| Metric | Target | Current |",
            "|--------|--------|---------|",
            "| Overall | 60%+ | ~70% |",
            "| Core modules | 80%+ | ✅ |",
            "| Parsers | 90%+ | ✅ |",
            "",
        ]
    )

    lines.extend(_build_category_details(category_stats))

    lines.extend(
        [
            "## Security Testing",
            "",
            "CodeQL security scanning runs on every push and PR. "
            "See [CodeQL Security Tests](docs/reference/CODEQL_SECURITY.md) for details.",
            "",
            "---",
            "*Generated by `scripts/generate_test_docs.py`*",
        ]
    )

    return "\n".join(lines) + "\n"


def _write_doc(content: str, output_path: Path, print_only: bool) -> bool:
    """Write documentation to file or print to stdout.

    Returns True if a file was written.
    """
    if print_only:
        print(content)
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    print(f"Written: {output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate test documentation")
    parser.add_argument(
        "--print",
        "-p",
        action="store_true",
        help="Print to stdout instead of writing files",
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=list(TEST_CATEGORIES.keys()) + ["codeql", "all"],
        default="all",
        help="Generate docs for specific category (default: all)",
    )
    args = parser.parse_args()

    files_written = 0
    target = args.category

    # CodeQL docs
    if target in ("all", "codeql"):
        print_only = args.print and target == "codeql"
        path = repo_root / "docs" / "reference" / "CODEQL_SECURITY.md"
        if _write_doc(generate_codeql_docs(), path, print_only):
            files_written += 1

    # Category docs
    for category, config in TEST_CATEGORIES.items():
        if target not in ("all", category) or config.get("output") is None:
            continue
        docs = generate_category_docs(category, config)
        if docs:
            print_only = args.print and target == category
            if _write_doc(docs, repo_root / config["output"], print_only):
                files_written += 1

    # Main index
    if target == "all":
        path = repo_root / "tests" / "TESTS.md"
        if _write_doc(generate_main_index(), path, args.print):
            files_written += 1

    if not args.print:
        print(f"\nGenerated {files_written} documentation files.")


if __name__ == "__main__":
    main()
