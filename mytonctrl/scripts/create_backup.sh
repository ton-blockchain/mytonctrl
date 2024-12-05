dest="mytonctrl_backup_$(hostname)_$(date +%s).tar.gz"
mtc_dir="$HOME/.local/share/mytoncore"
user=$(logname)
ton_dir="/var/ton-work"
keys_dir="/var/ton-work/keys"
# Get arguments
while getopts d:m:t:k: flag
do
	case "${flag}" in
		d) dest=${OPTARG};;
    m) mtc_dir=${OPTARG};;
    t) ton_dir=${OPTARG};;
    k) keys_dir=${OPTARG};;
    *)
        echo "Flag -${flag} is not recognized. Aborting"
        exit 1 ;;
	esac
done

COLOR='\033[92m'
ENDC='\033[0m'

tmp_dir="/tmp/mytoncore/backupv2"
rm -rf $tmp_dir
mkdir $tmp_dir
mkdir $tmp_dir/db

cp $ton_dir/db/config.json ${tmp_dir}/db
cp -r $ton_dir/db/keyring ${tmp_dir}/db
cp -r $keys_dir ${tmp_dir}
cp -r $mtc_dir $tmp_dir

python3 -c "import json;f=open('${tmp_dir}/db/config.json');json.load(f);f.close()" || exit 1  # Check if config.json is copied correctly
python3 -c "import json;f=open('${tmp_dir}/mytoncore/mytoncore.db');json.load(f);f.close()" || exit 2  # Check if mytoncore.db is copied correctly

echo -e "${COLOR}[1/2]${ENDC} Copied files to ${tmp_dir}"

tar -zcf $dest -C $tmp_dir .

chown $user:$user $dest

echo -e "${COLOR}[2/2]${ENDC} Backup successfully created in ${dest}!"

rm -rf $tmp_dir

echo -e "If you wish to use archive package to migrate node to different machine please make sure to stop validator and mytoncore on donor (this) host prior to migration."
