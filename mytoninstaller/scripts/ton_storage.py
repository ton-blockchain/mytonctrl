import random
import subprocess
import sys
import time

from mypylib.mypylib import Dict
from mytoninstaller.utils import add2systemd
from mytoncore.utils import get_package_resource_path
from mytoninstaller.config import GetConfig, get_own_ip, SetConfig


def enable_ton_storage(user: str, mconfig_path: str, global_config_path: str, src_dir: str):
    udp_port = random.randint(2000, 65000)
    api_port = random.randint(2000, 65000)
    bin_name = "ton_storage"
    db_path = f"/var/{bin_name}"
    bin_path = f"{db_path}/{bin_name}"
    config_path = f"{db_path}/tonutils-storage-db/config.json"
    network_config = global_config_path

    with get_package_resource_path('mytoninstaller.scripts', 'ton_storage_installer.sh') as installer_path:
        process = subprocess.run(["bash", str(installer_path), "-u", user, "-s", src_dir], capture_output=True)
    if process.returncode != 0:
        raise Exception(f"Failed to run ton_storage installer: {process.stdout.decode()} {process.stderr.decode()}")

    start_cmd = f"{bin_path} -network-config {network_config} -daemon -api 127.0.0.1:{api_port}"
    add2systemd(name=bin_name, user=user, start=start_cmd, workdir=db_path, force=True)

    # first run

    subprocess.run(["systemctl", "restart", bin_name])
    time.sleep(10)

    subprocess.run(["systemctl", "stop", bin_name])

    ton_storage_config = GetConfig(path=config_path)
    ton_storage_config.ListenAddr = f"0.0.0.0:{udp_port}"
    ton_storage_config.ExternalIP = get_own_ip()

    SetConfig(path=config_path, data=ton_storage_config)
    SetConfig(path=config_path + '.backup', data=ton_storage_config)

    mconfig = GetConfig(path=mconfig_path)

    ton_storage = Dict()
    ton_storage.udp_port = udp_port
    ton_storage.api_port = api_port
    mconfig.ton_storage = ton_storage

    SetConfig(path=mconfig_path, data=mconfig)

    subprocess.run(["systemctl", "restart", bin_name])

    print("Installed TON Storage")
    return api_port


if __name__ == '__main__':
    if len(sys.argv) != 5:
        sys.exit("usage: ton_storage.py <user> <mconfig_path> <network_config_path> <src_dir>")
    enable_ton_storage(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
