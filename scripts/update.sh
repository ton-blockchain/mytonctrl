#!/bin/sh
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Запустите скрипт от имени администратора"
	exit 1
fi

# Цвета
COLOR='\033[92m'
ENDC='\033[0m'

cd /usr/src/mytonctrl
git pull --recurse-submodules
systemctl restart mytoncore

# Скачать свежий конфиг
wget https://newton-blockchain.github.io/global.config.json -O /usr/bin/ton/lite-client/ton-lite-client-test1.config.json

# Конец
echo -e "${COLOR}[1/1]${ENDC} MyTonCtrl components update completed"
exit 0
