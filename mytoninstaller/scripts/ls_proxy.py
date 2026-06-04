import base64
import random
import subprocess
import sys
import time

from mypylib.mypylib import add2systemd

from mytoncore.utils import get_package_resource_path
from mytoninstaller.config import GetConfig, SetConfig


def enable_ls_proxy(user: str, mconfig_path: str):
    ls_proxy_port = random.randint(2000, 65000)
    metrics_port = random.randint(2000, 65000)
    bin_name = "ls_proxy"
    ls_proxy_db_path = f"/var/{bin_name}"
    ls_proxy_path = f"{ls_proxy_db_path}/{bin_name}"
    ls_proxy_config_path = f"{ls_proxy_db_path}/ls-proxy-config.json"

    with get_package_resource_path('mytoninstaller.scripts', 'ls_proxy_installer.sh') as installer_path:
        process = subprocess.run(["bash", str(installer_path), "-u", user], capture_output=True)
    if process.returncode != 0:
        raise Exception(f"Failed to run ls proxy installer: {process.stdout.decode()} {process.stderr.decode()}")

    add2systemd(name=bin_name, user=user, start=ls_proxy_path, workdir=ls_proxy_db_path)

    # first run
    subprocess.run(["systemctl", "restart", bin_name])
    time.sleep(1)

    subprocess.run(["systemctl", "stop", bin_name])

    ls_proxy_config = GetConfig(path=ls_proxy_config_path)

    mconfig = GetConfig(path=mconfig_path)
    ls_pubkey_path = mconfig.liteClient.liteServer.pubkeyPath
    ls_port = mconfig.liteClient.liteServer.port

    with open(ls_pubkey_path, 'rb') as file:
        data = file.read()
        pubkey = data[4:]
        ls_pubkey = base64.b64encode(pubkey).decode("utf-8")

    ls_proxy_config.ListenAddr = f"0.0.0.0:{ls_proxy_port}"
    ls_proxy_config.MetricsAddr = f"127.0.0.1:{metrics_port}"
    ls_proxy_config.Backends = [{
        "Name": "local_ls",
        "Addr": f"127.0.0.1:{ls_port}",
        "Key": ls_pubkey
    }]

    SetConfig(path=ls_proxy_config_path, data=ls_proxy_config)

    # start ls_proxy
    subprocess.run(["systemctl", "restart", bin_name])

    print("enabled ls proxy")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit("usage: ls_proxy.py <user> <mconfig_path>")
    enable_ls_proxy(sys.argv[1], sys.argv[2])
