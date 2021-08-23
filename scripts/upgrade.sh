#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Цвета
COLOR='\033[92m'
ENDC='\033[0m'

cd /usr/src/ton
git pull --recurse-submodules
export CC=/usr/bin/clang
export CXX=/usr/bin/clang++
export CCACHE_DISABLE=1

cd /usr/bin/ton
rm -f CMakeCache.txt
systemctl stop validator && sleep 5
memory=$(cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
let "cpuNumber = memory / 2100000"
cmake -DCMAKE_BUILD_TYPE=Release /usr/src/ton
make -j ${cpuNumber} fift validator-engine lite-client pow-miner validator-engine-console generate-random-id
rm -f global.config.json
wget https://newton-blockchain.github.io/global.config.json
systemctl restart validator

# Конец
echo -e "${COLOR}[1/1]${ENDC} TON components update completed"
exit 0
