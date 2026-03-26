"""Protocol-level primitives shared across layers.

Transport protocols (HNAP, HTTP) have signing, framing, and constant
definitions that are used by auth, loaders, and action executors.
This package provides shared implementations to avoid duplication.
"""
