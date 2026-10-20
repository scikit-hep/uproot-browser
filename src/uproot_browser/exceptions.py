"""Custom exceptions for uproot-browser"""

from __future__ import annotations


class EmptyTreeError(ValueError):
    pass


class ExpressionError(Exception):
    """A plot expression failed; the original exception is ``__cause__``."""
