#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Set default arguments
author="tonbakers"
repo="mytonctrl"
branch="master"
srcdir="/usr/src/"
bindir="/usr/bin/"

# Get arguments
while getopts a:r:b: flag
do
	case "${flag}" in
		a) author=${OPTARG};;
		r) repo=${OPTARG};;
		b) branch=${OPTARG};;
	esac
done

# Цвета
COLOR='\033[92m'
ENDC='\033[0m'

# Go to work dir
cd ${srcdir}
rm -rf ${srcdir}/${repo}

# Update code
echo "https://github.com/${author}/${repo}.git -> ${branch}"
git clone --recursive https://github.com/${author}/${repo}.git
cd ${repo} && git checkout ${branch} && git submodule update --init --recursive
systemctl restart mytoncore

# Конец
echo -e "${COLOR}[1/1]${ENDC} MyTonCtrl components update completed"
exit 0
