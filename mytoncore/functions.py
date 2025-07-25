#!/usr/bin/env python3
# -*- coding: utf_8 -*-l
import os
import sys
import psutil
import time
import json
import base64
import requests
import subprocess

from mytoncore.mytoncore import MyTonCore
from mytonctrl.utils import fix_git_config
from mytoninstaller.config import GetConfig
from mypylib.mypylib import (
    b2mb,
    get_timestamp,
    get_internet_interface_name,
    get_git_hash,
    get_load_avg,
    thr_sleep,
)
from mytoncore.telemetry import *
from mytoninstaller.node_args import get_node_args


def Init(local):
    # Event reaction
    if ("-e" in sys.argv):
        x = sys.argv.index("-e")
        event_name = sys.argv[x+1]
        Event(local, event_name)
    # end if

    local.run()

    # statistics
    local.buffer.blocksData = dict()
    local.buffer.transData = dict()
    local.buffer.network = [None]*15*6
    local.buffer.diskio = [None]*15*6

    # scan blocks
    local.buffer.masterBlocksList = list()
    local.buffer.prevShardsBlock = dict()
    local.buffer.blocksNum = 0
    local.buffer.transNum = 0
# end define


def Event(local, event_name):
    if event_name == "enableVC":
        EnableVcEvent(local)
    elif event_name == "validator down":
        ValidatorDownEvent(local)
    elif event_name.startswith("enable_mode"):
        enable_mode(local, event_name)
    elif event_name == "enable_btc_teleport":
        enable_btc_teleport(local)
    local.exit()
# end define


def EnableVcEvent(local):
    local.add_log("start EnableVcEvent function", "debug")
    # Создать новый кошелек для валидатора
    ton = MyTonCore(local)
    wallet = ton.CreateWallet("validator_wallet_001", -1)
    local.db["validatorWalletName"] = wallet.name

    # Создать новый ADNL адрес для валидатора
    adnlAddr = ton.CreateNewKey()
    ton.AddAdnlAddrToValidator(adnlAddr)
    local.db["adnlAddr"] = adnlAddr

    # Сохранить
    local.save()
# end define


def ValidatorDownEvent(local):
    local.add_log("start ValidatorDownEvent function", "debug")
    local.add_log("Validator is down", "error")
# end define


def enable_mode(local, event_name):
    ton = MyTonCore(local)
    mode = event_name.split("_")[-1]
    if mode == "liteserver":
        ton.disable_mode('validator')
    ton.enable_mode(mode)
#end define

def enable_btc_teleport(local):
    ton = MyTonCore(local)
    from modules.btc_teleport import BtcTeleportModule
    BtcTeleportModule(ton, local).init(reinstall=True)

def Elections(local, ton):
    use_pool = ton.using_pool()
    use_liquid_staking = ton.using_liquid_staking()
    if use_pool:
        ton.PoolsUpdateValidatorSet()
    if use_liquid_staking:
        ton.ControllersUpdateValidatorSet()
    ton.RecoverStake()
    if ton.using_validator():
        ton.ElectionEntry()


def Statistics(local):
    ReadNetworkData(local)
    SaveNetworkStatistics(local)
    # ReadTransData(local, scanner)
    SaveTransStatistics(local)
    ReadDiskData(local)
    SaveDiskStatistics(local)
# end define


def ReadDiskData(local):
    timestamp = get_timestamp()
    disks = GetDisksList()
    buff = psutil.disk_io_counters(perdisk=True)
    data = dict()
    for name in disks:
        data[name] = dict()
        data[name]["timestamp"] = timestamp
        data[name]["busyTime"] = buff[name].busy_time
        data[name]["readBytes"] = buff[name].read_bytes
        data[name]["writeBytes"] = buff[name].write_bytes
        data[name]["readCount"] = buff[name].read_count
        data[name]["writeCount"] = buff[name].write_count
    # end for

    local.buffer.diskio.pop(0)
    local.buffer.diskio.append(data)
# end define


def SaveDiskStatistics(local):
    data = local.buffer.diskio
    data = data[::-1]
    zerodata = data[0]
    buff1 = data[1*6-1]
    buff5 = data[5*6-1]
    buff15 = data[15*6-1]
    if buff5 is None:
        buff5 = buff1
    if buff15 is None:
        buff15 = buff5
    # end if

    disksLoadAvg = dict()
    disksLoadPercentAvg = dict()
    iopsAvg = dict()
    disks = GetDisksList()
    for name in disks:
        if zerodata[name]["busyTime"] == 0:
            continue
        diskLoad1, diskLoadPercent1, iops1 = CalculateDiskStatistics(
            zerodata, buff1, name)
        diskLoad5, diskLoadPercent5, iops5 = CalculateDiskStatistics(
            zerodata, buff5, name)
        diskLoad15, diskLoadPercent15, iops15 = CalculateDiskStatistics(
            zerodata, buff15, name)
        disksLoadAvg[name] = [diskLoad1, diskLoad5, diskLoad15]
        disksLoadPercentAvg[name] = [diskLoadPercent1,
                                     diskLoadPercent5, diskLoadPercent15]
        iopsAvg[name] = [iops1, iops5, iops15]
    # end fore

    # save statistics
    statistics = local.db.get("statistics", dict())
    statistics["disksLoadAvg"] = disksLoadAvg
    statistics["disksLoadPercentAvg"] = disksLoadPercentAvg
    statistics["iopsAvg"] = iopsAvg
    local.db["statistics"] = statistics
# end define


def CalculateDiskStatistics(zerodata, data, name):
    if data is None:
        return None, None, None
    data = data[name]
    zerodata = zerodata[name]
    timeDiff = zerodata["timestamp"] - data["timestamp"]
    busyTimeDiff = zerodata["busyTime"] - data["busyTime"]
    diskReadDiff = zerodata["readBytes"] - data["readBytes"]
    diskWriteDiff = zerodata["writeBytes"] - data["writeBytes"]
    diskReadCountDiff = zerodata["readCount"] - data["readCount"]
    diskWriteCountDiff = zerodata["writeCount"] - data["writeCount"]
    diskLoadPercent = busyTimeDiff / 1000 / timeDiff * \
        100  # /1000 - to second, *100 - to percent
    diskLoadPercent = round(diskLoadPercent, 2)
    diskRead = diskReadDiff / timeDiff
    diskWrite = diskWriteDiff / timeDiff
    diskReadCount = diskReadCountDiff / timeDiff
    diskWriteCount = diskWriteCountDiff / timeDiff
    diskLoad = b2mb(diskRead + diskWrite)
    iops = round(diskReadCount + diskWriteCount, 2)
    return diskLoad, diskLoadPercent, iops
# end define


def GetDisksList():
    data = list()
    buff = os.listdir("/sys/block/")
    for item in buff:
        if "loop" in item:
            continue
        data.append(item)
    # end for
    data.sort()
    return data
# end define


def ReadNetworkData(local):
    timestamp = get_timestamp()
    interfaceName = get_internet_interface_name()
    buff = psutil.net_io_counters(pernic=True)
    buff = buff[interfaceName]
    data = dict()
    data["timestamp"] = timestamp
    data["bytesRecv"] = buff.bytes_recv
    data["bytesSent"] = buff.bytes_sent
    data["packetsSent"] = buff.packets_sent
    data["packetsRecv"] = buff.packets_recv

    local.buffer.network.pop(0)
    local.buffer.network.append(data)
# end define


def SaveNetworkStatistics(local):
    data = local.buffer.network
    data = data[::-1]
    zerodata = data[0]
    buff1 = data[1*6-1]
    buff5 = data[5*6-1]
    buff15 = data[15*6-1]
    if buff5 is None:
        buff5 = buff1
    if buff15 is None:
        buff15 = buff5
    # end if

    netLoadAvg = dict()
    ppsAvg = dict()
    networkLoadAvg1, ppsAvg1 = CalculateNetworkStatistics(zerodata, buff1)
    networkLoadAvg5, ppsAvg5 = CalculateNetworkStatistics(zerodata, buff5)
    networkLoadAvg15, ppsAvg15 = CalculateNetworkStatistics(zerodata, buff15)
    netLoadAvg = [networkLoadAvg1, networkLoadAvg5, networkLoadAvg15]
    ppsAvg = [ppsAvg1, ppsAvg5, ppsAvg15]

    # save statistics
    statistics = local.db.get("statistics", dict())
    statistics["netLoadAvg"] = netLoadAvg
    statistics["ppsAvg"] = ppsAvg
    local.db["statistics"] = statistics
# end define


def CalculateNetworkStatistics(zerodata, data):
    if data is None:
        return None, None
    timeDiff = zerodata["timestamp"] - data["timestamp"]
    bytesRecvDiff = zerodata["bytesRecv"] - data["bytesRecv"]
    bytesSentDiff = zerodata["bytesSent"] - data["bytesSent"]
    packetsRecvDiff = zerodata["packetsRecv"] - data["packetsRecv"]
    packetsSentDiff = zerodata["packetsSent"] - data["packetsSent"]
    bitesRecvAvg = bytesRecvDiff / timeDiff * 8
    bitesSentAvg = bytesSentDiff / timeDiff * 8
    packetsRecvAvg = packetsRecvDiff / timeDiff
    packetsSentAvg = packetsSentDiff / timeDiff
    netLoadAvg = b2mb(bitesRecvAvg + bitesSentAvg)
    ppsAvg = round(packetsRecvAvg + packetsSentAvg, 2)
    return netLoadAvg, ppsAvg
# end define


def save_node_statistics(local, ton):
    status = ton.GetValidatorStatus(no_cache=True)
    if status.unixtime is None:
        return
    data = {'timestamp': status.unixtime}

    def get_ok_error(value: str):
        ok, error = value.split()
        return int(ok.split(':')[1]), int(error.split(':')[1])

    if 'total.collated_blocks.master' in status:
        master_ok, master_error = get_ok_error(status['total.collated_blocks.master'])
        shard_ok, shard_error = get_ok_error(status['total.collated_blocks.shard'])
        data['collated_blocks'] = {
            'master': {'ok': master_ok, 'error': master_error},
            'shard': {'ok': shard_ok, 'error': shard_error},
        }
    if 'total.validated_blocks.master' in status:
        master_ok, master_error = get_ok_error(status['total.validated_blocks.master'])
        shard_ok, shard_error = get_ok_error(status['total.validated_blocks.shard'])
        data['validated_blocks'] = {
            'master': {'ok': master_ok, 'error': master_error},
            'shard': {'ok': shard_ok, 'error': shard_error},
        }
    if 'total.ext_msg_check' in status:
        ok, error = get_ok_error(status['total.ext_msg_check'])
        data['ext_msg_check'] = {'ok': ok, 'error': error}
    if 'total.ls_queries_ok' in status and 'total.ls_queries_error' in status:
        data['ls_queries'] = {}
        for k in status['total.ls_queries_ok'].split():
            if k.startswith('TOTAL'):
                data['ls_queries']['ok'] = int(k.split(':')[1])
        for k in status['total.ls_queries_error'].split():
            if k.startswith('TOTAL'):
                data['ls_queries']['error'] = int(k.split(':')[1])
    statistics = local.db.get("statistics", dict())

    # if time.time() - int(status.start_time) <= 60:  # was node restart <60 sec ago, resetting node statistics
    #     statistics['node'] = []

    if 'node' not in statistics:
        statistics['node'] = []

    if statistics['node']:
        if int(status.start_time) > statistics['node'][-1]['timestamp']:
            # node was restarted, reset node statistics
            statistics['node'] = []

    # statistics['node']: [stats_from_election_id, stats_from_prev_min, stats_now]

    election_id = ton.GetConfig34(no_cache=True)['startWorkTime']
    if len(statistics['node']) == 0:
        statistics['node'] = [None, data]
    elif len(statistics['node']) < 3:
        statistics['node'].append(data)
    elif len(statistics['node']) == 3:
        if statistics['node'][0] is None:
            if 0 < data['timestamp'] - election_id < 90:
                statistics['node'][0] = data
        elif statistics['node'][0]['timestamp'] < election_id:
            statistics['node'][0] = data
        temp = statistics.get('node', []) + [data]
        temp.pop(1)
        statistics['node'] = temp
    local.db["statistics"] = statistics
    local.save()


def ReadTransData(local, scanner):
    transData = local.buffer.transData
    SetToTimeData(transData, scanner.transNum)
    ShortTimeData(transData)
# end define


def SetToTimeData(timeDataList, data):
    timenow = int(time.time())
    timeDataList[timenow] = data
# end define


def ShortTimeData(data, max=120, diff=20):
    if len(data) < max:
        return
    buff = data.copy()
    data.clear()
    keys = sorted(buff.keys(), reverse=True)
    for item in keys[:max-diff]:
        data[item] = buff[item]
# end define


def SaveTransStatistics(local):
    tps1 = GetTps(local, 60)
    tps5 = GetTps(local, 60*5)
    tps15 = GetTps(local, 60*15)

    # save statistics
    statistics = local.db.get("statistics", dict())
    statistics["tpsAvg"] = [tps1, tps5, tps15]
    local.db["statistics"] = statistics
# end define


def GetDataPerSecond(data, timediff):
    if len(data) == 0:
        return
    timenow = sorted(data.keys())[-1]
    now = data.get(timenow)
    prev = GetItemFromTimeData(data, timenow-timediff)
    if prev is None:
        return
    diff = now - prev
    result = diff / timediff
    result = round(result, 2)
    return result
# end define


def GetItemFromTimeData(data, timeneed):
    if timeneed in data:
        result = data.get(timeneed)
    else:
        result = data[min(data.keys(), key=lambda k: abs(k-timeneed))]
    return result
# end define


def GetTps(local, timediff):
    data = local.buffer.transData
    tps = GetDataPerSecond(data, timediff)
    return tps
# end define


def GetBps(local, timediff):
    data = local.buffer.blocksData
    bps = GetDataPerSecond(data, timediff)
    return bps
# end define


def GetBlockTimeAvg(local, timediff):
    bps = GetBps(local, timediff)
    if bps is None or bps == 0:
        return
    result = 1/bps
    result = round(result, 2)
    return result
# end define


def Offers(local, ton):
    save_offers = ton.GetSaveOffers()
    if save_offers:
        ton.offers_gc(save_offers)
    else:
        return
    offers = ton.GetOffers()
    for offer in offers:
        offer_hash = offer.get("hash")
        if offer_hash in save_offers:
            offer_pseudohash = offer.get("pseudohash")
            save_offer = save_offers.get(offer_hash)
            if isinstance(save_offer, list):  # new version of save offers {"hash": ["pseudohash", param_id]}
                save_offer_pseudohash = save_offer[0]
            else:  # old version of save offers {"hash": "pseudohash"}
                save_offer_pseudohash = save_offer
            if offer_pseudohash == save_offer_pseudohash and offer_pseudohash is not None:
                ton.VoteOffer(offer)
# end define

def Telemetry(local, ton):
    sendTelemetry = local.db.get("sendTelemetry")
    if sendTelemetry is not True:
        return
    # end if

    # Get validator status
    data = dict()
    data["adnlAddr"] = ton.GetAdnlAddr()
    data["validatorStatus"] = ton.GetValidatorStatus()
    data["cpuNumber"] = psutil.cpu_count()
    data["cpuLoad"] = get_load_avg()
    data["netLoad"] = ton.GetStatistics("netLoadAvg")
    data["tps"] = ton.GetStatistics("tpsAvg")
    data["disksLoad"] = ton.GetStatistics("disksLoadAvg")
    data["disksLoadPercent"] = ton.GetStatistics("disksLoadPercentAvg")
    data["iops"] = ton.GetStatistics("iopsAvg")
    data["pps"] = ton.GetStatistics("ppsAvg")
    data["dbUsage"] = ton.GetDbUsage()
    data["memory"] = GetMemoryInfo()
    data["swap"] = GetSwapInfo()
    data["uname"] = GetUname()
    data["vprocess"] = GetValidatorProcessInfo()
    data["dbStats"] = local.try_function(get_db_stats)
    data["nodeArgs"] = local.try_function(get_node_args)
    data["modes"] = local.try_function(ton.get_modes)
    data["cpuInfo"] = {'cpuName': local.try_function(get_cpu_name), 'virtual': local.try_function(is_host_virtual)}
    data["validatorDiskName"] = local.try_function(get_validator_disk_name)
    data["pings"] = local.try_function(get_pings_values)

    # Get git hashes
    gitHashes = dict()
    mtc_path = "/usr/src/mytonctrl"
    local.try_function(fix_git_config, args=[mtc_path])
    gitHashes["mytonctrl"] = get_git_hash(mtc_path)
    gitHashes["validator"] = GetBinGitHash(
        "/usr/bin/ton/validator-engine/validator-engine")
    data["gitHashes"] = gitHashes
    data["stake"] = local.db.get("stake")

    # Get validator config
    vconfig = ton.GetValidatorConfig()
    data["fullnode_adnl"] = vconfig.fullnode

    # Send data to toncenter server
    liteUrl_default = "https://telemetry.toncenter.com/report_status"
    liteUrl = local.db.get("telemetryLiteUrl", liteUrl_default)
    output = json.dumps(data)
    resp = requests.post(liteUrl, data=output, timeout=3)
# end define


def GetBinGitHash(path, short=False):
    if not os.path.isfile(path):
        return
    args = [path, "--version"]
    process = subprocess.run(args, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
    output = process.stdout.decode("utf-8")
    if "build information" not in output:
        return
    buff = output.split(' ')
    start = buff.index("Commit:") + 1
    result = buff[start].replace(',', '')
    if short is True:
        result = result[:7]
    return result
# end define


def OverlayTelemetry(local, ton):
    sendTelemetry = local.db.get("sendTelemetry")
    if sendTelemetry is not True:
        return
    # end if

    # Get validator status
    data = dict()
    data["adnlAddr"] = ton.GetAdnlAddr()
    data["overlaysStats"] = ton.GetOverlaysStats()

    # Send data to toncenter server
    overlayUrl_default = "https://telemetry.toncenter.com/report_overlays"
    overlayUrl = local.db.get("overlayTelemetryUrl", overlayUrl_default)
    output = json.dumps(data)
    resp = requests.post(overlayUrl, data=output, timeout=3)
# end define


def Complaints(local, ton):
    validatorIndex = ton.GetValidatorIndex()
    if validatorIndex < 0:
        return
    # end if

    # Voting for complaints
    config32 = ton.GetConfig32()
    election_id = config32.get("startWorkTime")
    complaints = ton.GetComplaints(election_id)  # get complaints from Elector
    valid_complaints = ton.get_valid_complaints(complaints, election_id)
    for c in valid_complaints.values():
        complaint_hash = c.get("hash")
        ton.VoteComplaint(election_id, complaint_hash)
# end define


def Slashing(local, ton):
    is_slashing = local.db.get("isSlashing")
    is_validator = ton.using_validator()
    if is_slashing is not True or not is_validator:
        return

    # Creating complaints
    slash_time = local.buffer.slash_time
    config32 = ton.GetConfig32()
    start = config32.get("startWorkTime")
    end = config32.get("endWorkTime")
    config15 = ton.GetConfig15()
    ts = get_timestamp()
    if not(end < ts < end + config15['stakeHeldFor']):  # check that currently is freeze time
        return
    local.add_log("slash_time {}, start {}, end {}".format(slash_time, start, end), "debug")
    if slash_time != start:
        end -= 60
        ton.CheckValidators(start, end)
        local.buffer.slash_time = start
# end define


def save_past_events(local, ton):
    local.try_function(ton.GetElectionEntries)
    local.try_function(ton.GetComplaints)
    local.try_function(ton.GetValidatorsList, args=[True])  # cache past vl


def ScanLiteServers(local, ton):
    # Считать список серверов
    filePath = ton.liteClient.configPath
    file = open(filePath, 'rt')
    text = file.read()
    file.close()
    data = json.loads(text)

    # Пройтись по серверам
    result = list()
    liteservers = data.get("liteservers")
    for index in range(len(liteservers)):
        try:
            ton.liteClient.Run("last", index=index)
            result.append(index)
        except:
            pass
    # end for

    # Записать данные в базу
    local.db["liteServers"] = result
# end define


def check_initial_sync(local, ton):
    if not ton.in_initial_sync():
        return
    validator_status = ton.GetValidatorStatus()
    if validator_status.initial_sync:
        return
    if validator_status.out_of_sync < 20:
        ton.set_initial_sync_off()
        return


def gc_import(local, ton):
    if not ton.local.db.get('importGc', False):
        return
    local.add_log("GC import is running", "debug")
    import_path = '/var/ton-work/db/import'
    files = os.listdir(import_path)
    if not files:
        local.add_log("No files left to import", "debug")
        ton.local.db['importGc'] = False
        return
    try:
        status = ton.GetValidatorStatus()
        node_seqno = int(status.shardclientmasterchainseqno)
    except Exception as e:
        local.add_log(f"Failed to get shardclientmasterchainseqno: {e}", "warning")
        return
    removed = 0
    for file in files:
        file_seqno = int(file.split('.')[1])
        if node_seqno > file_seqno + 101:
            try:
                os.remove(os.path.join(import_path, file))
                removed += 1
            except PermissionError:
                local.add_log(f"Failed to remove file {file}: Permission denied", "error")
                continue
    local.add_log(f"Removed {removed} import files up to {node_seqno} seqno", "debug")


def General(local):
    local.add_log("start General function", "debug")
    ton = MyTonCore(local)
    # scanner = Dict()
    # scanner.Run()

    # Start threads
    local.start_cycle(Statistics, sec=10, args=(local, ))
    local.start_cycle(Telemetry, sec=60, args=(local, ton, ))
    local.start_cycle(OverlayTelemetry, sec=7200, args=(local, ton, ))
    if local.db.get("onlyNode"):  # mytoncore service works only for telemetry
        thr_sleep()
        return

    local.start_cycle(Elections, sec=600, args=(local, ton, ))
    local.start_cycle(Offers, sec=600, args=(local, ton, ))
    local.start_cycle(save_past_events, sec=300, args=(local, ton, ))

    t = 600
    if ton.GetNetworkName() != 'mainnet':
        t = 60
    local.start_cycle(Complaints, sec=t, args=(local, ton, ))
    local.start_cycle(Slashing, sec=t, args=(local, ton, ))

    local.start_cycle(ScanLiteServers, sec=60, args=(local, ton,))

    local.start_cycle(save_node_statistics, sec=60, args=(local, ton, ))

    from modules.custom_overlays import CustomOverlayModule
    local.start_cycle(CustomOverlayModule(ton, local).custom_overlays, sec=60, args=())

    from modules.alert_bot import AlertBotModule
    local.start_cycle(AlertBotModule(ton, local).check_status, sec=60, args=())

    from modules.prometheus import PrometheusModule
    local.start_cycle(PrometheusModule(ton, local).push_metrics, sec=30, args=())

    from modules.btc_teleport import BtcTeleportModule
    local.start_cycle(BtcTeleportModule(ton, local).auto_vote_offers, sec=180, args=())

    if ton.in_initial_sync():
        local.start_cycle(check_initial_sync, sec=120, args=(local, ton))

    if ton.local.db.get('importGc'):
        local.start_cycle(gc_import, sec=300, args=(local, ton))

    thr_sleep()
# end define


def mytoncore():
    from mypylib.mypylib import MyPyClass

    local = MyPyClass('mytoncore.py')
    print('Local DB path:', local.buffer.db_path)
    Init(local)
    General(local)
