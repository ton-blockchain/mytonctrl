name="backup.tar.gz"
mtc_dir="$HOME/.local/share/mytoncore"
ip=0
# Get arguments
while getopts n:m:i: flag
do
	case "${flag}" in
		n) name=${OPTARG};;
    m) mtc_dir=${OPTARG};;
    i) ip=${OPTARG};;
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

rm -rf /var/ton-work/db/keyring
cp -f ${tmp_dir}/config.json /var/ton-work/db/
cp -rf ${tmp_dir}/keyring /var/ton-work/db/
cp -rf ${tmp_dir}/keys /var/ton-work
cp -rfT ${tmp_dir}/mytoncore $mtc_dir

chown -R validator:validator /var/ton-work/db/keyring

echo -e "${COLOR}[2/4]${ENDC} Extracted files from archive"

rm -r /var/ton-work/db/dht-*

python3 -c "import json;path='/var/ton-work/db/config.json';f=open(path);d=json.load(f);f.close();d['addrs'][0]['ip']=int($ip);f=open(path, 'w');f.write(json.dumps(d, indent=4));f.close()"

echo -e "${COLOR}[3/4]${ENDC} Deleted DHT files, replaced IP in node config"

systemctl start validator
systemctl start mytoncore

echo -e "${COLOR}[4/4]${ENDC} Started validator and mytoncore"
