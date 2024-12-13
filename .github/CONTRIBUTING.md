See the [Scikit-HEP Developer introduction][skhep-dev-intro] for a
detailed description of best practices for developing Scikit-HEP packages.

[skhep-dev-intro]: https://scikit-hep.org/developer/intro

# Quick development

The fastest way to start with development is to use nox. If you don't have nox,
you can use `pipx run nox` to run it without installing, or `pipx install nox`.
If you don't have pipx (pip for applications), then you can install with with
`pip install pipx` (the only case were installing an application with regular
pip is reasonable). If you use macOS, then pipx and nox are both in brew, use
`brew install pipx nox`.

To use, run `nox`. This will lint and test using every installed version of
Python on your system, skipping ones that are not installed. You can also run
specific jobs:

```console
$ nox -l # List all the defined sessions
$ nox -s lint  # Lint only
$ nox -s tests  # Run the tests
$ nox -s build  # Make an SDist and wheel
```

Nox handles everything for you, including setting up an temporary virtual
environment for each run.

# Setting up a development environment manually

You can set up a development environment by running:

```bash
python3 -m venv .venv
source ./.env/bin/activate
pip install -U pip dependency-groups
pip install -e. $(dependency-groups dev)
```

If you use `uv`, you can do:

```bash
uv sync
```

instead.

# Post setup

You should prepare pre-commit, which will help you by checking that commits
pass required checks:

```bash
pip install pre-commit # or brew install pre-commit on macOS
pre-commit install # Will install a pre-commit hook into the git repo
```

You can also/alternatively run `pre-commit run` (changes only) or `pre-commit
run --all-files` to check even without installing the hook.

# Testing

Use pytest to run the unit checks:

```bash
pytest
```

# Pre-commit

This project uses pre-commit for all style checking. While you can run it with
nox, this is such an important tool that it deserves to be installed on its
own. Install pre-commit and run:

```bash
pre-commit run -a
```

to check all files.
