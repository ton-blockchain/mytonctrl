#!/bin/env python3

#
# This is a migration script to update from legacy version of MTC
#
import os
import sys

sys.path.insert(0, '/usr/bin/mytonctrl')  # Add path to mytonctrl module


from mytonctrl.mytonctrl import run_migrations

if __name__ == '__main__':
    print('Found new version of mytonctrl! Migrating!')
    run_migrations()
