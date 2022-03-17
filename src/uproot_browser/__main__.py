"""
This is the click-powered CLI.
"""

from __future__ import annotations

import asyncio
import functools
import os
from pathlib import Path
from typing import Any, Callable

import click
import rich
import uproot

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
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
    import uproot_browser.tree  # pylint: disable=import-outside-toplevel

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

        import matplotlib.pyplot as plt  # pylint: disable=import-outside-toplevel

        import uproot_browser.plot_mpl  # pylint: disable=import-outside-toplevel
    else:
        import uproot_browser.plot  # pylint: disable=import-outside-toplevel

    import uproot_browser.dirs  # pylint: disable=import-outside-toplevel

    fname = uproot_browser.dirs.filename(filename)
    selections = uproot_browser.dirs.selections(filename)
    my_tree = uproot.open(fname)
    *_, item = uproot_browser.dirs.apply_selection(my_tree, selections)

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
    import uproot_browser.tui  # pylint: disable=import-outside-toplevel

    fname = uproot_browser.dirs.filename(filename)

    # Run the uproot-browser TUI
    async def amain() -> list[Any]:
        app = uproot_browser.tui.Browser(
            title="uproot-browser",
            log="textual.log",
            path=Path(fname),
        )
        await app.process_messages()
        return app.results

    results = asyncio.run(amain())

    for result in results:
        rich.print(result)


if __name__ == "__main__":
    main()
