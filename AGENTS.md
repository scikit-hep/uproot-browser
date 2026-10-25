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

A backend-neutral node model sits between the file formats and everything that displays them:

- **`src/uproot_browser/nodes.py`** — the abstract node classes. `Node` (a backend object plus its `parent`/`key`, hence `path`, `name`, `meta()` for the tree label, `children`); `Folder` (`keys()`, `lookup(key)`, and `resolve(path)` for `/`- or `:`-separated selections, which gives a `FailedNode` for a key that fails to load); `Root` (a node that opened a file: `open_source(var)` for Dump & Quit, `lookup_source`, `close()`); `DataTree` (a columnar dataset with `num_entries`); `Plottable` (`to_histogram(bins)`, `dump_hist(width)`, `plottable`, `ndim`); `Histogram` (any object with `axes`/`to_hist()`); `Column` (an array leaf: `numeric`, `entry_count`, `typename`, `read()`, `read_source(var)`, with default histogramming and dump text); `Pair` (two `Column`s as a 2D plot). `data_tree()` finds the dataset a node belongs to (the `tree` name in expressions) and `data_tree_source` its dump line. This is the whole interface a backend implements.
- **`src/uproot_browser/backends/`** — the backends and their registry. A backend is a module with `matches(spec)` and `open_spec(spec, *, parent, key) -> Node`, importable without its optional dependencies (`open_spec` raises `ModuleNotFoundError`, and the registry adds the install hint from `Backend.extra`). `backends()` tries `BUILTIN` (the `directory` backend), then the `uproot_browser.backends` entry-point group, then `uproot` as the fallback; `open_path(spec)` opens a `path` or `path:key` spec with the first that matches, and `split_spec` splits the spec. `as_node(obj)` wraps a raw object (uproot types register with it) so the plotting functions accept nodes or raw objects. `uproot.py` holds every uproot-specific detail (`UprootFile`, `UprootDirectory`, `UprootTTree`, `UprootRNTuple`, `UprootBranch`, `UprootField`, `UprootHistogram`, and the `wrap` dispatch). `directory.py` is the directory-of-files browser: `LocalDirectory` lists what some backend claims, and each file is a `LazyRoot` that opens with its own backend on first use and forwards to the opened root. Supporting a new format means a new module like `uproot.py`, plus a `Backend` entry in `BUILTIN` (or an entry point from another package).
- **`src/uproot_browser/tree.py`** — builds a `rich.tree.Tree` from a node (`make_tree`, `print_tree`).
- **`src/uproot_browser/plot.py`** — backend-neutral plotting: `to_histogram`/`plot` draw a `Plottable` into a plotext figure, the mpl path reuses the same calls. The optional `expr` string is `eval`'d with the histogram bound to `h` and the raw dataset to `tree` (used by the TUI's plot-input box for slicing, e.g. `h[:]`). `dump_expr`/`dump_plotext`/`dump_mpl` give the matching standalone source.
- **`src/uproot_browser/plot_mpl.py`** — alternate matplotlib rendering path for `plot --image`, `plot --save`, and `browse --image` (requires the `[image]` extra). `src/uproot_browser/tui/image_plot.py` (`MPLPlot`, `RequestImage`) is the TUI side of this path.
- **`src/uproot_browser/plotext_compat.py`** — version adaptor: all plotext drawing goes through the `PlotextFigure` protocol, which mirrors the native plotext 6 figure API. On 6+, `make_figure` returns the native figure directly; on 5.2.8+ it returns an adaptor over the module-level API (no 2D heatmaps — raises a clear error). The `minimums` nox session exercises the 5.x path.

The CLI (`src/uproot_browser/__main__.py`) is the Click entry point (`uproot-browser` script). It uses `click-default-group` so a bare invocation defaults to `browse`. Heavy imports (matplotlib, the TUI) are deferred inside command bodies to keep startup fast. `--testdata` resolves a filename through `skhep_testdata.data_path`.

### TUI (`src/uproot_browser/tui/`)

Textual app, entry point `browser.py:Browser`. Layout is composed in `Browser.compose`: a tabbed left panel (Tree / Info), a main `ViewWidget`, and a `RightPanel` (`right_panel.py`) with axis ranges, image scale, and the theme selector. Styling lives in `browser.css`.

Communication is **message-driven** (`messages.py` defines `UprootSelected`, `EmptyMessage`, `ErrorMessage`, `RequestPlot`). Flow when a user picks a tree node:

1. `left_panel.py:UprootTree` (a `textual.widgets.Tree[Node]`) posts `UprootSelected` with the root node and the selected path.
2. `Browser.on_uproot_selected` creates a `Plotext` (`tui/plot.py`) and assigns it to `view_widget.item`.
3. `ViewWidget` (a `ContentSwitcher` in `viewer.py`) switches between the logo, an error traceback, or the plot window based on `item`'s type.
4. `Plotext.display` switches to the plot window and, after the refresh, posts `RequestPlot`; a resize does the same through `ViewWidget.on_resize` (debounced). `Browser.on_request_plot` measures `plot_widget.content_size`, stores it on the item, shows a placeholder and starts `render_plot`, which is a **threaded Textual worker** that builds the plotext canvas off the UI thread and updates the widget via `call_from_thread`. This threading matters — plot generation must not block the event loop. `MPLPlot` (image mode) follows the same flow with `RequestImage`.

Plotext theme dictionaries are registered through `add_theme` (`plotext_compat.py`), called at import time in `browser.py`, to match light/dark terminal backgrounds. `d` ("Dump & Quit") exits printing equivalent Python code to reproduce the current plot: `tui/plot.py:dump_header` opens the file(s) through the selected node's `Root` and binds `item` (or `x_item`/`y_item`), then the plot item appends the node's `dump_hist`, the expression, and the drawing code. Press `/` to open a fuzzy finder over tree nodes (`tui/jump.py`).

Tests use Textual's `run_test()` pilot harness (`pytest-asyncio` in auto mode). Note the double `await pilot.pause()` after actions that trigger the threaded plot worker — the second wait lets a posted `EmptyMessage`/`ErrorMessage` settle.

## Conventions

- New object or format support goes into a backend: subclass the node classes in `nodes.py` (mypy reports missing abstract members) and register the type in the backend's `wrap`/`as_node`, instead of adding `isinstance` chains to the core.
- The package is fully typed (`py.typed`, mypy strict). `_version.py` is generated by hatch-vcs from git tags — never edit it.
- Two files carry per-file ruff ignores in `pyproject.toml`: `__main__.py` and `tui/image_plot.py`, both `PLC0415` (deferred imports). Respect these rather than fighting them.
