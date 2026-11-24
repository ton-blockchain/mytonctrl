name="backup.tar.gz"
mtc_dir="$HOME/.local/share/mytoncore"
ip=0
user=${SUDO_USER:-$(logname)}
ton_dir="/var/ton-work"
# Get arguments
while getopts n:m:i:u:t: flag
do
	case "${flag}" in
		n) name=${OPTARG};;
    m) mtc_dir=${OPTARG};;
    i) ip=${OPTARG};;
    u) user=${OPTARG};;
    t) ton_dir=${OPTARG};;
    *)
        echo "Flag -${flag} is not recognized. Aborting"
        exit 1 ;;
	esac
done

is_controller_container() {
    [ "${MYTONCTRL_CONTAINER:-}" = "1" ] || [ -f /etc/mytonctrl-container ]
}

# Host installs keep their existing service behavior. Containers must stop on
# failed extraction or copying before the entrypoint can mark them initialized.
restore_step() {
    "$@"
    result=$?
    if [ "$result" -ne 0 ] && is_controller_container; then
        echo "Backup restoration failed during $1 (exit code $result)" >&2
        exit "$result"
    fi
    return "$result"
}

if is_controller_container; then
    mtc_dir=$(readlink -f -- "$mtc_dir") || exit 1
    if [ -z "$mtc_dir" ] || [ ! -d "$mtc_dir" ]; then
        echo "Controller data directory does not exist: $mtc_dir" >&2
        exit 1
    fi
fi

if [ ! -f "$name" ]; then
    echo "Backup file not found, aborting."
    exit 1
fi

COLOR='\033[92m'
ENDC='\033[0m'

systemctl stop validator
systemctl stop mytoncore

echo -e "${COLOR}[1/4]${ENDC} Stopped validator and mytoncore"


tmp_dir="/tmp/mytoncore/backup"
restore_step rm -rf -- "$tmp_dir"
restore_step mkdir -p -- "$tmp_dir"
restore_step tar -xvzf "$name" -C "$tmp_dir"

if [ ! -d "${tmp_dir}/db" ]; then
    echo "Old version of backup detected"
    restore_step mkdir -- "${tmp_dir}/db"
    restore_step mv -- "${tmp_dir}/config.json" "${tmp_dir}/db"
    restore_step mv -- "${tmp_dir}/keyring" "${tmp_dir}/db"

fi

restore_step rm -rf -- "${ton_dir}/db/keyring"

restore_step chown -R "$user:$user" "${tmp_dir}/mytoncore"
restore_step chown -R "$user:$user" "${tmp_dir}/keys"
restore_step chown validator:validator "${tmp_dir}/keys"
restore_step chown -R validator:validator "${tmp_dir}/db"

restore_step cp -rfp -- "${tmp_dir}/db" "${ton_dir}"
restore_step cp -rfp -- "${tmp_dir}/keys" "${ton_dir}"
restore_step cp -rfpT -- "${tmp_dir}/mytoncore" "$mtc_dir"

restore_step chown -R validator:validator "${ton_dir}/db/keyring"

echo -e "${COLOR}[2/4]${ENDC} Extracted files from archive"

rm -r "${ton_dir}"/db/dht-*

if [ "$ip" -ne 0 ]; then
    echo "Replacing IP in node config"
    restore_step python3 - "${ton_dir}/db/config.json" "$ip" <<'PY'
import json
import sys

path, ip = sys.argv[1:]
with open(path) as source:
    data = json.load(source)
data['addrs'][0]['ip'] = int(ip)
with open(path, 'w') as destination:
    json.dump(data, destination, indent=4)
PY
else
    echo "IP is not provided, skipping IP replacement"
fi

echo -e "${COLOR}[3/4]${ENDC} Deleted DHT files"

systemctl start validator
if ! is_controller_container; then
    systemctl start mytoncore
fi

echo -e "${COLOR}[4/4]${ENDC} Started validator and mytoncore"
