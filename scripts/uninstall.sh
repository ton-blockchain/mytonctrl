#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

rm -rf /usr/src/ton
rm -rf /usr/src/mytonctrl
rm -rf /usr/bin/ton
rm -rf /var/ton-work
rm -rf /tmp/myton*
rm -rf /usr/loca/bin/myton*
rm -rf ~/.local/share/mytonctrl
rm -rf ~/.local/share/mytoncore/mytoncore.db
