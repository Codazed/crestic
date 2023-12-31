import os
import shutil
import sys


def is_root():
    return os.getuid() == 0


def systemd_available() -> bool:
    return shutil.which("systemctl") is not None


def assert_systemd_available():
    if not systemd_available():
        sys.exit("This operation is only available on a system running systemd")
