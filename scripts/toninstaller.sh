#!/bin/bash
set -e

# Проверить sudo
if [ "$(id -u)" != "0" ]; then
	echo "Please run script as root"
	exit 1
fi

# Get arguments
config="https://ton-blockchain.github.io/global.config.json"
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

	# Determine if it is a CentOS system
	if cat /etc/*release | grep ^NAME | grep CentOS ; then
		echo "CentOS Linux detected."
		yum update -y
		yum install -y epel-release
		yum install -y git gflags gflags-devel zlib zlib-devel openssl-devel openssl-libs readline-devel libmicrohttpd python3 python3-pip python36-devel g++ gcc libstdc++-devel zlib1g-dev libssl-dev which make gcc-c++ libstdc++-devel 
		
		# Upgrade make and gcc in CentOS system
		yum install centos-release-scl -y
		yum install devtoolset-10 -y
		echo "source /opt/rh/devtoolset-10/enable" >> /etc/bashrc
		source /opt/rh/devtoolset-10/enable

		# Install the new version of CMake
		yum remove cmake -y
		wget https://cmake.org/files/v3.24/cmake-3.24.2.tar.gz
		tar -zxvf cmake-3.24.2.tar.gz
		cd cmake-3.24.2 && ./bootstrap && make -j -j$(nproc) && make install
		yum remove cmake -y
		ln -s /usr/local/bin/cmake /usr/bin/cmake
		source ~/.bashrc
		cmake --version

		# Install ninja
		yum install -y ninja-build

	# Red Hat systems are not supported
	elif cat /etc/*release | grep ^NAME | grep Red ; then
		echo "Red Hat Linux detected."
		echo "This OS is not supported with this script at present. Sorry."
		echo "Please refer to https://github.com/ton-blockchain/mytonctrl for setup information."
		exit 1
	
	# Suse systems are not supported
	elif [ -f /etc/SuSE-release ]; then
		echo "Suse Linux detected."
		echo "This OS is not supported with this script at present. Sorry."
		echo "Please refer to https://github.com/ton-blockchain/mytonctrl for setup information."
		exit 1

	elif [ -f /etc/arch-release ]; then
		echo "Arch Linux detected."
		pacman -Syuy  --noconfirm
		pacman -S --noconfirm git cmake clang gflags zlib openssl readline libmicrohttpd python python-pip

		# Install ninja
		pacman -S  --noconfirm ninja

	elif [ -f /etc/debian_version ]; then
		echo "Ubuntu/Debian Linux detected."
		apt-get update
		apt-get install -y build-essential git cmake clang libgflags-dev zlib1g-dev libssl-dev libreadline-dev libmicrohttpd-dev pkg-config libgsl-dev python3 python3-dev python3-pip libsecp256k1-dev libsodium-dev liblz4-dev libjemalloc-dev

		# Install ninja
		apt-get install -y ninja-build

	else
		echo "Unknown Linux distribution."
		echo "This OS is not supported with this script at present. Sorry."
		echo "Please refer to https://github.com/ton-blockchain/mytonctrl for setup information."
		exit 1
	fi

# Detected mac os system.	
elif [[ "$OSTYPE" =~ darwin.* ]]; then
	echo "Mac OS (Darwin) detected."
	if [ ! which brew >/dev/null 2>&1 ]; then
		$BIN_DIR/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
	fi

	echo "Please, write down your username, because brew package manager cannot be run under root user:"
	read LOCAL_USERNAME
	
	su $LOCAL_USERNAME -c "brew update"
	su $LOCAL_USERNAME -c "brew install openssl cmake llvm"

	# Install ninja
	su $LOCAL_USERNAME -c "brew install ninja"

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
pip3 install psutil fastcrc requests

# Клонирование репозиториев с github.com
echo -e "${COLOR}[2/6]${ENDC} Cloning github repository"
cd $SOURCES_DIR
rm -rf $SOURCES_DIR/ton
rm -rf $SOURCES_DIR/mytonctrl
git clone --recursive https://github.com/ton-blockchain/ton.git
git clone --recursive https://github.com/ton-blockchain/mytonctrl.git
git config --global --add safe.directory $SOURCES_DIR/ton
git config --global --add safe.directory $SOURCES_DIR/mytonctrl

cd $BIN_DIR
rm -rf openssl_3
git clone https://github.com/openssl/openssl openssl_3
cd openssl_3
opensslPath=`pwd`
git checkout openssl-3.1.4
./config
make build_libs -j12

# Подготавливаем папки для компиляции
echo -e "${COLOR}[3/6]${ENDC} Preparing for compilation"
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
		CC="clang -mcpu=apple-a14" CXX="clang++ -mcpu=apple-a14" cmake $SOURCES_DIR/ton -DCMAKE_BUILD_TYPE=Release -DTON_ARCH= -Wno-dev -GNinja
	else
		cmake -DCMAKE_BUILD_TYPE=Release $SOURCES_DIR/ton -GNinja
	fi
else
	cmake -DCMAKE_BUILD_TYPE=Release $SOURCES_DIR/ton -GNinja -DTON_USE_JEMALLOC=ON -DOPENSSL_FOUND=1 -DOPENSSL_INCLUDE_DIR=$opensslPath/include -DOPENSSL_CRYPTO_LIBRARY=$opensslPath/libcrypto.a
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
ninja -j ${cpuNumber} fift validator-engine lite-client validator-engine-console generate-random-id dht-server func tonlibjson rldp-http-proxy

# Скачиваем конфигурационные файлы lite-client
echo -e "${COLOR}[5/6]${ENDC} Downloading config files"
wget ${config} -O global.config.json

# Выход из программы
echo -e "${COLOR}[6/6]${ENDC} TON software installation complete"
exit 0
