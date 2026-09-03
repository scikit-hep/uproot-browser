"""
This is the click-powered CLI.
"""

from __future__ import annotations

__lazy_modules__ = {"difflib", "pathlib", "shutil", "uproot"}

import difflib
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

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


def image_extra_required(flag: str) -> NoReturn:
    msg = f"Install the [image] extra to use {flag}"
    raise click.ClickException(msg) from None


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
    "--save",
    type=click.Path(dir_okay=False, writable=True),
    help="Save the plot to a file instead (any matplotlib format, "
    "transparent background where supported).",
)
@click.option(
    "--testdata", is_flag=True, help="Interpret the filename as a testdata file"
)
def plot(
    filename: str | None, *, image: bool, save: str | None, testdata: bool
) -> None:
    """
    Display a plot.
    """
    item = uproot.open(get_testdata(filename, testdata=testdata))

    if save:
        # Set before pyplot is imported: this path must not open a window
        os.environ.setdefault("MPLBACKEND", "agg")
        try:
            import matplotlib.pyplot as plt

            import uproot_browser.plot_mpl
        except ModuleNotFoundError:
            image_extra_required("--save")

        uproot_browser.plot_mpl.plot(item)
        plt.savefig(save, transparent=True)
    elif image:
        try:
            # Importing textual_image queries the terminal for image support
            import textual_image.renderable
            from textual_image.widget import get_cell_size
        except ModuleNotFoundError:
            image_extra_required("--image")

        import rich.console

        import uproot_browser.plot_mpl

        cell = get_cell_size()
        width = shutil.get_terminal_size().columns
        pixel_width = width * cell.width
        height = round(pixel_width * uproot_browser.plot_mpl.ASPECT_RATIO / cell.height)
        pil_image = uproot_browser.plot_mpl.make_image(
            item, size=(pixel_width, height * cell.height)
        )
        console = rich.console.Console()
        console.print(textual_image.renderable.Image(pil_image, width, height))
    else:
        import uproot_browser.plot
        import uproot_browser.plotext_compat

        fig = uproot_browser.plotext_compat.make_figure()
        fig.clear()
        uproot_browser.plot.plot(item, fig=fig)
        # Not fig.show(): the plotext 6 kernel prints via wcout, which silently
        # truncates at the first non-ASCII glyph in a "C" locale
        click.echo(str(fig.build()))


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
            image_extra_required("--image")

    import uproot_browser.tui.browser

    app = uproot_browser.tui.browser.Browser(
        path=get_testdata(filename, testdata=testdata), image=image
    )

    app.run()


if __name__ == "__main__":
    main()
