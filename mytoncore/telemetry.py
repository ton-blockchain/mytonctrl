from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

import psutil

from mytoncore import MyTonCore
from mytoncore.utils import parse_db_stats
from mytoninstaller.node_args import get_node_args
from mypylib.mypylib import get_service_pid, MyPyClass, get_git_hash, get_load_avg
from mytonctrl.utils import fix_git_config


def build_overlay_telemetry_payload(ton: MyTonCore) -> dict[str, Any]:
    return {"adnlAddr": ton.GetAdnlAddr(), "overlaysStats": ton.GetOverlaysStats()}


def build_telemetry_payload(local: MyPyClass, ton: MyTonCore):
    data: dict[str, Any] = {
        "adnlAddr": ton.GetAdnlAddr(),
        "validatorStatus": ton.GetValidatorStatus(),
        "cpuNumber": psutil.cpu_count(),
        "cpuLoad": get_load_avg(),
        "netLoad": ton.GetStatistics("netLoadAvg"),
        "disksLoad": ton.GetStatistics("disksLoadAvg"),
        "disksLoadPercent": ton.GetStatistics("disksLoadPercentAvg"),
        "iops": ton.GetStatistics("iopsAvg"),
        "pps": ton.GetStatistics("ppsAvg"),
        "dbUsage": ton.GetDbUsage(),
        "memory": get_memory_info(),
        "swap": get_swap_info(),
        "uname": get_uname(),
        "vprocess": get_validator_process_info(),
        "dbStats": local.try_function(get_db_stats),
        "nodeArgs": local.try_function(get_node_args),
        "modes": local.try_function(ton.get_modes),
        "cpuInfo": {
            "cpuName": local.try_function(get_cpu_name),
            "virtual": local.try_function(is_host_virtual),
        },
        "validatorDiskName": local.try_function(get_validator_disk_name),
        "pings": local.try_function(get_pings_values),
        "pythonVersion": sys.version,
    }

    mtc_path = "/usr/src/mytonctrl"
    local.try_function(fix_git_config, args=[mtc_path])

    data["gitHashes"] = {
        "mytonctrl": get_git_hash(mtc_path),
        "validator": get_bin_git_hash("/usr/bin/ton/validator-engine/validator-engine"),
    }
    data["stake"] = local.db.get("stake")

    # Get validator config
    vconfig = ton.GetValidatorConfig()
    data["fullnode_adnl"] = vconfig.fullnode

    return data


def get_uname():
    data = os.uname()
    result = dict(zip("sysname nodename release version machine".split(), data))
    result.pop("nodename")
    return result


def get_memory_info() -> dict[str, int | float]:
    data = psutil.virtual_memory()
    result = {
        "total": round(data.total / 10**9, 2),
        "usage": round(data.used / 10**9, 2),
        "usagePercent": data.percent,
    }
    return result


def get_swap_info():
    result = dict()
    data = psutil.swap_memory()
    result["total"] = round(data.total / 10**9, 2)
    result["usage"] = round(data.used / 10**9, 2)
    result["usagePercent"] = data.percent
    return result


def get_validator_process_info():
    pid = get_service_pid("validator")
    if not pid:
        return None
    p = psutil.Process(pid)
    mem = p.memory_info()
    result = dict()
    result["cpuPercent"] = p.cpu_percent()
    memory = dict()
    memory["rss"] = mem.rss
    memory["vms"] = mem.vms
    memory["shared"] = mem.shared  # pyright: ignore[reportAttributeAccessIssue]
    memory["text"] = mem.text  # pyright: ignore[reportAttributeAccessIssue]
    memory["lib"] = mem.lib  # pyright: ignore[reportAttributeAccessIssue]
    memory["data"] = mem.data  # pyright: ignore[reportAttributeAccessIssue]
    memory["dirty"] = mem.dirty  # pyright: ignore[reportAttributeAccessIssue]
    result["memory"] = memory
    return result


def get_db_stats():
    result = {
        "rocksdb": {"ok": True, "message": "", "data": {}},
        "celldb": {"ok": True, "message": "", "data": {}},
    }
    rocksdb_stats_path = "/var/ton-work/db/db_stats.txt"
    celldb_stats_path = "/var/ton-work/db/celldb/db_stats.txt"
    if os.path.exists(rocksdb_stats_path):
        try:
            result["rocksdb"]["data"] = parse_db_stats(rocksdb_stats_path)
        except Exception as e:
            result["rocksdb"]["ok"] = False
            result["rocksdb"]["message"] = f"failed to fetch db stats: {e}"
    else:
        result["rocksdb"]["ok"] = False
        result["rocksdb"]["message"] = "db stats file is not exists"

    if os.path.exists(celldb_stats_path):
        try:
            result["celldb"]["data"] = parse_db_stats(celldb_stats_path)
        except Exception as e:
            result["celldb"]["ok"] = False
            result["celldb"]["message"] = f"failed to fetch db stats: {e}"
    else:
        result["celldb"]["ok"] = False
        result["celldb"]["message"] = "db stats file is not exists"

    return result


def get_cpu_name():
    with open("/proc/cpuinfo") as f:
        for line in f:
            if line.strip():
                if line.rstrip("\n").startswith("model name"):
                    return line.rstrip("\n").split(":")[1].strip()
    return None


def is_host_virtual():
    try:
        with open("/sys/class/dmi/id/product_name") as f:
            product_name = f.read().strip().lower()
            if (
                "virtual" in product_name
                or "kvm" in product_name
                or "qemu" in product_name
                or "vmware" in product_name
            ):
                return {"virtual": True, "product_name": product_name}
            return {"virtual": False, "product_name": product_name}
    except FileNotFoundError:
        return {"virtual": None, "product_name": None}


def do_beacon_ping(host: str, count: int, timeout: int):
    args = ["ping", "-c", str(count), "-W", str(timeout), host]
    process = subprocess.run(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    output = process.stdout.decode("utf-8")
    avg = output.split("\n")[-2].split("=")[1].split("/")[1]
    return float(avg)


def get_pings_values():
    return {
        "beacon-eu-01.toncenter.com": do_beacon_ping(
            "beacon-eu-01.toncenter.com", 5, 10
        ),
        "beacon-apac-01.toncenter.com": do_beacon_ping(
            "beacon-apac-01.toncenter.com", 5, 10
        ),
    }


def get_validator_disk_name():
    process = subprocess.run(
        "df -h /var/ton-work/ | sed -n '2 p' | awk '{print $1}'",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=3,
        shell=True,
    )
    output = process.stdout.decode("utf-8")
    return output.strip()


def get_bin_git_hash(path: str, short: bool = False) -> str | None:
    if not os.path.isfile(path):
        return None
    args = [path, "--version"]
    process = subprocess.run(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=3,
    )
    output = process.stdout.decode("utf-8")
    if "build information" not in output:
        return None
    buff = output.split(" ")
    start = buff.index("Commit:") + 1
    result = buff[start].replace(",", "")
    if short:
        result = result[:7]
    return result
