#!/bin/bash
set -e

show_help_and_exit() {
    echo 'Supported arguments:'
    echo ' -c, --config  URL             Provide custom network config'
    echo ' -e, --env-file  PATH          Provide env file with installation parameters'
    echo ' --print-env                   Print result command and envs after interactive installer without installing MyTonCtrl'
    echo ' -t, --telemetry               Disable telemetry'
    echo ' -i, --ignore-reqs             Ignore minimum requirements'
    echo ' -d, --dump                    Use pre-packaged dump. Reduces duration of initial synchronization'
    echo ' -a, --author                  Set MyTonCtrl git repo author'
    echo ' -r, --repo                    Set MyTonCtrl git repo name'
    echo ' -b, --branch                  Set MyTonCtrl git repo branch'
    echo ' -m, --mode  MODE              Install MyTonCtrl with specified mode (validator, liteserver or collator). Leave empty to launch interactive installer'
    echo ' --archive                     With -m liteserver, install full archive liteserver'
    echo ' -n, --network  NETWORK        Specify the network (mainnet or testnet)'
    echo ' -g, --node-repo  URL          TON node git repo URL (default: https://github.com/ton-blockchain/ton.git)'
    echo ' -v, --node-version  VERSION   Specify the TON node version (commit, branch, or tag)'
    echo ' -u, --user  USER              Specify the user to be used for MyTonCtrl installation'
    echo ' -p, --backup  PATH            Provide backup file for MyTonCtrl installation'
    echo ' -o, --only-mtc                Install only MyTonCtrl. Must be used with -p'
    echo ' -l, --only-node               Install only TON node'
    echo ' -h, --help                    Show this help'
    exit
}

if [[ "${1-}" =~ ^-*h(elp)?$ ]]; then
    show_help_and_exit
fi

# colors
COLOR='\033[92m'
ENDC='\033[0m'

# check sudo permissions
if [ "$(id -u)" != "0" ]; then
    echo "Please run script as root"
    exit 1
fi

# node install parameters

author="ton-blockchain"
repo="mytonctrl"
branch="master"
network="mainnet"
ton_node_version="master"  # Default version
ton_node_git_url="https://github.com/ton-blockchain/ton.git"
config_overridden=false

config="https://ton-blockchain.github.io/global.config.json"
env_file=""
telemetry=true
ignore=false
dump=false
archive=false
only_mtc=false
only_node=false
backup=none
mode=none
cpu_required=16
mem_required=64000000  # 64GB in KB

# transform --long options to short, because getopts only supports short ones

newargv=()
while (($#)); do
  case "$1" in
    --) # end of options
      shift
      newargv+=( -- "$@" )
      break
      ;;

    # no arg
    --archive)      newargv+=(-A) ;;
    --dump)         newargv+=(-d) ;;
    --only-mtc)     newargv+=(-o) ;;
    --only-node)    newargv+=(-l) ;;
    --help)         newargv+=(-h) ;;
    --telemetry)    newargv+=(-t) ;;
    --ignore-reqs)  newargv+=(-i) ;;
    --print-env)    export PRINT_ENV=true ;;

    # with arg
    --config|--author|--repo|--branch|--mode|--network|--node-repo|--backup|--user|--node-version|--env-file)
      if (($# < 2)); then
        echo "Error: option $1 requires value" >&2; exit 2
      fi
      case "$1" in
        --config)       newargv+=(-c "$2") ;;
        --author)       newargv+=(-a "$2") ;;
        --repo)         newargv+=(-r "$2") ;;
        --branch)       newargv+=(-b "$2") ;;
        --mode)         newargv+=(-m "$2") ;;
        --network)      newargv+=(-n "$2") ;;
        --node-repo)    newargv+=(-g "$2") ;;
        --backup)       newargv+=(-p "$2") ;;
        --user)         newargv+=(-u "$2") ;;
        --node-version) newargv+=(-v "$2") ;;
        --env-file)     newargv+=(-e "$2") ;;
      esac
      shift ;;
    --*)
      echo "Error: unknown option '$1'" >&2; exit 2 ;;
    *)
      newargv+=("$1") ;;
  esac
  shift
done

#printf ' %q' "${newargv[@]}"
#printf '\n'
set -- "${newargv[@]}"

while getopts ":Ac:tidola:r:b:m:n:v:u:p:g:e:h" flag; do
    case "${flag}" in
        A) archive=true;;
        c) config=${OPTARG}; config_overridden=true;;
        t) telemetry=false;;
        i) ignore=true;;
        d) dump=true;;
        a) author=${OPTARG};;
        r) repo=${OPTARG};;
        g) ton_node_git_url=${OPTARG};;
        b) branch=${OPTARG};;
        m) mode=${OPTARG};;
        n) network=${OPTARG};;
        v) ton_node_version=${OPTARG};;
        u) user=${OPTARG};;
        o) only_mtc=true;;
        l) only_node=true;;
        p) backup=${OPTARG};;
        e) env_file=${OPTARG};;
        h) show_help_and_exit;;
        *)
            echo "Flag -${flag} is not recognized. Aborting"
        exit 1 ;;
    esac
done

if [ -n "$env_file" ]; then
  if [ ! -f "$env_file" ]; then
    echo "Env file not found, aborting."
    exit 1
  fi
  set -a
  source "$env_file"
  set +a
fi

if [ "$only_mtc" = true ] && [ "$backup" = "none" ]; then
    echo "Backup file must be provided if only mtc installation"
    exit 1
fi

if [ "$archive" = true ] && [ "$mode" != "liteserver" ]; then
    echo "Flag --archive can only be used with -m liteserver"
    exit 1
fi

if [ "$archive" = true ]; then
    export ARCHIVE_BLOCKS=1
    export ARCHIVE_TTL=-1
    unset STATE_TTL
fi


if [ "${mode}" = "none" ] && [ "$backup" = "none" ]; then  # no mode or backup was provided
    echo "Running cli installer"
    wget https://raw.githubusercontent.com/${author}/${repo}/${branch}/scripts/install.py
    if ! command -v pip3 &> /dev/null; then
        echo "pip not found. Installing pip..."
        python3 -m pip install --upgrade pip
    fi
    pip3 install questionary==2.1.1 --break-system-packages
    python3 install.py "$@"
    pip3 uninstall questionary -y
    exit
fi

# Set config based on network argument
if [ "${network}" = "testnet" ]; then
    if [ "${config_overridden}" = false ]; then
        config="https://ton-blockchain.github.io/testnet-global.config.json"
    fi

    cpu_required=8
    mem_required=16000000  # 16GB in KB
fi

# check machine configuration
echo -e "${COLOR}[1/5]${ENDC} Checking system requirements"

cpus=$(lscpu | grep "CPU(s)" | head -n 1 | awk '{print $2}')
memory=$(cat /proc/meminfo | grep MemTotal | awk '{print $2}')

echo "This machine has ${cpus} CPUs and ${memory}KB of Memory"
if [ "$ignore" = false ] && ([ "${cpus}" -lt "${cpu_required}" ] || [ "${memory}" -lt "${mem_required}" ]); then
    echo "Insufficient resources. Requires a minimum of "${cpu_required}"  processors and  "${mem_required}" RAM."
    exit 1
fi

echo -e "${COLOR}[2/5]${ENDC} Checking for required TON components"
SOURCES_DIR=/usr/src
BIN_DIR=/usr/bin

# create dirs for OSX
if [[ "$OSTYPE" =~ darwin.* ]]; then
    SOURCES_DIR=/usr/local/src
    BIN_DIR=/usr/local/bin
    mkdir -p ${SOURCES_DIR}
fi

if [ ! -f ~/.config/pip/pip.conf ]; then  # create pip config
    mkdir -p ~/.config/pip
cat > ~/.config/pip/pip.conf <<EOF
[global]
break-system-packages = true
EOF
fi

# check TON components
file1=${BIN_DIR}/ton/crypto/fift
file2=${BIN_DIR}/ton/lite-client/lite-client
file3=${BIN_DIR}/ton/validator-engine-console/validator-engine-console

if  [ ! -f "${file1}" ] || [ ! -f "${file2}" ] || [ ! -f "${file3}" ]; then
    echo "TON does not exists, building"
    wget https://raw.githubusercontent.com/${author}/${repo}/${branch}/scripts/install_clang.sh -O /tmp/install_clang.sh
    bash /tmp/install_clang.sh
    wget https://raw.githubusercontent.com/${author}/${repo}/${branch}/scripts/ton_installer.sh -O /tmp/ton_installer.sh
    bash /tmp/ton_installer.sh -c ${config} -g ${ton_node_git_url} -v ${ton_node_version}
fi

# Cloning mytonctrl
echo -e "${COLOR}[3/5]${ENDC} Installing MyTonCtrl"
echo "https://github.com/${author}/${repo}.git -> ${branch}"

# remove previous installation
cd $SOURCES_DIR
rm -rf $SOURCES_DIR/mytonctrl
pip3 uninstall -y mytonctrl

git clone --branch ${branch} --recursive https://github.com/${author}/${repo}.git ${repo}  # TODO: return --recursive back when fix libraries
git config --global --add safe.directory $SOURCES_DIR/${repo}
cd $SOURCES_DIR/${repo}

pip3 install -U .  # TODO: make installation from git directly

echo -e "${COLOR}[4/5]${ENDC} Running mytoninstaller"
# DEBUG

if [ "${user}" = "" ]; then  # no user
    parent_name=$(ps -p $PPID -o comm=)
    user=$(whoami)
    if [ "$parent_name" = "sudo" ] || [ "$parent_name" = "su" ] || [ "$parent_name" = "python3" ]; then
        user=${SUDO_USER:-$(logname)}
    fi
fi
echo "User: $user"
python3 -m mytoninstaller -u ${user} -t ${telemetry} --dump ${dump} -m ${mode} --only-mtc ${only_mtc} --backup ${backup} --only-node ${only_node}

# create symbolic link if branch not eq mytonctrl
if [ "${repo}" != "mytonctrl" ]; then
    ln -sf ${SOURCES_DIR}/${repo} ${SOURCES_DIR}/mytonctrl
fi

echo -e "${COLOR}[5/5]${ENDC} Mytonctrl installation completed"
exit 0
