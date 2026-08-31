"""Shared domain library for the Council.

Nothing in this package may import from a service (`runtime/`, `pipeline/`,
`evaluation/`). The dependency arrow points one way: services import from here.
"""

__version__ = "0.1.0"
