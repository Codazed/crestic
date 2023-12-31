import configparser
from crestic.config import Config, Entry, RepositoryType
from crestic.utils import is_root, assert_systemd_available
from dataclasses import dataclass, field, InitVar
from enum import StrEnum
import os.path
from pathlib import Path
import re
import shutil
import subprocess
import sys

systemd_unit_prefix = "crestic--"


def get_units_location():
    if os.geteuid() == 0:
        # If user is root, install units in system location
        return Path("/etc/systemd/system")
    else:
        # If user is not root, install as a user unit
        return Path(f"{os.environ.get('HOME')}/.config/systemd/user")


def entry_systemd_filenames(entry: Entry | str):
    if type(entry) is Entry:
        name = entry.name
    else:
        name = entry
    return f"{systemd_unit_prefix}{name}.service", f"{systemd_unit_prefix}{name}.timer"


def reload_systemd():
    command = ["systemctl"]
    if not is_root():
        command.append("--user")
    command.append("daemon-reload")
    subprocess.run(command)


def entry_already_installed(entry: Entry | str):
    location = get_units_location()
    return False not in [os.path.exists(location / filename) for filename in entry_systemd_filenames(entry)]


def get_installed_entries():
    units_location = get_units_location()
    found_entries = set(
        [
            f.replace(systemd_unit_prefix, "").replace(".service", "").replace(".timer", "")
            for f in os.listdir(units_location)
            if f.startswith(systemd_unit_prefix)
        ]
    )
    return [entry for entry in found_entries if entry_already_installed(entry)]


def assert_entry_installed(entry: Entry | str):
    if not entry_already_installed(entry):
        if type(entry) is Entry:
            entry_name = entry.name
        else:
            entry_name = entry
        sys.exit(f"Entry {entry_name} is not installed")


def service_status(entry: Entry | str):
    assert_systemd_available()
    assert_entry_installed(entry)

    service_name, _ = entry_systemd_filenames(entry)
    command = ["systemctl", "status", service_name]
    if not is_root():
        command.append("--user")
    subprocess.run(command)


def timer_status(entry: Entry | str):
    assert_systemd_available()
    assert_entry_installed(entry)

    _, timer_name = entry_systemd_filenames(entry)
    command = ["systemctl", "status", timer_name]
    if not is_root():
        command.append("--user")
    subprocess.run(command)


class Operations(StrEnum):
    LIST = "list"
    INSTALL = "install"
    UNINSTALL = "uninstall"
    STATUS = "status"
    TIMER_CTRL = "set-timer"
    BACKUP = "backup"
    CHECK = "check"
    FORGET = "forget"
    INIT = "init"
    PRUNE = "prune"
    SNAPSHOTS = "snapshots"
    UNLOCK = "unlock"


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

    def check_entry(self):
        self.exec_restic_cmd(["check"])

    def forget_entry(self):
        command = ["forget"]

        policy = self.entry.retention

        if policy is not None:
            command.extend(str(policy).split(" "))

        if self.args.get("prune", False):
            command.append("--prune")
        self.exec_restic_cmd(command)

    def prune_entry(self):
        self.exec_restic_cmd(["prune"])

    def list_entry_snapshots(self):
        self.exec_restic_cmd(["snapshots"])

    def unlock_entry(self):
        self.exec_restic_cmd(["unlock"])

    @property
    def entry_systemd_filenames(self):
        return entry_systemd_filenames(self.entry)

    @property
    def entry_already_installed(self):
        return entry_already_installed(self.entry)

    def assert_entry_installed(self):
        return assert_entry_installed(self.entry)

    def install_entry(self):
        assert_systemd_available()

        if self.entry_already_installed:
            sys.exit(f"Entry {self.entry.name} is already installed")

        if self.entry.schedule is None:
            sys.exit(f"No schedule has been defined for entry {self.entry.name}")

        # Systemd units are basically super-simple ini files
        service_name, timer_name = self.entry_systemd_filenames
        service_config = configparser.ConfigParser()
        service_config.optionxform = str
        service_config["Unit"] = {
            "Description": f"Crestic operations for entry {self.entry.name}",
        }
        service_config["Service"] = {
            "ExecStart": f"{shutil.which('crestic')} -c {os.path.realpath(self.config_path)} backup {self.entry.name}",
        }
        service_config["Install"] = {"WantedBy": "default.target"}

        timer_config = configparser.ConfigParser()
        timer_config.optionxform = str
        timer_config["Unit"] = {
            "Description": f"Crestic timer for entry {self.entry.name}",
        }
        timer_config["Timer"] = {
            "OnCalendar": self.entry.schedule,
            "Unit": service_name,
        }
        timer_config["Install"] = {"WantedBy": "timers.target"}

        units_location = get_units_location()

        with open(units_location / service_name, "w") as f:
            service_config.write(f)
            print("Created unit", units_location / service_name)
        with open(units_location / timer_name, "w") as f:
            timer_config.write(f)
            print("Created unit", units_location / timer_name)

        print("Enabling timer")
        command = ["systemctl"]
        if not is_root():
            command.append("--user")
        command.extend(["enable", "--now", timer_name])
        subprocess.run(command)
        reload_systemd()

    def uninstall_entry(self):
        assert_systemd_available()
        self.assert_entry_installed()

        units_location = get_units_location()
        for filename in self.entry_systemd_filenames:
            os.remove(units_location / filename)

        reload_systemd()

    def timer_status(self):
        return timer_status(self.entry)

    def service_status(self):
        return service_status(self.entry)

    def unit_status(self):
        if self.args["entry"]:
            queries = [self.args["entry"]]
        else:
            queries = get_installed_entries()
        for query in queries:
            if self.args["timer"]:
                timer_status(query)
            elif self.args["service"]:
                service_status(query)
            else:
                timer_status(query)
                service_status(query)

    def set_timer(self):
        assert_systemd_available()
        self.assert_entry_installed()

        _, timer_name = self.entry_systemd_filenames
        command = ["systemctl"]
        if not is_root():
            command.append("--user")
        if self.args["enabled"]:
            command.append("enable")
        elif self.args["disabled"]:
            command.append("disable")
        command.extend(["--now", timer_name])
        subprocess.run(command)

    def go(self):
        mapping = {
            Operations.LIST: self.print_entries,
            Operations.INSTALL: self.install_entry,
            Operations.UNINSTALL: self.uninstall_entry,
            Operations.STATUS: self.unit_status,
            Operations.TIMER_CTRL: self.set_timer,
            Operations.BACKUP: self.backup_entry,
            Operations.CHECK: self.check_entry,
            Operations.FORGET: self.forget_entry,
            Operations.INIT: self.initialize_entry,
            Operations.PRUNE: self.prune_entry,
            Operations.SNAPSHOTS: self.list_entry_snapshots,
            Operations.UNLOCK: self.unlock_entry,
        }
        mapping[self.operation]()
