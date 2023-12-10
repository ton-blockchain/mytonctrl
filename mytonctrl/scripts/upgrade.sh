#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Set default arguments
author="ton-blockchain"
repo="ton"
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

# Установить дополнительные зависимости
apt-get install -y libsecp256k1-dev libsodium-dev ninja-build

# bugfix if the files are in the wrong place
wget "https://ton-blockchain.github.io/global.config.json" -O global.config.json
if [ -f "/var/ton-work/keys/liteserver.pub" ]; then
    echo "Ok"
else
	echo "bugfix"
	mkdir /var/ton-work/keys
    cp /usr/bin/ton/validator-engine-console/client /var/ton-work/keys/client
    cp /usr/bin/ton/validator-engine-console/client.pub /var/ton-work/keys/client.pub
    cp /usr/bin/ton/validator-engine-console/server.pub /var/ton-work/keys/server.pub
    cp /usr/bin/ton/validator-engine-console/liteserver.pub /var/ton-work/keys/liteserver.pub

	# fix validator.service
	sed -i 's/validator-engine\/ton-global.config.json/global.config.json/' /etc/systemd/system/validator.service
	systemctl daemon-reload
fi

# Go to work dir
cd ${srcdir}
rm -rf ${srcdir}/${repo}

# compile openssl_3
git clone --branch openssl-3.1.4 https://github.com/openssl/openssl ${bindir}/openssl_3
cd ${bindir}/openssl_3
./config
make build_libs -j$(nproc)
opensslPath=`pwd`

# Update code
echo "https://github.com/${author}/${repo}.git -> ${branch}"
git clone --branch ${branch} --recursive https://github.com/${author}/${repo}.git
cd ${repo}
export CC=/usr/bin/clang
export CXX=/usr/bin/clang++
export CCACHE_DISABLE=1

# Update binary
cd ${bindir}/${repo}
ls --hide=global.config.json | xargs -d '\n' rm -rf
rm -rf .ninja_*
memory=$(cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
let "cpuNumber = memory / 2100000" || cpuNumber=1

cmake -DCMAKE_BUILD_TYPE=Release ${srcdir}/${repo} -GNinja -DOPENSSL_FOUND=1 -DOPENSSL_INCLUDE_DIR=$opensslPath/include -DOPENSSL_CRYPTO_LIBRARY=$opensslPath/libcrypto.a
ninja -j ${cpuNumber} fift validator-engine lite-client pow-miner validator-engine-console generate-random-id dht-server func tonlibjson rldp-http-proxy
systemctl restart validator

# Конец
echo -e "${COLOR}[1/1]${ENDC} TON components update completed"
exit 0
