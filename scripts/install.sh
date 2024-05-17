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
mode="validator"

show_help_and_exit() {
  echo 'Supported argumets:'
  echo ' -c  PATH         Provide custom config for toninstaller.sh'
  echo ' -t               Disable telemetry'
  echo ' -i               Ignore minimum reqiurements'
  echo ' -d               Use pre-packaged dump. Reduces duration of initial synchronization.'
  echo ' -a               Set MyTonCtrl git repo author'
	echo ' -r               Set MyTonCtrl git repo'
	echo ' -b               Set MyTonCtrl git repo branch'
	echo ' -m  MODE             Install MyTonCtrl with specified mode (validator or liteserver)'
	echo ' -h               Show this help'
    exit
}

if [[ "${1-}" =~ ^-*h(elp)?$ ]]; then
    show_help_and_exit
fi

# node install parameters
config="https://ton-blockchain.github.io/global.config.json"
telemetry=true
ignore=false
dump=false



while getopts c:tida:r:b:m: flag
do
	case "${flag}" in
		c) config=${OPTARG};;
		t) telemetry=false;;
		i) ignore=true;;
		d) dump=true;;
		a) author=${OPTARG};;
		r) repo=${OPTARG};;
		b) branch=${OPTARG};;
    m) mode=${OPTARG};;
		h) show_help_and_exit;;
		*)
            echo "Flag -${flag} is not recognized. Aborting"
            exit 1 ;;
	esac
done

# check machine configuration
echo -e "${COLOR}[1/5]${ENDC} Checking system requirements"

cpus=$(lscpu | grep "CPU(s)" | head -n 1 | awk '{print $2}')
memory=$(cat /proc/meminfo | grep MemTotal | awk '{print $2}')

echo "This machine has ${cpus} CPUs and ${memory}KB of Memory"
if [ "$ignore" = false ] && ([ "${cpus}" -lt 16 ] || [ "${memory}" -lt 64000000 ]); then
	echo "Insufficient resources. Requires a minimum of 16 processors and 64Gb RAM."
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

# remove previous installation
cd $SOURCES_DIR
rm -rf $SOURCES_DIR/mytonctrl
pip3 uninstall -y mytonctrl

git clone --branch ${branch} --recursive https://github.com/${author}/${repo}.git ${repo}  # TODO: return --recursive back when fix libraries
git config --global --add safe.directory $SOURCES_DIR/${repo}
cd $SOURCES_DIR/${repo}

pip3 install -U .  # TODO: make installation from git directly

echo -e "${COLOR}[4/5]${ENDC} Running mytoninstaller"
# DEBUG

parent_name=$(ps -p $PPID -o comm=)
user=$(whoami)
if [ "$parent_name" = "sudo" ] || [ "$parent_name" = "su" ]; then
    user=$(logname)
fi
echo "User: $user"
python3 -m mytoninstaller -u ${user} -t ${telemetry} --dump ${dump} -m ${mode}

# set migrate version
migrate_version=1
version_dir="/home/${user}/.local/share/mytonctrl"
version_path="${version_dir}/VERSION"
mkdir -p ${version_dir}
echo ${migrate_version} > ${version_path}
chown ${user}:${user} ${version_dir} ${version_path}

echo -e "${COLOR}[5/5]${ENDC} Mytonctrl installation completed"
exit 0
