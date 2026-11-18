"""
This is uproot-browser. There is no user accessible API; only a terminal
interface is provided currently.
"""

from __future__ import annotations

__lazy_modules__ = {"uproot_browser._version"}

from uproot_browser._version import version as __version__

__all__ = ("__version__",)
