import os.path

from crestic.config import Config, Entry, RepositoryType
from dataclasses import dataclass, field, InitVar
from enum import StrEnum
import re
import subprocess


class Operations(StrEnum):
    LIST = "list"
    BACKUP = "backup"
    INIT = "init"


@dataclass
class Crestic:
    operation: Operations = field(init=False)
    operation_str: InitVar[str]
    config_path: str
    args: dict[str, any] = None
    config: Config = field(init=False)
    entry: Entry | None = field(init=False)
    entry_str: InitVar[str | None] = None
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self, operation_str: str, entry_str: str):
        if operation_str is not None:
            self.operation = Operations(operation_str)

        if self.config_path is None:
            raise ValueError("Unable to find config file")
        self.config = Config(self.config_path)

        if entry_str is not None:
            self.entry = self.config.entries[entry_str]

    def print_entries(self):
        for entry in self.config.entries.keys():
            print(entry)
            if self.args.get("paths", False):
                for path in self.config.entries[entry].paths:
                    print("\t-", path)

    def validate_restic(self):
        if self.config.globals.restic_bin is None:
            return False

        restic = self.config.globals.restic_bin
        restic_version = subprocess.check_output([restic, "version"]).decode().replace("\n", "")
        restic_version_regex = r"restic [\d\.]+ compiled with"

        if not re.match(restic_version_regex, restic_version):
            print(f"Invalid restic binary detected at path [{restic}], version output was [{restic_version}]")
            return False

        print(f"Using [{restic_version}] located at [{restic}]")
        return True

    def set_env(self, key: str, value: str):
        self.env[key] = value

    def init_env(self):
        if not os.path.exists(self.config.globals.cache_dir):
            os.mkdir(self.config.globals.cache_dir, mode=0o750)
        if not os.path.exists(self.config.globals.tmp_dir):
            os.mkdir(self.config.globals.tmp_dir, mode=0o750)
        if not self.validate_restic():
            raise RuntimeError("Restic was not found in your PATH")

        self.set_env("RESTIC_CACHE_DIR", self.config.globals.cache_dir)
        self.set_env("TMPDIR", self.config.globals.tmp_dir)

        if self.entry.repo_type is RepositoryType.B2:
            if self.entry.b2 is not None:
                self.set_env("B2_ACCOUNT_ID", self.entry.b2.account_id)
                self.set_env("B2_ACCOUNT_KEY", self.entry.b2.account_key)
            elif self.config.globals.b2 is not None:
                self.set_env("B2_ACCOUNT_ID", self.config.globals.b2.account_id)
                self.set_env("B2_ACCOUNT_KEY", self.config.globals.b2.account_key)
            else:
                raise AttributeError(f"{self.entry.name} is a B2 repository, but the credentials have not been defined")

        self.set_env("RESTIC_REPOSITORY", self.entry.repository)
        self.set_env("RESTIC_PASSWORD", self.entry.password)

    def exec_restic_cmd(self, command: list[str]):
        self.init_env()
        restic = self.config.globals.restic_bin
        command = [str(part) for part in command]
        full_cmd = [restic] + command
        print(f"Executing [{' '.join(full_cmd)}]")
        subprocess.run(full_cmd, env=self.env)

    def backup_entry(self):
        exclusions = self.entry.exclusions
        cmd_exclusions = [v for elt in exclusions for v in ("--iexclude", elt)]

        command = ["backup", "--one-file-system", "--verbose"]
        command.extend(cmd_exclusions)
        command.extend(self.entry.paths)
        self.exec_restic_cmd(command)

    def initialize_entry(self):
        command = ["init", "--repository-version", self.entry.repository_version]
        self.exec_restic_cmd(command)

    def go(self):
        if self.operation == Operations.LIST:
            self.print_entries()
        elif self.operation == Operations.BACKUP:
            self.backup_entry()
        elif self.operation == Operations.INIT:
            self.initialize_entry()
