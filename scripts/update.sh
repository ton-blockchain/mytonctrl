#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Get arguments
while getopts r:b: flag
do
	case "${flag}" in
		r) repo=${OPTARG};;
		b) branch=${OPTARG};;
	esac
done

# Цвета
COLOR='\033[92m'
ENDC='\033[0m'

# Go to work dir
cd /usr/src/mytonctrl

# Adjust repo
if [ -z ${repo+x} ]; then
	echo "repo without changes"
else
	git remote set-url origin ${repo}
	git pull --rebase
fi

# Adjust branch
if [ -z ${branch+x} ]; then
	echo "branch without changes"
else
	git checkout ${branch}
	git pull --rebase
fi

# Update code
git pull --recurse-submodules
systemctl restart mytoncore

# Конец
echo -e "${COLOR}[1/1]${ENDC} MyTonCtrl components update completed"
exit 0
