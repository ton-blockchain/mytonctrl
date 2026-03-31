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
tmp_src_dir="/tmp/ton_src/"
tmp_bin_dir="/tmp/ton_bin/"

# Get arguments
while getopts a:r:b:g: flag
do
	case "${flag}" in
		a) author=${OPTARG};;
		r) repo=${OPTARG};;
		b) branch=${OPTARG};;
    g) git_url=${OPTARG};;
	esac
done

remote_url="https://github.com/${author}/${repo}.git"
if [ -n "${git_url}" ]; then
  remote_url="${git_url}"
fi

# Цвета
COLOR='\033[92m'
ENDC='\033[0m'

# Установить дополнительные зависимости
apt-get install -y libsecp256k1-dev libsodium-dev ninja-build fio rocksdb-tools liblz4-dev libjemalloc-dev automake libtool

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

rm -rf ${tmp_src_dir}/${repo}
mkdir -p ${tmp_src_dir}/${repo}
cd ${tmp_src_dir}/${repo}
echo "${remote_url} -> ${branch}"
git clone --recursive ${remote_url} . || exit 1

# Go to work dir
cd ${srcdir}/${repo}
ls -A1 | xargs rm -rf

# Update code
cp -rfT ${tmp_src_dir}/${repo} .
git checkout ${branch}

git submodule sync --recursive
git submodule update

export CC=/usr/bin/clang
export CXX=/usr/bin/clang++
export CCACHE_DISABLE=1

# Update binary
rm -rf ${tmp_bin_dir}/${repo}
mkdir -p ${tmp_bin_dir}/${repo}
cd ${tmp_bin_dir}/${repo}
cpuNumber=$(cat /proc/cpuinfo | grep "processor" | wc -l)

cmake -DCMAKE_BUILD_TYPE=Release ${srcdir}/${repo} -GNinja -DTON_USE_JEMALLOC=ON || exit 1
ninja -j ${cpuNumber} fift validator-engine lite-client validator-engine-console generate-random-id dht-server func tonlibjson rldp-http-proxy create-state || exit 1
cd ${bindir}/${repo}
ls --hide="*.config.json" | xargs -d '\n' rm -rf
rm -rf .ninja_*
cp -r ${tmp_bin_dir}/${repo}/. .
systemctl restart validator

# Конец
echo -e "${COLOR}[1/1]${ENDC} TON components update completed"
exit 0
