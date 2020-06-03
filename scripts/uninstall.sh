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

# Удаление файлов
rm -rf /usr/src/ton
rm -rf /usr/src/mytonctrl
rm -rf /usr/bin/ton
rm -rf /var/ton-work
rm -rf /tmp/myton*
rm -rf /usr/loca/bin/myton*
rm -rf ~/.local/share/mytonctrl
rm -rf ~/.local/share/mytoncore/mytoncore.db

# Удаление ссылок
rm -rf /usr/bin/fift
rm -rf /usr/bin/liteclient
rm -rf /usr/bin/validator-console
rm -rf /usr/bin/mytonctrl

# Конец
echo -e "${COLOR}Uninstall Complete${ENDC}"
