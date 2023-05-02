from __future__ import annotations

import sys

if sys.version_info < (3, 8):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict


__all__ = ["TypedDict"]
