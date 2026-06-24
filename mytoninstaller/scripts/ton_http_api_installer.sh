#!/bin/bash
set -e

# check sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

user=${SUDO_USER:-}
bindir="/usr/bin/ton"
ls_config="/usr/bin/ton/local.config.json"
mtc_python="python3"


while getopts u:b:c:p: flag
do
	case "${flag}" in
    u) user=${OPTARG};;
    b) bindir=${OPTARG};;
    c) ls_config=${OPTARG};;
    p) mtc_python=${OPTARG};;
    *) echo "Flag -${flag} is not recognized. Aborting"; exit 1 ;;
	esac
done

if [ -z "${user}" ]; then
	user=$(logname)
fi

# Цвета
COLOR='\033[92m'
ENDC='\033[0m'

# prepare the virtual environment
echo -e "${COLOR}[1/4]${ENDC} Preparing the virtual environment"
venv_path="/opt/virtualenv/ton_http_api"
apt-get install -y python3-venv
python3 -m venv ${venv_path}

# install python3 packages
echo -e "${COLOR}[2/4]${ENDC} Installing required packages"
venv_pip3="${venv_path}/bin/pip3"
${venv_pip3} install -U pip
${venv_pip3} install ton-http-api -U
chown -R ${user}:${user} ${venv_path}

# add to startup
echo -e "${COLOR}[3/4]${ENDC} Add to startup"
venv_ton_http_api="${venv_path}/bin/ton-http-api"
tonlib_path="${bindir}/tonlib/libtonlibjson.so"
cmd="from mytoninstaller.utils import add2systemd; add2systemd(name='ton_http_api', user='${user}', start='${venv_ton_http_api} --logs-level=INFO --host 127.0.0.1 --port 8801 --liteserver-config ${ls_config} --cdll-path ${tonlib_path} --tonlib-keystore /tmp/tonlib_keystore/')"
"${mtc_python}" -c "${cmd}"
systemctl daemon-reload
systemctl restart ton_http_api

# check connection
echo -e "Requesting masterchain info from local ton http api"
sleep 5
curl http://127.0.0.1:8801/getMasterchainInfo

# end
echo -e "${COLOR}[4/4]${ENDC} ton_http_api service installation complete"
exit 0
