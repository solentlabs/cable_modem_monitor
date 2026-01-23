"""Utility functions for Cable Modem Monitor integration."""

from __future__ import annotations

from .connectivity import ConnectivityResult, check_connectivity

__all__ = ["check_connectivity", "ConnectivityResult"]
