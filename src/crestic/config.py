import importlib.resources
import os
import platform
import shutil
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional, Self, TypedDict

import lonely
import tomllib

if platform.system() == "Linux":
    USER_LOCATION = Path.home() / ".config/crestic/config.toml"
    ROOT_LOCATION = Path("/etc/crestic/config.toml")
elif platform.system() == "Windows":
    USER_LOCATION = Path.home() / "AppData/Local/crestic/config.toml"
    ROOT_LOCATION = USER_LOCATION
else:
    raise NotImplementedError(platform.system())


def _get_home():
    return USER_LOCATION.parent


def _get_cache_dir():
    if platform.system() == "Windows":
        return _get_home() / "cache"
    if platform.system() == "Linux":
        if "XDG_CACHE_HOME" in os.environ:
            return Path(os.environ.get("XDG_CACHE_HOME"))
        return Path.home() / ".cache/crestic"
    raise NotImplementedError(platform.system())


def _get_tmp_dir():
    if platform.system() == "Windows":
        return Path(os.environ.get("TEMP")) / "crestic"
    if platform.system() == "Linux":
        return "/tmp/crestic"
    raise NotImplementedError(platform.system())


def _find_config_win():
    paths_to_search = (_get_home(), os.getcwd())
    for path in paths_to_search:
        cpath = Path(path) / "config.toml"
        if cpath.exists():
            return cpath
    else:
        return None


def _find_config_linux():
    paths_to_search = ("/etc/crestic", _get_home(), os.getcwd())
    for path in paths_to_search:
        cpath = Path(path) / "config.toml"
        if cpath.exists():
            return cpath
    return None


def find_config():
    if platform.system() == "Windows":
        if USER_LOCATION.exists():
            return USER_LOCATION
        return _find_config_win()
    if platform.system() == "Linux":
        if os.geteuid() == 0 and ROOT_LOCATION.exists():
            return ROOT_LOCATION
        if USER_LOCATION.exists():
            return USER_LOCATION
        return _find_config_linux()
    raise NotImplementedError(platform.system())


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

    def as_args(self) -> list[str]:
        """Get the retention policy as a list of arguments."""
        return str(self).split()

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
class Repository:
    name: str
    location: str
    password: str
    paths: tuple[str]
    exclusions: tuple[str] = ()
    version: int = 2
    retention: RetentionPolicy | None = None
    b2: B2Config | None = None

    @property
    def type(self):
        if self.location.startswith("b2"):
            return RepositoryType.B2
        return RepositoryType.FILESYSTEM

    # noinspection PyArgumentList
    def __post_init__(self):
        if self.retention is not None:
            self.retention = RetentionPolicy(**self.retention)
        if self.b2 is not None:
            self.b2 = B2Config(**self.b2)


class ResticEnvironment(TypedDict):
    """Environment variables for Restic."""

    RESTIC_CACHE_DIR: str
    TMPDIR: str
    RESTIC_REPOSITORY: str
    RESTIC_PASSWORD: str
    B2_ACCOUNT_ID: str | None
    B2_ACCOUNT_KEY: str | None


class Config(metaclass=lonely.Singleton):
    path: Path
    cache_dir: Path
    tmp_dir: Path
    restic_bin: str
    b2: Optional[B2Config] = None
    repos: dict[str, Repository]

    def __init__(self, file_path: str | Path):
        self.path = Path(file_path).resolve(strict=True)
        with self.path.open("rb") as f:
            loaded = tomllib.load(f)
        self.cache_dir = Path(loaded.get("cache_dir", _get_cache_dir()))
        self.tmp_dir = Path(loaded.get("tmp_dir", _get_tmp_dir()))
        self.restic_bin = loaded.get("restic_bin", find_restic())
        global_b2: dict | None = loaded.get("b2", None)
        if global_b2 is not None:
            self.b2 = B2Config(**global_b2)
        repositories: list[dict] = loaded.get("repository", [])
        self.repos = {}
        for repo in repositories:
            self.repos[repo["name"]] = Repository(**repo)

    @classmethod
    def create(cls) -> Self:
        """Create a new config file at one of the default paths.

        Returns:
            A new Config object created from the new config file.
        """
        if platform.system() == "Linux":
            path = ROOT_LOCATION if os.geteuid() == 0 else USER_LOCATION
        else:
            path = USER_LOCATION

        path.parent.mkdir(parents=True, exist_ok=True)
        template = importlib.resources.files("crestic").joinpath("data/config.example.toml")
        with importlib.resources.as_file(template) as template_file:
            shutil.copyfile(template_file, path)
        return cls(path)

    def env(self, repository: Repository) -> ResticEnvironment:
        """Get the relevant environment variables for a given repository.

        Args:
            repository(Repository): The repository object to create env variables for.

        Returns:
            A dictionary of environment variables for the given repository.
        """
        env: ResticEnvironment = {
            "RESTIC_CACHE_DIR": str(self.cache_dir),
            "TMPDIR": str(self.tmp_dir),
            "RESTIC_REPOSITORY": repository.location,
            "RESTIC_PASSWORD": repository.password,
            "B2_ACCOUNT_ID": None,
            "B2_ACCOUNT_KEY": None,
        }
        if repository.type == RepositoryType.B2:
            if repository.b2:
                env["B2_ACCOUNT_ID"] = repository.b2.account_id
                env["B2_ACCOUNT_KEY"] = repository.b2.account_key
            elif self.b2:
                env["B2_ACCOUNT_ID"] = self.b2.account_id
                env["B2_ACCOUNT_KEY"] = self.b2.account_key
            else:
                msg = (
                    f"{repository.name} is a B2 repository, but the credentials have not "
                    f"been defined"
                )
                raise AttributeError(msg)

        return env
