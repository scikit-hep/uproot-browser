"""
This is the click-powered CLI.
"""

from __future__ import annotations

import click
import uproot


@click.group()
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
def plot(filename: str) -> None:
    """
    Display a plot.
    """
    import uproot_browser.dirs  # pylint: disable=import-outside-toplevel
    import uproot_browser.plot  # pylint: disable=import-outside-toplevel

    fname = uproot_browser.dirs.filename(filename)
    selections = uproot_browser.dirs.selections(filename)
    my_tree = uproot.open(fname)
    *_, item = uproot_browser.dirs.apply_selection(my_tree, selections)

    uproot_browser.plot.plot(item)


if __name__ == "__main__":
    main()
