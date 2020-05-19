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

#cd /usr/src/ton && git pull --recurse-submodules
#export CC=/usr/bin/clang
#export CXX=/usr/bin/clang++
#cd /usr/bin/ton && cmake /usr/src/ton && make -j

cd /usr/src/mytonctrl && git pull --recurse-submodules


# Конец
echo -e "${COLOR}[6/6]${ENDC} Обновление компонентов завершена"
