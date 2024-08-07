#!/bin/bash
set -e

# import functions: check_superuser, check_go_version
my_dir=$(dirname $(realpath ${0}))
. ${my_dir}/utils.sh

# Проверить sudo
check_superuser

# install parameters
src_path=/usr/src
bin_path=/usr/bin

# Get arguments
while getopts u:s:b: flag
do
	case "${flag}" in
		u) user=${OPTARG};;
		s) src_path=${OPTARG};;
		b) bin_path=${OPTARG};;
		*)
			echo "Flag -${flag} is not recognized. Aborting"
			exit 1;;
	esac
done

# install parameters
author=xssnick
repo=tonutils-storage-provider
branch=master
bin_name=ton_storage_provider

# Цвета
COLOR='\033[95m'
ENDC='\033[0m'

# Клонирование репозиториев с github.com
echo -e "${COLOR}[1/4]${ENDC} Cloning github repository"
echo "https://github.com/${author}/${repo}.git -> ${branch}"

package_src_path="${src_path}/${repo}"
rm -rf ${package_src_path}

cd ${src_path}
git clone --branch=${branch} --recursive https://github.com/${author}/${repo}.git

# Установка компонентов
echo -e "${COLOR}[2/4]${ENDC} Installing required packages"
go_path=/usr/local/go/bin/go
check_go_version "${package_src_path}/go.mod" ${go_path}

# Компилируем из исходников
echo -e "${COLOR}[3/4]${ENDC} Source compilation"

# Создать директорию работы
db_path="/var/${bin_name}"
mkdir -p ${db_path}

# Компилируем
cd ${package_src_path}
#entry_point=$(find ${package_src_path} -name "main.go" | head -n 1)
CGO_ENABLED=1 ${go_path} build -o ${db_path}/${bin_name} ${package_src_path}/cmd/main.go

# Настроить директорию работы
chown -R ${user}:${user} ${db_path}

# Выход из программы
echo -e "${COLOR}[4/4]${ENDC} ${bin_name} installation complete"
exit 0
