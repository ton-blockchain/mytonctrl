name="backup.tar.gz"
mtc_dir="$HOME/.local/share/mytoncore"
# Get arguments
while getopts n:m: flag
do
	case "${flag}" in
		n) name=${OPTARG};;
    m) mtc_dir=${OPTARG};;
    *)
        echo "Flag -${flag} is not recognized. Aborting"
        exit 1 ;;
	esac
done


COLOR='\033[92m'
ENDC='\033[0m'

systemctl stop validator
systemctl stop mytoncore

echo -e "${COLOR}[1/3]${ENDC} Stopped validator and mytoncore"


tmp_dir="/tmp/mytoncore/backup"
rm -rf $tmp_dir
mkdir $tmp_dir
tar -xvzf $name -C $tmp_dir

cp -f ${tmp_dir}/config.json /var/ton-work/db/
cp -rf ${tmp_dir}/keyring /var/ton-work/db/
cp -rf ${tmp_dir}/keys /var/ton-work
cp -rfT ${tmp_dir}/mytoncore $mtc_dir

echo -e "${COLOR}[2/3]${ENDC} Extracted files from archive"

rm /var/ton-work/db/dht-*

systemctl start validator
systemctl start mytoncore

echo -e "${COLOR}[3/3]${ENDC} Started validator and mytoncore"
