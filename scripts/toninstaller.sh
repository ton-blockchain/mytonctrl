#!/bin/sh
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Цвета
COLOR='\033[95m'
ENDC='\033[0m'

# Установка требуемых пакетов
echo -e "${COLOR}[1/7]${ENDC} Installing required packages"

if [[ $(whoami) == "root" ]]; then
	MAKE_ME_ROOT=
else
	MAKE_ME_ROOT=sudo
fi

if [[ "$OSTYPE" == "linux-gnu" ]]; then
	set -e

	if hash yum 2>/dev/null; then
		echo "RHEL-based Linux detected."
		$MAKE_ME_ROOT yum install -y epel-release
		$MAKE_ME_ROOT dnf config-manager --set-enabled PowerTools
		$MAKE_ME_ROOT yum install -y git make cmake clang gflags gflags-devel zlib zlib-devel openssl-devel openssl-libs readline-devel libmicrohttpd python3 python3-pip python36-devel
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
		$MAKE_ME_ROOT apt update
		$MAKE_ME_ROOT apt-get install git make cmake clang libgflags-dev zlib1g-dev libssl-dev libreadline-dev libmicrohttpd-dev python3 python3-pip -y
	else
		echo "Unknown Linux distribution."
		echo "This OS is not supported with this script at present. Sorry."
		echo "Please refer to https://github.com/igroman787/mytonctrl for setup information."
		exit 1
	fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
	set -e
	echo "Mac OS (Darwin) detected."

	if ! which brew >/dev/null 2>&1; then
		$BIN_DIR/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
	fi

	echo "Please, write down your username, because brew package manager cannot be run under root user:"
	read LOCAL_USERNAME

	su $LOCAL_USERNAME -c "brew update"
	su $LOCAL_USERNAME -c "brew install openssl cmake llvm"
elif [[ "$OSTYPE" == "freebsd"* ]]; then
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

pip3 install wheel psutil crc16

# Клонирование репозиториев с github.com
echo -e "${COLOR}[2/7]${ENDC} Cloning github repository"

# На OSX нет такой директории по-умолчанию, поэтому создаем...
SOURCES_DIR=/usr/src
BIN_DIR=/usr/bin
if [[ "$OSTYPE" == "darwin"* ]]; then
	SOURCES_DIR=/usr/local/src
	BIN_DIR=/usr/local/bin
	$MAKE_ME_ROOT mkdir $SOURCES_DIR
fi

cd $SOURCES_DIR
rm -rf $SOURCES_DIR/ton
rm -rf $SOURCES_DIR/mytonctrl
git clone --recursive https://github.com/ton-blockchain/ton.git
git clone --recursive https://github.com/igroman787/mytonctrl.git

# Подготавливаем папки для компиляции
echo -e "${COLOR}[3/7]${ENDC} Preparing for compilation"
rm -rf $BIN_DIR/ton
mkdir $BIN_DIR/ton
cd $BIN_DIR/ton

# Подготовиться к компиляции
if [[ "$OSTYPE" == "darwin"* ]]; then
	export CMAKE_C_COMPILER=$(which clang)
	export CMAKE_CXX_COMPILER=$(which clang++)
else
	export CC=$BIN_DIR/clang
	export CXX=$BIN_DIR/clang++
fi

cmake $SOURCES_DIR/ton

# Компилируем из исходников
echo -e "${COLOR}[4/7]${ENDC} Source Compilation"
make # use only `make` if some error

# Скачиваем конфигурационные файлы lite-client
echo -e "${COLOR}[5/7]${ENDC} Downloading config files"
cd $BIN_DIR/ton/lite-client
#wget https://test.ton.org/ton-lite-client-test1.config.json
wget -O ton-lite-client-test1.config.json https://newton-blockchain.github.io/newton-test.global.config.json

# Скачиваем конфигурационные файлы validator-engine
cd $BIN_DIR/ton/validator-engine
#wget https://test.ton.org/ton-global.config.json
wget -O ton-global.config.json https://newton-blockchain.github.io/newton-test.global.config.json

# Создаем символические ссылки
echo -e "${COLOR}[6/7]${ENDC} Creating symbol links"
echo "$BIN_DIR/python3 $SOURCES_DIR/mytonctrl/mytonctrl.py" > $BIN_DIR/mytonctrl
echo "$BIN_DIR/ton/crypto/fift \$@" > $BIN_DIR/fift
echo "$BIN_DIR/ton/lite-client/lite-client -C $BIN_DIR/ton/lite-client/ton-lite-client-test1.config.json \$@" > $BIN_DIR/liteclient
echo "$BIN_DIR/ton/validator-engine-console/validator-engine-console \$@" > $BIN_DIR/validatorconsole
echo "export FIFTPATH=$SOURCES_DIR/ton/crypto/fift/lib/:$SOURCES_DIR/ton/crypto/smartcont/" >> /etc/environment
chmod +x $BIN_DIR/mytonctrl
chmod +x $BIN_DIR/fift
chmod +x $BIN_DIR/liteclient
chmod +x $BIN_DIR/validatorconsole

# Выход из программы
echo -e "${COLOR}[7/7]${ENDC} TON software installation complete"
exit 0
