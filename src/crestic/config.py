from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import platform
import os
import shutil
import tomllib
from typing import Optional


class PlatformNotImplementedError(NotImplementedError):
    def __init__(self):
        super().__init__(f"Unimplemented platform {platform.system()}")


def _get_home():
    if platform.system() == "Windows":
        return str(Path(os.environ.get("APPDATA")) / "crestic")
    elif platform.system() == "Linux":
        xdg_home = "XDG_CONFIG_HOME"
        if xdg_home in os.environ.keys():
            return str(Path(os.environ.get(xdg_home)) / "crestic")
        elif "HOME" in os.environ.keys():
            return str(Path(os.environ.get("HOME")) / ".config" / "crestic")
        else:
            return os.getcwd()
    else:
        raise PlatformNotImplementedError()


def _get_cache_dir():
    if platform.system() == "Windows":
        return str(Path(_get_home()) / "cache")
    elif platform.system() == "Linux":
        xdg_home = "XDG_CACHE_HOME"
        if xdg_home in os.environ.keys():
            return str(Path(os.environ.get(xdg_home)))
        elif "HOME" in os.environ.keys():
            return str(Path(os.environ.get("HOME")) / ".cache" / "crestic")
        else:
            return "/var/tmp/crestic"
    else:
        raise PlatformNotImplementedError()


def _get_tmp_dir():
    if platform.system() == "Windows":
        return str(Path(os.environ.get("TEMP")) / "crestic")
    elif platform.system() == "Linux":
        return "/tmp/crestic"
    else:
        raise PlatformNotImplementedError()


def _find_config_win():
    paths_to_search = (_get_home(), os.getcwd())
    for path in paths_to_search:
        if os.path.exists(Path(path) / "config.yml"):
            return str(Path(path) / "config.yml")
    else:
        return None


def _find_config_linux():
    paths_to_search = ("/etc/crestic", _get_home(), os.getcwd())
    for path in paths_to_search:
        if os.path.exists(Path(path) / "config.yml"):
            return str(Path(path) / "config.yml")
    return None


def find_config():
    if platform.system() == "Windows":
        return _find_config_win()
    elif platform.system() == "Linux":
        return _find_config_linux()
    else:
        raise PlatformNotImplementedError()


def find_restic():
    return shutil.which("restic")


@dataclass
class B2Config:
    account_id: str
    account_key: str


class RepositoryType(StrEnum):
    B2 = "b2"
    FILESYSTEM = "fs"


@dataclass
class RetentionPolicy:
    last: int = None
    hourly: int = None
    daily: int = None
    weekly: int = None
    monthly: int = None
    yearly: int = None
    tag: list[str] = None

    def __str__(self):
        string = []
        for attr, val in vars(self).items():
            if type(val) is int:
                string.extend([f"--keep-{attr}", str(val)])
            elif type(val) is list:
                for elem in val:
                    string.extend([f"--keep-{attr}", str(elem)])
        return " ".join(string)


@dataclass
class Task:
    name: str
    repository: str
    password: str
    paths: tuple[str]
    exclusions: tuple[str] = ()
    repository_version: int = 2
    schedule: str = None
    retention: RetentionPolicy = None
    b2: B2Config | None = None

    @property
    def repo_type(self):
        if self.repository.startswith("b2"):
            return RepositoryType.B2
        else:
            return RepositoryType.FILESYSTEM

    # noinspection PyArgumentList
    def __post_init__(self):
        if self.retention is not None:
            self.retention = RetentionPolicy(**self.retention)
        if self.b2 is not None:
            self.b2 = B2Config(**self.b2)


class Config:
    cache_dir: str
    tmp_dir: str
    restic_bin: str
    b2: Optional[B2Config] = None
    tasks: list[Task]

    def __init__(self, file_path: str):
        with open(file_path, "rb") as f:
            loaded = tomllib.load(f)
        self.cache_dir = loaded.get("cache_dir", _get_cache_dir())
        self.tmp_dir = loaded.get("tmp_dir", _get_tmp_dir())
        self.restic_bin = loaded.get("restic_bin", find_restic())
        global_b2: dict | None = loaded.get("b2", None)
        if global_b2 is not None:
            self.b2 = B2Config(**global_b2)
        tasks: list[dict] = loaded.get("tasks", [])
        self.tasks = []
        for task in tasks:
            self.tasks.append(Task(**task))
