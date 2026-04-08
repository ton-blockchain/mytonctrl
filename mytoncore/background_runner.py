from __future__ import annotations

import datetime
import os
import time
import json
import subprocess

import requests

from mypylib import MyPyClass
from mytoncore.mytoncore import MyTonCore
from mypylib.mypylib import get_timestamp
from mytoncore.stats_collector import StatsCollector
from mytoncore.telemetry import build_telemetry_payload, build_overlay_telemetry_payload

from modules.custom_overlays import CustomOverlayModule
from modules.alert_bot import AlertBotModule
from modules.prometheus import PrometheusModule
from modules.validator import ValidatorModule


class BackgroundRunner:
    def __init__(self, local: MyPyClass):
        self._local = local
        self._ton = MyTonCore(local)
        self._stats_collector = StatsCollector(local, self._ton)

        self._validator_module = ValidatorModule(self._ton, local)
        self._custom_overlay_module = CustomOverlayModule(self._ton, local)
        self._alert_bot_module = AlertBotModule(self._ton, local)
        self._prometheus_module = PrometheusModule(self._ton, local)

        self._slash_time: int | None = None

    def _offers(self):
        save_offers = self._ton.GetSaveOffers()
        if save_offers:
            self._ton.offers_gc(save_offers)
        else:
            return
        offers = self._ton.GetOffers()
        for offer in offers:
            offer_hash = offer.get("hash")
            if offer_hash in save_offers:
                offer_pseudohash = offer.get("pseudohash")
                save_offer = save_offers.get(offer_hash)
                if isinstance(
                    save_offer, list
                ):  # new version of save offers {"hash": ["pseudohash", param_id]}
                    save_offer_pseudohash = save_offer[0]
                else:  # old version of save offers {"hash": "pseudohash"}
                    save_offer_pseudohash = save_offer
                if (
                    offer_pseudohash == save_offer_pseudohash
                    and offer_pseudohash is not None
                ):
                    self._ton.VoteOffer(offer)

    def _complaints(self):
        validator_index = self._ton.GetValidatorIndex()
        if validator_index < 0:
            return
        if time.time() < 1776643200:
            return

        # Voting for complaints
        config32 = self._ton.GetConfig32()
        election_id = config32.get("startWorkTime")
        complaints = self._ton.GetComplaints(election_id)  # get complaints from Elector
        if not complaints:
            return
        valid_complaints = self._ton.get_valid_complaints(complaints, election_id)
        for c in valid_complaints.values():
            complaint_hash = c.get("hash")
            self._ton.VoteComplaint(election_id, complaint_hash)

    def _slashing(self):
        is_slashing = self._local.db.get("isSlashing")
        is_validator = self._ton.using_validator()
        if is_slashing is not True or not is_validator:
            return

        # Creating complaints
        config32 = self._ton.GetConfig32()
        start = config32.get("startWorkTime")
        end = config32.get("endWorkTime")
        config15 = self._ton.GetConfig15()
        ts = get_timestamp()
        if not (
            end < ts < end + config15["stakeHeldFor"]
        ):  # check that currently is freeze time
            return
        self._local.add_log(
            "slash_time {}, start {}, end {}".format(self._slash_time, start, end),
            "debug",
        )
        if self._slash_time != start:
            end -= 60
            self._ton.CheckValidators(start, end)
            self._slash_time = start

    def _save_past_events(self):
        self._local.try_function(self._ton.GetElectionEntries)
        self._local.try_function(self._ton.GetComplaints)
        self._local.try_function(
            self._ton.GetValidatorsList, args=[True]
        )  # cache past vl

    def _scan_lite_servers(self):
        file_path = self._ton.liteClient.configPath
        if file_path is None:
            raise RuntimeError("liteClient.configPath is None")
        with open(file_path, "rt") as f:
            text = f.read()
        data = json.loads(text)

        result = []
        liteservers = data.get("liteservers")
        for index in range(len(liteservers)):
            try:
                self._ton.liteClient.Run("last", index=index)
                result.append(index)
            except Exception:
                pass

        self._local.db["liteServers"] = result

    def _check_initial_sync(self):
        if not self._ton.in_initial_sync():
            return
        validator_status = self._ton.GetValidatorStatus()
        if validator_status.initial_sync:
            return
        if validator_status.out_of_sync < 20:
            self._ton.set_initial_sync_off()
            return

    def _gc_import(self):
        if not self._ton.local.db.get("importGc", False):
            return
        self._local.add_log("GC import is running", "debug")
        import_path = "/var/ton-work/db/import"
        files = os.listdir(import_path)
        if not files:
            self._local.add_log("No files left to import", "debug")
            self._ton.local.db["importGc"] = False
            self._ton.local.save()
            return
        try:
            status = self._ton.GetValidatorStatus()
            node_seqno = int(status.shardclientmasterchainseqno)
        except Exception as e:
            self._local.add_log(
                f"Failed to get shardclientmasterchainseqno: {e}", "warning"
            )
            return
        to_delete = []
        to_delete_dirs = []
        for root, dirs, files in os.walk(import_path):
            if root != import_path and not dirs and not files:
                to_delete_dirs.append(root)
            for file in files:
                file_seqno = int(file.split(".")[1])
                if node_seqno > file_seqno + 101:
                    to_delete.append(os.path.join(root, file))
        for file_path in to_delete:
            try:
                os.remove(file_path)
            except Exception as e:
                self._local.add_log(f"Failed to remove file {file_path}: {e}", "error")
        for dir_path in to_delete_dirs:
            try:
                os.rmdir(dir_path)
            except Exception as e:
                self._local.add_log(f"Failed to remove dir {dir_path}: {e}", "error")
        self._local.add_log(
            f"Removed {len(to_delete)} import files and {len(to_delete_dirs)} import dirs up to {node_seqno} seqno",
            "debug",
        )

    def _backup_mytoncore_logs(self):
        logs_path = os.path.join(self._ton.tempDir, "old_logs")
        os.makedirs(logs_path, exist_ok=True)
        for file in os.listdir(logs_path):
            file_path = os.path.join(logs_path, file)
            if (
                time.time() - os.path.getmtime(file_path) < 3600
            ):  # check that last file was created not less than an hour ago
                return
        now = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        log_backup_tmp_path = os.path.join(logs_path, "mytoncore_log_" + now + ".log")
        subprocess.run(["cp", self._local.log_file_name, log_backup_tmp_path])
        self._ton.clear_dir(logs_path)

    def _telemetry(self):
        if self._local.db.get("sendTelemetry") is not True:
            return

        data = build_telemetry_payload(self._local, self._ton)

        lite_url_default = "https://telemetry.toncenter.com/report_status"
        lite_url = self._local.db.get("telemetryLiteUrl", lite_url_default)
        output = json.dumps(data)
        requests.post(lite_url, data=output, timeout=3)

    def _overlay_telemetry(self):
        if self._local.db.get("sendTelemetry") is not True:
            return

        data = build_overlay_telemetry_payload(self._ton)

        overlay_url_default = "https://telemetry.toncenter.com/report_overlays"
        overlay_url = self._local.db.get("overlayTelemetryUrl", overlay_url_default)
        output = json.dumps(data)
        requests.post(overlay_url, data=output, timeout=3)

    def _check_mytoncore_db(self):
        try:
            self._local.read_db(self._local.db_path)
            backup_path = self._local.db_path + ".backup"
            if (
                not os.path.isfile(backup_path)
                or time.time() - os.path.getmtime(backup_path) > 3600 * 6
            ):
                self._ton.create_self_db_backup()
            return
        except Exception as e:
            print(f"Failed to read mytoncore db: {e}")
            self._local.add_log(f"Failed to read mytoncore db: {e}", "error")
        self._ton.CheckConfigFile(None, None)  # get mytoncore db from backup

    def run(self):
        self._local.add_log("start background tasks running", "info")

        self._local.start_cycle(self._stats_collector.save_statistics, sec=10)
        self._local.start_cycle(self._telemetry, sec=60)
        self._local.start_cycle(self._overlay_telemetry, sec=7200)
        self._local.start_cycle(self._backup_mytoncore_logs, sec=3600 * 4)
        self._local.start_cycle(self._check_mytoncore_db, sec=600)

        if self._local.db.get("onlyNode"):  # mytoncore service works only for telemetry
            while True:
                time.sleep(10)
                continue

        self._local.start_cycle(self._validator_module.run_elections, sec=600)
        self._local.start_cycle(self._offers, sec=600)
        self._local.start_cycle(self._save_past_events, sec=300)

        t = 1800
        if self._ton.GetNetworkName() != "mainnet":
            t = 300
        self._local.start_cycle(self._complaints, sec=t)
        self._local.start_cycle(self._slashing, sec=t)
        self._local.start_cycle(self._scan_lite_servers, sec=60)
        self._local.start_cycle(self._stats_collector.save_node_statistics, sec=60)
        self._local.start_cycle(self._custom_overlay_module.custom_overlays, sec=60)
        self._local.start_cycle(self._alert_bot_module.check_status, sec=60)
        self._local.start_cycle(self._prometheus_module.push_metrics, sec=30)

        if self._ton.in_initial_sync():
            self._local.start_cycle(self._check_initial_sync, sec=120)

        self._local.start_cycle(self._gc_import, sec=600)

        while True:
            time.sleep(10)
            continue
