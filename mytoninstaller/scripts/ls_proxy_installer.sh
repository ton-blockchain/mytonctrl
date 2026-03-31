#!/bin/bash
set -e

# import functions: check_superuser, get_cpu_number, check_go_version
my_dir=$(dirname $(realpath ${0}))
. ${my_dir}/utils.sh

# Проверить sudo
check_superuser

# install parameters
src_path=/usr/src

# Get arguments
while getopts u:s: flag
do
	case "${flag}" in
		u) user=${OPTARG};;
		s) src_path=${OPTARG};;
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

echo -e "${COLOR}[1/3]${ENDC} Cloning github repository"
echo "https://github.com/${author}/${repo}.git -> ${branch}"

package_src_path=${src_path}/${repo}
rm -rf ${package_src_path}

cd ${src_path}
git clone --branch=${branch} https://github.com/${author}/${repo}.git

echo -e "${COLOR}[2/3]${ENDC} Installing required packages"
go_path=/usr/local/go/bin/go
check_go_version "${package_src_path}/go.mod" ${go_path}

db_path=/var/${bin_name}
mkdir -p ${db_path}

cd "${package_src_path}"
${go_path} build -o ${db_path}/${bin_name} cmd/main.go

chown -R ${user}:${user} ${db_path}

echo -e "${COLOR}[3/3]${ENDC} ${bin_name} installation complete"
