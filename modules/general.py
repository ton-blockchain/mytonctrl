from __future__ import annotations

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
    fix_git_config,
    check_git,
    get_git_hash,
    get_git_branch,
)
from mytoninstaller.archive_blocks import download_blocks
from mytoninstaller.utils import get_ton_storage_port

from mytoncore.utils import get_package_resource_path, b642hex
from mytonctrl.console_cmd import (
    check_usage_one_arg,
    check_usage_args_min_max_len,
    add_command,
)
from mytonctrl.utils import (
    timestamp2utcdatetime,
    GetColorInt,
    get_clang_major_version,
    pop_arg_from_args,
    ts_diff_to_human,
    get_service_status,
    get_service_uptime,
)
from mytoncore.models import Config15, Config17
from modules.module import MtcModule


class GeneralModule(MtcModule):
    CLANG_VERSION_REQUIRED = 21

    def mode_status(self, _):
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

    def settings_status(self, _):
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

    def print_status(self, args: list[str]):
        opt = None
        if len(args) == 1:
            opt = args[0]
        fast = opt == "fast"

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

    def GetSettings(self, args: list[str]):
        if not check_usage_one_arg("get", args):
            return
        name = args[0]
        result = self.ton.GetSettings(name)
        print(json.dumps(result, indent=2))

    def SetSettings(self, args: list[str]):
        if not check_usage_args_min_max_len("set", args, min_len=2, max_len=3):
            return
        name = args[0]
        value = args[1]
        if name == "usePool" or name == "useController":
            mode_name = "nominator-pool" if name == "usePool" else "liquid-staking"
            color_print(
                f"{{red}} Error: set {name} ... is deprecated and does not work {{endc}}."
                f"\nInstead, use {{bold}}enable_mode {mode_name}{{endc}}"
            )
            return
        force = False
        if len(args) > 2:
            if args[2] == "--force":
                force = True
        from modules import get_setting

        setting = get_setting(name)
        if setting is None and not force:
            color_print(
                f"{{red}} Error: setting {name} not found.{{endc}} Use flag --force to set it anyway"
            )
            return
        if setting is not None and setting.mode is not None:
            if not self.ton.get_mode_value(setting.mode) and not force:
                color_print(
                    f"{{red}} Error: mode {setting.mode} is disabled.{{endc}} Use flag --force to set it anyway"
                )
                return
        self.ton.SetSettings(name, value)
        color_print("SetSettings - {green}OK{endc}")

    def enable_mode(self, args: list[str]):
        if not check_usage_one_arg("enable_mode", args):
            return
        name = args[0]
        self.ton.enable_mode(name)
        color_print("enable_mode - {green}OK{endc}")
        self.local.exit()

    def disable_mode(self, args: list[str]):
        if not check_usage_one_arg("disable_mode", args):
            return
        name = args[0]
        self.ton.disable_mode(name)
        color_print("disable_mode - {green}OK{endc}")
        self.local.exit()

    def download_archive_blocks(self, args: list[str]):
        if not check_usage_args_min_max_len("download_archive_blocks", args, 2, 5):
            return

        only_master = "--only-master" in args
        args.remove("--only-master") if only_master else None
        api_port = None
        if args[0].isdigit():
            api_port = int(args.pop(0))
        path = pathlib.Path(args[0])
        from_block = args[1]
        to_block = args[2] if len(args) >= 3 else None
        try:
            from_block, to_block = int(from_block), int(to_block) if to_block else None
        except ValueError:
            color_print(
                "{red}Bad args. from_block and to_block must be integers.{endc}"
            )
            return

        if api_port is None:
            api_port = get_ton_storage_port(self.local)
            if api_port is None:
                raise Exception(
                    "Failed to get Ton Storage API port and port was not provided"
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
            self.local, str(path.absolute()), api_port, self.ton.IsTestnet(), from_block, to_block, only_master
        )

    def set_quic_port(self, args: list[str]):
        if not check_usage_args_min_max_len("set_quic_port", args, 1, 2):
            return
        try:
            port = int(args[0])
        except ValueError:
            color_print("{red}Port must be an integer{endc}")
            return
        if port < 0 or port > 65535:
            color_print("{red}Port must be between 0 and 65535{endc}")
            return
        category = 2
        if len(args) > 1:
            try:
                category = int(args[1])
            except ValueError:
                color_print("{red}Category must be an integer{endc}")
                return

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
                collator_adnls.append(b642hex(collator["adnl_id"]).upper())
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

    def Update(self, args: list[str]):
        repo = "mytonctrl"
        paths = self.ton.get_paths()
        author, repo, branch, _ = check_git(
            args, paths.mtc_src, repo, "update"
        )  # todo: implement --url for update
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

    def Upgrade(self, args: list[str]):
        paths = self.ton.get_paths()

        author, repo, branch, git_url = check_git(
            args, paths.ton_src, default_repo="ton", text="upgrade"
        )

        clang_version = get_clang_major_version()
        if clang_version is None or clang_version < self.CLANG_VERSION_REQUIRED:
            text = f"{{red}}WARNING: THIS UPGRADE WILL MOST PROBABLY FAIL DUE TO A WRONG CLANG VERSION: {clang_version}, REQUIRED VERSION IS {self.CLANG_VERSION_REQUIRED}. RECOMMENDED TO EXIT NOW AND UPGRADE CLANG AS PER INSTRUCTIONS: https://gist.github.com/neodix42/24d6a401e928f7e895fcc8e7b7c5c24a{{endc}}\n"
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

    def run_benchmark(self, args: list[str]):
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

        tmp_parent_dir = pop_arg_from_args(args, "--tmp-dir")
        if tmp_parent_dir is not None:
            tmp_parent_dir = os.path.expanduser(tmp_parent_dir)
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

        with tempfile.TemporaryDirectory(dir=tmp_parent_dir) as tmp_dir:
            tmp_dir = Path(tmp_dir)
            with get_package_resource_path(
                "mytonctrl", "scripts/benchmark.py"
            ) as benchmark_path:
                paths = self.ton.get_paths()
                shutil.copy(benchmark_path, tmp_dir / "benchmark.py")

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
                    cwd=tmp_dir,
                    check=True,
                )

                src_dir = paths.ton_src
                test_dir = tmp_dir / "test"
                tontester_dir = test_dir / "tontester"

                shutil.copytree(src_dir / "test", test_dir)

                tl_dest = tmp_dir / "tl" / "generate" / "scheme"
                Path(tl_dest).mkdir(parents=True, exist_ok=True)

                for f in (src_dir / "tl" / "generate" / "scheme").glob("*.tl"):
                    shutil.copy(f, tl_dest)

                subprocess.run(["uv", "add", tontester_dir], cwd=tmp_dir, check=True)

                subprocess.run(
                    ["uv", "run", tontester_dir / "generate_tl.py"],
                    cwd=tmp_dir,
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
                    str(tmp_dir / "test" / "integration" / ".network"),
                ] + args
                subprocess.run(cmd, cwd=tmp_dir)

    def about(self, args: list[str]):
        from modules import get_mode, get_mode_settings

        if not check_usage_one_arg("about", args):
            return
        mode_name = args[0]
        mode = get_mode(mode_name)
        if mode is None:
            color_print(f"{{red}}Mode {mode_name} not found{{endc}}")
            return
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

    def run_installer(self, args: list[str]):
        from mytoninstaller.mytoninstaller import InstallerCtrl
        installer = InstallerCtrl.from_ton(self.ton)
        try:
            installer.run(' '.join(args))
        except SystemExit:
            self.local.add_log("Exited MyTonInstaller")
            pass

    def add_console_commands(self, console):
        add_command(self.local, console, "update", self.Update)
        add_command(self.local, console, "upgrade", self.Upgrade)
        add_command(self.local, console, "installer", self.run_installer)
        add_command(self.local, console, "status", self.print_status)
        add_command(self.local, console, "status_modes", self.mode_status)
        add_command(self.local, console, "status_settings", self.settings_status)
        add_command(self.local, console, "enable_mode", self.enable_mode)
        add_command(self.local, console, "disable_mode", self.disable_mode)
        add_command(self.local, console, "about", self.about)
        add_command(self.local, console, "get", self.GetSettings)
        add_command(self.local, console, "set", self.SetSettings)
        add_command(
            self.local, console, "download_archive_blocks", self.download_archive_blocks
        )
        add_command(self.local, console, "benchmark", self.run_benchmark)
        add_command(self.local, console, "set_quic_port", self.set_quic_port)
