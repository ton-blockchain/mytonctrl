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

# mkdir -p /tmp/mytoninstaller/
# mv /usr/bin/ton/validator-engine-console/client /tmp/mytoninstaller/client
# mv /usr/bin/ton/validator-engine-console/client.pub /tmp/mytoninstaller/client.pub
# mv /usr/bin/ton/validator-engine-console/server.pub /tmp/mytoninstaller/server.pub
# mv /usr/bin/ton/validator-engine-console/liteserver.pub /tmp/mytoninstaller/liteserver.pub

# rm -rf /usr/bin/ton
# mkdir /usr/bin/ton
cd /usr/bin/ton
rm -f CMakeCache.txt
systemctl stop validator && sleep 5
memory=$(cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
let "cpuNumber = memory / 2100000"
cmake -DCMAKE_BUILD_TYPE=Release /usr/src/ton
make -j ${cpuNumber} validator-engine lite-client pow-miner validator-engine-console
rm -f global.config.json
wget https://newton-blockchain.github.io/global.config.json
# cd /usr/bin/ton/lite-client
# wget https://newton-blockchain.github.io/global.config.json -O ton-lite-client-test1.config.json
# cd /usr/bin/ton/validator-engine
# wget https://newton-blockchain.github.io/global.config.json -O ton-global.config.json
systemctl restart validator

# mv /tmp/mytoninstaller/client /usr/bin/ton/validator-engine-console/client
# mv /tmp/mytoninstaller/client.pub /usr/bin/ton/validator-engine-console/client.pub
# mv /tmp/mytoninstaller/server.pub /usr/bin/ton/validator-engine-console/server.pub
# mv /tmp/mytoninstaller/liteserver.pub /usr/bin/ton/validator-engine-console/liteserver.pub

# fix me
rm -rf /usr/bin/ton2
rm -rf /usr/src/ton2
rm -f /etc/systemd/system/validator2.service
systemctl daemon-reload

# Конец
echo -e "${COLOR}[1/1]${ENDC} TON components update completed"
exit 0
