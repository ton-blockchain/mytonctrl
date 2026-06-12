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
tmpdir="/tmp/mytonctrl_src/"

# Get arguments
while getopts a:r:b:S: flag
do
	case "${flag}" in
		a) author=${OPTARG};;
		r) repo=${OPTARG};;
		b) branch=${OPTARG};;
    S) srcdir=${OPTARG};;
    *) echo "Unknown arg"
       exit 1;;
	esac
done

COLOR='\033[92m'
ENDC='\033[0m'

if [ -z "${srcdir}" ]; then
    srcdir="/usr/src/${repo}"
fi

mkdir -p ${tmpdir}
cd ${tmpdir}
rm -rf ${tmpdir}/${repo}
echo "https://github.com/${author}/${repo}.git -> ${branch}"
git clone https://github.com/${author}/${repo}.git

cd ${tmpdir}/${repo} && git checkout ${branch}
git submodule update --init --recursive

rm -rf ${srcdir}

# Update code
mkdir -p ${srcdir}
cp -rfT ${tmpdir}/${repo} ${srcdir}
cd ${srcdir}
python3 -m pip install -U "setuptools>=64"
python3 -m pip install -U .

systemctl daemon-reload
systemctl restart mytoncore

# Конец
echo -e "${COLOR}[1/1]${ENDC} MyTonCtrl components update completed"
exit 0
