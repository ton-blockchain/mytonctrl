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

db_path=/var/ton-work/db

function get_directory_size {
	buff=$(du -sh ${db_path} | awk '{print $1}')
	echo ${buff}
}

echo -e "${COLOR}[1/7]${ENDC} Start node/validator DB cleanup process"
echo -e "${COLOR}[2/7]${ENDC} Stop node/validator"
systemctl stop validator

echo -e "${COLOR}[3/7]${ENDC} Node/validator DB size before cleanup = $(get_directory_size)"
find /var/ton-work/db -name 'LOG.old*' -exec rm {} +

echo -e "${COLOR}[4/7]${ENDC} Node/validator DB size after deleting old files = $(get_directory_size)"
rm -r /var/ton-work/db/files/packages/temp.archive.*

echo -e "${COLOR}[5/7]${ENDC} Node/validator DB size after deleting temporary files = $(get_directory_size)"
echo -e "${COLOR}[6/7]${ENDC} Start node/validator"
systemctl start validator

echo -e "${COLOR}[7/7]${ENDC} Node/validator DB cleanup process completed"
