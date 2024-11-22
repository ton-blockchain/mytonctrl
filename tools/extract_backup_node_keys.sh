name="backup.tar.gz"
dest="cleared_backup_$(hostname)_$(date +%s).tar.gz"
ton_db=""
tmp_dir="tmp/backup"
user=$(logname)


# Get arguments
while getopts n:d:t: flag
do
	case "${flag}" in
		n) name=${OPTARG};;
    d) dest=${OPTARG};;
    t) ton_db=${OPTARG};;
    *)
        echo "Flag -${flag} is not recognized. Aborting"
        exit 1 ;;
	esac
done

rm -rf $tmp_dir
mkdir tmp/backup -p

if [ ! -z "$ton_db" ]; then
  mkdir ${tmp_dir}/db
  cp -r "$ton_db"/db/keyring ${tmp_dir}/db
  cp "$ton_db"/db/config.json ${tmp_dir}/db
else
  tar -xzf $name -C $tmp_dir
fi

rm -rf ${tmp_dir}/mytoncore
rm -rf ${tmp_dir}/keys
mv ${tmp_dir}/db/keyring ${tmp_dir}/db/old_keyring
mkdir ${tmp_dir}/db/keyring

keys=$(python3 -c "import json;import base64;f=open('${tmp_dir}/db/config.json');config=json.load(f);f.close();keys=set();[([keys.add(base64.b64decode(key['key']).hex().upper()) for key in v['temp_keys']], [keys.add(base64.b64decode(adnl['id']).hex().upper()) for adnl in v['adnl_addrs']]) for v in config['validators']];print('\n'.join(list(keys)))")

for key in $keys; do
  mv ${tmp_dir}/db/old_keyring/${key} ${tmp_dir}/db/keyring
done

rm -rf ${tmp_dir}/db/old_keyring

tar -zcf $dest -C $tmp_dir .
chown $user:$user $dest

echo -e "Node keys backup successfully created in ${dest}!"
