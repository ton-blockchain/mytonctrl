#!/bin/sh

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Запустите скрипт от имени администратора"
	exit 1
fi

# Цвета
COLOR='\033[92m'
ENDC='\033[0m'

cd /usr/src/ton &&
git pull &&
cd /usr/bin/ton &&


# Конец
echo -e "${COLOR}[6/6]${ENDC} Обновление компонентов завершена"
