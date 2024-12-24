name="backup.tar.gz"
mtc_dir="$HOME/.local/share/mytoncore"
ip=0
user=$(logname)
# Get arguments
while getopts n:m:i:u: flag
do
	case "${flag}" in
		n) name=${OPTARG};;
    m) mtc_dir=${OPTARG};;
    i) ip=${OPTARG};;
    u) user=${OPTARG};;
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
tar -xvzf $name -C $tmp_dir

if [ ! -d ${tmp_dir}/db ]; then
    echo "Old version of backup detected"
    mkdir ${tmp_dir}/db
    mv ${tmp_dir}/config.json ${tmp_dir}/db
    mv ${tmp_dir}/keyring ${tmp_dir}/db

fi

rm -rf /var/ton-work/db/keyring

chown -R $user:$user ${tmp_dir}/mytoncore
chown -R $user:$user ${tmp_dir}/keys

cp -rfp ${tmp_dir}/db /var/ton-work
cp -rfp ${tmp_dir}/keys /var/ton-work
cp -rfpT ${tmp_dir}/mytoncore $mtc_dir

chown -R validator:validator /var/ton-work/db/keyring

echo -e "${COLOR}[2/4]${ENDC} Extracted files from archive"

rm -r /var/ton-work/db/dht-*

if [ $ip -ne 0 ]; then
    echo "Replacing IP in node config"
    python3 -c "import json;path='/var/ton-work/db/config.json';f=open(path);d=json.load(f);f.close();d['addrs'][0]['ip']=int($ip);f=open(path, 'w');f.write(json.dumps(d, indent=4));f.close()"
else
    echo "IP is not provided, skipping IP replacement"
fi

echo -e "${COLOR}[3/4]${ENDC} Deleted DHT files"

systemctl start validator
systemctl start mytoncore

echo -e "${COLOR}[4/4]${ENDC} Started validator and mytoncore"
