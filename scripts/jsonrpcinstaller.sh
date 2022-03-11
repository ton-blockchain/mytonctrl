#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Get arguments
while getopts u: flag
do
	case "${flag}" in
		u) user=${OPTARG};;
	esac
done

# Цвета
COLOR='\033[95m'
ENDC='\033[0m'

# Установка компонентов python3
echo -e "${COLOR}[1/4]${ENDC} Installing required packages"
pip3 install Werkzeug json-rpc cloudscraper pyotp

# Клонирование репозиториев с github.com
echo -e "${COLOR}[2/4]${ENDC} Cloning github repository"
cd /usr/src/
rm -rf mtc-jsonrpc
git clone --recursive https://github.com/igroman787/mtc-jsonrpc.git

# Прописать автозагрузку
echo -e "${COLOR}[3/4]${ENDC} Add to startup"
cmd="from sys import path; path.append('/usr/src/mytonctrl/'); from mypylib.mypylib import *; Add2Systemd(name='mtc-jsonrpc', user='${user}', start='/usr/bin/python3 /usr/src/mtc-jsonrpc/mtc-jsonrpc.py')"
python3 -c "${cmd}"
systemctl restart mtc-jsonrpc

# Выход из программы
echo -e "${COLOR}[4/4]${ENDC} JsonRPC installation complete"
exit 0
