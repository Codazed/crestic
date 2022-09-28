import subprocess
import os
import sys
import shutil
import re
import yaml
import argparse
from systemd_service import Service

def get_config(path: str) -> dict:
    full_path = os.path.abspath(path)
    with open(full_path, 'r') as stream:
        for data in yaml.safe_load_all(stream):
            return data

class ResticGenerator:
    def __init__(self):
        parser = argparse.ArgumentParser(description="Wrapper for restic that utilizes a config file")
        parser.add_argument('command')
        parser.add_argument('-c', '--config', help='Config file to use', default='/etc/resticg/config.yml')
        args = parser.parse_args(sys.argv[1:2])
        self.config = get_config(args.config)

        try:
            os.mkdir(self.config['config']['cache_dir'])
        except:
            pass
            
        try:
            os.mkdir(self.config['config']['tmp_dir'])
        except:
            pass

        getattr(self, args.command)()

    def __initialize__(self, entry):
        main_cfg = self.config['config']
        entry_cfg = self.config['entries'][entry]

        # Check for restic binary
        if 'restic_bin' not in main_cfg:
            print('Searching for restic binary')
            restic_binary = shutil.which('restic')
            self.restic_bin = restic_binary
        else:
            restic_binary = self.restic_bin = main_cfg['restic_bin']

        if not restic_binary:
            print('No restic binary found in PATH')
            exit(1)

        restic_version = subprocess.run([restic_binary, 'version'], capture_output=True).stdout.decode().replace("\n", "")

        restic_version_regex = 'restic [\d\.]+ compiled with'

        if not re.match(restic_version_regex, restic_version):
            print(f'Invalid restic binary detected at path [{restic_binary}], version output was [{restic_version}]')
            exit(1)

        print(f'Using [{restic_version}] located at [{restic_binary}]')

        self.env = {}
        if entry_cfg['repository'].startswith('b2'):
            self.env['B2_ACCOUNT_ID'] = entry_cfg['b2_account_id'] if 'b2_account_id' in entry_cfg else main_cfg['b2_account_id']
            self.env['B2_ACCOUNT_KEY'] = entry_cfg['b2_account_key'] if 'b2_account_key' in entry_cfg else main_cfg['b2_account_key']

        self.env['RESTIC_CACHE_DIR'] = main_cfg['cache_dir']
        self.env['TMPDIR'] = main_cfg['tmp_dir']

        self.env['RESTIC_REPOSITORY'] = entry_cfg['repository']
        self.env['RESTIC_PASSWORD'] = entry_cfg['password']

    def run(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('entry')
        args = parser.parse_args(sys.argv[2:])
        entry = args.entry

        if not entry in self.config['entries']:
            print(f'Entry {entry} is not defined!')
            exit(1)

        self.__initialize__(entry)

        entry_cfg = self.config['entries'][entry]

        exclusions = entry_cfg['exclude']
        cmd_exclusions = [v for elt in exclusions for v in ('--iexclude', elt)]
        command = [self.restic_bin, 'backup', '--one-file-system', '--verbose'] + cmd_exclusions + [entry_cfg['path_to_backup']]
        print(command)
        subprocess.run(command, env=self.env)

    def generate_units(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('entry')
        args = parser.parse_args(sys.argv[2:])
        entry = args.entry

        if not entry in self.config['entries']:
            print(f'Entry {entry} is not defined!')
            exit(1)

        entry_cfg = self.config['entries'][entry]

        service_name = f'resticg-{entry}'

        python_bin = shutil.which('python3')
        this_script = os.path.realpath(__file__)

        service = Service(service_name, f'{python_bin} {this_script} run {entry}')
        service.create_timer(on_calendar=entry_cfg['schedule'])
        service.start(unit='timer')
        service.enable(unit='timer')

    def init_repo(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('entry')
        args = parser.parse_args(sys.argv[2:])
        entry = args.entry

        if not entry in self.config['entries']:
            print(f'Entry {entry} is not defined!')
            exit(1)

        self.__initialize__(entry)
        command = [self.restic_bin, 'init']
        print(command)
        subprocess.run(command, env=self.env)

    def prune(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('entry')
        args = parser.parse_args(sys.argv[2:])
        entry = args.entry

        if not entry in self.config['entries']:
            print(f'Entry {entry} is not defined!')
            exit(1)

        self.__initialize__(entry)

        entry_cfg = self.config['entries'][entry]

        retention = entry_cfg['retention']
        cmd_retentions = [v for elt in retention for v in (f'--{elt}', str(retention[elt]))]

        command = [self.restic_bin, '--verbose', 'forget'] + cmd_retentions + ['--prune']
        print(command)
        subprocess.run(command, env=self.env)

    def snapshots(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('entry')
        args = parser.parse_args(sys.argv[2:])
        entry = args.entry

        if not entry in self.config['entries']:
            print(f'Entry {entry} is not defined!')
            exit(1)

        self.__initialize__(entry)

        command = [self.restic_bin, '--verbose', 'snapshots']
        print(command)
        subprocess.run(command, env=self.env)

if __name__ == '__main__':
    ResticGenerator()
