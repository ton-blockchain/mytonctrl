from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstallerPaths:
    bin_dir: str = "/usr/bin/"
    src_dir: str = "/usr/src/"
    ton_work_dir: str = "/var/ton-work/"

    @property
    def ton_bin_dir(self) -> str:
        return self.bin_dir + "ton/"

    @property
    def ton_src_dir(self) -> str:
        return self.src_dir + "ton/"

    @property
    def mtc_src_dir(self) -> str:
        return self.src_dir + "mytonctrl/"

    @property
    def ton_db_dir(self) -> str:
        return self.ton_work_dir + "db/"

    @property
    def keys_dir(self) -> str:
        return self.ton_work_dir + "keys/"

    @property
    def ton_log_path(self) -> str:
        return self.ton_work_dir + "log"

    @property
    def validator_app_path(self) -> str:
        return self.ton_bin_dir + "validator-engine/validator-engine"

    @property
    def global_config_path(self) -> str:
        return self.ton_bin_dir + "global.config.json"

    @property
    def local_config_path(self) -> str:
        return self.ton_bin_dir + "local.config.json"

    @property
    def vconfig_path(self) -> str:
        return self.ton_db_dir + "config.json"


@dataclass(frozen=True)
class InstallerPorts:
    validator_console: int
    liteserver: int
    validator: int
    quic: int | None = None


@dataclass(frozen=True)
class InstallerContext:
    user: str
    validator_user: str
    paths: InstallerPaths
    ports: InstallerPorts

    telemetry: bool | None
    dump: bool | None
    mode: str | None
    only_mtc: bool | None
    only_node: bool | None
    backup: str | None

    archive_ttl: int | None
    state_ttl: int | None
    public_ip: str | None
    add_shard: str | None
    archive_blocks: str | None
    collate_shard: str = ""

    @property
    def mconfig_path(self) -> str:
        if self.user == 'root':
            return "/usr/local/bin/mytoncore/mytoncore.db"
        return f"/home/{self.user}/.local/share/mytoncore/mytoncore.db"
