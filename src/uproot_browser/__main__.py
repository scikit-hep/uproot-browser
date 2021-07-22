from __future__ import annotations

import click

import uproot_browser.tree


@click.group()
def main() -> None:
    pass


@main.command()
@click.argument("filename")
def tree(filename: str) -> None:
    """
    Display a tree.
    """
    uproot_browser.tree.print_tree(filename)


if __name__ == "__main__":
    main()
