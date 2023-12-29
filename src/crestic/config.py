from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
import platform
import os
import shutil
import yaml


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
        else:
            return str(Path(os.environ.get("HOME")) / ".config" / "crestic")
    else:
        raise PlatformNotImplementedError()


def _get_cache_dir():
    if platform.system() == "Windows":
        return str(Path(_get_home()) / "cache")
    elif platform.system() == "Linux":
        xdg_home = "XDG_CACHE_HOME"
        if xdg_home in os.environ.keys():
            return str(Path(os.environ.get(xdg_home)))
        else:
            return str(Path(os.environ.get("HOME")) / ".cache" / "crestic")
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
    config_home = _get_home()
    if os.path.exists(Path(config_home) / "config.yml"):
        return str(Path(config_home) / "config.yml")
    else:
        return None

def _find_config_linux():
    paths_to_search = (
        "/etc/crestic/config.yml",
        Path(_get_home()) / "config.yml"
    )
    for path in paths_to_search:
        if os.path.exists(path):
            return str(path)
    return None

def find_config():
    if platform.system() == "Windows":
        return _find_config_win()
    elif platform.system() == "Linux":
        return _find_config_linux()
    else:
        raise PlatformNotImplementedError()

def find_restic():
    return shutil.which('restic')

@dataclass
class B2Config:
    account_id: str
    account_key: str


@dataclass
class GlobalConfig:
    cache_dir: str = _get_cache_dir()
    tmp_dir: str = _get_tmp_dir()
    restic_bin: str = find_restic()
    b2: B2Config | None = None

    def __post_init__(self):
        if self.b2 is not None:
            self.b2 = B2Config(**self.b2)

class RepositoryType(StrEnum):
    B2 = "b2"
    FILESYSTEM = "fs"


@dataclass
class Entry:
    name: str
    repository: str
    password: str
    paths: tuple[str]
    exclusions: tuple[str] = ()
    repository_version: int = 2
    b2: B2Config | None = None

    @property
    def repo_type(self):
        if self.repository.startswith("b2"):
            return RepositoryType.B2
        else:
            return RepositoryType.FILESYSTEM


@dataclass
class Config:
    globals: GlobalConfig
    entries: dict[str, Entry]

    def __init__(self, file_path: str):
        with open(file_path, "r") as f:
            loaded = yaml.safe_load(f)
        self.globals = GlobalConfig(**loaded.get("global", None))
        entries: dict[str, any] = loaded.get("entries", {})
        self.entries = {}
        if entries is not None:
            for name, entry in entries.items():
                self.entries[name] = Entry(name=name, **entry)
        print(self)
