dest="backup_$(hostname)_$(date +%s).tar.gz"
mtc_dir="$HOME/.local/share/mytoncore"
# Get arguments
while getopts d:m: flag
do
	case "${flag}" in
		d) dest=${OPTARG};;
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

echo -e "${COLOR}[1/4]${ENDC} Stopped validator and mytoncore"


tmp_dir="/tmp/mytoncore/backup"
rm -rf $tmp_dir
mkdir $tmp_dir

cp /var/ton-work/db/config.json ${tmp_dir}
cp -r /var/ton-work/db/keyring ${tmp_dir}
cp -r /var/ton-work/keys ${tmp_dir}
cp -r $mtc_dir $tmp_dir

echo -e "${COLOR}[2/4]${ENDC} Copied files to ${tmp_dir}"


systemctl start validator
systemctl start mytoncore

echo -e "${COLOR}[3/4]${ENDC} Started validator and mytoncore"

sudo tar -zcf ${dest} -C ${tmp_dir} .

echo -e "${COLOR}[4/4]${ENDC} Backup successfully created in ${dest}!"
echo -e "If you wish to use archive package to migrate node to different machine please make sure to stop validator and mytoncore on donor (this) host prior to migration."
