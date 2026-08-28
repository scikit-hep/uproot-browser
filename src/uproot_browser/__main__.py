"""
This is the click-powered CLI.
"""

from __future__ import annotations

import difflib
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import click
import uproot

from ._version import version as __version__

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

if TYPE_CHECKING:
    DefaultGroup = click.Group
else:
    from click_default_group import DefaultGroup


def get_testdata(filename: str | None, *, testdata: bool) -> str:
    if not testdata:
        if filename is None:
            msg = "Missing argument 'FILENAME'."
            raise click.UsageError(msg)
        name, _, _ = filename.partition(":")
        if (
            "://" not in filename
            and not Path(name).is_file()
            and not Path(filename).is_file()
        ):
            msg = f"File {name!r} does not exist."
            raise click.ClickException(msg)
        return filename

    try:
        from skhep_testdata import data_path, known_files
    except ModuleNotFoundError:
        msg = "Install scikit-hep-testdata to use --testdata"
        raise click.ClickException(msg) from None

    if filename is None:
        files = "\n  ".join(sorted(known_files))
        msg = f"Missing argument 'FILENAME'. Available testdata files:\n  {files}"
        raise click.ClickException(msg)

    name, _, sel = filename.partition(":")
    if name not in known_files:
        msg = f"{name!r} is not a known testdata file."
        matches = difflib.get_close_matches(name, known_files, n=3)
        if matches:
            msg += " Did you mean:\n  " + "\n  ".join(matches)
        raise click.ClickException(msg)
    data_name: str = data_path(name)
    return f"{data_name}:{sel}" if sel else data_name


@click.group(context_settings=CONTEXT_SETTINGS, cls=DefaultGroup, default="browse")
@click.version_option(version=__version__)
def main() -> None:
    """
    Must provide a subcommand.
    """


@main.command()
@click.argument("filename", required=False)
@click.option(
    "--testdata", is_flag=True, help="Interpret the filename as a testdata file"
)
def tree(filename: str | None, *, testdata: bool) -> None:
    """
    Display a tree.
    """
    import uproot_browser.tree

    uproot_browser.tree.print_tree(get_testdata(filename, testdata=testdata))


@main.command()
@click.argument("filename", required=False)
@click.option(
    "--image",
    is_flag=True,
    help="Plot with a real image (Sixel/TGP, works in iTerm2; requires [image] extra).",
)
@click.option(
    "--testdata", is_flag=True, help="Interpret the filename as a testdata file"
)
def plot(filename: str | None, *, image: bool, testdata: bool) -> None:
    """
    Display a plot.
    """
    if image:
        os.environ.setdefault("MPLBACKEND", "agg")
        try:
            # Importing textual_image queries the terminal for image support
            import textual_image.renderable
            from textual_image._terminal import get_cell_size
        except ModuleNotFoundError:
            msg = "Install the [image] extra to use --image"
            raise click.ClickException(msg) from None

        import rich.console

        import uproot_browser.plot_mpl

        item = uproot.open(get_testdata(filename, testdata=testdata))

        cell = get_cell_size()
        term = shutil.get_terminal_size()
        width = term.columns
        height = round(width * cell.width * 5 / 8 / cell.height)
        pil_image = uproot_browser.plot_mpl.make_image(
            item, size=(width * cell.width, height * cell.height)
        )
        console = rich.console.Console()
        console.print(textual_image.renderable.Image(pil_image, width, height))
    else:
        import plotext

        import uproot_browser.plot

        item = uproot.open(get_testdata(filename, testdata=testdata))

        fig = plotext.figure
        fig.clear()
        uproot_browser.plot.plot(item, fig=fig)
        fig.show()


@main.command()
@click.argument("filename", required=False)
@click.option(
    "--image",
    is_flag=True,
    help="Plot with real images (Sixel/TGP, works in iTerm2; requires [image] extra).",
)
@click.option(
    "--testdata", is_flag=True, help="Interpret the filename as a testdata file"
)
def browse(filename: str | None, *, image: bool, testdata: bool) -> None:
    """
    Display a TUI.
    """
    if image:
        try:
            # The terminal graphics query must run before the app starts
            import textual_image.widget  # noqa: F401  # pylint: disable=unused-import
        except ModuleNotFoundError:
            msg = "Install the [image] extra to use --image"
            raise click.ClickException(msg) from None

    import uproot_browser.tui.browser

    app = uproot_browser.tui.browser.Browser(
        path=get_testdata(filename, testdata=testdata), image=image
    )

    app.run()


if __name__ == "__main__":
    main()
