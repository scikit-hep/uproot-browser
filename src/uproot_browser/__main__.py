"""
This is the click-powered CLI.
"""

from __future__ import annotations

import functools
import os
import typing
from typing import TYPE_CHECKING, Any

import click
import uproot

from ._version import version as __version__

if TYPE_CHECKING:
    from collections.abc import Callable

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

VERSION = __version__

if typing.TYPE_CHECKING:
    DefaultGroup = click.Group
else:
    from click_default_group import DefaultGroup


def get_testdata(filename: str, *, testdata: bool) -> str:
    if not testdata:
        return filename

    try:
        from skhep_testdata import data_path
    except ModuleNotFoundError:
        msg = "Install scikit-hep-testdata to use --testdata"
        raise click.ClickException(msg) from None

    name, _, sel = filename.partition(":")
    data_name: str = data_path(name)
    return f"{data_name}:{sel}" if sel else data_name


@click.group(context_settings=CONTEXT_SETTINGS, cls=DefaultGroup, default="browse")
@click.version_option(version=VERSION)
def main() -> None:
    """
    Must provide a subcommand.
    """


@main.command()
@click.argument("filename")
@click.option(
    "--testdata", is_flag=True, help="Interpret the filename as a testdata file"
)
def tree(filename: str, *, testdata: bool) -> None:
    """
    Display a tree.
    """
    import uproot_browser.tree

    uproot_browser.tree.print_tree(get_testdata(filename, testdata=testdata))


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
@click.option(
    "--testdata", is_flag=True, help="Interpret the filename as a testdata file"
)
def plot(filename: str, *, iterm: bool, testdata: bool) -> None:
    """
    Display a plot.
    """
    if iterm:
        os.environ.setdefault("MPLBACKEND", r"module://itermplot")

        import matplotlib.pyplot as plt

        import uproot_browser.plot_mpl
    else:
        import uproot_browser.plot

    item = uproot.open(get_testdata(filename, testdata=testdata))

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
@click.option(
    "--testdata", is_flag=True, help="Interpret the filename as a testdata file"
)
def browse(filename: str, *, testdata: bool) -> None:
    """
    Display a TUI.
    """
    import uproot_browser.tui.browser

    app = uproot_browser.tui.browser.Browser(
        path=get_testdata(filename, testdata=testdata)
    )

    app.run()


if __name__ == "__main__":
    main()
