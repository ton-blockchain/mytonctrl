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
cd /usr/src/ton

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
	git branch --set-upstream-to=origin/${branch} ${branch}
	git pull --rebase
fi

# Update code
git pull --recurse-submodules
export CC=/usr/bin/clang
export CXX=/usr/bin/clang++
export CCACHE_DISABLE=1

# Update binary
cd /usr/bin/ton
rm -f CMakeCache.txt
systemctl stop validator && sleep 5
memory=$(cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
let "cpuNumber = memory / 2100000"
cmake -DCMAKE_BUILD_TYPE=Release /usr/src/ton
make -j ${cpuNumber} fift validator-engine lite-client pow-miner validator-engine-console generate-random-id
systemctl restart validator

# Конец
echo -e "${COLOR}[1/1]${ENDC} TON components update completed"
exit 0
