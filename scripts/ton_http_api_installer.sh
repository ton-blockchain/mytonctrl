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

# Установка компонентов python3
pip3 install virtualenv

# Подготовить папку с виртуальным окружением
echo -e "${COLOR}[1/4]${ENDC} Preparing the virtual environment"
venv_path="/opt/virtualenv/ton_http_api"
virtualenv ${venv_path}

# Установка компонентов python3
echo -e "${COLOR}[2/4]${ENDC} Installing required packages"
user=$(logname)
venv_pip3="${venv_path}/bin/pip3"
${venv_pip3} install ton-http-api
chown -R ${user}:${user} ${venv_path}

# Прописать автозагрузку
echo -e "${COLOR}[3/4]${ENDC} Add to startup"
venv_ton_http_api="${venv_path}/bin/ton-http-api"
tonlib_path="/usr/bin/ton/tonlib/libtonlibjson.so"
ls_config="/usr/bin/ton/localhost.config.json"
cmd="from sys import path; path.append('/usr/src/mytonctrl/'); from mypylib.mypylib import add2systemd; add2systemd(name='ton_http_api', user='${user}', start='${venv_ton_http_api} --host 127.0.0.1 --port 8801 --liteserver-config ${ls_config} --cdll-path ${tonlib_path} --tonlib-keystore /tmp/tonlib_keystore/')"
python3 -c "${cmd}"
systemctl restart ton_http_api

# Конец
echo -e "${COLOR}[4/4]${ENDC} ton_http_api service installation complete"
exit 0
