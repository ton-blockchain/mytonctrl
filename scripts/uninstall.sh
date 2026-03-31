#!/bin/bash
full=true
while getopts "f" flag; do
	case "${flag}" in
		f) full=false ;;
		*) echo "Usage: $0 [-f]"; exit 1 ;;
	esac
done

if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

COLOR='\033[34m'
ENDC='\033[0m'

systemctl stop validator
systemctl stop mytoncore
systemctl stop dht-server
systemctl stop btc_teleport
systemctl stop ton_storage

str=$(systemctl cat mytoncore | grep User | cut -d '=' -f2)
user=$(echo ${str})

rm -rf /etc/systemd/system/validator.service
rm -rf /etc/systemd/system/mytoncore.service
rm -rf /etc/systemd/system/dht-server.service
rm -rf /etc/systemd/system/btc_teleport.service
rm -rf /etc/systemd/system/ton_storage.service

systemctl daemon-reload

if $full; then
	echo "removing Ton node"
	rm -rf /usr/src/ton
	rm -rf /usr/bin/ton
	rm -rf /var/ton-work
	rm -rf /var/ton-dht-server
fi

rm -rf /usr/src/mytonctrl
rm -rf /usr/src/ton-teleport-btc-periphery
rm -rf /usr/src/tonutils-storage
rm -rf /var/ton_storage
rm -rf /usr/src/mtc-jsonrpc
rm -rf /usr/src/pytonv3
rm -rf /tmp/myton*
rm -rf /usr/local/bin/mytoninstaller/
rm -rf /usr/local/bin/mytoncore/mytoncore.db
rm -rf /home/${user}/.local/share/mytonctrl
rm -rf /home/${user}/.local/share/mytoncore/mytoncore.db

if $full; then
	echo "removing ton node"
	rm -rf /usr/bin/fift
	rm -rf /usr/bin/liteclient
	rm -rf /usr/bin/validator-console
fi
rm -rf /usr/bin/mytonctrl

pip3 uninstall -y mytonctrl
pip3 uninstall -y ton-http-api

echo -e "${COLOR}Uninstall Complete${ENDC}"
