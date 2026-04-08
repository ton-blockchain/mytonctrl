from __future__ import annotations

import os
from collections import deque

import psutil

from mypylib.mypylib import MyPyClass, get_timestamp, b2mb, get_internet_interface_name

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mytoncore import MyTonCore

BUFFER_SIZE = 15 * 6


class StatsCollector:
    def __init__(self, local: MyPyClass, ton: "MyTonCore"):
        self._local = local
        self._ton = ton
        self._network: deque = deque([None] * BUFFER_SIZE, maxlen=BUFFER_SIZE)
        self._diskio: deque = deque([None] * BUFFER_SIZE, maxlen=BUFFER_SIZE)

    def save_statistics(self):
        self.read_network_data()
        self.save_network_statistics()
        self.read_disk_data()
        self.save_disk_statistics()

    def read_disk_data(self):
        timestamp = get_timestamp()
        disks = self.get_disks_list()
        buff = psutil.disk_io_counters(perdisk=True)
        data = dict()
        for name in disks:
            data[name] = dict()
            data[name]["timestamp"] = timestamp
            data[name]["busyTime"] = buff[name].busy_time  # pyright: ignore[reportAttributeAccessIssue]
            data[name]["readBytes"] = buff[name].read_bytes
            data[name]["writeBytes"] = buff[name].write_bytes
            data[name]["readCount"] = buff[name].read_count
            data[name]["writeCount"] = buff[name].write_count

        self._diskio.append(data)

    def save_disk_statistics(self):
        data = list(reversed(self._diskio))
        zerodata = data[0]
        buff1 = data[1 * 6 - 1]
        buff5 = data[5 * 6 - 1]
        buff15 = data[15 * 6 - 1]
        if buff5 is None:
            buff5 = buff1
        if buff15 is None:
            buff15 = buff5

        disks_load_avg = dict()
        disks_load_percent_avg = dict()
        iops_avg = dict()
        disks = self.get_disks_list()
        for name in disks:
            if zerodata[name]["busyTime"] == 0:
                continue
            disk_load1, disk_load_percent1, iops1 = self.calculate_disk_statistics(
                zerodata, buff1, name
            )
            disk_load5, disk_load_percent5, iops5 = self.calculate_disk_statistics(
                zerodata, buff5, name
            )
            disk_load15, disk_load_percent15, iops15 = self.calculate_disk_statistics(
                zerodata, buff15, name
            )
            disks_load_avg[name] = [disk_load1, disk_load5, disk_load15]
            disks_load_percent_avg[name] = [
                disk_load_percent1,
                disk_load_percent5,
                disk_load_percent15,
            ]
            iops_avg[name] = [iops1, iops5, iops15]

        statistics = self._local.db.get("statistics", dict())
        statistics["disksLoadAvg"] = disks_load_avg
        statistics["disksLoadPercentAvg"] = disks_load_percent_avg
        statistics["iopsAvg"] = iops_avg
        self._local.db["statistics"] = statistics

    @staticmethod
    def calculate_disk_statistics(zerodata: dict, data: dict, name: str):
        if data is None:
            return None, None, None
        data = data[name]
        zerodata = zerodata[name]
        time_diff = zerodata["timestamp"] - data["timestamp"]
        busy_time_diff = zerodata["busyTime"] - data["busyTime"]
        disk_read_diff = zerodata["readBytes"] - data["readBytes"]
        disk_write_diff = zerodata["writeBytes"] - data["writeBytes"]
        disk_read_count_diff = zerodata["readCount"] - data["readCount"]
        disk_write_count_diff = zerodata["writeCount"] - data["writeCount"]
        disk_load_percent = (
            busy_time_diff / 1000 / time_diff * 100
        )  # /1000 - to second, *100 - to percent
        disk_load_percent = round(disk_load_percent, 2)
        disk_read = disk_read_diff / time_diff
        disk_write = disk_write_diff / time_diff
        disk_read_count = disk_read_count_diff / time_diff
        disk_write_count = disk_write_count_diff / time_diff
        disk_load = b2mb(disk_read + disk_write)
        iops = round(disk_read_count + disk_write_count, 2)
        return disk_load, disk_load_percent, iops

    @staticmethod
    def get_disks_list():
        data = list()
        buff = os.listdir("/sys/block/")
        for item in buff:
            if "loop" in item:
                continue
            data.append(item)
        data.sort()
        return data

    def read_network_data(self):
        timestamp = get_timestamp()
        interface_name = get_internet_interface_name()
        counters = psutil.net_io_counters(pernic=True)
        counters = counters[interface_name]

        data = {
            "timestamp": timestamp,
            "bytesRecv": counters.bytes_recv,
            "bytesSent": counters.bytes_sent,
            "packetsSent": counters.packets_sent,
            "packetsRecv": counters.packets_recv,
        }

        self._network.append(data)

    def save_network_statistics(self):
        data = list(reversed(self._network))
        zerodata = data[0]
        buff1 = data[1 * 6 - 1]
        buff5 = data[5 * 6 - 1]
        buff15 = data[15 * 6 - 1]
        if buff5 is None:
            buff5 = buff1
        if buff15 is None:
            buff15 = buff5

        network_load_avg1, pps_avg1 = self.calculate_network_statistics(zerodata, buff1)
        network_load_avg5, pps_avg5 = self.calculate_network_statistics(zerodata, buff5)
        network_load_avg15, pps_avg15 = self.calculate_network_statistics(
            zerodata, buff15
        )
        net_load_avg = [network_load_avg1, network_load_avg5, network_load_avg15]
        pps_avg = [pps_avg1, pps_avg5, pps_avg15]

        statistics = self._local.db.get("statistics", dict())
        statistics["netLoadAvg"] = net_load_avg
        statistics["ppsAvg"] = pps_avg
        self._local.db["statistics"] = statistics

    @staticmethod
    def calculate_network_statistics(zerodata: dict, data: dict):
        if data is None:
            return None, None
        time_diff = zerodata["timestamp"] - data["timestamp"]
        bytes_recv_diff = zerodata["bytesRecv"] - data["bytesRecv"]
        bytes_sent_diff = zerodata["bytesSent"] - data["bytesSent"]
        packets_recv_diff = zerodata["packetsRecv"] - data["packetsRecv"]
        packets_sent_diff = zerodata["packetsSent"] - data["packetsSent"]
        bites_recv_avg = bytes_recv_diff / time_diff * 8
        bites_sent_avg = bytes_sent_diff / time_diff * 8
        packets_recv_avg = packets_recv_diff / time_diff
        packets_sent_avg = packets_sent_diff / time_diff
        net_load_avg = b2mb(bites_recv_avg + bites_sent_avg)
        pps_avg = round(packets_recv_avg + packets_sent_avg, 2)
        return net_load_avg, pps_avg

    def save_node_statistics(self):
        status = self._ton.GetValidatorStatus(no_cache=True)
        if status.unixtime is None:
            return
        data = {"timestamp": status.unixtime}

        def get_ok_error(value: str):
            ok, error = value.split()
            return int(ok.split(":")[1]), int(error.split(":")[1])

        if "total.collated_blocks.master" in status:
            master_ok, master_error = get_ok_error(
                status["total.collated_blocks.master"]
            )
            shard_ok, shard_error = get_ok_error(status["total.collated_blocks.shard"])
            data["collated_blocks"] = {
                "master": {"ok": master_ok, "error": master_error},
                "shard": {"ok": shard_ok, "error": shard_error},
            }
        if "total.validated_blocks.master" in status:
            master_ok, master_error = get_ok_error(
                status["total.validated_blocks.master"]
            )
            shard_ok, shard_error = get_ok_error(status["total.validated_blocks.shard"])
            data["validated_blocks"] = {
                "master": {"ok": master_ok, "error": master_error},
                "shard": {"ok": shard_ok, "error": shard_error},
            }
        if "total.ext_msg_check" in status:
            ok, error = get_ok_error(status["total.ext_msg_check"])
            data["ext_msg_check"] = {"ok": ok, "error": error}
        if "total.ls_queries_ok" in status and "total.ls_queries_error" in status:
            data["ls_queries"] = {}
            for k in status["total.ls_queries_ok"].split():
                if k.startswith("TOTAL"):
                    data["ls_queries"]["ok"] = int(k.split(":")[1])
            for k in status["total.ls_queries_error"].split():
                if k.startswith("TOTAL"):
                    data["ls_queries"]["error"] = int(k.split(":")[1])
        statistics = self._local.db.get("statistics", dict())

        # if time.time() - int(status.start_time) <= 60:  # was node restart <60 sec ago, resetting node statistics
        #     statistics['node'] = []

        if "node" not in statistics:
            statistics["node"] = []

        if statistics["node"]:
            if int(status.start_time) > statistics["node"][-1]["timestamp"]:
                # node was restarted, reset node statistics
                statistics["node"] = []

        # statistics['node']: [stats_from_election_id, stats_from_prev_min, stats_now]

        election_id = self._ton.GetConfig34(no_cache=True)["startWorkTime"]
        if len(statistics["node"]) == 0:
            statistics["node"] = [None, data]
        elif len(statistics["node"]) < 3:
            statistics["node"].append(data)
        elif len(statistics["node"]) == 3:
            if statistics["node"][0] is None:
                if 0 < data["timestamp"] - election_id < 90:
                    statistics["node"][0] = data
            elif statistics["node"][0]["timestamp"] < election_id:
                statistics["node"][0] = data
            temp = statistics.get("node", []) + [data]
            temp.pop(1)
            statistics["node"] = temp
        self._local.db["statistics"] = statistics
        self._local.save()

    @staticmethod
    def parse_node_statistics(stats: list[None | dict]):
        """
        :return: stats for collated/validated blocks since the round beginning and stats for ls queries for the last minute
        """
        result = {}
        if len(stats) == 3 and stats[0] is not None and stats[2] is not None:
            result = {
                "collated": {
                    "ok": 0,
                    "error": 0,
                    "master": {},
                    "shard": {},
                },
                "validated": {
                    "ok": 0,
                    "error": 0,
                    "master": {},
                    "shard": {},
                },
            }
            for k in ["master", "shard"]:
                collated_ok = (
                    stats[2]["collated_blocks"][k]["ok"]
                    - stats[0]["collated_blocks"][k]["ok"]
                )
                collated_error = (
                    stats[2]["collated_blocks"][k]["error"]
                    - stats[0]["collated_blocks"][k]["error"]
                )
                validated_ok = (
                    stats[2]["validated_blocks"][k]["ok"]
                    - stats[0]["validated_blocks"][k]["ok"]
                )
                validated_error = (
                    stats[2]["validated_blocks"][k]["error"]
                    - stats[0]["validated_blocks"][k]["error"]
                )
                result["collated"][k] = {
                    "ok": collated_ok,
                    "error": collated_error,
                }
                result["validated"][k] = {
                    "ok": validated_ok,
                    "error": validated_error,
                }
                result["collated"]["ok"] += collated_ok
                result["collated"]["error"] += collated_error
                result["validated"]["ok"] += validated_ok
                result["validated"]["error"] += validated_error
        if len(stats) >= 2 and stats[-2] is not None and stats[-1] is not None:
            result["ls_queries"] = {
                "ok": stats[-1]["ls_queries"]["ok"] - stats[-2]["ls_queries"]["ok"],
                "error": stats[-1]["ls_queries"]["error"]
                - stats[-2]["ls_queries"]["error"],
                "time": stats[-1].get("timestamp", 0) - stats[-2].get("timestamp", 0),
            }
        return result
