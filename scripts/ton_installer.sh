
#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Get arguments
config=https://ton-blockchain.github.io/global.config.json
while getopts c: flag
do
	case "${flag}" in
		c) config=${OPTARG};;
	esac
done

# Цвета
COLOR='\033[95m'
ENDC='\033[0m'

# На OSX нет такой директории по-умолчанию, поэтому создаем...
SOURCES_DIR=/usr/src
BIN_DIR=/usr/bin
if [[ "$OSTYPE" =~ darwin.* ]]; then
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
		yum install -y curl git make cmake clang gflags gflags-devel zlib zlib-devel openssl-devel openssl-libs readline-devel libmicrohttpd python3 python3-pip python36-devel
	elif [ -f /etc/SuSE-release ]; then
		echo "Suse Linux detected."
		echo "This OS is not supported with this script at present. Sorry."
		echo "Please refer to https://github.com/ton-blockchain/mytonctrl for setup information."
		exit 1
	elif [ -f /etc/arch-release ]; then
		echo "Arch Linux detected."
		pacman -Syuy
		pacman -S --noconfirm curl git make cmake clang gflags zlib openssl readline libmicrohttpd python python-pip
	elif [ -f /etc/debian_version ]; then
		echo "Ubuntu/Debian Linux detected."
		apt-get update
		apt-get install -y build-essential curl git cmake clang libgflags-dev zlib1g-dev libssl-dev libreadline-dev libmicrohttpd-dev pkg-config libgsl-dev python3 python3-dev python3-pip libsecp256k1-dev libsodium-dev

		# Install ninja
		apt-get install -y ninja-build

	else
		echo "Unknown Linux distribution."
		echo "This OS is not supported with this script at present. Sorry."
		echo "Please refer to https://github.com/ton-blockchain/mytonctrl for setup information."
		exit 1
	fi
elif [[ "$OSTYPE" =~ darwin.* ]]; then
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
	echo "Please refer to https://github.com/paritytech/substrate for setup information."  # TODO: remove links
	exit 1
else
	echo "Unknown operating system."
	echo "This OS is not supported with this script at present. Sorry."
	echo "Please refer to https://github.com/paritytech/substrate for setup information."  # TODO: remove links
	exit 1
fi

# Установка компонентов python3
pip3 install psutil crc16 requests

# build openssl 3.0
echo -e "${COLOR}[2/6]${ENDC} Building OpenSSL 3.0"
rm -rf $BIN_DIR/openssl_3
git clone --branch openssl-3.1.4 https://github.com/openssl/openssl $BIN_DIR/openssl_3
cd $BIN_DIR/openssl_3
opensslPath=`pwd`
git checkout 
./config
make build_libs -j$(nproc)

# Клонирование репозиториев с github.com
echo -e "${COLOR}[3/6]${ENDC} Preparing for compilation"
cd $SOURCES_DIR
rm -rf $SOURCES_DIR/ton
git clone --recursive https://github.com/ton-blockchain/ton.git
git config --global --add safe.directory $SOURCES_DIR/ton

# Подготавливаем папки для компиляции
rm -rf $BIN_DIR/ton
mkdir $BIN_DIR/ton
cd $BIN_DIR/ton

# Подготовиться к компиляции
if [[ "$OSTYPE" =~ darwin.* ]]; then
	export CMAKE_C_COMPILER=$(which clang)
	export CMAKE_CXX_COMPILER=$(which clang++)
	export CCACHE_DISABLE=1
else
	export CC=$(which clang)
	export CXX=$(which clang++)
	export CCACHE_DISABLE=1
fi

# Подготовиться к компиляции
if [[ "$OSTYPE" =~ darwin.* ]]; then
	if [[ $(uname -p) == 'arm' ]]; then
		echo M1
		CC="clang -mcpu=apple-a14" CXX="clang++ -mcpu=apple-a14" cmake $SOURCES_DIR/ton -DCMAKE_BUILD_TYPE=Release -DTON_ARCH= -Wno-dev
	else
		cmake -DCMAKE_BUILD_TYPE=Release $SOURCES_DIR/ton
	fi
else
	cmake -DCMAKE_BUILD_TYPE=Release $SOURCES_DIR/ton -GNinja -DOPENSSL_FOUND=1 -DOPENSSL_INCLUDE_DIR=$opensslPath/include -DOPENSSL_CRYPTO_LIBRARY=$opensslPath/libcrypto.a
fi

# Компилируем из исходников
echo -e "${COLOR}[4/6]${ENDC} Source Compilation"
if [[ "$OSTYPE" =~ darwin.* ]]; then
	cpuNumber=$(sysctl -n hw.logicalcpu)
else
	memory=$(cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
	cpuNumber=$(($memory/2100000))
	if [ ${cpuNumber} == 0 ]; then
		echo "Warning! insufficient RAM"
		cpuNumber=1
	fi
fi

echo "use ${cpuNumber} cpus"
ninja -j ${cpuNumber} fift validator-engine lite-client pow-miner validator-engine-console generate-random-id dht-server func tonlibjson rldp-http-proxy

# Скачиваем конфигурационные файлы lite-client
echo -e "${COLOR}[5/6]${ENDC} Downloading config files"
wget ${config} -O global.config.json

# Выход из программы
echo -e "${COLOR}[6/6]${ENDC} TON software installation complete"
exit 0
