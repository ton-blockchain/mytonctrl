import argparse
import base64
import json
import subprocess
tmp_dir = "tmp/cleared_backup"


def b64tohex(b64str: str):
    return base64.b64decode(b64str).hex().upper()


def run_vc(cmd: str):
    args = ['/usr/bin/ton/validator-engine-console/validator-engine-console', '-k', '/var/ton-work/keys/client', '-p', '/var/ton-work/keys/server.pub', '-a', vc_address, '--cmd', cmd]
    subprocess.run(args)


parser = argparse.ArgumentParser()
parser.add_argument('-n')
parser.add_argument('-a')

args = parser.parse_args()
name = args.n
vc_address = args.a

if not name or not vc_address:
    print("Usage: inject_backup_node_keys.py -n <backup_name> -a <vc_address>")
    exit(1)


subprocess.run(f"rm -rf {tmp_dir}", shell=True)
subprocess.run(f"mkdir -p {tmp_dir}", shell=True)

subprocess.run(f'tar -xzf {name} -C {tmp_dir}', shell=True)

subprocess.run(f'cp -rf {tmp_dir}/db/keyring /var/ton-work/db/', shell=True)
subprocess.run(f'chown -R validator:validator /var/ton-work/db/keyring', shell=True)

with open(f'{tmp_dir}/db/config.json', 'r') as f:
    config = json.load(f)

for v in config['validators']:
    run_vc(f'addpermkey {b64tohex(v["id"])} {v["election_date"]} {v["expire_at"]}')
    for tkey in v['temp_keys']:
        run_vc(f'addtempkey {b64tohex(v["id"])} {b64tohex(tkey["key"])} {v["expire_at"]}')
    for adnl in v['adnl_addrs']:
        run_vc(f'addadnl {b64tohex(adnl["id"])} 0')
        run_vc(f'addvalidatoraddr {b64tohex(v["id"])} {b64tohex(adnl["id"])} {v["expire_at"]}')

subprocess.run(f'systemctl restart validator', shell=True)
