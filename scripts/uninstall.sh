#!/bin/bash
full=true
while getopts f flag; do
	case "${flag}" in
		f) full=false
	esac
done

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
if $full; then
	echo "removing Ton node"
	rm -rf /usr/src/ton
	rm -rf /usr/bin/ton
	rm -rf /var/ton-work
	rm -rf /var/ton-dht-server
fi

rm -rf /usr/src/mytonctrl
rm -rf /usr/src/mtc-jsonrpc
rm -rf /usr/src/pytonv3
rm -rf /tmp/myton*
rm -rf /usr/local/bin/mytoninstaller/
rm -rf /usr/local/bin/mytoncore/mytoncore.db
rm -rf /home/${user}/.local/share/mytonctrl
rm -rf /home/${user}/.local/share/mytoncore/mytoncore.db

# Удаление ссылок
if $full; then
	echo "removing ton node"
	rm -rf /usr/bin/fift
	rm -rf /usr/bin/liteclient
	rm -rf /usr/bin/validator-console
fi
rm -rf /usr/bin/mytonctrl

# removing pip packages
pip3 uninstall -y mytonctrl
pip3 uninstall -y ton-http-api

# Конец
echo -e "${COLOR}Uninstall Complete${ENDC}"
