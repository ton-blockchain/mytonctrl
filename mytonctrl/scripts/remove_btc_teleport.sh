SRC_DIR=""
KEYSTORE_PATH=""

while getopts s:k: flag
do
	case "${flag}" in
    s) SRC_DIR=${OPTARG};;
    k) KEYSTORE_PATH=${OPTARG};;
    *) echo "Flag -${flag} is not recognized. Aborting"; exit 1 ;;
	esac
done


rm -rf $KEYSTORE_PATH
rm -rf $SRC_DIR
systemctl stop btc_teleport
rm -rf /etc/systemd/system/btc_teleport.service
systemctl daemon-reload