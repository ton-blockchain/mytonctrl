import os
import pkg_resources

from mypylib.mypylib import MyPyClass
from mytoncore.mytoncore import MyTonCore

from mypylib.mypylib import (
    run_as_root
)

from typing import Optional


def migrate_to_version_1(local: MyPyClass, ton: MyTonCore):
    # get script path
    migrate_script_path = pkg_resources.resource_filename('mytonctrl', 'migrations/migration_001.sh')
    args = ["/bin/bash", migrate_script_path]
    exit_code = run_as_root(args)
    if exit_code != 0:
        raise RuntimeError(f'Failed to run migration error. Exit code: {exit_code}')
    return


def migrate(version: 0, local: MyPyClass, ton: MyTonCore):
    if version < 1:
        local.add_log(f'Running migration {version} -> 1', 'info')
        migrate_to_version_1(local, ton)


def run_migrations(local: Optional[MyPyClass]=None, ton: Optional[MyTonCore]=None):
	if local is None:
		local = MyPyClass('mytonctrl.py')
	if ton is None:
		ton = MyTonCore(MyPyClass('mytoncore.py'))

	# migrations
	local.add_log('Running MyTonCtrl migrations', 'info')
	
	workdir = local.buffer.my_work_dir
	local.add_log(f"Workdir: {workdir}", 'info')

	version = 0
	version_file_path = os.path.join(workdir, 'VERSION')
	if os.path.exists(version_file_path):
		with open(version_file_path, 'r') as f:
			version = int(f.read())
	local.add_log(f'Current version: {version}', 'info')
	
	migrate(version, local, ton)
#end define