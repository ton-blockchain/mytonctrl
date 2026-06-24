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

tmp_src_dir="/tmp/ton_src/"
tmp_bin_dir="/tmp/ton_bin/"

# Get arguments
while getopts a:r:b:g:B:S: flag
do
	case "${flag}" in
		a) author=${OPTARG};;
		r) repo=${OPTARG};;
		b) branch=${OPTARG};;
    g) git_url=${OPTARG};;
    B) bindir=${OPTARG};;
    S) srcdir=${OPTARG};;
    *) echo "Unknown arg"
       exit 1;;
	esac
done

remote_url="https://github.com/${author}/${repo}.git"
if [ -n "${git_url}" ]; then
  remote_url="${git_url}"
fi

if [ -z "${srcdir}" ]; then
    srcdir="/usr/src/${repo}"
fi
if [ -z "${bindir}" ]; then
    bindir="/usr/bin/${repo}"
fi

# Цвета
COLOR='\033[92m'
ENDC='\033[0m'

# Установить дополнительные зависимости
apt-get install -y libsecp256k1-dev libsodium-dev ninja-build fio rocksdb-tools liblz4-dev libjemalloc-dev automake libtool

# bugfix if the files are in the wrong place
wget "https://ton-blockchain.github.io/global.config.json" -O global.config.json

rm -rf ${tmp_src_dir}/${repo}
mkdir -p ${tmp_src_dir}/${repo}
cd ${tmp_src_dir}/${repo}
echo "${remote_url} -> ${branch}"
git clone --recursive ${remote_url} . || exit 1

# Go to work dir
mkdir -p ${srcdir}
cd ${srcdir}
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

cmake -DCMAKE_BUILD_TYPE=Release ${srcdir} -GNinja -DTON_USE_JEMALLOC=ON || exit 1
ninja -j ${cpuNumber} fift validator-engine lite-client validator-engine-console generate-random-id dht-server func tonlibjson rldp-http-proxy create-state || exit 1
cd ${bindir}
ls --hide="*.config.json" | xargs -d '\n' rm -rf
rm -rf .ninja_*
cp -r ${tmp_bin_dir}/${repo}/. .
systemctl restart validator

# stop BTC Teleport
systemctl stop btc_teleport 2>/dev/null || true
systemctl disable btc_teleport 2>/dev/null || true
if [ -f /etc/systemd/system/btc_teleport.service ]; then
    rm -f /etc/systemd/system/btc_teleport.service
    systemctl daemon-reload
fi

echo -e "${COLOR}[1/1]${ENDC} TON components update completed"

# Patch wrappers
for wrapper in /usr/bin/mytonctrl /usr/bin/fift /usr/bin/lite-client /usr/bin/validator-console; do
		if [ -f "$wrapper" ]; then
			sed -i 's| \$@$| "$@"|' "$wrapper"
		fi
done

exit 0
