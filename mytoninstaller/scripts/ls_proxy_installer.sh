#!/bin/bash
set -e

# import functions: check_superuser, get_cpu_number, check_go_version
my_dir=$(dirname $(realpath ${0}))
. ${my_dir}/utils.sh

# Проверить sudo
check_superuser

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


package_src_path=${src_path}/${repo}
rm -rf ${package_src_path}

cd ${src_path}
git clone --branch=${branch} --recursive https://github.com/${author}/${repo}.git

# Установка компонентов
echo -e "${COLOR}[2/4]${ENDC} Installing required packages"
go_path=/usr/local/go/bin/go
check_go_version "${package_src_path}/go.mod" ${go_path}

# Компилируем из исходников
cpu_number=$(get_cpu_number)
echo -e "${COLOR}[3/4]${ENDC} Source compilation, use ${cpu_number} cpus"

ton_src_path=${package_src_path}/ton
proxy_internal_path=${package_src_path}/internal/emulate/lib

proxy_build_path=${bin_path}/${bin_name}
ton_build_path=${proxy_build_path}/ton
db_path=/var/${bin_name}
lib_path=${db_path}/lib

mkdir -p ${lib_path}
mkdir -p ${ton_build_path} && cd ${ton_build_path}
cmake -DCMAKE_BUILD_TYPE=Release -DOPENSSL_FOUND=1 -DOPENSSL_INCLUDE_DIR=${openssl_path}/include -DOPENSSL_CRYPTO_LIBRARY=${openssl_path}/libcrypto.a ${ton_src_path}
make emulator -j ${cpu_number}
cp ${ton_build_path}/emulator/libemulator.so ${lib_path}
cp ${ton_build_path}/emulator/libemulator.so ${proxy_internal_path}
cp ${ton_build_path}/emulator/emulator_export.h ${proxy_internal_path}

# Компилируем
cd ${package_src_path}
entry_point=$(find ${package_src_path} -name "main.go" | head -n 1)
CGO_ENABLED=1 ${go_path} build -o ${db_path}/${bin_name} ${entry_point}

# Настроить директорию работы
chown -R ${user}:${user} ${db_path}

# Выход из программы
echo -e "${COLOR}[4/4]${ENDC} ${bin_name} installation complete"
exit 0