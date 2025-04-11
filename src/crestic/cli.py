# ruff: noqa D100

import enum
import os
import pathlib
import sys
from typing import Annotated

import rich
import rich.table
from typer import Argument, Context, Option, Typer

import crestic.config
import crestic.wrapper

app = Typer(no_args_is_help=True)


@app.callback()
def main(
    ctx: Context,
    config: Annotated[
        pathlib.Path,
        Option(help="Config file to use."),
    ] = crestic.config.find_config(),
    print_command: Annotated[bool, Option(help="Print the command that would run.")] = False,
):
    if config is None:
        rich.print("[bold yellow]WARNING:[/bold yellow] Config file not found!")
        config_obj = crestic.config.Config.create()
        rich.print(f"Wrote template config file to {config_obj.path}")
    else:
        config_obj = crestic.config.Config(config)

    ctx.obj = {"config": config_obj, "print_command": print_command}


@app.command(name="list")
def list_cmd(
    ctx: Context,
    detailed: Annotated[bool, Option(help="Show details for each repository.")] = False,
    passwords: Annotated[bool, Option(help="Show passwords in detailed output.")] = False,
):
    """List configured tasks."""
    config: crestic.config.Config = ctx.obj["config"]
    if detailed:
        fields = ["Name", "Location", "Paths"]
        if passwords:
            fields.append("Password")
        table = rich.table.Table(*fields)
        for repo in config.repos.values():
            row = [repo.name, repo.location, "\n".join(repo.paths)]
            if passwords:
                row.append(repo.password)
            table.add_row(*row)
        rich.print(table)
    else:
        for repo in config.repos:
            rich.print(repo)


@app.command(name="env")
def env_cmd(
    ctx: Context,
    repository: Annotated[str, Argument(help="Repository to use.")],
):
    """Generate environment variables for the given repository.

    Make sure you run this like `eval "$(crestic env [REPOSITORY])"`
    """
    config: crestic.config.Config = ctx.obj["config"]
    repo = config.repos[repository]
    environment = config.env(repo)
    env_vars = []
    for k, v in environment.items():
        if v:
            env_vars.append(f'export {k}="{v}"')
    sys.stdout.write("; ".join(env_vars))


@app.command(name="backup")
def backup_cmd(
    ctx: Context,
    repository: Annotated[str, Argument(help="Repository to backup.")],
    host: Annotated[str, Option(help="Hostname for the new snapshot.")] = None,
    parent: Annotated[str, Option(help="Parent for the new snapshot.")] = None,
    tag: Annotated[
        list[str],
        Option(help="Tag for the new snapshot. Can be specified multiple times."),
    ] = (),
    one_file_system: Annotated[
        bool, Option(help="Don't cross filesystem boundaries and subvolumes.")
    ] = True,
):
    """Create a new snapshot of files and/or directories for the specified repository."""
    config: crestic.config.Config = ctx.obj["config"]
    repo = config.repos[repository]
    wrapper = crestic.wrapper.Wrapper(config, repo)
    command = wrapper.backup(host, parent, tag, one_file_system)
    if ctx.obj["print_command"]:
        rich.print(str(command))
    else:
        wrapper.exec(command)


@app.command(name="check")
def check_cmd(
    ctx: Context,
    repository: Annotated[str, Argument(help="Repository to check.")],
):
    """Check the specified repository for errors."""
    config: crestic.config.Config = ctx.obj["config"]
    repo = config.repos[repository]
    wrapper = crestic.wrapper.Wrapper(config, repo)
    command = wrapper.check()
    if ctx.obj["print_command"]:
        rich.print(str(command))
    else:
        wrapper.exec(command)


@app.command(name="diff")
def diff_cmd(
    repository: Annotated[str, Argument(help="Repository to diff.")],
    snapshots: Annotated[
        tuple[str, str],
        Argument(metavar="SNAPSHOT_A SNAPSHOT_B", help="Snapshot IDs to diff."),
    ],
    metadata: Annotated[bool, Option(help="Print changes in metadata.")] = False,
):
    """Show differences from the first to second snapshot in the specified repository."""


class DumpArchiveFormat(enum.StrEnum):
    tar = "tar"
    zip = "zip"


@app.command(name="dump")
def dump_cmd(
    repository: Annotated[str, Argument(help="Repository to dump files from.")],
    snapshot: Annotated[str, Argument(help="Snapshot ID to dump from.")],
    file: Annotated[str, Argument(help="File or folder in snapshot to dump.")],
    archive: Annotated[
        DumpArchiveFormat,
        Option(help="Set archive format for folder dump."),
    ] = DumpArchiveFormat.tar,
    host: Annotated[
        list[str],
        Option(
            help='Only consider snapshots for this host when snapshot ID "latest" is given '
            "(can be specified multiple times).",
        ),
    ] = (),
    path: Annotated[
        list[str],
        Option(
            help="Only consider snapshots including this (absolute) path when snapshot ID "
            '"latest" is given (can be specified multiple times).',
        ),
    ] = (),
    tag: Annotated[
        list[str],
        Option(
            help='Only consider snapshots including this tag when snapshot ID "latest" is '
            "given (can be specified multiple times).",
        ),
    ] = (),
    target: Annotated[pathlib.Path, Option(help="Write the output to target path.")] = None,
):
    """Extract files or folders from a snapshot in the specified repository."""
    rich.print("[bold red]Not implemented yet[/bold red]")


@app.command(name="forget")
def forget_cmd(
    ctx: Context,
    repository: Annotated[str, Argument(help="Repository to forget snapshots from.")],
    prune: Annotated[
        bool,
        Option(help="Automatically run the 'prune' command if snapshots have been removed."),
    ],
):
    config: crestic.config.Config = ctx.obj["config"]
    repo = config.repos[repository]
    wrapper = crestic.wrapper.Wrapper(config, repo)
    command = wrapper.forget(prune)
    if ctx.obj["print_command"]:
        rich.print(str(command))
    else:
        wrapper.exec(command)


@app.command(name="snapshots")
def snapshots_cmd(
    ctx: Context,
    repository: Annotated[str, Argument(help="Repository to list snapshots for.")],
    compact: Annotated[bool, Option(help="Use compact output format.")] = False,
    group_by: Annotated[
        str, Option(help="Group snapshots by host, paths and/or tags, separated by comma.")
    ] = None,
    host: Annotated[
        list[str],
        Option(
            help="Only consider snapshots for this host (can be specified multiple times)."
        ),
    ] = (),
    latest: Annotated[
        int, Option(help="Only shot the last n snapshots for each host and path.")
    ] = None,
    path: Annotated[
        list[str],
        Option(
            help="Only consider snapshots including this (absolute) path (can be specified "
            "multiple times, snapshots must include all specified paths."
        ),
    ] = (),
    tag: Annotated[
        list[str],
        Option(
            help="Only consider snapshots including this tag (can be specified multiple "
            "times)."
        ),
    ] = (),
):
    """List all the snapshots stored in the specified repository."""
    config: crestic.config.Config = ctx.obj["config"]
    repo = config.repos[repository]
    wrapper = crestic.wrapper.Wrapper(config, repo)
    command = wrapper.snapshots()
    if ctx.obj["print_command"]:
        rich.print(str(command))
    else:
        wrapper.exec(command)


if __name__ == "__main__":
    app()
