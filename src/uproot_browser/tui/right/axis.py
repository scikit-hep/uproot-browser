from __future__ import annotations

import dataclasses

AxisRange = tuple[float | None, float | None]


@dataclasses.dataclass(frozen=True)
class AxisLimits:
    """Typed display limits for the histogram's X and Y axes."""

    x: AxisRange = (None, None)
    y: AxisRange = (None, None)
