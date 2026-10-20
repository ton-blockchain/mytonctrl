from __future__ import annotations

from typing import Literal, Optional

import stat
import tempfile
from pathlib import Path
import json
import psutil
import requests
import base64
import pathlib
import subprocess
import os
import sys
import shutil

from mypylib.mypylib import (
    run_as_root,
    get_timestamp,
    print_table,
    color_print,
    color_text,
    bcolors,
    Dict,
    int2ip,
)
from mytoncore.telemetry import get_memory_info, get_swap_info, get_bin_git_hash, get_load_avg
from mytonctrl.git import (
    parse_git_target,
    fix_git_config,
    check_git,
    get_git_hash,
    get_git_branch,
)
from mytonctrl.images import get_controller_image_ref, get_ton_image_ref
from mytoninstaller.archive_blocks import download_blocks
from mytoninstaller.utils import get_ton_storage_port
from mytonctrl.argtypes import tcp_port
from mypyconsole.command_parser import Annotated, Arg

from mytoncore.utils import get_package_resource_path, b642hex
from mytonctrl.utils import (
    timestamp2utcdatetime,
    GetColorInt,
    get_clang_major_version,
    ts_diff_to_human,
    get_service_status,
    get_service_uptime,
    get_service_state,
    container_initialization_complete,
    is_container,
)
from mytoncore.models import Config15, Config17
from modules import MODES, get_mode_settings
from modules.module import MtcModule

_ModeName = Annotated[
    str, Arg(choices=list(MODES), metavar="mode_name", help="one of: %(choices)s")
]


class GeneralModule(MtcModule):
    CLANG_VERSION_REQUIRED = 21

    def mode_status(self) -> None:
        from modules import get_mode

        modes = self.ton.get_modes()
        table = [["Name", "Status", "Description"]]
        for mode_name in modes:
            mode = get_mode(mode_name)
            if mode is None:
                color_print(f"{{red}}Mode {mode_name} not found{{endc}}")
                continue
            status = color_text(
                "{green}enabled{endc}" if modes[mode_name] else "{red}disabled{endc}"
            )
            table.append([mode_name, status, mode.description])
        print_table(table)

    def settings_status(self) -> None:
        from modules import SETTINGS

        table = [["Name", "Description", "Mode", "Default value", "Current value"]]
        for name, setting in SETTINGS.items():
            current_value = self.ton.local.db.get(name)
            table.append(
                [
                    name,
                    setting.description,
                    str(setting.mode),
                    str(setting.default_value),
                    str(current_value),
                ]
            )
        print_table(table)

    def print_status(self, mode: Optional[Literal["fast"]] = None) -> None:
        if is_container():
            return self._print_status_container(mode)

        fast = mode == "fast"

        # Local status
        validator_status = self.ton.GetValidatorStatus()
        all_status = (
            validator_status.is_working and validator_status.out_of_sync < 20
        ) and not fast
        full_elector_addr = "n/a"
        start_work_time = None
        config34 = None
        config36 = None

        if all_status:
            try:
                config34 = self.ton.get_config_34()
                total_validators = config34.total_validators
                config36 = self.ton.get_config_36()
                full_elector_addr = self.ton.GetFullElectorAddr()
                start_work_time = self.ton.GetActiveElectionId(full_elector_addr)
                self.print_ton_status(start_work_time, total_validators)
            except Exception as e:
                self.local.add_log(f"Failed to get TON status: {e}", "error")

        self.print_local_status(validator_status, all_status)

        if all_status and self.ton.using_validator():
            full_config_addr = self.ton.GetFullConfigAddr()
            config15 = self.ton.get_config_15()
            config17 = self.ton.get_config_17()
            self.print_ton_config(
                full_config_addr, full_elector_addr, config15, config17
            )
            if (
                config34 is not None
                and start_work_time is not None
            ):
                if config36 is not None:
                    old_start_work_time = config36.start_work_time
                else:
                    old_start_work_time = config34.start_work_time
                root_workchain_enabled_time_int = self.local.try_function(
                    self.ton.get_root_workchain_enabled_time
                )
                self.print_network_times(
                    root_workchain_enabled_time_int,
                    start_work_time,
                    old_start_work_time,
                    config15,
                )


    def _print_status_container(self, mode: Optional[Literal["fast"]] = None) -> None:
        fast = mode == "fast"

        if is_container() and Path(self.ton.local.db_path).is_file():
            # The installer may add console/client settings after this console opens.
            try:
                self.ton.local.load_db()
                self.ton.apply_db_settings()
            except Exception as error:
                self.local.add_log(f"Could not refresh controller settings: {error}", "warning")

        # Local status
        if (self.ton.local.db.get("validatorConsole") is None
                or not container_initialization_complete(self.ton)):
            validator_status = Dict()
        else:
            validator_status = self._status_value(self.ton.GetValidatorStatus) or Dict()
        all_status = bool(
            validator_status.is_working
            and isinstance(validator_status.out_of_sync, (int, float))
            and validator_status.out_of_sync < 20
        ) and not fast
        full_elector_addr = "n/a"
        start_work_time = None
        config34 = None
        config36 = None

        if all_status:
            try:
                config34 = self.ton.get_config_34()
                total_validators = config34.total_validators
                config36 = self.ton.get_config_36()
                full_elector_addr = self.ton.GetFullElectorAddr()
                start_work_time = self.ton.GetActiveElectionId(full_elector_addr)
                self.print_ton_status(start_work_time, total_validators)
            except Exception as e:
                self.local.add_log(f"Failed to get TON status: {e}", "error")

        self.print_local_status(validator_status, all_status)

        if all_status and self.ton.using_validator():
            try:
                full_config_addr = self.ton.GetFullConfigAddr()
                config15 = self.ton.get_config_15()
                config17 = self.ton.get_config_17()
                self.print_ton_config(
                    full_config_addr, full_elector_addr, config15, config17
                )
                if config34 is not None and start_work_time is not None:
                    old_start_work_time = config36.start_work_time if config36 is not None else config34.start_work_time
                    root_workchain_enabled_time_int = self.local.try_function(
                        self.ton.get_root_workchain_enabled_time
                    )
                    self.print_network_times(
                        root_workchain_enabled_time_int, start_work_time,
                        old_start_work_time, config15,
                    )
            except Exception as error:
                self.local.add_log(f"Failed to get TON configuration: {error}", "warning")

    @staticmethod
    def _status_value(getter, default=None):
        try:
            value = getter()
            return default if value is None else value
        except Exception:
            return default

    @staticmethod
    def _status_number(value, threshold, **kwargs):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "n/a"
        return GetColorInt(value, threshold, **kwargs)

    @staticmethod
    def _read_status_json(path):
        try:
            data = json.loads(path.read_text())
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def print_initialization_status(self, paths):
        if not is_container():
            return
        controller = paths.ton_work / "controller"
        progress = self._read_status_json(controller / "installer-progress.json")
        if (controller / "initialized.json").is_file():
            print("Initialization status: ready")
            return
        if progress.get("status") == "failed":
            print("Initialization status: failed")
        elif (controller / ".initializing").exists() or progress.get("status") == "running":
            print("Initialization status: pending")
        else:
            print("Initialization status: not complete")
        pending = self._read_status_json(controller / ".initializing")
        environment = pending.get("installer_environment")
        if isinstance(environment, dict) and isinstance(environment.get("MODE"), str):
            print(f"Installation mode: {environment['MODE']}")
        if isinstance(progress.get("stage"), str):
            print(f"Installer stage: {progress['stage']} ({progress.get('status', 'unknown')})")
        if isinstance(progress.get("error"), str):
            print(f"Initialization error: {progress['error']}")
        if (controller / "node-initialized.json").is_file():
            print("Node setup: complete")
        # Docker exec keeps the container environment even when initialization restores saved settings.
        if isinstance(environment, dict):
            cache_setting = environment.get("DUMP_CACHE_DIR")
        else:
            cache_setting = os.getenv("DUMP_CACHE_DIR")
        cache = paths.ton_work / "dump-cache"
        if isinstance(cache_setting, str) and cache_setting:
            cache = Path(cache_setting)
        dump_state = self._read_status_json(cache / "dump-state.json")
        phase = dump_state.get("phase")
        if phase in ("downloading", "verified", "extracting", "extracted"):
            print(f"Dump phase: {phase}")
            print(f"Dump cache: {cache}")
            archive_name = dump_state.get("archive_name")
            if isinstance(archive_name, str) and Path(archive_name).name == archive_name:
                print(f"Dump archive: {cache / archive_name}")
            archive_size = dump_state.get("archive_size")
            if isinstance(archive_size, int) and archive_size >= 0:
                print(f"Dump archive size: {archive_size} bytes")

    def print_ton_status(self, start_work_time: int, total_validators: int):
        color_print(self.local.translate("ton_status_head"))

        network_name = self.ton.GetNetworkName()
        color_network_name = (
            bcolors.green_text(network_name)
            if network_name == "mainnet"
            else bcolors.yellow_text(network_name)
        )
        network_name_text = self.local.translate("ton_status_network_name").format(
            color_network_name
        )
        print(network_name_text)

        all_validators_text = bcolors.yellow_text(total_validators)
        validators_text = self.local.translate("ton_status_validators").format(
            all_validators_text
        )
        print(validators_text)

        shards_number = self.ton.GetShardsNumber()
        shards_text = self.local.translate("ton_status_shards").format(
            bcolors.green_text(shards_number)
        )
        print(shards_text)

        offers_number = self.local.try_function(self.ton.GetOffersNumber)
        new_offers = offers_number.get("new") if offers_number else "n/a"
        all_offers = offers_number.get("all") if offers_number else "n/a"
        new_offers_text = bcolors.green_text(new_offers)
        all_offers_text = bcolors.yellow_text(all_offers)
        offers_text = self.local.translate("ton_status_offers").format(
            new_offers_text, all_offers_text
        )
        print(offers_text)

        complaints_number = self.local.try_function(self.ton.GetComplaintsNumber)
        new_complaints = complaints_number.get("new") if complaints_number else "n/a"
        all_complaints = complaints_number.get("all") if complaints_number else "n/a"
        new_complaints_text = bcolors.green_text(new_complaints)
        all_complaints_text = bcolors.yellow_text(all_complaints)
        complaints_text = self.local.translate("ton_status_complaints").format(
            new_complaints_text, all_complaints_text
        )
        print(complaints_text)

        if start_work_time == 0:
            election_text = bcolors.yellow_text("closed")
        else:
            election_text = bcolors.green_text("open")
        election_text = self.local.translate("ton_status_election").format(
            election_text
        )
        print(election_text)

        print()

    def _get_node_ports(self, vconfig: Dict) -> list[str]:
        main_port = None
        quic_port = None
        for addr in vconfig.get("addrs", []):
            if addr.get("@type") == "engine.addr" and main_port is None:
                main_port = addr.get("port")
            elif addr.get("@type") == "engine.quicAddr" and quic_port is None:
                quic_port = addr.get("port")
        ports_parts = []
        if main_port is not None:
            ports_parts.append(bcolors.yellow_text(main_port))
        if self.ton.using_validator():
            if quic_port is not None:
                ports_parts.append(bcolors.yellow_text(f"{quic_port} (QUIC)"))
            elif main_port is not None:
                ports_parts.append(bcolors.yellow_text(f"{main_port + 1000} (QUIC)"))
        return ports_parts

    def print_local_status(self, validator_status: Dict, all_status: bool):
        if is_container():
            return self._print_local_status_container(validator_status, all_status)

        color_print(self.local.translate("local_status_head"))

        node_mode = self.ton.get_node_mode()
        color_print(self.local.translate("node_mode").format(node_mode))

        node_ip = self.ton.get_validator_engine_ip()
        is_node_remote = node_ip != "127.0.0.1"
        if is_node_remote:
            node_ip_addr_text = self.local.translate("node_ip_address").format(node_ip)
            color_print(node_ip_addr_text)

        vconfig = None
        try:
            vconfig = self.ton.GetValidatorConfig()
            fullnode_adnl = base64.b64decode(vconfig.fullnode).hex().upper()
        except Exception:
            fullnode_adnl = "n/a"

        # Node ports
        if vconfig is not None:
            try:
                ports_parts = self._get_node_ports(vconfig)
                if ports_parts:
                    color_print(
                        self.local.translate("node_ports").format(
                            ", ".join(ports_parts)
                        )
                    )
            except Exception:
                pass

        if self.ton.using_validator():
            if all_status:
                validator_index = self.ton.GetValidatorIndex()
                validator_index_text = GetColorInt(validator_index, 0, logic="more")
            else:
                validator_index_text = "n/a"
            validator_index_text = self.local.translate(
                "local_status_validator_index"
            ).format(validator_index_text)
            print(validator_index_text)

        adnl_addr = self.ton.GetAdnlAddr()
        adnl_addr_text = self.local.translate("local_status_adnl_addr").format(
            bcolors.yellow_text(adnl_addr)
        )
        print(adnl_addr_text)

        fullnode_adnl_text = self.local.translate("local_status_fullnode_adnl").format(
            bcolors.yellow_text(fullnode_adnl)
        )
        print(fullnode_adnl_text)

        wallet_addr = "n/a"
        wallet_balance = "n/a"
        if self.ton.using_validator():
            try:
                validator_wallet = self.ton.GetValidatorWallet()
                wallet_addr = validator_wallet.addrB64
                if all_status:
                    validator_account = self.ton.GetAccount(validator_wallet.addrB64)
                    wallet_balance = validator_account.balance
            except Exception:
                pass

            wallet_addr_text = self.local.translate("local_status_wallet_addr").format(
                bcolors.yellow_text(wallet_addr)
            )
            print(wallet_addr_text)

            wallet_balance_text = self.local.translate(
                "local_status_wallet_balance"
            ).format(bcolors.green_text(wallet_balance))
            print(wallet_balance_text)

        cpu_number = psutil.cpu_count()
        cpu_load1, cpu_load5, cpu_load15 = get_load_avg()
        cpu_number_text = bcolors.yellow_text(cpu_number)
        cpu_load1_text = GetColorInt(cpu_load1, cpu_number, logic="less")
        cpu_load5_text = GetColorInt(cpu_load5, cpu_number, logic="less")
        cpu_load15_text = GetColorInt(cpu_load15, cpu_number, logic="less")
        cpu_load_text = self.local.translate("local_status_cpu_load").format(
            cpu_number_text, cpu_load1_text, cpu_load5_text, cpu_load15_text
        )
        print(cpu_load_text)

        statistics = self.ton.GetSettings("statistics")

        net_load_avg = self.ton.GetStatistics("netLoadAvg", statistics)
        if net_load_avg and isinstance(net_load_avg, list):
            net_load1, net_load5, net_load15 = net_load_avg[:3]
            net_load1_text = GetColorInt(net_load1, 300, logic="less")
            net_load5_text = GetColorInt(net_load5, 300, logic="less")
            net_load15_text = GetColorInt(net_load15, 300, logic="less")
            net_load_text = self.local.translate("local_status_net_load").format(
                net_load1_text, net_load5_text, net_load15_text
            )
            print(net_load_text)

        memory_info = get_memory_info()
        swap_info = get_swap_info()
        ram_usage = memory_info.get("usage")
        ram_usage_percent = memory_info.get("usagePercent")
        swap_usage = swap_info.get("usage")
        swap_usage_percent = swap_info.get("usagePercent")
        ram_usage_text = GetColorInt(ram_usage, 100, logic="less", ending=" Gb")
        ram_usage_percent_text = GetColorInt(
            ram_usage_percent, 90, logic="less", ending="%"
        )
        swap_usage_text = GetColorInt(swap_usage, 100, logic="less", ending=" Gb")
        swap_usage_percent_text = GetColorInt(
            swap_usage_percent, 90, logic="less", ending="%"
        )
        ram_load_text = "{cyan}ram:[{default}{data}, {percent}{cyan}]{endc}"
        ram_load_text = ram_load_text.format(
            cyan=bcolors.cyan,
            default=bcolors.default,
            endc=bcolors.endc,
            data=ram_usage_text,
            percent=ram_usage_percent_text,
        )
        swap_load_text = "{cyan}swap:[{default}{data}, {percent}{cyan}]{endc}"
        swap_load_text = swap_load_text.format(
            cyan=bcolors.cyan,
            default=bcolors.default,
            endc=bcolors.endc,
            data=swap_usage_text,
            percent=swap_usage_percent_text,
        )
        memory_load_text = self.local.translate("local_status_memory").format(
            ram_load_text, swap_load_text
        )
        print(memory_load_text)

        disks_load_avg = self.ton.GetStatistics("disksLoadAvg", statistics)
        disks_load_percent_avg = self.ton.GetStatistics(
            "disksLoadPercentAvg", statistics
        )
        if (
            disks_load_avg
            and isinstance(disks_load_avg, dict)
            and isinstance(disks_load_percent_avg, dict)
        ):
            disks_load_data = list()
            for key, item in disks_load_avg.items():
                disk_load15_text = bcolors.green_text(item[2])
                disk_load_percent15_text = GetColorInt(
                    disks_load_percent_avg[key][2], 80, logic="less", ending="%"
                )
                buff = "{}, {}"
                buff = "{}{}:[{}{}{}]{}".format(
                    bcolors.cyan, key, bcolors.default, buff, bcolors.cyan, bcolors.endc
                )
                disks_load_buff = buff.format(
                    disk_load15_text, disk_load_percent15_text
                )
                disks_load_data.append(disks_load_buff)
            disks_load_data = ", ".join(disks_load_data)
            disks_load_text = self.local.translate("local_status_disks_load").format(
                disks_load_data
            )
            print(disks_load_text)

        def _get_color_status(status: bool):
            if status:
                result = bcolors.green_text("working")
            else:
                result = bcolors.red_text("not working")
            return result

        mytoncore_status_bool = get_service_status("mytoncore")
        mytoncore_uptime = get_service_uptime("mytoncore")
        if mytoncore_uptime is not None:
            mytoncore_uptime_text = bcolors.green_text(ts_diff_to_human(mytoncore_uptime))
            mytoncore_status_color = _get_color_status(mytoncore_status_bool)
            mytoncore_status_text = self.local.translate(
                "local_status_mytoncore_status"
            ).format(mytoncore_status_color, mytoncore_uptime_text)
            print(mytoncore_status_text)

        if not is_node_remote:
            validator_status_bool = get_service_status("validator")
            validator_uptime = get_service_uptime("validator")
            if validator_uptime is not None:
                validator_uptime_text = bcolors.green_text(ts_diff_to_human(validator_uptime))
                validator_status_color = _get_color_status(validator_status_bool)
                validator_status_text = self.local.translate(
                    "local_status_validator_status"
                ).format(validator_status_color, validator_uptime_text)
                print(validator_status_text)

        if validator_status.initial_sync:
            validator_initial_sync_text = self.local.translate(
                "local_status_validator_initial_sync"
            ).format(validator_status["process.initial_sync"])
            print(validator_initial_sync_text)
        elif (
            self.ton.in_initial_sync()
        ):  # states have been downloaded, now downloading blocks
            validator_initial_sync_text = self.local.translate(
                "local_status_validator_initial_sync"
            ).format(
                f"Syncing blocks, last known block was {validator_status.out_of_sync} s ago"
            )
            print(validator_initial_sync_text)
        else:
            validator_out_of_sync_text = self.local.translate(
                "local_status_validator_out_of_sync"
            ).format(GetColorInt(validator_status.out_of_sync, 20, logic="less"))
            master_out_of_sync_text = self.local.translate(
                "local_status_master_out_of_sync"
            ).format(
                GetColorInt(
                    validator_status.masterchain_out_of_sync,
                    20,
                    logic="less",
                    ending=" sec",
                )
            )
            shard_out_of_sync_text = self.local.translate(
                "local_status_shard_out_of_sync"
            ).format(
                GetColorInt(
                    validator_status.shardchain_out_of_sync,
                    5,
                    logic="less",
                    ending=" blocks",
                )
            )
            print(validator_out_of_sync_text)
            print(master_out_of_sync_text)
            print(shard_out_of_sync_text)

        if validator_status.stateserializerenabled:
            validator_out_of_ser_text = self.local.translate(
                "local_status_validator_out_of_ser"
            ).format(f"{validator_status.out_of_ser} blocks ago")
            print(validator_out_of_ser_text)

        if (
            self.ton.using_validator()
            and validator_status.validator_groups_master is not None
            and validator_status.validator_groups_shard is not None
        ):
            active_validator_groups = self.local.translate(
                "active_validator_groups"
            ).format(
                validator_status.validator_groups_master,
                validator_status.validator_groups_shard,
            )
            print(active_validator_groups)

        node_stats = self.local.try_function(self.ton.get_node_statistics)
        if node_stats is not None:
            if self.ton.using_validator():
                if "collated" in node_stats and "validated" in node_stats:
                    collated = self.local.translate("collated_blocks").format(
                        node_stats["collated"]["ok"], node_stats["collated"]["error"]
                    )
                    validated = self.local.translate("validated_blocks").format(
                        node_stats["validated"]["ok"], node_stats["validated"]["error"]
                    )
                else:
                    collated = self.local.translate("collated_blocks").format(
                        "collecting data...", "wait for the next validation round"
                    )
                    validated = self.local.translate("validated_blocks").format(
                        "collecting data...", "wait for the next validation round"
                    )
                print(collated)
                print(validated)
            if self.ton.using_liteserver():
                if "ls_queries" in node_stats:
                    ls_queries = self.local.translate("ls_queries").format(
                        node_stats["ls_queries"]["time"],
                        node_stats["ls_queries"]["ok"],
                        node_stats["ls_queries"]["error"],
                    )
                    print(ls_queries)
        else:
            self.local.add_log("Failed to get node statistics", "warning")

        db_size = self.ton.GetDbSize()
        db_usage = self.ton.GetDbUsage()
        db_size_text = GetColorInt(db_size, 1000, logic="less", ending=" Gb")
        db_usage_text = GetColorInt(db_usage, 80, logic="less", ending="%")
        db_status_text = self.local.translate("local_status_db").format(
            db_size_text, db_usage_text
        )
        print(db_status_text)

        paths = self.ton.get_paths()
        mtc_git_path = paths.mtc_src
        try:
            fix_git_config(mtc_git_path)
            mtc_git_hash = get_git_hash(mtc_git_path, short=True)
            mtc_git_branch = get_git_branch(mtc_git_path)
            mtc_git_hash_text = bcolors.yellow_text(mtc_git_hash)
            mtc_git_branch_text = bcolors.yellow_text(mtc_git_branch)
            mtc_version_text = self.local.translate("local_status_version_mtc").format(
                mtc_git_hash_text, mtc_git_branch_text
            )
            print(mtc_version_text)
        except Exception:
            pass

        validator_git_path = paths.ton_src
        try:
            fix_git_config(validator_git_path)
            validator_bin_git_path = paths.ton_bin / "validator-engine" / "validator-engine"
            validator_git_branch = get_git_branch(validator_git_path)
            validator_git_hash = get_bin_git_hash(validator_bin_git_path, short=True)
            validator_git_hash_text = bcolors.yellow_text(validator_git_hash)
            validator_git_branch_text = bcolors.yellow_text(validator_git_branch)
            validator_version_text = self.local.translate(
                "local_status_version_validator"
            ).format(validator_git_hash_text, validator_git_branch_text)
            print(validator_version_text)
        except Exception:
            pass

        print()


    def _print_local_status_container(self, validator_status: Dict, all_status: bool):
        color_print(self.local.translate("local_status_head"))
        paths = self.ton.get_paths()
        self.print_initialization_status(paths)

        node_mode = self._status_value(self.ton.get_node_mode, "n/a")
        if (is_container() and self.ton.local.db.get("validatorConsole") is None
                and not (paths.ton_work / "controller/initialized.json").is_file()):
            node_mode = "n/a (not configured yet)"
        color_print(self.local.translate("node_mode").format(node_mode))

        node_ip = self._status_value(self.ton.get_validator_engine_ip)
        is_node_remote = node_ip is not None and node_ip != "127.0.0.1"
        if is_node_remote:
            node_ip_addr_text = self.local.translate("node_ip_address").format(node_ip)
            color_print(node_ip_addr_text)

        vconfig = None
        if validator_status.is_working or not is_container():
            vconfig = self._status_value(self.ton.GetValidatorConfig)
        if vconfig is None:
            # The node writes this file before console keys are initialized.
            config = self._read_status_json(paths.ton_db / "config.json")
            if config:
                vconfig = Dict(config)
        try:
            fullnode_adnl = base64.b64decode(vconfig.fullnode).hex().upper() if vconfig else "n/a"
        except Exception:
            fullnode_adnl = "n/a"

        if not validator_status.is_working:
            configured = self.ton.local.db.get("validatorConsole") is not None
            detail = "unavailable" if configured else "unavailable (not configured yet)"
            print(f"Validator console: {detail}")

        # Node ports
        if vconfig is not None:
            try:
                ports_parts = self._get_node_ports(vconfig)
                if ports_parts:
                    color_print(
                        self.local.translate("node_ports").format(
                            ", ".join(ports_parts)
                        )
                    )
            except Exception:
                pass

        if self.ton.using_validator():
            if all_status:
                validator_index = self._status_value(self.ton.GetValidatorIndex)
                validator_index_text = self._status_number(validator_index, 0, logic="more")
            else:
                validator_index_text = "n/a"
            validator_index_text = self.local.translate(
                "local_status_validator_index"
            ).format(validator_index_text)
            print(validator_index_text)

        adnl_addr = self._status_value(self.ton.GetAdnlAddr, "n/a")
        adnl_addr_text = self.local.translate("local_status_adnl_addr").format(
            bcolors.yellow_text(adnl_addr)
        )
        print(adnl_addr_text)

        fullnode_adnl_text = self.local.translate("local_status_fullnode_adnl").format(
            bcolors.yellow_text(fullnode_adnl)
        )
        print(fullnode_adnl_text)

        wallet_addr = "n/a"
        wallet_balance = "n/a"
        if self.ton.using_validator():
            try:
                validator_wallet = self.ton.GetValidatorWallet()
                wallet_addr = validator_wallet.addrB64
                if all_status:
                    validator_account = self.ton.GetAccount(validator_wallet.addrB64)
                    wallet_balance = validator_account.balance
            except Exception:
                pass

            wallet_addr_text = self.local.translate("local_status_wallet_addr").format(
                bcolors.yellow_text(wallet_addr)
            )
            print(wallet_addr_text)

            wallet_balance_text = self.local.translate(
                "local_status_wallet_balance"
            ).format(bcolors.green_text(wallet_balance) if isinstance(wallet_balance, (int, float)) else "n/a")
            print(wallet_balance_text)

        cpu_number = psutil.cpu_count()
        cpu_load1, cpu_load5, cpu_load15 = get_load_avg()
        cpu_number_text = bcolors.yellow_text(cpu_number)
        cpu_load1_text = GetColorInt(cpu_load1, cpu_number, logic="less")
        cpu_load5_text = GetColorInt(cpu_load5, cpu_number, logic="less")
        cpu_load15_text = GetColorInt(cpu_load15, cpu_number, logic="less")
        cpu_load_text = self.local.translate("local_status_cpu_load").format(
            cpu_number_text, cpu_load1_text, cpu_load5_text, cpu_load15_text
        )
        print(cpu_load_text)

        statistics = self._status_value(lambda: self.ton.GetSettings("statistics"), {})

        net_load_avg = self._status_value(lambda: self.ton.GetStatistics("netLoadAvg", statistics))
        if isinstance(net_load_avg, list) and len(net_load_avg) >= 3:
            net_load1, net_load5, net_load15 = net_load_avg[:3]
            def format_network_load(value):
                measured = value if isinstance(value, (int, float)) and value >= 0 else None
                return self._status_number(measured, 300, logic="less")

            net_load1_text = format_network_load(net_load1)
            net_load5_text = format_network_load(net_load5)
            net_load15_text = format_network_load(net_load15)
            net_load_text = self.local.translate("local_status_net_load").format(
                net_load1_text, net_load5_text, net_load15_text
            )
            print(net_load_text)

        memory_info = self._status_value(get_memory_info) or {}
        swap_info = self._status_value(get_swap_info) or {}
        ram_usage = memory_info.get("usage")
        ram_usage_percent = memory_info.get("usagePercent")
        swap_usage = swap_info.get("usage")
        swap_usage_percent = swap_info.get("usagePercent")
        ram_usage_text = self._status_number(ram_usage, 100, logic="less", ending=" Gb")
        ram_usage_percent_text = self._status_number(
            ram_usage_percent, 90, logic="less", ending="%"
        )
        swap_usage_text = self._status_number(swap_usage, 100, logic="less", ending=" Gb")
        swap_usage_percent_text = self._status_number(
            swap_usage_percent, 90, logic="less", ending="%"
        )
        ram_load_text = "{cyan}ram:[{default}{data}, {percent}{cyan}]{endc}"
        ram_load_text = ram_load_text.format(
            cyan=bcolors.cyan,
            default=bcolors.default,
            endc=bcolors.endc,
            data=ram_usage_text,
            percent=ram_usage_percent_text,
        )
        swap_load_text = "{cyan}swap:[{default}{data}, {percent}{cyan}]{endc}"
        swap_load_text = swap_load_text.format(
            cyan=bcolors.cyan,
            default=bcolors.default,
            endc=bcolors.endc,
            data=swap_usage_text,
            percent=swap_usage_percent_text,
        )
        memory_load_text = self.local.translate("local_status_memory").format(
            ram_load_text, swap_load_text
        )
        print(memory_load_text)

        disks_load_avg = self._status_value(lambda: self.ton.GetStatistics("disksLoadAvg", statistics))
        disks_load_percent_avg = self._status_value(lambda: self.ton.GetStatistics("disksLoadPercentAvg", statistics))
        if (
            disks_load_avg
            and isinstance(disks_load_avg, dict)
            and isinstance(disks_load_percent_avg, dict)
        ):
            disks_load_data = list()
            for key, item in disks_load_avg.items():
                percent = disks_load_percent_avg.get(key)
                if not isinstance(item, list) or len(item) < 3 or not isinstance(percent, list) or len(percent) < 3:
                    continue
                disk_load = item[2]
                disk_load15_text = bcolors.green_text(disk_load) if isinstance(disk_load, (int, float)) and disk_load >= 0 else "n/a"
                disk_load_percent15_text = self._status_number(
                    percent[2], 80, logic="less", ending="%"
                )
                buff = "{}, {}"
                buff = "{}{}:[{}{}{}]{}".format(
                    bcolors.cyan, key, bcolors.default, buff, bcolors.cyan, bcolors.endc
                )
                disks_load_buff = buff.format(
                    disk_load15_text, disk_load_percent15_text
                )
                disks_load_data.append(disks_load_buff)
            disks_load_data = ", ".join(disks_load_data)
            disks_load_text = self.local.translate("local_status_disks_load").format(
                disks_load_data
            )
            print(disks_load_text)

        def _get_color_status(status: bool | None):
            if status is None:
                result = bcolors.yellow_text("unavailable")
            elif status:
                result = bcolors.green_text("working")
            else:
                result = bcolors.red_text("not working")
            return result

        def _service_text(name, working):
            if not is_container():
                return _get_color_status(working)
            state = self._status_value(lambda: get_service_state(name))
            if state in ("STARTING", "BACKOFF", "STOPPING"):
                detail = {"STARTING": "starting", "BACKOFF": "restarting", "STOPPING": "stopping"}[state]
                return bcolors.yellow_text(detail)
            if state in ("EXITED", "FATAL"):
                return bcolors.red_text("failed")
            if state == "RUNNING" and not container_initialization_complete(self.ton):
                return bcolors.yellow_text("running (initializing)")
            return _get_color_status(working)

        mytoncore_status_bool = self._status_value(lambda: get_service_status("mytoncore"))
        mytoncore_uptime = self._status_value(lambda: get_service_uptime("mytoncore")) if mytoncore_status_bool else None
        mytoncore_uptime_text = bcolors.green_text(ts_diff_to_human(mytoncore_uptime)) if mytoncore_uptime is not None else "uptime n/a"
        mytoncore_status_text = self.local.translate(
            "local_status_mytoncore_status"
        ).format(_service_text("mytoncore", mytoncore_status_bool), mytoncore_uptime_text)
        print(mytoncore_status_text)

        if not is_node_remote:
            validator_status_bool = self._status_value(lambda: get_service_status("validator"))
            validator_uptime = self._status_value(lambda: get_service_uptime("validator")) if validator_status_bool else None
            validator_uptime_text = bcolors.green_text(ts_diff_to_human(validator_uptime)) if validator_uptime is not None else "uptime n/a"
            validator_status_text = self.local.translate(
                "local_status_validator_status"
            ).format(_service_text("validator", validator_status_bool), validator_uptime_text)
            print(validator_status_text)

        if validator_status.initial_sync:
            validator_initial_sync_text = self.local.translate(
                "local_status_validator_initial_sync"
            ).format(validator_status["process.initial_sync"])
            print(validator_initial_sync_text)
        elif (
            self.ton.in_initial_sync()
            and (
                isinstance(validator_status.masterchain_out_of_sync, (int, float))
                or isinstance(validator_status.shardchain_out_of_sync, (int, float))
            )
        ):  # states have been downloaded, now downloading blocks
            sync_details = []
            if isinstance(validator_status.masterchain_out_of_sync, (int, float)):
                sync_details.append(f"masterchain is {validator_status.masterchain_out_of_sync} sec behind")
            if isinstance(validator_status.shardchain_out_of_sync, (int, float)):
                sync_details.append(f"shardchain is {validator_status.shardchain_out_of_sync} blocks behind")
            validator_initial_sync_text = self.local.translate(
                "local_status_validator_initial_sync"
            ).format("Syncing blocks, " + ", ".join(sync_details))
            print(validator_initial_sync_text)
        else:
            validator_out_of_sync_text = self.local.translate(
                "local_status_validator_out_of_sync"
            ).format(self._status_number(validator_status.out_of_sync, 20, logic="less"))
            master_out_of_sync_text = self.local.translate(
                "local_status_master_out_of_sync"
            ).format(
                self._status_number(
                    validator_status.masterchain_out_of_sync,
                    20,
                    logic="less",
                    ending=" sec",
                )
            )
            shard_out_of_sync_text = self.local.translate(
                "local_status_shard_out_of_sync"
            ).format(
                self._status_number(
                    validator_status.shardchain_out_of_sync,
                    5,
                    logic="less",
                    ending=" blocks",
                )
            )
            print(validator_out_of_sync_text)
            print(master_out_of_sync_text)
            print(shard_out_of_sync_text)

        if validator_status.stateserializerenabled:
            validator_out_of_ser_text = self.local.translate(
                "local_status_validator_out_of_ser"
            ).format(f"{validator_status.out_of_ser} blocks ago")
            print(validator_out_of_ser_text)

        if (
            self.ton.using_validator()
            and validator_status.validator_groups_master is not None
            and validator_status.validator_groups_shard is not None
        ):
            active_validator_groups = self.local.translate(
                "active_validator_groups"
            ).format(
                validator_status.validator_groups_master,
                validator_status.validator_groups_shard,
            )
            print(active_validator_groups)

        node_stats = self._status_value(self.ton.get_node_statistics)
        if node_stats is not None:
            if self.ton.using_validator() and validator_status.is_working:
                if "collated" in node_stats and "validated" in node_stats:
                    collated = self.local.translate("collated_blocks").format(
                        node_stats["collated"]["ok"], node_stats["collated"]["error"]
                    )
                    validated = self.local.translate("validated_blocks").format(
                        node_stats["validated"]["ok"], node_stats["validated"]["error"]
                    )
                else:
                    collated = self.local.translate("collated_blocks").format(
                        "collecting data...", "wait for the next validation round"
                    )
                    validated = self.local.translate("validated_blocks").format(
                        "collecting data...", "wait for the next validation round"
                    )
                print(collated)
                print(validated)
            if self.ton.using_liteserver():
                if "ls_queries" in node_stats:
                    ls_queries = self.local.translate("ls_queries").format(
                        node_stats["ls_queries"]["time"],
                        node_stats["ls_queries"]["ok"],
                        node_stats["ls_queries"]["error"],
                    )
                    print(ls_queries)
        else:
            self.local.add_log("Failed to get node statistics", "warning")

        db_size = self._status_value(self.ton.GetDbSize)
        db_usage = self._status_value(self.ton.GetDbUsage)
        db_size_text = self._status_number(db_size, 1000, logic="less", ending=" Gb")
        db_usage_text = self._status_number(db_usage, 80, logic="less", ending="%")
        db_status_text = self.local.translate("local_status_db").format(
            db_size_text, db_usage_text
        )
        print(db_status_text)

        mtc_image = bcolors.yellow_text(get_controller_image_ref())
        validator_image = bcolors.yellow_text(get_ton_image_ref())
        print(self.local.translate("local_status_image_mtc").format(mtc_image))
        print(self.local.translate("local_status_image_validator").format(validator_image))

        print()

    def print_ton_config(
        self,
        full_config_addr: str,
        full_elector_addr: str,
        config15: Config15,
        config17: Config17,
    ):
        color_print(self.local.translate("ton_config_head"))

        full_config_addr_text = self.local.translate(
            "ton_config_configurator_addr"
        ).format(bcolors.yellow_text(full_config_addr))
        print(full_config_addr_text)

        full_elector_addr_text = self.local.translate("ton_config_elector_addr").format(
            bcolors.yellow_text(full_elector_addr)
        )
        print(full_elector_addr_text)

        validators_elected_for_text = bcolors.yellow_text(
            config15.validators_elected_for
        )
        elections_start_before_text = bcolors.yellow_text(
            config15.elections_start_before
        )
        elections_end_before_text = bcolors.yellow_text(config15.elections_end_before)
        stake_held_for_text = bcolors.yellow_text(config15.stake_held_for)
        elections_text = self.local.translate("ton_config_elections").format(
            validators_elected_for_text,
            elections_start_before_text,
            elections_end_before_text,
            stake_held_for_text,
        )
        print(elections_text)

        min_stake_text = bcolors.yellow_text(config17.min_stake)
        max_stake_text = bcolors.yellow_text(config17.max_stake)
        stake_text = self.local.translate("ton_config_stake").format(
            min_stake_text, max_stake_text
        )
        print(stake_text)
        print()

    def print_network_times(
        self,
        root_workchain_enabled_time_int: int,
        start_work_time: int,
        old_start_work_time: int,
        config15: Config15,
    ):
        color_print(self.local.translate("times_head"))

        root_workchain_enabled_time = timestamp2utcdatetime(
            root_workchain_enabled_time_int
        )
        root_workchain_enabled_time_text = self.local.translate(
            "times_root_workchain_enabled_time"
        ).format(bcolors.yellow_text(root_workchain_enabled_time))
        print(root_workchain_enabled_time_text)

        validators_elected_for = config15.validators_elected_for
        elections_start_before = config15.elections_start_before
        elections_end_before = config15.elections_end_before

        if start_work_time == 0:
            start_work_time = old_start_work_time

        start_validation = start_work_time
        end_validation = start_work_time + validators_elected_for
        start_election = start_work_time - elections_start_before
        end_election = start_work_time - elections_end_before
        start_next_election = start_election + validators_elected_for

        start_validation_time = timestamp2utcdatetime(start_validation)
        end_validation_time = timestamp2utcdatetime(end_validation)
        start_election_time = timestamp2utcdatetime(start_election)
        end_election_time = timestamp2utcdatetime(end_election)
        start_next_election_time = timestamp2utcdatetime(start_next_election)

        def _get_color_time(datetime: str, timestamp: int):
            new_timestamp = get_timestamp()
            if timestamp > new_timestamp:
                result = bcolors.green_text(datetime)
            else:
                result = bcolors.yellow_text(datetime)
            return result

        start_validation_time_text = self.local.translate(
            "times_start_validation_time"
        ).format(_get_color_time(start_validation_time, start_validation))
        print(start_validation_time_text)

        end_validation_time_text = self.local.translate(
            "times_end_validation_time"
        ).format(_get_color_time(end_validation_time, end_validation))
        print(end_validation_time_text)

        start_election_time_text = self.local.translate(
            "times_start_election_time"
        ).format(_get_color_time(start_election_time, start_election))
        print(start_election_time_text)

        end_election_time_text = self.local.translate("times_end_election_time").format(
            _get_color_time(end_election_time, end_election)
        )
        print(end_election_time_text)

        start_next_election_time_text = self.local.translate(
            "times_start_next_election_time"
        ).format(_get_color_time(start_next_election_time, start_next_election))
        print(start_next_election_time_text)

    def GetSettings(self, name: str) -> None:
        result = self.ton.GetSettings(name)
        print(json.dumps(result, indent=2))

    def SetSettings(self, name: str, value: str, *, force: bool = False) -> None:
        if name == "usePool" or name == "useController":
            mode_name = "nominator-pool" if name == "usePool" else "liquid-staking"
            color_print(
                f"{{red}} Error: set {name} ... is deprecated and does not work {{endc}}."
                f"\nInstead, use {{bold}}enable_mode {mode_name}{{endc}}"
            )
            return
        from modules import get_setting

        setting = get_setting(name)
        if not force:
            if setting is None:
                color_print(
                    f"{{red}} Error: setting {name} not found.{{endc}} Use flag --force to set it anyway"
                )
                return
            if name == "validatorWalletName":
                wallet = self.ton.GetLocalWallet(value, version="v1")  # avoid using network to determine wallet version
                if wallet.workchain != -1:
                    raise Exception("Validator wallet must be in masterchain")

        if setting is not None and setting.mode is not None:
            if not self.ton.get_mode_value(setting.mode) and not force:
                color_print(
                    f"{{red}} Error: mode {setting.mode} is disabled.{{endc}} Use flag --force to set it anyway"
                )
                return
        self.ton.SetSettings(name, value)
        color_print("SetSettings - {green}OK{endc}")

    def enable_mode(
        self,
        mode_name: _ModeName,
    ) -> None:
        self.ton.enable_mode(mode_name)
        color_print("enable_mode - {green}OK{endc}")
        self.local.exit()

    def disable_mode(
        self,
        mode_name: _ModeName,
    ) -> None:
        self.ton.disable_mode(mode_name)
        color_print("disable_mode - {green}OK{endc}")
        self.local.exit()

    def download_archive_blocks(
        self,
        download_path: pathlib.Path,
        from_block_seqno: int,
        to_block_seqno: Optional[int] = None,
        *,
        port: Annotated[Optional[int], Arg(help="TON Storage API port, default: the one of ton_storage.service")] = None,
        only_master: Annotated[bool, Arg(help="download only masterchain blocks")] = False,
    ) -> None:
        api_port = port
        if api_port is None:
            api_port = get_ton_storage_port(self.local)
            if api_port is None:
                raise Exception(
                    "Failed to get Ton Storage API port and --port was not given"
                )

        # check ton storage is alive
        local_ts_url = f"http://127.0.0.1:{api_port}"

        try:
            requests.get(local_ts_url + "/api/v1/list", timeout=3)
        except Exception as e:
            color_print(
                f"{{red}}Error: cannot connect to ton-storage at 127.0.0.1:{api_port}: {type(e)}: {e}. "
                f"Make sure `ton_storage` daemon is running or install it via `installer enable TS`.{{endc}}"
            )
            return

        download_blocks(
            self.local,
            str(download_path.absolute()),
            api_port,
            self.ton.IsTestnet(),
            from_block_seqno,
            to_block_seqno,
            only_master,
        )

    def set_quic_port(
        self, port: Annotated[int, Arg(type=tcp_port)], category: int = 2
    ) -> None:
        vconfig = self.ton.GetValidatorConfig()
        ip = int2ip(vconfig["addrs"][0]["ip"])
        adnl_addr = self.ton.GetAdnlAddr()
        if adnl_addr is None:
            raise Exception("ADNL address is not set")

        for addr in vconfig["addrs"]:
            if addr.get("@type") == "engine.addr" and category not in addr.get(
                "categories", []
            ):
                raise Exception(f"Category {category} is not set for address {addr}")

        for addr in vconfig["addrs"]:
            if addr.get("@type") == "engine.quicAddr":
                addr_ip = int2ip(addr["ip"])
                addr_port = addr["port"]
                cat = addr["categories"]
                priocat = addr["priority_categories"]
                cat = f"[ {' '.join(map(str, cat))} ]"
                priocat = f"[ {' '.join(map(str, priocat))} ]"
                result = self.ton.validatorConsole.run(
                    f"del-quic-addr {addr_ip}:{addr_port} {cat} {priocat}"
                )
                color_print(
                    f"Deleted quic addr {addr_ip}:{addr_port}: {result.splitlines()[-1].strip()}"
                )

        if port > 0:
            self.ton.update_adnl_category(adnl_addr=adnl_addr, category=category)

            from modules.collator import CollatorModule

            collators = CollatorModule(self.ton, self.local).get_collators()
            collator_adnls = []
            for collator in collators:
                collator_adnls.append(b642hex(collator).upper())
            for collator_adnl in set(collator_adnls):
                self.ton.update_adnl_category(
                    adnl_addr=collator_adnl, category=category
                )

            result = self.ton.validatorConsole.run(
                f"add-quic-addr {ip}:{port} [ {category} ] [ ]"
            )
            self.local.add_log(
                f"Added quic addr {ip}:{port}: {result.splitlines()[-1].strip()}",
                "info",
            )

    def Update(
        self,
        target: Annotated[Optional[str], Arg(help="branch, tag or commit, or a github url (optionally .../tree/<branch>)")] = None,
        target_branch: Annotated[Optional[str], Arg(help="branch, tag or commit when target is a github url")] = None,
        *,
        branch: Annotated[Optional[str], Arg(help="branch, tag or commit to update to")] = None,
    ) -> None:
        if is_container():
            color_print(
                "The update command is disabled inside this container. "
                "Update MyTonCtrl using the appropriate Docker image "
                "(MYTONCTRL_IMAGE in .env) and recreate the container."
            )
            return
        paths = self.ton.get_paths()
        author, repo, branch, _ = check_git(
            parse_git_target(target, target_branch, branch=branch),
            paths.mtc_src,
            "mytonctrl",
            "update",
        )
        # Run script
        with get_package_resource_path(
            "mytonctrl", "scripts/update.sh"
        ) as update_script_path:
            runArgs = [
                "bash",
                str(update_script_path),
                "-a",
                author,
                "-r",
                repo,
                "-b",
                branch,
                "-S",
                str(paths.mtc_src),
                "-p",
                sys.executable,
            ]
            exitCode = run_as_root(runArgs)
        if exitCode == 0:
            text = "Update - {green}OK{endc}"
        else:
            text = "Update - {red}Error{endc}"
        color_print(text)
        self.local.exit()

    def Upgrade(
        self,
        target: Annotated[Optional[str], Arg(help="branch, tag or commit, or a github url (optionally .../tree/<branch>)")] = None,
        target_branch: Annotated[Optional[str], Arg(help="branch, tag or commit when target is a github url")] = None,
        *,
        branch: Annotated[Optional[str], Arg(help="branch, tag or commit to build")] = None,
        url: Annotated[Optional[str], Arg(help="git url of a TON fork, optionally with #ref")] = None,
    ) -> None:
        if is_container():
            color_print(
                "The upgrade command is disabled inside this container. "
                "Update TON binaries using the appropriate Docker image "
                "(TON_IMAGE in .env), export the binaries and restart the MyTonCtrl container."
            )
            return
        paths = self.ton.get_paths()
        author, repo, branch, git_url = check_git(
            parse_git_target(target, target_branch, branch=branch, url=url),
            paths.ton_src,
            "ton",
            "upgrade",
        )

        clang_version = get_clang_major_version()
        if clang_version is None or clang_version < self.CLANG_VERSION_REQUIRED:
            text = f"{{red}}WARNING: THIS UPGRADE WILL MOST PROBABLY FAIL DUE TO A WRONG CLANG VERSION: {clang_version}, REQUIRED VERSION IS {self.CLANG_VERSION_REQUIRED}. RECOMMENDED TO EXIT NOW AND UPGRADE CLANG AS PER INSTRUCTIONS: https://apt.llvm.org/{{endc}}\n"
            color_print(text)
            if input("Continue with upgrade anyway? [Y/n]\n").strip().lower() not in (
                "y",
                "",
            ):
                print("aborted.")
                return

        with get_package_resource_path(
            "mytonctrl", "scripts/upgrade.sh"
        ) as upgrade_script_path:
            if git_url:
                runArgs = [
                    "bash",
                    str(upgrade_script_path),
                    "-g",
                    git_url,
                    "-b",
                    branch,
                ]
            else:
                runArgs = [
                    "bash",
                    str(upgrade_script_path),
                    "-a",
                    author,
                    "-r",
                    repo,
                    "-b",
                    branch,
                ]
            runArgs += ["-B", str(paths.ton_bin), "-S", str(paths.ton_src)]
            exitCode = run_as_root(runArgs)
        if exitCode == 0:
            text = "Upgrade - {green}OK{endc}"
        else:
            text = "Upgrade - {red}Error{endc}"
        color_print(text)

    def reload_global_config(self, url: Optional[str] = None) -> None:
        if url is None:
            network_name = self.ton.GetNetworkName()
            if network_name == "mainnet":
                url = "https://ton-blockchain.github.io/global.config.json"
            elif network_name == "testnet":
                url = "https://ton-blockchain.github.io/testnet-global.config.json"
            else:
                raise Exception(
                    "could not detect the network, please provide the config url explicitly"
                )

        self.local.add_log(f"Downloading global config from {url}", "info")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            config_text = response.text
            json.loads(config_text)  # make sure the downloaded config is valid json before replacing
        except Exception as e:
            color_print(
                f"reload_global_config error: {{red}}failed to download config from {url}: {e}{{endc}}"
            )
            return

        global_config_path = self.ton.get_paths().global_config_path
        with tempfile.NamedTemporaryFile("w", suffix=".json") as tmp_file:
            tmp_file.write(config_text)
            tmp_file.flush()
            exit_code = run_as_root(
                ["install", "-m", "0644", tmp_file.name, str(global_config_path)]
            )

        if exit_code == 0:
            color_print("reload_global_config - {green}OK{endc}")
        else:
            color_print("reload_global_config - {red}Error{endc}")

    def run_benchmark(
        self, *benchmark_args: str, tmp_dir: Optional[str] = None
    ) -> None:
        """Every option except --tmp-dir goes to benchmark.py: benchmark --nodes 4 --tps 1000

        To pass -h or --tmp-dir to benchmark.py itself, put it after --: benchmark -- -h
        """
        if is_container():
            args = list(benchmark_args)
            if tmp_dir is not None:
                args = ["--tmp-dir", tmp_dir, *args]
            return self._run_container_benchmark(args)

        if shutil.which("uv") is None:
            answer = input("uv is not installed. Install it? [y/n] ").strip().lower()
            if answer == "y":
                with tempfile.NamedTemporaryFile(prefix="uv_install_", suffix=".sh") as installer:
                    subprocess.run(
                        [
                            "curl",
                            "-LsSf",
                            "https://astral.sh/uv/install.sh",
                            "-o",
                            installer.name,
                        ],
                        check=True,
                    )
                    subprocess.run(["sh", installer.name], check=True)
                uv_local_bin = os.path.expanduser("~/.local/bin")
                if uv_local_bin not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = (
                        uv_local_bin + os.pathsep + os.environ.get("PATH", "")
                    )
                if shutil.which("uv") is None:
                    color_print("{red}Error: uv installation failed{endc}")
                    return
            else:
                return

        if get_service_status("validator"):
            color_print(
                "{red}Error: validator service is running. Stop it before running benchmark: `sudo systemctl stop validator`{endc}"
            )
            return

        if tmp_dir is not None:
            tmp_parent_dir = os.path.expanduser(tmp_dir)
            os.makedirs(tmp_parent_dir, exist_ok=True)
        else:
            tmp_parent_dir = str(self.ton.get_paths().ton_work / "tmp")
            try:
                st = os.lstat(tmp_parent_dir)
            except FileNotFoundError:
                self.local.add_log(f"Creating cache dir for the benchmark: {tmp_parent_dir}")
                exit_code = run_as_root(["mkdir", "-m", "777", tmp_parent_dir])
                if exit_code != 0:
                    color_print("{red}Error: failed to create benchmark temp directory{endc}")
                    return
            else:
                if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
                    color_print("{red}Error: benchmark temp path is not a directory{endc}")
                    return

        with tempfile.TemporaryDirectory(dir=tmp_parent_dir) as run_dir:
            run_dir = Path(run_dir).resolve()
            with get_package_resource_path(
                "mytonctrl", "scripts/benchmark.py"
            ) as benchmark_path:
                paths = self.ton.get_paths()
                shutil.copy(benchmark_path, run_dir / "benchmark.py")

                subprocess.run(
                    [
                        "uv",
                        "init",
                        "--python",
                        "3.14",
                        "--no-workspace",
                        "--name",
                        "benchmark",
                    ],
                    cwd=run_dir,
                    check=True,
                )

                src_dir = paths.ton_src
                test_dir = run_dir / "test"
                tontester_dir = test_dir / "tontester"

                shutil.copytree(src_dir / "test", test_dir)

                tl_dest = run_dir / "tl" / "generate" / "scheme"
                Path(tl_dest).mkdir(parents=True, exist_ok=True)

                for f in (src_dir / "tl" / "generate" / "scheme").glob("*.tl"):
                    shutil.copy(f, tl_dest)

                block_tlb_dest = run_dir / "crypto" / "block"
                block_tlb_dest.mkdir(parents=True, exist_ok=True)
                shutil.copy(src_dir / "crypto" / "block" / "block.tlb", block_tlb_dest)

                subprocess.run(
                    ["uv", "add", "--editable", tontester_dir], cwd=run_dir, check=True
                )

                subprocess.run(
                    ["uv", "run", tontester_dir / "generate_tl.py"],
                    cwd=run_dir,
                    check=True,
                )

                cmd = [
                    "uv",
                    "run",
                    "benchmark.py",
                    "--build-dir",
                    paths.ton_bin,
                    "--source-dir",
                    paths.ton_src,
                    "--work-dir",
                    str(run_dir / "test" / "integration" / ".network"),
                ] + list(benchmark_args)
                subprocess.run(cmd, cwd=run_dir)

    def _run_container_benchmark(self, args: list[str]):
        if not any(arg in ("--help", "-h") for arg in args):
            if not container_initialization_complete(self.ton):
                color_print("{red}Error: wait for node initialization to finish before running benchmark.{endc}")
                return
            state = get_service_state("validator")
            if state not in ("STOPPED", "FATAL"):
                color_print(
                    f"{{red}}Error: validator service state is {state or 'unknown'}. "
                    "Stop it before running benchmark.{endc}\n"
                    "Run these commands in the host shell:\n"
                    "docker compose exec mytonctrl sudo systemctl stop mytoncore\n"
                    "docker compose exec mytonctrl sudo systemctl stop validator"
                )
                return

        paths = self.ton.get_paths()
        subprocess.run([
            sys.executable, "/usr/local/lib/mytonctrl/benchmark.py",
            "--build-dir", str(paths.ton_bin),
            "--source-dir", str(paths.ton_src),
            "--work-root", str(paths.ton_work),
            "--", *args,
        ], check=True)

    def about(
        self,
        mode_name: _ModeName,
    ) -> None:
        mode = MODES[mode_name]
        mode_settings = get_mode_settings(mode_name)
        color_print(f"""{{cyan}}===[ {mode_name} MODE ]==={{endc}}""")
        color_print(f"""Description: {mode.description}""")
        color_print(
            "Enabled: "
            + color_text(
                "{green}yes{endc}"
                if self.ton.get_mode_value(mode_name)
                else "{red}no{endc}"
            )
        )
        print("Settings:", "no" if len(mode_settings) == 0 else "")
        for setting_name, setting in mode_settings.items():
            color_print(
                f"  {{bold}}{setting_name}{{endc}}: {setting.description}.\n    Default value: {setting.default_value}"
            )

    def run_installer(self, *command: str) -> None:
        from mytoninstaller.mytoninstaller import InstallerCtrl
        installer = InstallerCtrl.from_ton(self.ton)
        try:
            installer.run(' '.join(command))
        except SystemExit:
            self.local.add_log("Exited MyTonInstaller")
            pass

    def add_console_commands(self, console):
        console.add_command("update", self.Update)
        console.add_command("upgrade", self.Upgrade)
        console.add_command("reload_global_config", self.reload_global_config
        )
        console.add_command("installer", self.run_installer, forward_unknown=True
        )
        console.add_command("status", self.print_status)
        console.add_command("status_modes", self.mode_status)
        console.add_command("status_settings", self.settings_status)
        console.add_command("enable_mode", self.enable_mode)
        console.add_command("disable_mode", self.disable_mode)
        console.add_command("about", self.about)
        console.add_command("get", self.GetSettings)
        console.add_command("set", self.SetSettings)
        console.add_command("download_archive_blocks", self.download_archive_blocks
        )
        console.add_command("benchmark", self.run_benchmark, forward_unknown=True
        )
        console.add_command("set_quic_port", self.set_quic_port)
