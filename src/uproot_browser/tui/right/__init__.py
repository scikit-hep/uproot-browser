"""Widgets docked on the right side of the browser."""

__lazy_modules__ = {f"{__spec__.parent}.axis", f"{__spec__.parent}.panel"}

from .axis import AxisLimits
from .panel import AxisControls

__all__ = ("AxisControls", "AxisLimits")
