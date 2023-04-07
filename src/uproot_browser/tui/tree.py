from __future__ import annotations

from pathlib import Path

import textual.widget
import textual.widgets
import rich.panel
import rich.text

from ..tree import UprootItem
import uproot

class TreeWidget(textual.widgets.DirectoryTree):
    ''' currently just extending DirectoryTree, showing current path'''

    pass