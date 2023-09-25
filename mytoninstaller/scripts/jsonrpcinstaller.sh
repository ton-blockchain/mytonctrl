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

author=kdimentionaltree
repo=mtc-jsonrpc
branch=master

echo "User: $user"
echo "Workdir: `pwd`"

# Цвета
COLOR='\033[95m'
ENDC='\033[0m'

# Установка компонентов python3
echo -e "${COLOR}[1/4]${ENDC} Installing required packages"
pip3 install Werkzeug json-rpc cloudscraper pyotp

# Клонирование репозиториев с github.com
echo -e "${COLOR}[2/4]${ENDC} Cloning github repository"
echo "https://github.com/${author}/${repo}.git -> ${branch}"

cd /usr/src/
rm -rf mtc-jsonrpc
git clone --branch=${branch} --recursive https://github.com/${author}/${repo}.git

# Прописать автозагрузку
echo -e "${COLOR}[3/4]${ENDC} Add to startup"
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
echo "Script dir: ${SCRIPT_DIR}"
${SCRIPT_DIR}/add2systemd.sh -n mtc-jsonrpc -s "/usr/bin/python3 /usr/src/mtc-jsonrpc/mtc-jsonrpc.py" -u ${user} -g ${user}
systemctl restart mtc-jsonrpc

# Выход из программы
echo -e "${COLOR}[4/4]${ENDC} JsonRPC installation complete"
exit 0
