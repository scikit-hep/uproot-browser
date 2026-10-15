from __future__ import annotations

import dataclasses

AxisRange = tuple[float | None, float | None]


@dataclasses.dataclass(frozen=True)
class AxisLimits:
    """Display limits for the X and Y axes; ``None`` means automatic."""

    x: AxisRange = (None, None)
    y: AxisRange = (None, None)


NO_LIMITS = AxisLimits()
