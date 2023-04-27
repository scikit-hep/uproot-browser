from __future__ import annotations

import nox

nox.options.sessions = ["lint", "pylint", "tests"]


@nox.session
def lint(session: nox.Session) -> None:
    """
    Run the linter.
    """
    session.install("pre-commit")
    session.run("pre-commit", "run", "--all-files", *session.posargs)


@nox.session
def tests(session: nox.Session) -> None:
    """
    Run the unit and regular tests.
    """
    session.install(".[test]")
    session.run("pytest", *session.posargs)


@nox.session
def pylint(session: nox.Session) -> None:
    """
    Run pylint.
    """

    session.install("pylint", "matplotlib")
    session.install("-e", ".")
    session.run("pylint", "src", *session.posargs)


@nox.session
def build(session: nox.Session) -> None:
    """
    Build an SDist and wheel.
    """

    session.install("build")
    session.run("python", "-m", "build")


@nox.session
def make_logo(session: nox.Session) -> None:
    """
    Rerender the logo
    """

    session.install("pillow")
    session.run("python", "docs/make_logo.py")
