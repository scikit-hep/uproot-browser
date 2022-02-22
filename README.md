# uproot-browser

[![Actions Status][actions-badge]][actions-link]
[![Documentation Status][rtd-badge]][rtd-link]
[![Code style: black][black-badge]][black-link]

[![PyPI version][pypi-version]][pypi-link]
[![Conda-Forge][conda-badge]][conda-link]
[![PyPI platforms][pypi-platforms]][pypi-link]

[![GitHub Discussion][github-discussions-badge]][github-discussions-link]
[![Gitter][gitter-badge]][gitter-link]
[![Scikit-HEP][sk-badge]](https://scikit-hep.org/)

uproot-browser is a [plotext](https://github.com/piccolomo/plotext) based command line library. Its aim is to enable a user to browse and look inside a ROOT file, completely via the terminal. It takes its inspiration from the [ROOT object browser](https://root.cern/doc/master/classTRootBrowser.html).

## Installation

You can install this library from [PyPI](https://pypi.org/project/uproot-browser/) with `pip`:

```bash
python3 -m pip install uproot-browser
```

You can also use `pipx` to run the library without installing it:

```bash
pipx run uproot-browser
```

## Features

uproot-browser currently provides the following features:

- `plot` can be used to display a plot.
- `tree` can be used to display a tree.

## Usage

**`-h` or `--help` option:**

```bash
uproot-browser -h
```

The help page is also shown if no argument or command is passed.

```bash
Usage: uproot-browser [OPTIONS] COMMAND [ARGS]...

  Must provide a subcommand.

Options:
  -h, --help  Show this message and exit.

Commands:
  plot  Display a plot.
  tree  Display a tree.
```

## Example

This example uses data from the [scikit-hep-testdata](https://github.com/scikit-hep/scikit-hep-testdata). It is placed in the same directory as the uproot-browser repository.

**`plot` command:**

```bash
uproot-browser plot ../scikit-hep-testdata/src/skhep_testdata/data/uproot-Event.root:htime
```

**`tree` command:**

```bash
uproot-browser tree ../scikit-hep-testdata/src/skhep_testdata/data/uproot-Event.root
```

## Development

See [CONTRIBUTING.md](https://github.com/henryiii/uproot-browser/blob/main/.github/CONTRIBUTING.md) for details on how to set up a development environment.

[actions-badge]:            https://github.com/henryiii/uproot-browser/workflows/CI/badge.svg
[actions-link]:             https://github.com/henryiii/uproot-browser/actions
[black-badge]:              https://img.shields.io/badge/code%20style-black-000000.svg
[black-link]:               https://github.com/psf/black
[conda-badge]:              https://img.shields.io/conda/vn/conda-forge/uproot-browser
[conda-link]:               https://github.com/conda-forge/uproot-browser-feedstock
[github-discussions-badge]: https://img.shields.io/static/v1?label=Discussions&message=Ask&color=blue&logo=github
[github-discussions-link]:  https://github.com/henryiii/uproot-browser/discussions
[gitter-badge]:             https://badges.gitter.im/https://github.com/Scikit-HEP/uproot-browser/community.svg
[gitter-link]:              https://gitter.im/https://github.com/Scikit-HEP/uproot-browser/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge
[pypi-link]:                https://pypi.org/project/uproot-browser/
[pypi-platforms]:           https://img.shields.io/pypi/pyversions/uproot-browser
[pypi-version]:             https://badge.fury.io/py/uproot-browser.svg
[rtd-badge]:                https://readthedocs.org/projects/uproot-browser/badge/?version=latest
[rtd-link]:                 https://uproot-browser.readthedocs.io/en/latest/?badge=latest
[sk-badge]:                 https://scikit-hep.org/assets/images/Scikit--HEP-Project-blue.svg
