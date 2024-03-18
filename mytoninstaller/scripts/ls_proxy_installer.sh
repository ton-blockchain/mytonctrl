#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# install parameters
src_path=/usr/src
bin_path=/usr/bin
openssl_path=${bin_path}/openssl_3

# Get arguments
while getopts u:s:b:o: flag
do
	case "${flag}" in
		u) user=${OPTARG};;
		s) src_path=${OPTARG};;
		b) bin_path=${OPTARG};;
		o) openssl_path=${OPTARG};;
		*)
			echo "Flag -${flag} is not recognized. Aborting"
			exit 1;;
	esac
done

# install parameters
author=xssnick
repo=tonutils-liteserver-proxy
branch=master
bin_name=ls_proxy

# Цвета
COLOR='\033[95m'
ENDC='\033[0m'

# Клонирование репозиториев с github.com
echo -e "${COLOR}[1/4]${ENDC} Cloning github repository"
echo "https://github.com/${author}/${repo}.git -> ${branch}"

cd ${src_path}
rm -rf ${repo}
git clone --branch=${branch} --recursive https://github.com/${author}/${repo}.git

# Установка компонентов
echo -e "${COLOR}[2/4]${ENDC} Installing required packages"

arc=$(dpkg --print-architecture)
go_version_url=https://go.dev/VERSION?m=text
go_version=$(curl -s ${go_version_url} | head -n 1)
go_url=https://go.dev/dl/${go_version}.linux-${arc}.tar.gz
go_path=/usr/local/go/bin/go
rm -rf /usr/local/go
wget -c ${go_url} -O - | tar -C /usr/local -xz

# Расчитываем количество процессоров для сборки
if [[ "$OSTYPE" =~ darwin.* ]]; then
	cpu_number=$(sysctl -n hw.logicalcpu)
else
	memory=$(cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
	cpu_number=$(($memory/2100000))
	max_cpu_number=$(nproc)
	if [ ${cpu_number} -gt ${max_cpu_number} ]; then
		cpu_number=$((${max_cpu_number}-1))
	fi
	if [ ${cpu_number} == 0 ]; then
		echo "Warning! insufficient RAM"
		cpu_number=1
	fi
fi

# Компилируем из исходников
echo -e "${COLOR}[3/4]${ENDC} Source compilation, use ${cpu_number} cpus"

proxy_src_path=${src_path}/${repo}
ton_src_path=${proxy_src_path}/ton
proxy_internal_path=${proxy_src_path}/internal/emulate/lib

proxy_build_path=${bin_path}/${bin_name}
ton_build_path=${proxy_build_path}/ton
proxy_db_path=/var/${bin_name}
proxy_lib_path=${proxy_db_path}/lib

mkdir -p ${proxy_lib_path}
mkdir -p ${ton_build_path} && cd ${ton_build_path}
cmake -DCMAKE_BUILD_TYPE=Release -DOPENSSL_FOUND=1 -DOPENSSL_INCLUDE_DIR=${openssl_path}/include -DOPENSSL_CRYPTO_LIBRARY=${openssl_path}/libcrypto.a ${ton_src_path}
make emulator -j ${cpu_number}
cp ${ton_build_path}/emulator/libemulator.so ${proxy_lib_path}
cp ${ton_build_path}/emulator/libemulator.so ${proxy_internal_path}
cp ${ton_build_path}/emulator/emulator_export.h ${proxy_internal_path}

# Компилируем
cd ${proxy_src_path}
CGO_ENABLED=1 ${go_path} build -o ${proxy_db_path}/${bin_name} ${proxy_src_path}/cmd/main.go

# Настроить директорию работы
chown -R ${user}:${user} ${proxy_db_path}

# Выход из программы
echo -e "${COLOR}[4/4]${ENDC} ${bin_name} installation complete"
exit 0
