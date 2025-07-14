"""
This is the click-powered CLI.
"""

from __future__ import annotations

import functools
import os
import typing
from typing import Any, Callable

import click
import uproot

from ._version import version as __version__

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

VERSION = __version__

if typing.TYPE_CHECKING:
    DefaultGroup = click.Group
else:
    from click_default_group import DefaultGroup


@click.group(context_settings=CONTEXT_SETTINGS, cls=DefaultGroup, default="browse")
@click.version_option(version=VERSION)
def main() -> None:
    """
    Must provide a subcommand.
    """


@main.command()
@click.argument("filename")
def tree(filename: str) -> None:
    """
    Display a tree.
    """
    import uproot_browser.tree  # noqa: PLC0415

    uproot_browser.tree.print_tree(filename)


def intercept(func: Callable[..., Any], *names: str) -> Callable[..., Any]:
    """
    Intercept function arguments and remove them
    """

    @functools.wraps(func)
    def new_func(*args: Any, **kwargs: Any) -> Any:
        for name in names:
            kwargs.pop(name)
        return func(*args, **kwargs)

    return new_func


@main.command()
@click.argument("filename")
@click.option(
    "--iterm", is_flag=True, help="Display an iTerm plot (requires [iterm] extra)."
)
def plot(filename: str, iterm: bool) -> None:
    """
    Display a plot.
    """
    if iterm:
        os.environ.setdefault("MPLBACKEND", r"module://itermplot")

        import matplotlib.pyplot as plt  # noqa: PLC0415

        import uproot_browser.plot_mpl  # noqa: PLC0415
    else:
        import uproot_browser.plot  # noqa: PLC0415

    item = uproot.open(filename)

    if iterm:
        uproot_browser.plot_mpl.plot(item)
        if plt.get_backend() == r"module://itermplot":
            fm = plt.get_current_fig_manager()
            canvas = fm.canvas
            canvas.__class__.print_figure = intercept(
                canvas.__class__.print_figure, "facecolor", "edgecolor"
            )

        plt.show()
    else:
        uproot_browser.plot.clf()
        uproot_browser.plot.plot(item)
        uproot_browser.plot.show()


@main.command()
@click.argument("filename")
def browse(filename: str) -> None:
    """
    Display a TUI.
    """
    import uproot_browser.tui.browser  # noqa: PLC0415

    app = uproot_browser.tui.browser.Browser(
        path=filename,
    )

    app.run()


if __name__ == "__main__":
    main()
