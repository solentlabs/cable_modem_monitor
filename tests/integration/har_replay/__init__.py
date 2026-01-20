"""HAR Replay test infrastructure for auth strategy validation.

This module provides core tooling to:
1. Load and parse HAR (HTTP Archive) files from modems/<mfr>/<model>/har/
2. Extract HTTP request/response exchanges
3. Register them as mock responses for testing
4. Validate auth strategies against real modem captures

Modem-specific HAR tests live in modems/<mfr>/<model>/tests/test_har.py.
This module contains only the shared infrastructure.
"""
