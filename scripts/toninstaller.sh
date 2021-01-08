#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Цвета
COLOR='\033[95m'
ENDC='\033[0m'

# На OSX нет такой директории по-умолчанию, поэтому создаем...
SOURCES_DIR=/usr/src
BIN_DIR=/usr/bin
if [ "$OSTYPE" == "darwin"* ]; then
	SOURCES_DIR=/usr/local/src
	BIN_DIR=/usr/local/bin
	mkdir -p $SOURCES_DIR
fi

# Установка требуемых пакетов
echo -e "${COLOR}[1/6]${ENDC} Installing required packages"
if [ "$OSTYPE" == "linux-gnu" ]; then
	if [ hash yum 2>/dev/null ]; then
		echo "RHEL-based Linux detected."
		yum install -y epel-release
		dnf config-manager --set-enabled PowerTools
		yum install -y git make cmake clang gflags gflags-devel zlib zlib-devel openssl-devel openssl-libs readline-devel libmicrohttpd python3 python3-pip python36-devel
	elif [ -f /etc/SuSE-release ]; then
		echo "Suse Linux detected."
		echo "This OS is not supported with this script at present. Sorry."
		echo "Please refer to https://github.com/igroman787/mytonctrl for setup information."
		exit 1
	elif [ -f /etc/arch-release ]; then
		echo "Arch Linux detected."
		echo "This OS is not supported with this script at present. Sorry."
		echo "Please refer to https://github.com/igroman787/mytonctrl for setup information."
		exit 1
	elif [ -f /etc/debian_version ]; then
		echo "Ubuntu/Debian Linux detected."
		apt-get update
		apt-get install -y git make cmake clang libgflags-dev zlib1g-dev libssl-dev libreadline-dev libmicrohttpd-dev pkg-config libgsl-dev python3 python3-pip
	else
		echo "Unknown Linux distribution."
		echo "This OS is not supported with this script at present. Sorry."
		echo "Please refer to https://github.com/igroman787/mytonctrl for setup information."
		exit 1
	fi
elif [ "$OSTYPE" == "darwin"* ]; then
	echo "Mac OS (Darwin) detected."
	if [ ! which brew >/dev/null 2>&1 ]; then
		$BIN_DIR/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
	fi

	echo "Please, write down your username, because brew package manager cannot be run under root user:"
	read LOCAL_USERNAME
	
	su $LOCAL_USERNAME -c "brew update"
	su $LOCAL_USERNAME -c "brew install openssl cmake llvm"
elif [ "$OSTYPE" == "freebsd"* ]; then
	echo "FreeBSD detected."
	echo "This OS is not supported with this script at present. Sorry."
	echo "Please refer to https://github.com/paritytech/substrate for setup information."
	exit 1
else
	echo "Unknown operating system."
	echo "This OS is not supported with this script at present. Sorry."
	echo "Please refer to https://github.com/paritytech/substrate for setup information."
	exit 1
fi

# Установка компонентов python3
pip3 install psutil crc16 requests

# Клонирование репозиториев с github.com
echo -e "${COLOR}[2/6]${ENDC} Cloning github repository"
cd $SOURCES_DIR
rm -rf $SOURCES_DIR/ton
rm -rf $SOURCES_DIR/mytonctrl
git clone --recursive https://github.com/newton-blockchain/ton.git
git clone --recursive https://github.com/igroman787/mytonctrl.git


# Подготавливаем папки для компиляции
echo -e "${COLOR}[3/6]${ENDC} Preparing for compilation"
rm -rf $BIN_DIR/ton
mkdir $BIN_DIR/ton
cd $BIN_DIR/ton

# Подготовиться к компиляции
if [ "$OSTYPE" == "darwin"* ]; then
	export CMAKE_C_COMPILER=$(which clang)
	export CMAKE_CXX_COMPILER=$(which clang++)
else
	export CC=$(which clang)
	export CXX=$(which clang++)
fi

# Подготовиться к компиляции
cmake $SOURCES_DIR/ton

# Компилируем из исходников
echo -e "${COLOR}[4/6]${ENDC} Source Compilation"
memory=$(cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
let "cpuNumber = memory / 2100000"
echo "use ${cpuNumber} cpus"
make -j ${cpuNumber}

# Скачиваем конфигурационные файлы lite-client
echo -e "${COLOR}[5/6]${ENDC} Downloading config files"
cd $BIN_DIR/ton/lite-client
wget https://newton-blockchain.github.io/ton-lite-client-test1.config.json

# Скачиваем конфигурационные файлы validator-engine
cd $BIN_DIR/ton/validator-engine
wget https://newton-blockchain.github.io/ton-global.config.json

# Выход из программы
echo -e "${COLOR}[6/6]${ENDC} TON software installation complete"
exit 0
