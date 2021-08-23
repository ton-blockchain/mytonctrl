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

#fix me
mkdir -p /var/ton-work/keys
cp -p /usr/bin/ton/validator-engine-console/client /var/ton-work/keys/client
cp -p /usr/bin/ton/validator-engine-console/client.pub /var/ton-work/keys/client.pub
cp -p /usr/bin/ton/validator-engine-console/server.pub /var/ton-work/keys/server.pub
cp -p /usr/bin/ton/validator-engine-console/liteserver.pub /var/ton-work/keys/liteserver.pub


# Конец
echo -e "${COLOR}[1/1]${ENDC} MyTonCtrl components update completed"
exit 0
