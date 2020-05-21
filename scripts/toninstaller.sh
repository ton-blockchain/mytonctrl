#!/bin/sh
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please, run script as root"
	exit 1
fi

# Цвета
COLOR='\033[95m'
ENDC='\033[0m'

# Установка требуемых пакетов
echo -e "${COLOR}[1/7]${ENDC} Installing required packages"
apt-get install git make cmake clang libgflags-dev zlib1g-dev libssl-dev libreadline-dev python3-setuptools libmicrohttpd-dev python3 python3-pip -y
pip3 install psutil crc16

# Клонирование репозиториев с github.com
echo -e "${COLOR}[2/7]${ENDC} Cloning github repository"
cd /usr/src
rm -rf /usr/src/ton
rm -rf /usr/src/mytonctrl
git clone --recursive https://github.com/ton-blockchain/ton.git
git clone --recursive https://github.com/dinamicby/mytonctrl.git

# Подготавливаем папки для компиляции
echo -e "${COLOR}[3/7]${ENDC} Preparing for compilation"
rm -rf /usr/bin/ton
mkdir /usr/bin/ton
cd /usr/bin/ton

# Подготовиться к компиляции
export CC=/usr/bin/clang
export CXX=/usr/bin/clang++
cmake /usr/src/ton

# Компилируем из исходников
echo -e "${COLOR}[4/7]${ENDC} Source Compilation"
make # use only `make` if some error

# Скачиваем конфигурационные файлы lite-client
echo -e "${COLOR}[5/7]${ENDC} Downloading config files"
cd /usr/bin/ton/lite-client
#wget https://test.ton.org/ton-lite-client-test1.config.json
wget -O ton-lite-client-test1.config.json https://newton-blockchain.github.io/newton-test.global.config.json

# Скачиваем конфигурационные файлы validator-engine
cd /usr/bin/ton/validator-engine
#wget https://test.ton.org/ton-global.config.json
wget -O ton-global.config.json https://newton-blockchain.github.io/newton-test.global.config.json

# Создаем символические ссылки
echo -e "${COLOR}[6/7]${ENDC} Creating symbol links"
echo "/usr/bin/python3 /usr/src/mytonctrl/mytonctrl.py" > /usr/bin/mytonctrl
echo "/usr/bin/ton/crypto/fift \$@" > /usr/bin/fift
echo "/usr/bin/ton/lite-client/lite-client -C /usr/bin/ton/lite-client/ton-lite-client-test1.config.json \$@" > /usr/bin/liteclient
echo "/usr/bin/ton/validator-engine-console/validator-engine-console \$@" > /usr/bin/validatorconsole
echo "export FIFTPATH=/usr/src/ton/crypto/fift/lib/:/usr/src/ton/crypto/smartcont/" >> /etc/environment
chmod +x /usr/bin/mytonctrl
chmod +x /usr/bin/fift
chmod +x /usr/bin/liteclient
chmod +x /usr/bin/validatorconsole

# Выход из программы
echo -e "${COLOR}[7/7]${ENDC} TON software installation complete"
exit 0
