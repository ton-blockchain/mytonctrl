#!/bin/bash
set -e

# Check sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Set default arguments
author="ton-blockchain"
repo="mytonctrl"
branch="master"
srcdir="/usr/src/"

# Get arguments
while getopts a:r:b: flag
do
	case "${flag}" in
		a) author=${OPTARG};;
		r) repo=${OPTARG};;
		b) branch=${OPTARG};;
	esac
done

# Colors
COLOR='\033[92m'
ENDC='\033[0m'

# Installation of python3 components
pip3 install fastcrc

# Go to work dir
cd ${srcdir}
rm -rf ${srcdir}/${repo}

# Update code
echo "https://github.com/${author}/${repo}.git -> ${branch}"
git clone --recursive https://github.com/${author}/${repo}.git
cd ${repo} && git checkout ${branch} && git submodule update --init --recursive
systemctl restart mytoncore

# End
echo -e "${COLOR}[1/1]${ENDC} MyTonCtrl components update completed"
exit 0
