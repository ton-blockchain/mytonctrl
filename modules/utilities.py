import json
import random
import subprocess
import time

import requests

from mypylib.mypylib import color_print, print_table, color_text, timeago, bcolors
from modules.module import MtcModule


class UtilitiesModule(MtcModule):

    description = ''
    default_value = False

    def view_account_status(self, args):
        try:
            addrB64 = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} vas <account-addr>")
            return
        addrB64 = self.ton.get_destination_addr(addrB64)
        account = self.ton.GetAccount(addrB64)
        version = self.ton.GetVersionFromCodeHash(account.codeHash)
        statusTable = list()
        statusTable += [["Address", "Status", "Balance", "Version"]]
        statusTable += [[addrB64, account.status, account.balance, version]]
        codeHashTable = list()
        codeHashTable += [["Code hash"]]
        codeHashTable += [[account.codeHash]]
        historyTable = self.get_history_table(addrB64, 10)
        print_table(statusTable)
        print()
        print_table(codeHashTable)
        print()
        print_table(historyTable)
    # end define

    def get_history_table(self, addr, limit):
        addr = self.ton.get_destination_addr(addr)
        account = self.ton.GetAccount(addr)
        history = self.ton.GetAccountHistory(account, limit)
        table = list()
        typeText = color_text("{red}{bold}{endc}")
        table += [["Time", typeText, "Coins", "From/To"]]
        for message in history:
            if message.srcAddr is None:
                continue
            srcAddrFull = f"{message.srcWorkchain}:{message.srcAddr}"
            destAddFull = f"{message.destWorkchain}:{message.destAddr}"
            if srcAddrFull == account.addrFull:
                type = color_text("{red}{bold}>>>{endc}")
                fromto = destAddFull
            else:
                type = color_text("{blue}{bold}<<<{endc}")
                fromto = srcAddrFull
            fromto = self.ton.AddrFull2AddrB64(fromto)
            # datetime = timestamp2datetime(message.time, "%Y.%m.%d %H:%M:%S")
            datetime = timeago(message.time)
            table += [[datetime, type, message.value, fromto]]
        return table
    # end define

    def view_account_history(self, args):
        try:
            addr = args[0]
            limit = int(args[1])
        except:
            color_print("{red}Bad args. Usage:{endc} vah <account-addr> <limit>")
            return
        table = self.get_history_table(addr, limit)
        print_table(table)
    # end define

    def create_new_bookmark(self, args):
        try:
            name = args[0]
            addr = args[1]
        except:
            color_print("{red}Bad args. Usage:{endc} nb <bookmark-name> <account-addr>")
            return
        if not self.ton.IsAddr(addr):
            raise Exception("Incorrect address")
        # end if

        bookmark = dict()
        bookmark["name"] = name
        bookmark["addr"] = addr
        self.ton.AddBookmark(bookmark)
        color_print("CreatNewBookmark - {green}OK{endc}")
    # end define

    def print_bookmarks_list(self, args):
        data = self.ton.GetBookmarks()
        if data is None or len(data) == 0:
            print("No data")
            return
        table = list()
        table += [["Name", "Address", "Balance / Exp. date"]]
        for item in data:
            name = item.get("name")
            addr = item.get("addr")
            bookmark_data = item.get("data")
            table += [[name, addr, bookmark_data]]
        print_table(table)
    # end define

    def delete_bookmark(self, args):
        try:
            name = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} db <bookmark-name>")
            return
        self.ton.DeleteBookmark(name)
        color_print("DeleteBookmark - {green}OK{endc}")
    # end define

    @staticmethod
    def reduct(item):
        item = str(item)
        if item is None:
            result = None
        else:
            end = len(item)
            result = item[0:6] + "..." + item[end - 6:end]
        return result
    # end define

    def print_offers_list(self, args):
        data = self.ton.GetOffers()
        if data is None or len(data) == 0:
            print("No data")
            return
        if "--json" in args:
            text = json.dumps(data, indent=2)
            print(text)
        else:
            table = list()
            table += [["Hash", "Config", "Votes", "W/L", "Approved", "Is passed"]]
            for item in data:
                hash = item.get("hash")
                votedValidators = len(item.get("votedValidators"))
                wins = item.get("wins")
                losses = item.get("losses")
                wl = "{0}/{1}".format(wins, losses)
                approvedPercent = item.get("approvedPercent")
                approvedPercent_text = "{0}%".format(approvedPercent)
                isPassed = item.get("isPassed")
                if "hash" not in args:
                    hash = self.reduct(hash)
                if isPassed == True:
                    isPassed = bcolors.green_text("true")
                if isPassed == False:
                    isPassed = bcolors.red_text("false")
                table += [[hash, item.config.id, votedValidators, wl, approvedPercent_text, isPassed]]
            print_table(table)
    # end define

    def get_offer_diff(self, offer_hash):
        self.local.add_log("start GetOfferDiff function", "debug")
        offer = self.ton.GetOffer(offer_hash)
        config_id = offer["config"]["id"]
        config_value = offer["config"]["value"]

        if '{' in config_value or '}' in config_value:
            start = config_value.find('{') + 1
            end = config_value.find('}')
            config_value = config_value[start:end]
        # end if

        args = [self.ton.liteClient.appPath, "--global-config", self.ton.liteClient.configPath, "--verbosity", "0"]
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(1)

        fullConfigAddr = self.ton.GetFullConfigAddr()
        cmd = "runmethodfull {fullConfigAddr} list_proposals".format(fullConfigAddr=fullConfigAddr)
        process.stdin.write(cmd.encode() + b'\n')
        process.stdin.flush()
        time.sleep(1)

        cmd = "dumpcellas ConfigParam{configId} {configValue}".format(configId=config_id, configValue=config_value)
        process.stdin.write(cmd.encode() + b'\n')
        process.stdin.flush()
        time.sleep(1)

        process.terminate()
        text = process.stdout.read().decode()

        lines = text.split('\n')
        b = len(lines)
        for i in range(b):
            line = lines[i]
            if "dumping cells as values of TLB type" in line:
                a = i + 2
                break
        # end for

        for i in range(a, b):
            line = lines[i]
            if '(' in line:
                start = i
                break
        # end for

        for i in range(a, b):
            line = lines[i]
            if '>' in line:
                end = i
                break
        # end for

        buff = lines[start:end]
        text = "".join(buff)
        newData = self.ton.Tlb2Json(text)
        newFileName = self.ton.tempDir + "data1diff"
        file = open(newFileName, 'wt')
        newText = json.dumps(newData, indent=2)
        file.write(newText)
        file.close()

        oldData = self.ton.GetConfig(config_id)
        oldFileName = self.ton.tempDir + "data2diff"
        file = open(oldFileName, 'wt')
        oldText = json.dumps(oldData, indent=2)
        file.write(oldText)
        file.close()

        print(oldText)
        args = ["diff", "--color", oldFileName, newFileName]
        subprocess.run(args)
    # end define

    def offer_diff(self, args):
        try:
            offer_hash = args[0]
            offer_hash = offer_hash
        except:
            color_print("{red}Bad args. Usage:{endc} od <offer-hash>")
            return
        self.get_offer_diff(offer_hash)
    # end define

    def print_complaints_list(self, args):
        past = "past" in args
        data = self.ton.GetComplaints(past=past)
        if data is None or len(data) == 0:
            print("No data")
            return
        if "--json" in args:
            text = json.dumps(data, indent=2)
            print(text)
        else:
            table = list()
            table += [["Election id", "ADNL", "Fine (part)", "Votes", "Approved", "Is passed"]]
            for key, item in data.items():
                electionId = item.get("electionId")
                adnl = item.get("adnl")
                suggestedFine = item.get("suggestedFine")
                suggestedFinePart = item.get("suggestedFinePart")
                Fine_text = "{0} ({1})".format(suggestedFine, suggestedFinePart)
                votedValidators = len(item.get("votedValidators"))
                approvedPercent = item.get("approvedPercent")
                approvedPercent_text = "{0}%".format(approvedPercent)
                isPassed = item.get("isPassed")
                if "adnl" not in args:
                    adnl = self.reduct(adnl)
                if isPassed:
                    isPassed = bcolors.green_text("true")
                if not isPassed:
                    isPassed = bcolors.red_text("false")
                table += [[electionId, adnl, Fine_text, votedValidators, approvedPercent_text, isPassed]]
            print_table(table)
    # end define

    def print_election_entries_list(self, args):
        past = "past" in args
        data = self.ton.GetElectionEntries(past=past)
        if data is None or len(data) == 0:
            print("No data")
            return
        if "--json" in args:
            text = json.dumps(data, indent=2)
            print(text)
        else:
            table = list()
            table += [["ADNL", "Pubkey", "Wallet", "Stake", "Max-factor"]]
            for key, item in data.items():
                adnl = item.get("adnlAddr")
                pubkey = item.get("pubkey")
                walletAddr = item.get("walletAddr")
                stake = item.get("stake")
                maxFactor = item.get("maxFactor")
                if "adnl" not in args:
                    adnl = self.reduct(adnl)
                if "pubkey" not in args:
                    pubkey = self.reduct(pubkey)
                if "wallet" not in args:
                    walletAddr = self.reduct(walletAddr)
                table += [[adnl, pubkey, walletAddr, stake, maxFactor]]
            print_table(table)
    # end define

    def print_validator_list(self, args):
        past = "past" in args
        fast = "fast" in args
        data = self.ton.GetValidatorsList(past=past, fast=fast)
        if data is None or len(data) == 0:
            print("No data")
            return
        if "--json" in args:
            text = json.dumps(data, indent=2)
            print(text)
        else:
            table = list()
            table += [["id", "ADNL", "Pubkey", "Wallet", "Stake", "Efficiency", "Online"]]
            for i, item in enumerate(data):
                adnl = item.get("adnlAddr")
                pubkey = item.get("pubkey")
                walletAddr = item.get("walletAddr")
                efficiency = item.get("efficiency")
                online = item.get("online")
                stake = item.get("stake")
                if "adnl" not in args:
                    adnl = self.reduct(adnl)
                if "pubkey" not in args:
                    pubkey = self.reduct(pubkey)
                if "wallet" not in args:
                    walletAddr = self.reduct(walletAddr)
                if "offline" in args and online != False:
                    continue
                if online:
                    online = bcolors.green_text("true")
                if not online:
                    online = bcolors.red_text("false")
                table += [[str(i), adnl, pubkey, walletAddr, stake, efficiency, online]]
            print_table(table)
    # end define

    def check_adnl_connection(self):
        telemetry = self.ton.local.db.get("sendTelemetry", False)
        check_adnl = self.ton.local.db.get("checkAdnl", telemetry)
        if not check_adnl:
            return True, ''
        self.local.add_log('Checking ADNL connection to local node', 'info')
        hosts = ['45.129.96.53', '5.154.181.153', '2.56.126.137', '91.194.11.68', '45.12.134.214', '138.124.184.27',
                 '103.106.3.171']
        hosts = random.sample(hosts, k=3)
        data = self.ton.get_local_adnl_data()
        error = ''
        ok = True
        for host in hosts:
            url = f'http://{host}/adnl_check'
            try:
                response = requests.post(url, json=data, timeout=5).json()
            except Exception as e:
                ok = False
                error = f'Failed to check ADNL connection to local node: {type(e)}: {e}'
                continue
            result = response.get("ok")
            if result:
                ok = True
                break
            if not result:
                ok = False
                error = f'Failed to check ADNL connection to local node: {response.get("message")}'
        return ok, error

    def get_seqno(self, args):
        try:
            walletName = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} seqno <wallet-name>")
            return
        wallet = self.ton.GetLocalWallet(walletName)
        seqno = self.ton.GetSeqno(wallet)
        print(walletName, "seqno:", seqno)
    # end define

    def get_config(self, args):
        try:
            configId = args[0]
            configId = int(configId)
        except:
            color_print("{red}Bad args. Usage:{endc} gc <config-id>")
            return
        data = self.ton.GetConfig(configId)
        text = json.dumps(data, indent=2)
        print(text)
    # end define

    def get_pool_data(self, args):
        try:
            pool_name = args[0]
        except:
            color_print("{red}Bad args. Usage:{endc} get_pool_data <pool-name | pool-addr>")
            return
        if self.ton.IsAddr(pool_name):
            pool_addr = pool_name
        else:
            pool = self.ton.GetLocalPool(pool_name)
            pool_addr = pool.addrB64
        pool_data = self.ton.GetPoolData(pool_addr)
        print(json.dumps(pool_data, indent=4))
    # end define

    def add_console_commands(self, console):
        console.AddItem("vas", self.view_account_status, self.local.translate("vas_cmd"))
        console.AddItem("vah", self.view_account_history, self.local.translate("vah_cmd"))

        console.AddItem("nb", self.create_new_bookmark, self.local.translate("nb_cmd"))
        console.AddItem("bl", self.print_bookmarks_list, self.local.translate("bl_cmd"))
        console.AddItem("db", self.delete_bookmark, self.local.translate("db_cmd"))

        console.AddItem("ol", self.print_offers_list, self.local.translate("ol_cmd"))
        console.AddItem("od", self.offer_diff, self.local.translate("od_cmd"))

        console.AddItem("el", self.print_election_entries_list, self.local.translate("el_cmd"))
        console.AddItem("vl", self.print_validator_list, self.local.translate("vl_cmd"))
        console.AddItem("cl", self.print_complaints_list, self.local.translate("cl_cmd"))

        console.AddItem("seqno", self.get_seqno, self.local.translate("seqno_cmd"))
        console.AddItem("getconfig", self.get_config, self.local.translate("getconfig_cmd"))
        console.AddItem("get_pool_data", self.get_pool_data, self.local.translate("get_pool_data_cmd"))
