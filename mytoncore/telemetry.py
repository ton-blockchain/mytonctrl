import os
import subprocess

import psutil

from mytoncore.utils import parse_db_stats
from mypylib.mypylib import get_service_pid


def GetUname():
    data = os.uname()
    result = dict(
        zip('sysname nodename release version machine'.split(), data))
    result.pop("nodename")
    return result
# end define


def GetMemoryInfo():
    result = dict()
    data = psutil.virtual_memory()
    result["total"] = round(data.total / 10**9, 2)
    result["usage"] = round(data.used / 10**9, 2)
    result["usagePercent"] = data.percent
    return result
# end define


def GetSwapInfo():
    result = dict()
    data = psutil.swap_memory()
    result["total"] = round(data.total / 10**9, 2)
    result["usage"] = round(data.used / 10**9, 2)
    result["usagePercent"] = data.percent
    return result
# end define


def GetValidatorProcessInfo():
    pid = get_service_pid("validator")
    if pid == None or pid == 0:
        return
    p = psutil.Process(pid)
    mem = p.memory_info()
    result = dict()
    result["cpuPercent"] = p.cpu_percent()
    memory = dict()
    memory["rss"] = mem.rss
    memory["vms"] = mem.vms
    memory["shared"] = mem.shared
    memory["text"] = mem.text
    memory["lib"] = mem.lib
    memory["data"] = mem.data
    memory["dirty"] = mem.dirty
    result["memory"] = memory
    # io = p.io_counters() # Permission denied: '/proc/{pid}/io'
    return result
# end define


def get_db_stats():
    result = {
        'rocksdb': {
            'ok': True,
            'message': '',
            'data': {}
        },
        'celldb': {
            'ok': True,
            'message': '',
            'data': {}
        },
    }
    rocksdb_stats_path = '/var/ton-work/db/db_stats.txt'
    celldb_stats_path = '/var/ton-work/db/celldb/db_stats.txt'
    if os.path.exists(rocksdb_stats_path):
        try:
            result['rocksdb']['data'] = parse_db_stats(rocksdb_stats_path)
        except Exception as e:
            result['rocksdb']['ok'] = False
            result['rocksdb']['message'] = f'failed to fetch db stats: {e}'
    else:
        result['rocksdb']['ok'] = False
        result['rocksdb']['message'] = 'db stats file is not exists'
    # end if

    if os.path.exists(celldb_stats_path):
        try:
            result['celldb']['data'] = parse_db_stats(celldb_stats_path)
        except Exception as e:
            result['celldb']['ok'] = False
            result['celldb']['message'] = f'failed to fetch db stats: {e}'
    else:
        result['celldb']['ok'] = False
        result['celldb']['message'] = 'db stats file is not exists'
    # end if

    return result
# end define


def get_cpu_name():
    with open('/proc/cpuinfo') as f:
        for line in f:
            if line.strip():
                if line.rstrip('\n').startswith('model name'):
                    return line.rstrip('\n').split(':')[1].strip()
    return None


def is_host_virtual():
    try:
        with open('/sys/class/dmi/id/product_name') as f:
            product_name = f.read().strip().lower()
            if 'virtual' in product_name or 'kvm' in product_name or 'qemu' in product_name or 'vmware' in product_name:
                return {'virtual': True, 'product_name': product_name}
            return {'virtual': False, 'product_name': product_name}
    except FileNotFoundError:
        return {'virtual': None, 'product_name': None}


def do_beacon_ping(host, count, timeout):
    args = ['ping', '-c', str(count), '-W', str(timeout), host]
    process = subprocess.run(args, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    output = process.stdout.decode("utf-8")
    avg = output.split('\n')[-2].split('=')[1].split('/')[1]
    return float(avg)


def get_pings_values():
    return {
        'beacon-eu-01.toncenter.com': do_beacon_ping('beacon-eu-01.toncenter.com', 5, 10),
        'beacon-apac-01.toncenter.com': do_beacon_ping('beacon-apac-01.toncenter.com', 5, 10)
    }


def get_validator_disk_name():
    process = subprocess.run("df -h /var/ton-work/ | sed -n '2 p' | awk '{print $1}'", stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3, shell=True)
    output = process.stdout.decode("utf-8")
    return output.strip()

