#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Set default arguments
author="ton-blockchain"
repo="mytonctrl"
branch="master"
srcdir="/usr/src/"
tmpdir="/tmp/mytonctrl_src/"

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

mkdir -p ${tmpdir}
cd ${tmpdir}
rm -rf ${tmpdir}/${repo}
echo "https://github.com/${author}/${repo}.git -> ${branch}"
git clone --recursive https://github.com/${author}/${repo}.git || exit 1

rm -rf ${srcdir}/${repo}
pip3 uninstall -y mytonctrl

# Update code
cd ${srcdir}
cp -rf ${tmpdir}/${repo} ${srcdir}
cd ${repo} && git checkout ${branch}
pip3 install -r requirements.txt
pip3 install -U .

systemctl daemon-reload
systemctl restart mytoncore

# Конец
echo -e "${COLOR}[1/1]${ENDC} MyTonCtrl components update completed"
exit 0
