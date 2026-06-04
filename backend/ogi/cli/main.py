"""OGI CLI — entry point.

Usage::

    ogi transform search <query>
    ogi transform install <slug>
    ogi transform list
    ogi transform update [slug]
    ogi transform remove <slug>
    ogi transform info <slug>
"""
from __future__ import annotations

import typer

from ogi.cli.commands.config import app as config_app
from ogi.cli.commands.transform import app as transform_app
from ogi.cli.commands.dev import app as dev_app

app = typer.Typer(
    name="ogi",
    help="OGI — OpenGraph Intel CLI",
    no_args_is_help=True,
)

app.add_typer(transform_app, name="transform")
app.add_typer(config_app, name="config")
app.add_typer(dev_app, name="dev")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
