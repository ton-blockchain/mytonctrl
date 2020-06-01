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

cd /usr/src/ton
git pull --recurse-submodules
export CC=/usr/bin/clang
export CXX=/usr/bin/clang++

cd /usr/bin/ton
systemctl stop ton-validator && sleep 5
memory=$(cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
let "cpuNumber = memory / 2100000"
cmake /usr/src/ton && make -j ${cpuNumber}
systemctl start ton-validator


# Конец
echo "${COLOR}[1/1]${ENDC} Обновление компонентов TON завершена"
