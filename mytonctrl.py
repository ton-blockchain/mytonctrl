#!/bin/env python3

#
# This is a migration script to update from legacy version of MTC
#
import os
import sys
import subprocess

requirements_path = "/usr/src/mytonctrl/requirements.txt"
if os.path.isfile(requirements_path):
    args = ["pip3", "install", "-r", requirements_path]
    subprocess.run(args)
#end if

sys.path.insert(0, '/usr/bin/mytonctrl')  # Add path to mytonctrl module


from mytonctrl.mytonctrl import run_migrations

if __name__ == '__main__':
    print('Found new version of mytonctrl! Migrating!')
    run_migrations()
