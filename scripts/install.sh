#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Проверка режима установки
if [ "${1}" != "-m" ]; then
	echo "Run script with with flag '-m lite' or '-m full'"
	exit 1
fi

# Цвета
COLOR='\033[92m'
ENDC='\033[0m'

# Начинаю установку mytonctrl
echo -e "${COLOR}[1/4]${ENDC} Starting installation MyTonCtrl"
mydir=$(pwd)

# На OSX нет такой директории по-умолчанию, поэтому создаем...
SOURCES_DIR=/usr/src
BIN_DIR=/usr/bin
if [ "$OSTYPE" == "darwin"* ]; then
	SOURCES_DIR=/usr/local/src
	BIN_DIR=/usr/local/bin
	mkdir -p $SOURCES_DIR
fi

# Проверяю наличие компонентов TON
echo -e "${COLOR}[2/4]${ENDC} Checking for required TON components"
file1=$BIN_DIR/ton/crypto/fift
file2=$BIN_DIR/ton/lite-client/lite-client
file3=$BIN_DIR/ton/validator-engine-console/validator-engine-console
if [ -f "${file1}" ] && [ -f "${file2}" ] && [ -f "${file3}" ]; then
	echo "TON exist"
	cd $SOURCES_DIR
	rm -rf $SOURCES_DIR/mytonctrl
	git clone --recursive https://github.com/igroman787/mytonctrl.git
else
	rm -f toninstaller.sh
	wget https://raw.githubusercontent.com/igroman787/mytonctrl/master/scripts/toninstaller.sh
	bash toninstaller.sh
	rm -f toninstaller.sh
fi

# Запускаю установщик mytoninstaller.py
echo -e "${COLOR}[3/4]${ENDC} Launching the mytoninstaller.py"
user=$(ls -lh ${mydir}/${0} | cut -d ' ' -f 3)

if [ "${2}" == "--no_send_telemetry" ]; then
	python3 $SOURCES_DIR/mytonctrl/mytoninstaller.py -m ${2} -u ${user} --no_send_telemetry
else
	python3 $SOURCES_DIR/mytonctrl/mytoninstaller.py -m ${2} -u ${user}
fi

# Выход из программы
echo -e "${COLOR}[4/4]${ENDC} Mytonctrl installation completed"
exit 0
