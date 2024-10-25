import argparse
from crestic.config import find_config
from crestic.crestic import Operations

parser = argparse.ArgumentParser(
    prog="crestic",
    description="Configurable command invocation for restic",
    epilog="For source code and issue-reporting, go to https://gitlab.com/codazed/crestic",
)

parser.add_argument("-c", "--config", metavar="PATH", help="config file to use", default=find_config())
parser.add_argument("--print-command", action="store_true", help="just print the command that would run")

subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND", required=True)

# Crestic-specific commands
parser_list = subparsers.add_parser(str(Operations.LIST), help="list entries in the config file")
parser_list.add_argument("--paths", action="store_true", help="show paths in output")

parser_install = subparsers.add_parser(str(Operations.INSTALL), help="install systemd unit files")
parser_install.add_argument("entry", help="the entry to perform the operation for")

parser_uninstall = subparsers.add_parser(str(Operations.UNINSTALL), help="uninstall systemd unit files")
parser_uninstall.add_argument("entry", help="the entry to perform the operation for")

parser_status = subparsers.add_parser(str(Operations.STATUS), help="show systemd unit file status")
parser_status.add_argument("--entry", help="the entry to perform the operation for")
group = parser_status.add_mutually_exclusive_group()
group.add_argument("--service", action="store_true", help="only show service status")
group.add_argument("--timer", action="store_true", help="only show timer status")

parser_timer_ctrl = subparsers.add_parser(str(Operations.TIMER_CTRL), help="control the systemd timer")
parser_timer_ctrl.add_argument("entry", help="the entry to perform the operation for")
parser_timer_ctrl.add_argument("status", choices=["enabled", "disabled"], help="enable/disable the timer")

# Commands for Restic operations
restic_operation_parsers: list[argparse.ArgumentParser] = []

parser_backup = subparsers.add_parser(
    str(Operations.BACKUP), help="create a new backup of files and/or directories for the specified entry"
)
parser_backup.add_argument("--host", metavar="hostname", help="set the hostname for the snapshot manually")
parser_backup.add_argument("--parent", metavar="snapshot", help="use this parent snapshot")
parser_backup.add_argument("--tag", metavar="tags", action="append", nargs="*", help="tag the backup")
restic_operation_parsers.append(parser_backup)

# TODO: restic cache

parser_check = subparsers.add_parser(
    str(Operations.CHECK), help="check the repository for errors for the specified entry"
)
restic_operation_parsers.append(parser_check)

# TODO: restic diff
# TODO: restic dump
# TODO: restic find

parser_forget = subparsers.add_parser(
    str(Operations.FORGET), help="remove snapshots from the repo for the specified entry"
)
parser_forget.add_argument(
    "--prune", action="store_true", help='automatically run the "prune" command if snapshots have been removed'
)
# TODO: Add args for specifying removal policy manually
# TODO: Add args for specifying a single snapshot to remove
restic_operation_parsers.append(parser_forget)

parser_init = subparsers.add_parser(str(Operations.INIT), help="initialize a new repository for the specified entry")
parser_init.add_argument(
    "-V", "--repository-version", metavar="version", help="restic repository version to use (Restic v0.14.0+)"
)
restic_operation_parsers.append(parser_init)

# TODO: restic list
# TODO: restic ls
# TODO: restic mount

parser_prune = subparsers.add_parser(
    str(Operations.PRUNE), help="remove unneeded data from the repository for the specified entry"
)
restic_operation_parsers.append(parser_prune)

# TODO: restic restore

parser_snapshots = subparsers.add_parser(str(Operations.SNAPSHOTS), help="list all snapshots for the specified entry")
# TODO: Add extra args available for 'restic snapshots' command
restic_operation_parsers.append(parser_snapshots)

# TODO: restic stats

parser_unlock = subparsers.add_parser(
    str(Operations.UNLOCK), help="remove locks other processes created for the specified entry"
)
restic_operation_parsers.append(parser_unlock)

for op_parser in restic_operation_parsers:
    op_parser.add_argument("entry", help="the entry to perform the operation for")
    op_parser.add_argument("-d", "--dry-run", action="store_true", help="perform dry-run of Restic command")
    op_parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")


def main():
    args = vars(parser.parse_args())
    from crestic.crestic import Crestic

    Crestic(
        operation_str=args["subcommand"], config_path=args["config"], entry_str=args.get("entry", None), args=args
    ).go()


if __name__ == "__main__":
    main()
