import pathlib
import shlex
import subprocess
from collections.abc import Sequence

import crestic.config


class InvalidResticBinaryError(Exception):
    """The given Restic binary was invalid."""


class ResticCommand(list[str]):
    """Wrapper for a Restic command."""

    def __str__(self) -> str:
        return " ".join(self)


class Wrapper:
    """Utility class that wraps Restic commands and executes them."""

    config: crestic.config.Config
    repository: crestic.config.Repository

    def __init__(
        self,
        config: crestic.config.Config,
        repository: crestic.config.Repository,
        dry_run: bool = False,
    ):
        """Initialize a new Restic command wrapper.

        Args:
            config(crestic.config.Config): Crestic config object.
            repository(crestic.config.Repository): Repository to operate on.
            dry_run(bool): Whether this wrapper will do dry runs only. Default: False.
        """
        self.config = config
        self.repository = repository
        # Global command parameters
        self.dry_run = dry_run

    def restic_cmd(self, *args: str) -> ResticCommand:
        """Generate Restic command.

        *args(str): Arguments to pass to Restic.
        """
        restic = self.config.restic_bin
        command = ResticCommand()
        command.append(restic)
        if self.dry_run:
            command.append("--dry-run")
        command.extend(args)
        return command

    def exec(self, command: ResticCommand):
        env = self.config.env(self.repository)
        subprocess.run(command, env=env)

    def backup(
        self,
        host: str | None = None,
        parent: str | None = None,
        tag: Sequence[str] = (),
        one_file_system: bool = True,
    ):
        args = ["backup", "--verbose"]

        if one_file_system:
            args.append("--one-file-system")

        exclusions = self.repository.exclusions
        cmd_exclusions = [v for item in exclusions for v in ("--iexclude", item)]
        args.extend(cmd_exclusions)

        if host:
            args.extend(["--host", host])
        if parent:
            args.extend(["--parent", parent])
        for t in tag:
            args.extend(["--tag", t])

        args.extend(self.repository.paths)
        return self.restic_cmd(*args)

    def check(self):
        """Build a `restic check` command."""
        return self.restic_cmd("check")

    def diff(self, snapshots: tuple[str, str], metadata: bool = False):
        """Build a `restic diff` command."""
        args = ["diff", snapshots[0], snapshots[1]]

        if metadata:
            args.append("--metadata")

        return self.restic_cmd(*args)

    def forget(self, prune: bool = False):
        """Build a `restic forget` command."""
        args = ["forget", "--verbose"]
        policy = self.repository.retention

        if policy:
            args.extend(policy.as_args())

        if prune:
            args.append("--prune")

        return self.restic_cmd(*args)

    def snapshots(self):
        """Build a `restic snapshots` command."""
        return self.restic_cmd("snapshots")
