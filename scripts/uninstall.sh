#!/bin/bash

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Цвета
COLOR='\033[34m'
ENDC='\033[0m'

# Остановка служб
systemctl stop validator
systemctl stop mytoncore
systemctl stop dht-server

# Переменные
str=$(systemctl cat mytoncore | grep User | cut -d '=' -f2)
user=$(echo ${str})

# Удаление служб
rm -rf /etc/systemd/system/validator.service
rm -rf /etc/systemd/system/mytoncore.service
rm -rf /etc/systemd/system/dht-server.service
systemctl daemon-reload

# Удаление файлов
rm -rf /usr/src/ton
rm -rf /usr/src/mytonctrl
rm -rf /usr/bin/ton
rm -rf /var/ton-work
rm -rf /var/ton-dht-server
rm -rf /tmp/myton*
rm -rf /usr/local/bin/mytoninstaller/
rm -rf /usr/local/bin/mytoncore/mytoncore.db
rm -rf /home/${user}/.local/share/mytonctrl
rm -rf /home/${user}/.local/share/mytoncore/mytoncore.db

# Удаление ссылок
rm -rf /usr/bin/fift
rm -rf /usr/bin/liteclient
rm -rf /usr/bin/validator-console
rm -rf /usr/bin/mytonctrl

# Конец
echo -e "${COLOR}Uninstall Complete${ENDC}"
