import os
import socket
import subprocess

from mypylib.mypylib import MyPyClass, color_print, int2ip
from mytoncore.mytoncore import MyTonCore
from mytoncore.telemetry import is_host_virtual
from mytonctrl.git import check_git_update
from mytonctrl.utils import get_os_version, get_ton_http_api_version


class WarningChecker:
    THA_VERSION_REQUIRED = "2.0.65"

    def __init__(self, local: MyPyClass, ton: MyTonCore):
        self.local = local
        self.ton = ton

    def print_warning(self, warning_name: str):
        color_print(
            "============================================================================================"
        )
        color_print(self.local.translate(warning_name))
        color_print(
            "============================================================================================"
        )

    def check_disk_usage(self):
        usage = self.ton.GetDbUsage()
        if usage > 90:
            self.print_warning("disk_usage_warning")

    def check_sync(self):
        validator_status = self.ton.GetValidatorStatus()
        if validator_status.initial_sync or self.ton.in_initial_sync():
            self.print_warning("initial_sync_warning")
            return
        if not validator_status.is_working or validator_status.out_of_sync >= 20:
            self.print_warning("sync_warning")

    def check_validator_balance(self):
        validator_status = self.ton.GetValidatorStatus()
        if not validator_status.is_working or validator_status.out_of_sync >= 20:
            # Do not check the validator wallet balance if the node is not synchronized (via public lite-servers)
            return
        if self.ton.using_validator():
            validator_wallet = self.ton.GetValidatorWallet()
            validator_account = self.local.try_function(
                self.ton.GetAccount, args=[validator_wallet.addrB64]
            )
            if validator_account is None:
                self.local.add_log(
                    "Failed to check validator wallet balance", "warning"
                )
                return
            if validator_account.balance < 100:
                self.print_warning("validator_balance_warning")

    def check_vps(self):
        if self.ton.using_validator():
            data = self.local.try_function(is_host_virtual)
            if data and data["virtual"]:
                color_print(f"Virtualization detected: {data['product_name']}")

    def check_tg_channel(self):
        if (
            self.ton.using_validator()
            and self.ton.local.db.get("subscribe_tg_channel") is None
        ):
            self.print_warning("subscribe_tg_channel_warning")

    def check_slashed(self):
        validator_status = self.ton.GetValidatorStatus()
        if (
            not self.ton.using_validator()
            or not validator_status.is_working
            or validator_status.out_of_sync >= 20
        ):
            return
        from modules import ValidatorModule

        validator_module = ValidatorModule(self.ton, self.local)
        c = validator_module.get_my_complaint()
        if c:
            warning = self.local.translate("slashed_warning").format(
                int(c["suggestedFine"])
            )
            self.print_warning(warning)

    def check_adnl(self):
        try:
            config = self.ton.GetValidatorConfig()
            if config.fullnodeslaves:
                return
        except Exception:
            pass
        from modules.utilities import UtilitiesModule

        utils_module = UtilitiesModule(self.ton, self.local)
        ok, error = utils_module.check_adnl_connection()
        if not ok:
            error = "{red}" + error + "{endc}"
            self.print_warning(error)

    def check_ubuntu_version(self):
        distro, ver = get_os_version()
        if distro == "ubuntu":
            if ver not in ["22.04", "24.04"]:
                warning = self.local.translate("ubuntu_version_warning").format(ver)
                self.print_warning(warning)

    def check_ton_http_api_version(self):
        version = get_ton_http_api_version()
        if version is None:
            return
        current = tuple(int(x) for x in version.split(".")[:3])
        required = tuple(int(x) for x in self.THA_VERSION_REQUIRED.split(".")[:3])
        if current < required:
            warning = self.local.translate("ton_http_api_version_warning").format(
                version, self.THA_VERSION_REQUIRED
            )
            self.print_warning(warning)

    def check_node_port(self):
        if not self.ton.using_validator():
            return
        try:
            vconfig = self.ton.GetValidatorConfig()
        except Exception:
            return
        for addr in vconfig["addrs"]:
            if addr.get("@type") == "engine.quicAddr":  # quic port exists
                return
        for addr in vconfig["addrs"]:
            port = addr["port"]
            if port > 64535:
                warning = self.local.translate("node_port_warning").format(port)
                self.print_warning(warning)
                return

    def check_installer_user(self):
        args = ["whoami"]
        process = subprocess.run(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
        )
        username = process.stdout.decode("utf-8").strip()

        args = ["ls", "-lh", "/var/ton-work/keys/"]
        process = subprocess.run(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
        )
        output = process.stdout.decode("utf-8")
        actual_user = output.split("\n")[1].split()[2]

        if username != actual_user:
            self.local.add_log(
                f"mytonctrl was installed by another user. Probably you need to launch mtc with `{actual_user}` user.",
                "error",
            )

    def check_vport(self):
        try:
            vconfig = self.ton.GetValidatorConfig()
        except Exception:
            self.local.add_log("GetValidatorConfig error", "error")
            return
        addr = vconfig.addrs.pop()
        ip = int2ip(addr.ip)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
            result = client_socket.connect_ex((ip, addr.port))
        if result != 0:
            color_print(self.local.translate("vport_error"))

    def check_mytonctrl_update(self):
        git_path = "/usr/src/mytonctrl"
        if not os.path.exists(git_path):
            return
        result = check_git_update(git_path)
        if result:
            color_print(self.local.translate("mytonctrl_update_available"))

    def run_warnings(self):
        self.local.try_function(self.check_disk_usage)
        self.local.try_function(self.check_sync)
        self.local.try_function(self.check_adnl)
        self.local.try_function(self.check_validator_balance)
        self.local.try_function(self.check_vps)
        self.local.try_function(self.check_tg_channel)
        self.local.try_function(self.check_slashed)
        self.local.try_function(self.check_ubuntu_version)
        self.local.try_function(self.check_node_port)
        self.local.try_function(self.check_ton_http_api_version)
