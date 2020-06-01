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
systemctl restart mytonctrl

# Конец
echo "${COLOR}[1/1]${ENDC} Обновление компонентов MyTonCtrl завершена"
