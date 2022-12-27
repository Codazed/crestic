import argparse

parser = argparse.ArgumentParser(prog='crestic', description='Configurable Restic command invocation', epilog='https://gitlab.com/codazed/crestic')
parser.add_argument('-d', '--dry-run', action='store_true', help='perform dry-run of Restic command')
parser.add_argument('-c', '--config', metavar='PATH', help='config file to use', default='/etc/resticg/config.yml')

subparsers = parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')

# CRestic-specific commands
parser_list = subparsers.add_parser('list', help='List entries in the config file')

# Commands for Restic operations
restic_operation_parsers: list[argparse.ArgumentParser] = []

parser_backup = subparsers.add_parser('backup', help='Create a new backup of files and/or directories for the specified entry')
restic_operation_parsers.append(parser_backup)

# TODO: restic cache

parser_check = subparsers.add_parser('check', help='Check the repository for errors for the specified entry')
restic_operation_parsers.append(parser_check)

# TODO: restic diff
# TODO: restic dump
# TODO: restic find

parser_forget = subparsers.add_parser('forget', help='Remove snapshots from the repo for the specified entry')
parser_forget.add_argument('--prune', action='store_true', help='automatically run the \'prune\' command if snapshots have been removed')
# TODO: Add args for specifying removal policy manually
# TODO: Add args for specifying a single snapshot to remove
restic_operation_parsers.append(parser_forget)

parser_init = subparsers.add_parser('init', help='Initialize a new repository for the specified entry')
parser_init.add_argument('-V', '--repository-version', metavar='version', help='restic repository version to use (Restic v0.14.0+)')
restic_operation_parsers.append(parser_init)

# TODO: restic list
# TODO: restic ls
# TODO: restic mount

parser_prune = subparsers.add_parser('prune', help='Remove unneeded data from the repository for the specified entry')
restic_operation_parsers.append(parser_prune)

# TODO: restic restore

parser_snapshots = subparsers.add_parser('snapshots', help='List all snapshots for the specified entry')
# TODO: Add extra args available for 'restic snapshots' command
restic_operation_parsers.append(parser_snapshots)

# TODO: restic stats

parser_unlock = subparsers.add_parser('unlock', help='Remove locks other processes created for the specified entry')
restic_operation_parsers.append(parser_unlock)

for restopparser in restic_operation_parsers:
    restopparser.add_argument('entry', help='The entry to perform the operation for')

print(parser.parse_args())