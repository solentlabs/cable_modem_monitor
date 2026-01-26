"""Resource loaders for cable modem data fetching.

This package provides loaders that handle all HTTP/API calls for modems,
keeping parsers focused purely on data extraction. Each loader type
corresponds to a data paradigm declared in modem.yaml.

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    LOADER HIERARCHY                              │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  ResourceLoader (ABC)     ← Base class with fetch() interface   │
    │       │                                                          │
    │       ├── HTMLLoader      ← Traditional web pages (GET HTML)    │
    │       │                     Used by: Most traditional modems    │
    │       │                                                          │
    │       ├── HNAPLoader      ← HNAP/SOAP protocol (POST JSON/XML)  │
    │       │                     Used by: S33, MB8611                │
    │       │                                                          │
    │       └── RESTLoader      ← JSON REST API (GET/POST JSON)       │
    │                             Used by: Virgin SuperHub5           │
    │                                                                  │
    │  ResourceLoaderFactory    ← Creates loader based on modem.yaml  │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘

Loader Selection:
    The factory reads modem.yaml's 'paradigm' field:
    - paradigm: html → HTMLLoader
    - paradigm: hnap → HNAPLoader
    - paradigm: rest_api → RESTLoader

Module Organization:
    - base.py: ResourceLoader ABC with fetch() -> dict[str, Any]
    - factory.py: ResourceLoaderFactory.create() selects appropriate loader
    - html.py: HTMLLoader for traditional web scraping
    - hnap.py: HNAPLoader for HNAP/SOAP modems
    - rest.py: RESTLoader for REST API modems

Usage:
    from custom_components.cable_modem_monitor.core.loaders import (
        ResourceLoaderFactory,
    )

    # Create loader based on modem.yaml config
    loader = ResourceLoaderFactory.create(
        session=session,
        base_url=base_url,
        modem_config=config,
        hnap_builder=builder,      # For HNAP modems
        url_token_config=url_token,  # For URL token auth
    )

    # Fetch all resources declared in modem.yaml
    resources = loader.fetch()  # dict[str, BeautifulSoup | dict]

    # Pass to parser for data extraction
    data = parser.parse_resources(resources)
"""

from .base import ResourceLoader
from .factory import ResourceLoaderFactory
from .hnap import HNAPLoader
from .html import HTMLLoader
from .rest import RESTLoader

__all__ = [
    "HNAPLoader",
    "HTMLLoader",
    "ResourceLoaderFactory",
    "RESTLoader",
    "ResourceLoader",
]
