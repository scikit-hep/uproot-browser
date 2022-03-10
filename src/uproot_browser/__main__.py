"""
This is the click-powered CLI.
"""

from __future__ import annotations

import os
from pathlib import Path

import click
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
    uproot_browser.tui.Browser.run(
        title="uproot-browser",
        log="textual.log",
        path=Path(fname),
    )


if __name__ == "__main__":
    main()
