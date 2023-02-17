#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Get arguments
while getopts u: flag
do
	case "${flag}" in
		u) user=${OPTARG};;
	esac
done

# Цвета
COLOR='\033[92m'
ENDC='\033[0m'

# Установка компонентов python3
echo -e "${COLOR}[1/3]${ENDC} Installing required packages"
pip3 install -U ton-http-api

# Установка модуля
echo -e "${COLOR}[2/3]${ENDC} Add to startup"
mkdir -p /var/ton-http-api/ton_keystore/
chown -R $user /var/ton-http-api/

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cmd="ton-http-api --port=8000 --logs-level=INFO --cdll-path=/usr/bin/ton/tonlib/libtonlibjson.so --liteserver-config /usr/bin/ton/local.config.json --tonlib-keystore=/var/ton-http-api/ton_keystore/ --parallel-requests-per-liteserver=1024"
${SCRIPT_DIR}/add2systemd.sh -n ton-http-api -s "${cmd}" -u ${user} -g ${user}
systemctl restart ton-http-api

# Конец
echo -e "${COLOR}[3/3]${ENDC} TonHttpApi installation complete"
exit 0
