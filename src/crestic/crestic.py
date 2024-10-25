import configparser
from crestic.config import Config, Task, RepositoryType
from crestic.utils import is_root, assert_systemd_available, stdout, stderr
from dataclasses import dataclass, field, InitVar
from enum import StrEnum
import os.path
from pathlib import Path
import re
import shutil
import subprocess
import sys

from prettytable import PrettyTable as Table

systemd_unit_prefix = "crestic--"


def get_units_location():
    if os.geteuid() == 0:
        # If user is root, install units in system location
        return Path("/etc/systemd/system")
    else:
        # If user is not root, install as a user unit
        return Path(f"{os.environ.get('HOME')}/.config/systemd/user")


def task_systemd_filenames(task: Task | str):
    if type(task) is Task:
        name = task.name
    else:
        name = task
    return f"{systemd_unit_prefix}{name}.service", f"{systemd_unit_prefix}{name}.timer"


def reload_systemd():
    command = ["systemctl"]
    if not is_root():
        command.append("--user")
    command.append("daemon-reload")
    subprocess.run(command)


def task_already_installed(task: Task | str):
    location = get_units_location()
    return False not in [os.path.exists(location / filename) for filename in task_systemd_filenames(task)]


def get_installed_tasks():
    units_location = get_units_location()
    found_tasks = set(
        [
            f.replace(systemd_unit_prefix, "").replace(".service", "").replace(".timer", "")
            for f in os.listdir(units_location)
            if f.startswith(systemd_unit_prefix)
        ]
    )
    return [task for task in found_tasks if task_already_installed(task)]


def assert_task_installed(task: Task | str):
    if not task_already_installed(task):
        if type(task) is Task:
            task_name = task.name
        else:
            task_name = task
        sys.exit(f"task {task_name} is not installed")


def service_status(task: Task | str):
    assert_systemd_available()
    assert_task_installed(task)

    service_name, _ = task_systemd_filenames(task)
    command = ["systemctl", "status", service_name]
    if not is_root():
        command.append("--user")
    subprocess.run(command)


def timer_status(task: Task | str):
    assert_systemd_available()
    assert_task_installed(task)

    _, timer_name = task_systemd_filenames(task)
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
    config_path: str
    operation_str: InitVar[str]
    task_name: InitVar[str | None] = None
    operation: Operations = field(init=False)
    args: dict[str, any] = None
    config: Config = field(init=False)
    task: Task | None = field(init=False)
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self, operation_str: str, task_name: str):
        if operation_str is not None:
            self.operation = Operations(operation_str)

        if self.config_path is None:
            raise ValueError("Unable to find config file")
        self.config = Config(self.config_path)

        if task_name is not None:
            try:
                self.task = next(task for task in self.config.tasks if task.name == task_name)
            except StopIteration:
                valid_tasks = ", ".join([task.name for task in self.config.tasks])
                stderr(f"Unknown task {task_name}, valid tasks: {valid_tasks}", exit=True)

    def print_tasks(self):
        if self.args["detailed"]:
            table = Table()
            fields = ["Name", "Repository", "Paths"]
            if self.args["passwords"]:
                fields.append("Password")
            table.field_names = fields
            table.align["Paths"] = "l"
            for task in self.config.tasks:
                row = [task.name, task.repository, "\n".join(task.paths)]
                if self.args["passwords"]:
                    row.append(task.password)
                table.add_row(row, divider=True)
            stdout(table)
        else:
            for task in self.config.tasks:
                stdout(task.name)

    def validate_restic(self):
        if self.config.restic_bin is None:
            return False

        restic = self.config.restic_bin
        restic_version = subprocess.check_output([restic, "version"]).decode().replace("\n", "")
        restic_version_regex = r"restic [\d\.]+ compiled with"

        if not re.match(restic_version_regex, restic_version):
            stderr(f"Invalid restic binary detected at path [{restic}], version output was [{restic_version}]")
            return False

        stdout(f"Using [{restic_version}] located at [{restic}]")
        return True

    def set_env(self, key: str, value: str):
        self.env[key] = value

    def init_env(self):
        if not os.path.exists(self.config.cache_dir):
            os.mkdir(self.config.cache_dir, mode=0o750)
        if not os.path.exists(self.config.tmp_dir):
            os.mkdir(self.config.tmp_dir, mode=0o750)
        if not self.validate_restic():
            raise RuntimeError("Restic was not found in your PATH")

        self.set_env("RESTIC_CACHE_DIR", self.config.cache_dir)
        self.set_env("TMPDIR", self.config.tmp_dir)

        if self.task.repo_type is RepositoryType.B2:
            if self.task.b2 is not None:
                self.set_env("B2_ACCOUNT_ID", self.task.b2.account_id)
                self.set_env("B2_ACCOUNT_KEY", self.task.b2.account_key)
            elif self.config.b2 is not None:
                self.set_env("B2_ACCOUNT_ID", self.config.b2.account_id)
                self.set_env("B2_ACCOUNT_KEY", self.config.b2.account_key)
            else:
                raise AttributeError(f"{self.task.name} is a B2 repository, but the credentials have not been defined")

        self.set_env("RESTIC_REPOSITORY", self.task.repository)
        self.set_env("RESTIC_PASSWORD", self.task.password)

    def exec_restic_cmd(self, command: list[str]):
        self.init_env()
        restic = self.config.restic_bin
        command = [str(part) for part in command]
        full_cmd = [restic] + command
        if self.args["dry_run"]:
            full_cmd.append("--dry-run")
        if self.args["print_command"]:
            stdout(f"Would run the below command:\n{' '.join(full_cmd)}")
        else:
            stdout(f"Executing [{' '.join(full_cmd)}]")
            subprocess.run(full_cmd, env=self.env)

    def backup_task(self):
        exclusions = self.task.exclusions
        cmd_exclusions = [v for elt in exclusions for v in ("--iexclude", elt)]

        command = ["backup", "--one-file-system", "--verbose"]

        if self.args["host"] is not None:
            command.extend(["--host", self.args["host"]])
        if self.args["parent"] is not None:
            command.extend(["--parent", self.args["parent"]])
        if self.args["tag"] is not None:
            for tag in self.args["tag"]:
                if type(tag) is list:
                    for sub in tag:
                        command.extend(["--tag", sub])
                else:
                    command.extend(["--tag", tag])

        command.extend(cmd_exclusions)
        command.extend(self.task.paths)
        self.exec_restic_cmd(command)

    def initialize_task(self):
        command = ["init", "--repository-version", self.task.repository_version]
        self.exec_restic_cmd(command)

    def check_task(self):
        self.exec_restic_cmd(["check"])

    def forget_task(self):
        command = ["forget"]

        policy = self.task.retention

        if policy is not None:
            command.extend(str(policy).split(" "))

        if self.args.get("prune", False):
            command.append("--prune")
        self.exec_restic_cmd(command)

    def prune_task(self):
        self.exec_restic_cmd(["prune"])

    def list_task_snapshots(self):
        self.exec_restic_cmd(["snapshots"])

    def unlock_task(self):
        self.exec_restic_cmd(["unlock"])

    @property
    def task_systemd_filenames(self):
        return task_systemd_filenames(self.task)

    @property
    def task_already_installed(self):
        return task_already_installed(self.task)

    def assert_task_installed(self):
        return assert_task_installed(self.task)

    def install_task(self):
        assert_systemd_available()

        if self.task_already_installed:
            sys.exit(f"task {self.task.name} is already installed")

        if self.task.schedule is None:
            sys.exit(f"No schedule has been defined for task {self.task.name}")

        # Systemd units are basically super-simple ini files
        service_name, timer_name = self.task_systemd_filenames
        service_config = configparser.ConfigParser()
        service_config.optionxform = str
        service_config["Unit"] = {
            "Description": f"Crestic operations for task {self.task.name}",
        }
        service_config["Service"] = {
            "ExecStart": f"{shutil.which('crestic')} -c {os.path.realpath(self.config_path)} backup {self.task.name}",
        }
        service_config["Install"] = {"WantedBy": "default.target"}

        timer_config = configparser.ConfigParser()
        timer_config.optionxform = str
        timer_config["Unit"] = {
            "Description": f"Crestic timer for task {self.task.name}",
        }
        timer_config["Timer"] = {
            "OnCalendar": self.task.schedule,
            "Unit": service_name,
        }
        timer_config["Install"] = {"WantedBy": "timers.target"}

        units_location = get_units_location()

        with open(units_location / service_name, "w") as f:
            # noinspection PyTypeChecker
            service_config.write(f)
            stdout("Created unit", units_location / service_name)
        with open(units_location / timer_name, "w") as f:
            # noinspection PyTypeChecker
            timer_config.write(f)
            stdout("Created unit", units_location / timer_name)

        stdout("Enabling timer")
        command = ["systemctl"]
        if not is_root():
            command.append("--user")
        command.extend(["enable", "--now", timer_name])
        subprocess.run(command)
        reload_systemd()

    def uninstall_task(self):
        assert_systemd_available()
        self.assert_task_installed()

        units_location = get_units_location()
        for filename in self.task_systemd_filenames:
            os.remove(units_location / filename)

        reload_systemd()

    def timer_status(self):
        return timer_status(self.task)

    def service_status(self):
        return service_status(self.task)

    def unit_status(self):
        if self.args["task"]:
            queries = [self.args["task"]]
        else:
            queries = get_installed_tasks()
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
        self.assert_task_installed()

        _, timer_name = self.task_systemd_filenames
        command = ["systemctl"]
        if not is_root():
            command.append("--user")
        if self.args["status"] == "enabled":
            command.append("enable")
        elif self.args["status"] == "disabled":
            command.append("disable")
        command.extend(["--now", timer_name])
        subprocess.run(command)

    def go(self):
        mapping = {
            Operations.LIST: self.print_tasks,
            Operations.INSTALL: self.install_task,
            Operations.UNINSTALL: self.uninstall_task,
            Operations.STATUS: self.unit_status,
            Operations.TIMER_CTRL: self.set_timer,
            Operations.BACKUP: self.backup_task,
            Operations.CHECK: self.check_task,
            Operations.FORGET: self.forget_task,
            Operations.INIT: self.initialize_task,
            Operations.PRUNE: self.prune_task,
            Operations.SNAPSHOTS: self.list_task_snapshots,
            Operations.UNLOCK: self.unlock_task,
        }
        mapping[self.operation]()
