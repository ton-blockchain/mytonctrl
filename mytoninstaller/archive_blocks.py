from __future__ import annotations

import datetime
import json
import os
import subprocess
import typing

import requests
import time

from concurrent.futures import ThreadPoolExecutor, as_completed

from mytoninstaller.utils import is_testnet


def get_block_from_toncenter(local, workchain: int, shard: int = -9223372036854775808, seqno: int = None, utime: int = None):
    url = f'https://toncenter.com/api/v2/lookupBlock?workchain={workchain}&shard={shard}'
    if is_testnet(local):
        url = url.replace('toncenter.com', 'testnet.toncenter.com')
    if seqno:
        url += f'&seqno={seqno}'
    if utime:
        url += f'&unixtime={utime}'
    local.add_log(f"Requesting block information from {url}", "debug")
    resp = requests.get(url, timeout=3)
    if resp.status_code != 200:
        local.add_log(f"Toncenter API returned status code {resp.status_code}", "error")
        raise Exception(f"Toncenter API request failed: {resp.text}")
    data = resp.json()
    if not data['ok']:
        local.add_log(f"Toncenter API returned error: {data.get('error', 'Unknown error')}", "error")
        raise Exception(f"Toncenter API returned error: {data.get('error', 'Unknown error')}")
    return data['result']


def download_blocks_bag(local, bag: dict, downloads_path: str):
    local.add_log(f"Downloading blocks from {bag['from']} to {bag['to']}", "info")
    if not download_bag(local, bag['bag'], downloads_path):
        local.add_log("Error downloading archive bag", "error")
        return


def download_master_blocks_bag(local, bag: dict, downloads_path: str):
    local.add_log(f"Downloading master blocks from {bag['from']} to {bag['to']}", "info")
    if not download_bag(local, bag['bag'], downloads_path, download_all=False, download_file=lambda f: ':' not in f['name']):
        local.add_log("Error downloading master bag", "error")
        return


def do_request(local, method: str, url: str, timeout: int = 3, **kwargs) -> dict:
    for _ in range(3):
        try:
            return requests.request(method, url, timeout=timeout, **kwargs).json()
        except Exception as e:
            local.add_log(f"Error making {method} request for {url}: {e}. Retrying", "error")
            time.sleep(5)
    raise Exception(f"Failed to make {method} request for {url}")


def download_bag(local, bag_id: str, downloads_path: str, download_all: bool = True, download_file: typing.Callable = None):
    indexes = []
    local_ts_url = f"http://127.0.0.1:{local.buffer.ton_storage.api_port}"

    resp = do_request(local, 'POST', local_ts_url + '/api/v1/add', json={'bag_id': bag_id, 'download_all': download_all, 'path': downloads_path})
    if not resp['ok']:
        local.add_log(f"Error adding bag: {resp}", "error")
        return False
    resp = do_request(local, 'GET', local_ts_url + f'/api/v1/details?bag_id={bag_id}')
    if not download_all:
        while not resp['header_loaded']:
            time.sleep(1)
            resp = do_request(local, 'GET', local_ts_url + f'/api/v1/details?bag_id={bag_id}')
        for f in resp['files']:
            if download_file(f):
                indexes.append(f['index'])
        resp = do_request(local, 'POST', local_ts_url + '/api/v1/add', json={'bag_id': bag_id, 'download_all': download_all, 'path': downloads_path, 'files': indexes})
        if not resp['ok']:
            local.add_log(f"Error adding bag: {resp}", "error")
            return False
        time.sleep(3)
        resp = do_request(local, 'GET', local_ts_url + f'/api/v1/details?bag_id={bag_id}')
    while not resp['completed']:
        if resp['size'] == 0:
            local.add_log(f"STARTING DOWNLOADING {bag_id}", "info")
            time.sleep(20)
            resp = do_request(local, 'GET', local_ts_url + f'/api/v1/details?bag_id={bag_id}')
            continue
        text = f'DOWNLOADING {bag_id} {round((resp["downloaded"] / resp["size"]) * 100)}% ({resp["downloaded"] / 10**6} / {resp["size"] / 10**6} MB), speed: {resp["download_speed"] / 10**6} MB/s'
        local.add_log(text, "info")
        time.sleep(20)
        resp = do_request(local, 'GET', local_ts_url + f'/api/v1/details?bag_id={bag_id}')
    local.add_log(f"DOWNLOADED {bag_id}", "info")
    do_request(local, 'POST', local_ts_url + '/api/v1/remove', json={'bag_id': bag_id, 'with_files': False})
    return True


def update_init_block(local, seqno: int):
    local.add_log(f"Editing init block in {local.buffer.global_config_path}", "info")
    with open(local.buffer.global_config_path, 'r') as f:
        config = json.load(f)
    if seqno != 0:
        data = get_block_from_toncenter(local, workchain=-1, seqno=seqno)
    else:
        data = config['validator']['zero_state']
    config['validator']['init_block']['seqno'] = seqno
    config['validator']['init_block']['file_hash'] = data['file_hash']
    config['validator']['init_block']['root_hash'] = data['root_hash']
    with open(local.buffer.global_config_path, 'w') as f:
        f.write(json.dumps(config, indent=4))
    return True


def parse_block_value(local, block: str):
    if block is None:
        return None
    if block.isdigit():
        return int(block)
    dt = datetime.datetime.strptime(block, "%Y-%m-%d")
    ts = int(dt.timestamp())
    data = get_block_from_toncenter(local, workchain=-1, utime=ts)
    return int(data['seqno'])


def download_blocks(local, downloads_path: str, block_from: int, block_to: int | None = None, only_master: bool = False):
    url = 'https://archival-dump.ton.org/index/mainnet.json'
    if is_testnet(local):
        url = 'https://archival-dump.ton.org/index/testnet.json'
    block_bags = []
    blocks_config = requests.get(url, timeout=3).json()

    if blocks_config is None:
        local.add_log(f"Failed to get blocks config: {url}. Aborting installation", "error")
        return

    for block in blocks_config['blocks']:
        if block_to is not None and block['from'] > block_to:
            break
        if block['to'] >= block_from:
            block_bags.append(block)

    estimated_size = len(block_bags) * 4 * 2 ** 30

    local.add_log(f"Downloading blocks. Rough estimate total blocks size is {int(estimated_size / 2 ** 30)} GB", "info")
    with ThreadPoolExecutor(max_workers=4) as executor:
        if only_master:
            futures = [executor.submit(download_master_blocks_bag, local, bag, downloads_path) for bag in block_bags]
        else:
            futures = [executor.submit(download_blocks_bag, local, bag, downloads_path) for bag in block_bags]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                local.add_log(f"Error while downloading blocks: {e}", "error")
                return
    local.add_log("Downloading blocks is completed", "info")


def run_process_hardforks(local, from_seqno: int):
    script_path = os.path.join(local.buffer.mtc_src_dir, 'mytoninstaller', 'scripts', 'process_hardforks.py')
    log_path = "/tmp/process_hardforks_logs.txt"
    log_file = open(log_path, "a")

    p = subprocess.Popen([
            "python3", script_path,
            "--from-seqno", str(from_seqno),
            "--config-path", local.buffer.global_config_path,
            # "--bin", local.buffer.ton_bin_dir + "validator-engine-console/validator-engine-console",
            # "--client", local.buffer.keys_dir + "client",
            # "--server", local.buffer.keys_dir + "server.pub",
            # "--address", "127.0.0.1:"
        ],
        stdout=log_file,
        stderr=log_file,
        stdin=subprocess.DEVNULL,
        start_new_session=True  # run in background
    )
    local.add_log(f"process_hardforks process is running in background, PID: {p.pid}, log file: {log_path}", "info")
