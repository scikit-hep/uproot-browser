from __future__ import annotations

import click
import uproot


@click.group()
def main() -> None:
    pass


@main.command()
@click.argument("filename")
def tree(filename: str) -> None:
    """
    Display a tree.
    """
    import uproot_browser.tree

    uproot_browser.tree.print_tree(filename)

@main.command()
@click.argument("filename")
def plot(filename: str) -> None:
    """
    Display a tree.
    """
    import uproot_browser.plot
    import uproot_browser.dirs
    
    fname = uproot_browser.dirs.filename(filename)
    selections = uproot_browser.dirs.selections(filename)
    tree = uproot.open(fname)
    *_, item = uproot_browser.dirs.apply_selection(tree, selections)

    uproot_browser.plot.plot(item)

if __name__ == "__main__":
    main()
