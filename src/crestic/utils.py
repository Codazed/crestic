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


def stdout(*message: any):
    message = (str(msg) for msg in message)
    print(" ".join(message), file=sys.stdout, flush=True)


def stderr(*message: any, exit: bool = False):
    message = (str(msg) for msg in message)
    print(" ".join(message), file=sys.stderr, flush=True)
    if exit:
        sys.exit(1)
