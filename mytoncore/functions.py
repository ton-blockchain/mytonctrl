#!/usr/bin/env python3
# -*- coding: utf_8 -*-l
import os
import sys
import psutil
import time
import json
import requests
import subprocess

from mytoncore.mytoncore import MyTonCore, Dec2HexAddr
from mytoncore.tonblocksscanner import TonBlocksScanner
from mypylib.mypylib import (
    GetTimestamp,
    GetInternetInterfaceName,
    b2mb,
    GetLoadAvg,
    GetGitHash,
    Sleep,
    GetServicePid
)


def Init(local):
    # Event reaction
    if ("-e" in sys.argv):
        x = sys.argv.index("-e")
        eventName = sys.argv[x+1]
        Event(local, eventName)
    # end if

    local.Run()

    # statistics
    local.buffer["transData"] = dict()
    local.buffer["network"] = [None]*15*6
    local.buffer["diskio"] = [None]*15*6

    # scan blocks
    local.buffer["masterBlocksList"] = list()
    local.buffer["prevShardsBlock"] = dict()
    local.buffer["blocksNum"] = 0
    local.buffer["transNum"] = 0
# end define


def Event(local, eventName):
    if eventName == "enableVC":
        EnableVcEvent(local)
    elif eventName == "validator down":
        ValidatorDownEvent(local)
    local.Exit()
# end define


def EnableVcEvent(local):
    local.AddLog("start EnableVcEvent function", "debug")
    # Создать новый кошелек для валидатора
    ton = MyTonCore(local)
    wallet = ton.CreateWallet("validator_wallet_001", -1)
    local.db["validatorWalletName"] = wallet.name

    # Создать новый ADNL адрес для валидатора
    adnlAddr = ton.CreateNewKey()
    ton.AddAdnlAddrToValidator(adnlAddr)
    local.db["adnlAddr"] = adnlAddr

    # Сохранить
    local.dbSave()
# end define


def ValidatorDownEvent(local):
    local.AddLog("start ValidatorDownEvent function", "debug")
    local.AddLog("Validator is down", "error")
# end define


def Elections(local, ton):
    usePool = local.db.get("usePool")
    if usePool == True:
        ton.PoolsUpdateValidatorSet()
        ton.RecoverStake()
        ton.ElectionEntry()
    else:
        ton.RecoverStake()
        ton.ElectionEntry()
# end define


def Statistics(local, scanner):
    ReadNetworkData(local)
    SaveNetworkStatistics(local)
    ReadTransData(local, scanner)
    SaveTransStatistics(local)
    ReadDiskData(local)
    SaveDiskStatistics(local)
# end define


def ReadDiskData(local):
    timestamp = GetTimestamp()
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

    local.buffer["diskio"].pop(0)
    local.buffer["diskio"].append(data)
# end define


def SaveDiskStatistics(local):
    data = local.buffer["diskio"]
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
    timestamp = GetTimestamp()
    interfaceName = GetInternetInterfaceName()
    buff = psutil.net_io_counters(pernic=True)
    buff = buff[interfaceName]
    data = dict()
    data = dict()
    data["timestamp"] = timestamp
    data["bytesRecv"] = buff.bytes_recv
    data["bytesSent"] = buff.bytes_sent
    data["packetsSent"] = buff.packets_sent
    data["packetsRecv"] = buff.packets_recv

    local.buffer["network"].pop(0)
    local.buffer["network"].append(data)
# end define


def SaveNetworkStatistics(local):
    data = local.buffer["network"]
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


def ReadTransData(local, scanner):
    transData = local.buffer.get("transData")
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
    data = local.buffer["transData"]
    tps = GetDataPerSecond(data, timediff)
    return tps
# end define


def GetBps(local, timediff):
    data = local.buffer["blocksData"]
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
    saveOffers = ton.GetSaveOffers()
    offers = ton.GetOffers()
    for offer in offers:
        offerHash = offer.get("hash")
        if offerHash in saveOffers:
            ton.VoteOffer(offerHash)
# end define


def Domains(local, ton):
    pass
# end define


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
    pid = GetServicePid("validator")
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
    data["cpuLoad"] = GetLoadAvg()
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
    elections = local.TryFunction(ton.GetElectionEntries)
    complaints = local.TryFunction(ton.GetComplaints)

    # Get git hashes
    gitHashes = dict()
    gitHashes["mytonctrl"] = GetGitHash("/usr/src/mytonctrl")
    gitHashes["validator"] = GetBinGitHash(
        "/usr/bin/ton/validator-engine/validator-engine")
    data["gitHashes"] = gitHashes
    data["stake"] = local.db.get("stake")

    # Send data to toncenter server
    liteUrl_default = "https://telemetry.toncenter.com/report_status"
    liteUrl = local.db.get("telemetryLiteUrl", liteUrl_default)
    output = json.dumps(data)
    resp = requests.post(liteUrl, data=output, timeout=3)
# end define


def GetBinGitHash(path):
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
    electionId = config32.get("startWorkTime")
    complaintsHashes = ton.SaveComplaints(electionId)
    complaints = ton.GetComplaints(electionId)
    for key, item in complaints.items():
        complaintHash = item.get("hash")
        complaintHash_hex = Dec2HexAddr(complaintHash)
        if complaintHash_hex in complaintsHashes:
            ton.VoteComplaint(electionId, complaintHash)
# end define


def Slashing(local, ton):
    isSlashing = local.db.get("isSlashing")
    if isSlashing is not True:
        return
    # end if

    # Creating complaints
    slashTime = local.buffer.get("slashTime")
    config32 = ton.GetConfig32()
    start = config32.get("startWorkTime")
    end = config32.get("endWorkTime")
    local.AddLog("slashTime {}, start {}, end {}".format(
        slashTime, start, end), "debug")
    if slashTime != start:
        end -= 60
        ton.CheckValidators(start, end)
        local.buffer["slashTime"] = start
# end define


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


def General(local):
    local.AddLog("start General function", "debug")
    ton = MyTonCore(local)
    scanner = TonBlocksScanner(ton, local=local)
    # scanner.Run()

    # Запустить потоки
    local.StartCycle(Elections, sec=600, args=(local, ton, ))
    local.StartCycle(Statistics, sec=10, args=(local, scanner,))
    local.StartCycle(Offers, sec=600, args=(local, ton, ))
    local.StartCycle(Complaints, sec=600, args=(local, ton, ))
    local.StartCycle(Slashing, sec=600, args=(local, ton, ))
    local.StartCycle(Domains, sec=600, args=(local, ton, ))
    local.StartCycle(Telemetry, sec=60, args=(local, ton, ))
    local.StartCycle(OverlayTelemetry, sec=7200, args=(local, ton, ))
    local.StartCycle(ScanLiteServers, sec=60, args=(local, ton,))
    Sleep()
# end define


def mytoncore():
    from mypylib.mypylib import MyPyClass

    local = MyPyClass('mytoncore.py')
    print('Local DB path:', local.buffer['localdbFileName'])
    Init(local)
    General(local)
