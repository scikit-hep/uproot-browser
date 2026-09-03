# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Overview

uproot-browser is a terminal tool to browse and inspect ROOT files (the file format used in high-energy physics). It exposes three subcommands — `tree`, `plot`, and `browse` (default) — built on the Scikit-HEP stack: uproot (file reading), awkward (arrays), hist (histogramming), plotext (text plots), Click (CLI), and Textual (TUI).

## Commands

```bash
uv sync                              # set up the dev environment
uv run pytest                        # run the test suite
uv run pytest tests/test_tui.py      # run one test file
uv run pytest -k test_browse_plot    # run a single test by name
prek -a --quiet                      # lint everything (ruff, mypy, etc. — preferred over pre-commit run -a)
uv run uproot-browser browse --testdata uproot-Event.root   # run the app against a testdata file
```

Nox sessions (`nox -s lint | tests | pylint | minimums | build`) run the same things in isolated environments; `minimums` tests against lowest-direct dependency versions. mypy runs in `strict` mode over `src`. Ruff uses `select = ["ALL"]` with a curated ignore list — expect strict linting.

## Architecture

There are two parallel rendering paths sharing the same data layer:

- **`src/uproot_browser/tree.py`** — builds a `rich.tree.Tree` from a ROOT file. `UprootEntry` (a dataclass wrapping a `path` + uproot object) lazily exposes `.children`, and `process_item` is a `functools.singledispatch` that maps each uproot type (TFile, TTree, RNTuple, TBranch, RField, histogram) to an icon + label. This dispatch table is the single source of truth for how object types are displayed; extend it to support a new type in the tree.
- **`src/uproot_browser/plot.py`** — `to_histogram` is another `singledispatch` that builds a `hist.Hist` from a plottable (TBranch, RField, TH1); `plot` draws it into a plotext figure, and the mpl path reuses the same dispatch. The optional `expr` string is `eval`'d with the histogram bound to `h` (used by the TUI's plot-input box for slicing, e.g. `h[:]`).
- **`src/uproot_browser/plot_mpl.py`** — alternate matplotlib rendering path for `plot --image`, `plot --save`, and `browse --image` (requires the `[image]` extra). `src/uproot_browser/tui/image_plot.py` (`MPLPlot`, `RequestImage`) is the TUI side of this path.
- **`src/uproot_browser/plotext_compat.py`** — version adaptor: all plotext drawing goes through the `PlotextFigure` protocol, which mirrors the native plotext 6 figure API. On 6+, `make_figure` returns the native figure directly; on 5.2.8+ it returns an adaptor over the module-level API (no 2D heatmaps — raises a clear error). The `minimums` nox session exercises the 5.x path.

The CLI (`src/uproot_browser/__main__.py`) is the Click entry point (`uproot-browser` script). It uses `click-default-group` so a bare invocation defaults to `browse`. Heavy imports (matplotlib, the TUI) are deferred inside command bodies to keep startup fast. `--testdata` resolves a filename through `skhep_testdata.data_path`.

### TUI (`src/uproot_browser/tui/`)

Textual app, entry point `browser.py:Browser`. Layout is composed in `Browser.compose`: a tabbed left panel (Tree / Tools / Info) plus a main `ViewWidget`. Styling lives in `browser.css`.

Communication is **message-driven** (`messages.py` defines `UprootSelected`, `EmptyMessage`, `ErrorMessage`, `RequestPlot`). Flow when a user picks a tree node:

1. `left_panel.py:UprootTree` posts `UprootSelected` on node selection.
2. `Browser.on_uproot_selected` creates a `Plotext` (`tui/plot.py`) and assigns it to `view_widget.item`.
3. `ViewWidget` (a `ContentSwitcher` in `viewer.py`) switches between the logo, an error traceback, or the plot window based on `item`'s type.
4. `Plotext.display` switches to the plot window and, after the refresh, posts `RequestPlot`; a resize does the same through `ViewWidget.on_resize` (debounced). `Browser.on_request_plot` measures `plot_widget.content_size`, stores it on the item, shows a placeholder and starts `render_plot`, which is a **threaded Textual worker** that builds the plotext canvas off the UI thread and updates the widget via `call_from_thread`. This threading matters — plot generation must not block the event loop. `MPLPlot` (image mode) follows the same flow with `RequestImage`.

Plotext theme dictionaries are registered through `add_theme` (`plotext_compat.py`), called at import time in `browser.py`, to match light/dark terminal backgrounds. `d` ("Dump & Quit") exits printing equivalent Python uproot code to reproduce the current plot. Press `/` to open a fuzzy finder over tree nodes (`tui/jump.py`).

Tests use Textual's `run_test()` pilot harness (`pytest-asyncio` in auto mode). Note the double `await pilot.pause()` after actions that trigger the threaded plot worker — the second wait lets a posted `EmptyMessage`/`ErrorMessage` settle.

## Conventions

- Type dispatch over `if isinstance` chains: new ROOT object support generally means registering a `process_item` (tree) and/or `to_histogram` (plotting) overload, not editing existing functions.
- The package is fully typed (`py.typed`, mypy strict). `_version.py` is generated by hatch-vcs from git tags — never edit it.
- Two files carry per-file ruff ignores in `pyproject.toml`: `__main__.py` and `tui/image_plot.py`, both `PLC0415` (deferred imports). Respect these rather than fighting them.
