#!/bin/bash
set -e

# colors
COLOR='\033[92m'
ENDC='\033[0m'
mydir=`pwd`

# check sudo permissions
if [ "$(id -u)" != "0" ]; then
    echo "Please run script as root"
    exit 1
fi

author="ton-blockchain"
repo="mytonctrl"
branch="master"

# node install parameters
config="https://ton-blockchain.github.io/global.config.json"
telemetry=true
ignore=false
dump=false

while getopts m:c:tida:r:b: flag
do
	case "${flag}" in
		m) mode=${OPTARG};;
		c) config=${OPTARG};;
		t) telemetry=false;;
		i) ignore=true;;
		d) dump=true;;
		a) author=${OPTARG};;
		r) repo=${OPTARG};;
		b) branch=${OPTARG};;
	esac
done

# check machine configuration
echo -e "${COLOR}[1/5]${ENDC} Checking system requirements"

cpus=$(lscpu | grep "CPU(s)" | head -n 1 | awk '{print $2}')
memory=$(cat /proc/meminfo | grep MemTotal | awk '{print $2}')

echo "This machine has ${cpus} CPUs and ${memory}KB of Memory"
if [ "${mode}" = "lite" ] && [ "$ignore" = false ] && ([ "${cpus}" -lt 2 ] || [ "${memory}" -lt 2000000 ]); then
	echo "Insufficient resources. Requires a minimum of 2 processors and 2Gb RAM."
	exit 1
fi
if [ "${mode}" = "full" ] && [ "$ignore" = false ] && ([ "${cpus}" -lt 8 ] || [ "${memory}" -lt 8000000 ]); then
	echo "Insufficient resources. Requires a minimum of 8 processors and 8Gb RAM."
	exit 1
fi

echo -e "${COLOR}[2/5]${ENDC} Checking for required TON components"
SOURCES_DIR=/usr/src
BIN_DIR=/usr/bin

# create dirs for OSX
if [[ "$OSTYPE" =~ darwin.* ]]; then
	SOURCES_DIR=/usr/local/src
	BIN_DIR=/usr/local/bin
	mkdir -p ${SOURCES_DIR}
fi

# check TON components
file1=${BIN_DIR}/ton/crypto/fift
file2=${BIN_DIR}/ton/lite-client/lite-client
file3=${BIN_DIR}/ton/validator-engine-console/validator-engine-console

if  [ ! -f "${file1}" ] || [ ! -f "${file2}" ] || [ ! -f "${file3}" ]; then
	echo "TON does not exists, building"
	wget https://raw.githubusercontent.com/${author}/${repo}/${branch}/scripts/ton_installer.sh -O /tmp/ton_installer.sh
	bash /tmp/ton_installer.sh -c ${config}
fi

# Cloning mytonctrl
echo -e "${COLOR}[3/5]${ENDC} Installing MyTonCtrl"
echo "https://github.com/${author}/${repo}.git -> ${branch}"

cd $SOURCES_DIR
rm -rf $SOURCES_DIR/mytonctrl

git clone https://github.com/${author}/${repo}.git ${repo}  # TODO: return --recursive back when fix libraries
cd $SOURCES_DIR/${repo}
git checkout ${branch}
git submodule update --init --recursive

# FIXME: add __init__.py in these repos
touch mypyconsole/__init__.py
touch mypylib/__init__.py

pip3 install -U .  # TODO: make installation from git directly

echo -e "${COLOR}[3/5]${ENDC} Running myton.installer"
# DEBUG

# check installation mode
if [ "${mode}" != "lite" ] && [ "${mode}" != "full" ]; then
	echo "Run script with flag '-m lite' or '-m full'"
	exit 1
fi

user=$(ls -lh ${mydir}/${0} | cut -d ' ' -f 3)
echo "User: $user"
python3 -m mytoninstaller -m ${mode} -u ${user} -t ${telemetry} --dump ${dump}

echo -e "${COLOR}[4/4]${ENDC} Mytonctrl installation completed"
exit 0
