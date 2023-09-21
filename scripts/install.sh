#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

show_help_and_exit() {
    echo 'Supported argumets:'
    echo ' -m [lite|full]   Choose installation mode'
    echo ' -c  PATH         Provide custom config for toninstaller.sh'
    echo ' -t               Disable telemetry'
    echo ' -i               Ignore minimum reqiurements'
    echo ' -d               Use pre-packaged dump. Reduces duration of initial synchronization.'
    echo ' -h               Show this help'
    exit
}

if [[ "${1-}" =~ ^-*h(elp)?$ ]]; then
    show_help_and_exit
fi

# Get arguments
config="https://ton-blockchain.github.io/global.config.json"
telemetry=true
ignore=false
dump=false
while getopts m:c:tidh flag
do
	case "${flag}" in
		m) mode=${OPTARG};;
		c) config=${OPTARG};;
		t) telemetry=false;;
		i) ignore=true;;
		d) dump=true;;
        h) show_help_and_exit;;
        *)
            echo "Flag -${flag} is not recognized. Aborting"
            exit 1 ;;
	esac
done


# Проверка режима установки
if [ "${mode}" != "lite" ] && [ "${mode}" != "full" ]; then
	echo "Run script with flag '-m lite' or '-m full'"
	exit 1
fi

# Проверка мощностей
cpus=$(lscpu | grep "CPU(s)" | head -n 1 | awk '{print $2}')
memory=$(grep MemTotal /proc/meminfo | awk '{print $2}')
if [ "${mode}" = "lite" ] && [ "$ignore" = false ] && ([ "${cpus}" -lt 2 ] || [ "${memory}" -lt 2000000 ]); then
	echo "Insufficient resources. Requires a minimum of 2 processors and 2Gb RAM."
	exit 1
fi
if [ "${mode}" = "full" ] && [ "$ignore" = false ] && ([ "${cpus}" -lt 8 ] || [ "${memory}" -lt 8000000 ]); then
	echo "Insufficient resources. Requires a minimum of 8 processors and 8Gb RAM."
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
if [[ "$OSTYPE" =~ darwin.* ]]; then
	SOURCES_DIR=/usr/local/src
	BIN_DIR=/usr/local/bin
	mkdir -p ${SOURCES_DIR}
fi

# Проверяю наличие компонентов TON
echo -e "${COLOR}[2/4]${ENDC} Checking for required TON components"
file1=${BIN_DIR}/ton/crypto/fift
file2=${BIN_DIR}/ton/lite-client/lite-client
file3=${BIN_DIR}/ton/validator-engine-console/validator-engine-console
if [ -f "${file1}" ] && [ -f "${file2}" ] && [ -f "${file3}" ]; then
	echo "TON exist"
	cd $SOURCES_DIR
	rm -rf $SOURCES_DIR/mytonctrl
	git clone --recursive https://github.com/ton-blockchain/mytonctrl.git
else
	rm -f toninstaller.sh
	wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/toninstaller.sh
	bash toninstaller.sh -c "${config}"
	rm -f toninstaller.sh
fi

# Запускаю установщик mytoninstaller.py
echo -e "${COLOR}[3/4]${ENDC} Launching the mytoninstaller.py"
parent_name=$(ps -p $PPID -o comm=)
user=$(whoami)
if [ "$parent_name" = "sudo" ] || [ "$parent_name" = "su" ]; then
    user=$(logname)
fi
python3 ${SOURCES_DIR}/mytonctrl/mytoninstaller.py -m ${mode} -u ${user} -t ${telemetry} --dump ${dump}

# Выход из программы
echo -e "${COLOR}[4/4]${ENDC} Mytonctrl installation completed"
exit 0
