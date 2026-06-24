import json
import os
import random
import subprocess
import sys

from mypylib.mypylib import ip2int
from mytoninstaller.config import get_own_ip
from mytoninstaller.utils import add2systemd


def EnableDhtServer(validator_user: str, ton_bin_dir: str, global_config_path: str):
    dht_server = os.path.join(ton_bin_dir, "dht-server", "dht-server")
    generate_random_id = os.path.join(ton_bin_dir, "utils", "generate-random-id")
    tonDhtServerDir = "/var/ton-dht-server/"
    tonDhtKeyringDir = tonDhtServerDir + "keyring/"

    dht_config_path = tonDhtServerDir + "config.json"
    if os.path.isfile(dht_config_path):
        raise Exception(f"DHT-Server config already exist at {dht_config_path}")

    os.makedirs(tonDhtServerDir, exist_ok=True)

    cmd = "{dht_server} -C {globalConfigPath} -D {tonDhtServerDir}"
    cmd = cmd.format(dht_server=dht_server, globalConfigPath=global_config_path,
                     tonDhtServerDir=tonDhtServerDir)
    add2systemd(name="dht-server", user=validator_user, start=cmd)

    ip = get_own_ip()
    port = random.randint(2000, 65000)
    addr = "{ip}:{port}".format(ip=ip, port=port)

    # first run
    args = [dht_server, "-C", global_config_path, "-D", tonDhtServerDir, "-I", addr]
    subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Получить вывод конфига
    key = os.listdir(tonDhtKeyringDir)[0]
    ip = ip2int(ip)
    text = '{"@type": "adnl.addressList", "addrs": [{"@type": "adnl.address.udp", "ip": ' + str(
        ip) + ', "port": ' + str(port) + '}], "version": 0, "reinit_date": 0, "priority": 0, "expire_at": 0}'
    args = [generate_random_id, "-m", "dht", "-k", tonDhtKeyringDir + key, "-a", text]
    process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
    output = process.stdout.decode("utf-8")
    err = process.stderr.decode("utf-8")
    if len(err) > 0:
        raise Exception(err)

    data = json.loads(output)
    text = json.dumps(data, indent=4)
    print(text)

    # chown 1
    args = ["chown", "-R", validator_user + ':' + validator_user, tonDhtServerDir]
    subprocess.run(args)

    # start DHT-Server
    args = ["systemctl", "restart", "dht-server"]
    subprocess.run(args)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit("usage: dht_server.py <validator_user> <ton_bin_dir> <global_config_path>")
    EnableDhtServer(sys.argv[1], sys.argv[2], sys.argv[3])
