from __future__ import annotations

__lazy_modules__ = {"contextlib", "rich.text", "uproot_browser.plotext_compat"}

import abc
import contextlib
import dataclasses
import sys
import threading
from typing import TYPE_CHECKING, Any, ClassVar, Self

import rich.text

import uproot_browser.plot
import uproot_browser.plotext_compat
from uproot_browser.axis import NO_LIMITS, AxisLimits
from uproot_browser.nodes import FILE_VAR, Pair

if TYPE_CHECKING:
    from uproot_browser.nodes import Node
    from uproot_browser.tui.viewer import ViewWidget


@dataclasses.dataclass(frozen=True)
class PlotItem(abc.ABC):
    """What a ViewWidget plots, in one rendering mode.

    An item compares by value, so an item equal to the last rendered one does
    not render again. The caches do not compare, and copies share them.
    A new rendering mode subclasses this, and adds a factory in ``Browser``
    and a window in ``ViewWidget``.
    """

    root: Node
    selection: str
    dark: bool
    y_selection: str = ""
    expr: str = ""
    size: tuple[int, int] | None = None
    axis_limits: AxisLimits = NO_LIMITS
    # a redraw reuses the expression result
    cache: uproot_browser.plot.ExprCache = dataclasses.field(
        default_factory=uproot_browser.plot.ExprCache, compare=False
    )

    window: ClassVar[str]
    """The id of the ViewWidget window that shows this item."""

    def display(self, view: ViewWidget) -> None:
        """Show the window of this item and ask for a render."""
        view.current = self.window
        # After the refresh, so the request measures the widget that is laid out
        view.call_after_refresh(view.request_render)

    def with_theme(self, *, dark: bool) -> Self:
        return dataclasses.replace(self, dark=dark)

    def with_expr(self, expr: str) -> Self:
        return dataclasses.replace(self, expr=expr)

    def with_axis_limits(self, limits: AxisLimits) -> Self:
        return dataclasses.replace(self, axis_limits=limits)

    def with_size(self, size: tuple[int, int]) -> Self:
        return self if size == self.size else dataclasses.replace(self, size=size)

    @abc.abstractmethod
    def with_view_size(self, view: ViewWidget) -> Self | None:
        """This item at the size the view gives it, or None to ask again later."""

    @abc.abstractmethod
    def render(self) -> Any:
        """Build the plot. This runs in a worker thread, and can raise."""

    @abc.abstractmethod
    def show(self, view: ViewWidget, result: Any) -> None:
        """Show the result of :meth:`render` in the view."""

    @abc.abstractmethod
    def show_expression_error(self, view: ViewWidget) -> None:
        """Show in the view that the expression of this item failed."""

    @abc.abstractmethod
    def dump_source(self, *, file_var: str = FILE_VAR) -> str:
        """Python source for Dump & Quit (appended after the ``item = ...`` lines)."""

    def dump_renderables(self) -> tuple[Any, ...]:
        """Renderables to print above the source on Dump & Quit."""
        return ()


def dump_header(root: Node, selection: str, y_selection: str = "") -> tuple[str, str]:
    """
    The lines of Dump & Quit that open the file(s) and bind ``item`` (or
    ``x_item`` and ``y_item``), and the variable the x file is bound to.
    """
    file_var = FILE_VAR
    try:
        if not selection:
            return root.root.open_source(file_var), file_var
        x = root.resolve(selection)
        if not y_selection:
            lines = [x.root.open_source(file_var), x.bind_source("item")]
            return "\n".join(lines), file_var
        y = root.resolve(y_selection)
        if x.root is y.root:
            lines = [
                x.root.open_source(file_var),
                x.bind_source("x_item"),
                y.bind_source("y_item"),
            ]
            return "\n".join(lines), file_var
    except LookupError:
        # Not opened from a file, or a path through a leaf (which produced the
        # traceback): name the selection from the paths alone
        return _path_header(root, file_var, selection, y_selection), file_var
    # Two files: open both (hoist_imports removes the repeated imports)
    lines = [
        x.root.open_source("x_file"),
        y.root.open_source("y_file"),
        x.bind_source("x_item", "x_file"),
        y.bind_source("y_item", "y_file"),
    ]
    return "\n".join(lines), "x_file"


def hoist_imports(source: str) -> str:
    """
    Move the top-level imports of ``source`` to the top, without duplicates,
    sorted like isort: standard library first, ``import`` before ``from``.
    """
    imports: set[str] = set()
    body: list[str] = []
    for line in source.splitlines():
        if line.startswith(("import ", "from ")):
            imports.add(line)
        elif line or (body and body[-1]):
            body.append(line)

    def key(line: str) -> tuple[bool, str]:
        return line.startswith("from "), line.split()[1].lower()

    sections = [
        sorted(
            (
                i
                for i in imports
                if (i.split()[1].split(".")[0] in sys.stdlib_module_names) is std
            ),
            key=key,
        )
        for std in (True, False)
    ]
    blocks = ["\n".join(s) for s in sections if s]
    return "\n\n".join([*blocks, "\n".join(body).strip("\n")])


def _path_header(root: Node, file_var: str, selection: str, y_selection: str) -> str:
    try:
        file, base = root.root, root.keys_below_root
    except LookupError:
        return ""
    binds = [("x_item", selection), ("y_item", y_selection)] if y_selection else []
    lines = [file.open_source(file_var)]
    for var, path in binds or [("item", selection)]:
        keys = [*base, *path.removeprefix("/").split("/")]
        lines.append(f"{var} = {file.lookup_source(file_var, keys)}")
    return "\n".join(lines)


def resolve_item(root: Node, selection: str, y_selection: str = "") -> Node:
    """The selected node, or a :class:`~uproot_browser.nodes.Pair` for 2D."""
    item = root.resolve(selection)
    if not y_selection:
        return item
    return Pair(item, root.resolve(y_selection))


# plotext draws on one global figure, and a cancelled thread worker keeps
# running, so draws must not overlap.
_PLOTEXT_LOCK = threading.Lock()


def render_canvas(
    item: Any,
    theme: str,
    *size: int,
    expr: str,
    limits: AxisLimits,
    cache: uproot_browser.plot.ExprCache | None = None,
) -> str:
    """Build the plotext canvas string for an item."""
    # Read the data before the lock, so a superseded render does not block
    node = uproot_browser.plot.plottable_node(item)
    histogram = node.to_histogram(bins=size[0] - 5)
    histogram = uproot_browser.plot.apply_expr(histogram, expr, item, cache=cache)
    with _PLOTEXT_LOCK:
        fig = uproot_browser.plotext_compat.make_figure()
        fig.clear()
        fig.theme(theme)
        fig.plot_size(*size)
        uproot_browser.plot.draw_hist(fig, item, histogram, limits=limits)
        return str(fig.build())


def make_dump(
    item: Any,
    *size: int,
    expr: str = "",
    limits: AxisLimits = NO_LIMITS,
    image: bool = False,
    file_var: str = FILE_VAR,
) -> str:
    """Standalone Python source rebuilding the plotted histogram as ``h`` and
    drawing it the way the TUI did. It never imports uproot_browser.
    """
    # plot_mpl builds with the to_histogram default bins
    width = 50 if image else (size[0] - 5 if size else 100)
    node = uproot_browser.plot.plottable_node(item)
    code = node.dump_hist(width=width)
    if expr:
        code += f"\n\n{uproot_browser.plot.dump_expr(node, expr, file_var=file_var)}"
    draw = uproot_browser.plot.dump_mpl if image else uproot_browser.plot.dump_plotext
    return f"{code}\n\n{draw(node, limits=limits)}"


@dataclasses.dataclass(frozen=True)
class Plotext(PlotItem):
    """A text plot drawn with plotext, sized in cells."""

    window: ClassVar[str] = "plot-window"

    @property
    def theme(self) -> str:
        return "uproot_dark" if self.dark else "uproot_light"

    def with_view_size(self, view: ViewWidget) -> Plotext | None:
        # The Static has a 1 cell padding, which content_size takes off already
        size = view.plot_widget.content_size
        if not size.width or not size.height:
            return None
        return self.with_size((size.width, size.height))

    def render(self) -> rich.text.Text:
        assert self.size
        return self._render(*self.size)

    def _render(self, *size: int) -> rich.text.Text:
        item = resolve_item(self.root, self.selection, self.y_selection)
        canvas = render_canvas(
            item,
            self.theme,
            *size,
            expr=self.expr,
            limits=self.axis_limits,
            cache=self.cache,
        )
        return rich.text.Text.from_ansi(canvas)

    def show(self, view: ViewWidget, result: Any) -> None:
        view.plot_widget.update(result)

    def show_expression_error(self, view: ViewWidget) -> None:
        view.plot_widget.update(
            "Expression could not be plotted. Edit the expression and try again."
        )

    def dump_source(self, *, file_var: str = FILE_VAR) -> str:
        selected = resolve_item(self.root, self.selection, self.y_selection)
        size = self.size or ()
        with contextlib.suppress(RuntimeError):
            return f"\n{make_dump(selected, *size, expr=self.expr, limits=self.axis_limits, file_var=file_var)}"
        return ""

    def dump_renderables(self) -> tuple[Any, ...]:
        # Render synchronously: the worker hands the finished canvas to the
        # widget, and the exit console has a different size than the widget.
        try:
            return (self._render(*(self.size or (100, 30))),)
        except Exception:  # noqa: BLE001
            # The render worker can still be in flight, so this item can be one
            # that fails. Quit with the source only instead of crashing.
            return ()
