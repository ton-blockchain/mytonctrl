# MyTonCtrl (v0.2, OS Ubuntu)

This page contains:
1. [Node types overview](/docs/en/manual-ubuntu#node-types-overview)
2. [MyTonCtrl installing](/docs/en/manual-ubuntu#mytonctrl-install)
3. [Become a validator](/docs/en/manual-ubuntu#how-to-become-a-validator-with-mytonctrl)
4. [Liteserver installation](/docs/en/manual-ubuntu#liteserver-installation)
5. [Archive node installation](/docs/en/manual-ubuntu#archive-node-installation)

More information can be found in [TON Node & mytonctrl documentation](https://docs.ton.org/participate/nodes/node-types)

## Node types overview

In *simplified terms*, a blockchain `node` is **one of the computers** that **collectively run the blockchain's software**. It enables the blockchain to search and optionally validate transactions and keep the network secure ensuring that the network remains **decentralized**.

When diving into the world of The Open Network (TON), understanding the distinct node types and their functionalities is crucial. This article breaks down each node type to provide clarity for developers wishing to engage with the TON blockchain.

### Full Node

A `Full Node` in TON is a node that **maintains synchronization** with the blockchain.

It retains the _current state_ of the blockchain and can house either the entire block history or parts of it. This makes it the backbone of the TON blockchain, facilitating the network's decentralization and security.

### Archive Node

If `Full node` archives the **entire block history** it's called `Archive Node`.

Such nodes are indispensable for creating blockchain explorers or other tools that necessitate a full blockchain history.

### Validator Node

TON operates on a **Proof-of-Stake** mechanism, where `validators` are pivotal in maintaining network functionality. `Validators` are [rewarded in Toncoin](/participate/network-maintenance/staking-incentives) for their contributions, incentivizing network participation and ensuring network security.

If `full node` holds a **necessary amount of Toncoin** as a **stake**, it can be used as `Validator Node`.

### Liteserver

`Full Node` can be used as `Liteserver`. This node type can field and respond to requests from `Lite Clients`, allowing to seamlessly interact with the TON Blockchain.

`Liteservers` enable swift communication with Lite Clients, facilitating tasks like retrieving balance or submitting transactions without necessitating the full block history.

Actually, there are two public `Liteservers`, that already have been provided by the TON Foundation. They are accessible for universal use.

- [Public Liteserver Configurations - mainnet](https://ton.org/global-config.json)
- [Public Liteserver Configurations - testnet](https://ton.org/testnet-global.config.json)

These endpoints, such as those used by standard wallets, ensure that even without setting up a personal liteserver, interaction with the TON Blockchain remains possible.

If your project requires a high level of _security_, you can run your own `Liteserver`. To run a `full node` as a `Liteserver`, simply enable the `Liteserver` mode in your node's configuration file.

### Lite Clients: the SDKs to interact with TON

Each SDK which supports ADNL protocol can be used as a `Lite Client` with `config.json` file (find how to download it [here](/participate/nodes/node-types#troubleshooting)). The `config.json` file contains a list of endpoints that can be used to connect to the TON Blockchain.

Each SDK without ADNL support usually uses HTTP middleware to connect to the TON Blockchain. It's less secure and slower than ADNL, but it's easier to use.

What to do if you get *Timed out after 3 seconds* error?

If you see this error this means that the liteserver you are trying to connect to is not available. The correct way to solve this issue for public liteservers is as follows:

1. Download the config.json file from the tontech link:

```bash
wget https://api.tontech.io/ton/wallet-mainnet.autoconf.json -O /usr/bin/ton/global.config.json
```

It removes slow liteservers from the configuration file.

2. Use the downloaded config.json file in your application with [TON SDK](/develop/dapps/apis/sdk).

## MyTonCtrl install

1. Download the installation script. We recommend installing the tool under your local user account, not as Root. In our example, a local user account is used:

    ```sh
    wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/install.sh
    ```

   ![wget output](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_wget-ls_ru.png)

2. Run the installation script as an administrator:

    ```sh
    sudo bash install.sh -m full
    ```

## How to Become a Validator with mytonctrl

Here are the steps to become a validator using mytonctrl. This example is applicable for the Ubuntu Operating System.

### 1. Install mytonctrl

### 2. Conduct an Operability Test:

1. Run **mytonctrl** from the local user account used for installation in step 1:

    ```sh
    mytonctrl
    ```

2. Check the **mytonctrl** statuses, particularly the following:

* **mytoncore status**: Should be in green.
* **Local validator status**: Should also be in green.
* **Local validator out of sync**: Initially, a large number is displayed. As soon as the newly created validator connects with other validators, the number will be around 250k. As synchronization progresses, this number decreases. When it falls below 20, the validator is synchronized.

  ![status](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/mytonctrl-status.png)


### 3. View the List of Available Wallets

Check out the list of available wallets. For instance, during the installation of **mytonctrl**, the **validator_wallet_001** wallet is created:

![wallet list](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-wl_ru.png)

### 4. Send the Required Number of Coins to the Wallet and Activate It

To determine the minimum amount of coins required to participate in one election round, head to **tonmon.xyz** > **Participant stakes**.

* Use the `vas` command to display the history of transfers
* Activate the wallet using the `aw` command

  ![account history](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-vas-aw_ru.png)

### 5. Your Validator is Now Ready

**mytoncore** will automatically join the elections. It divides the wallet balance into two parts and uses them as a stake to participate in the elections. You can also manually set the stake size:

`set stake 50000` — this sets the stake size to 50k coins. If the bet is accepted and our node becomes a validator, the bet can only be withdrawn in the second election (according to the rules of the electorate).

![setting stake](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-set_ru.png)

You can also command for help anytime.

![help command](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-help_ru.png)

To check **mytoncrl** logs, open `~/.local/share/mytoncore/mytoncore.log` for a local user or `/usr/local/bin/mytoncore/mytoncore.log` for Root.

![logs](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytoncore-log.png)

## Liteserver installation

1. Complete the previous steps to install [MyTonCtrl](/participate/run-nodes/full-node#run-a-node-text).

2. Create a config file

```bash
MyTonCtrl> installer
MyTonInstaller> clcf

Local config file created: /usr/bin/ton/local.config.json
```

3. This file will help you to connect to your liteserver. Copy the config file located on the specified path to your home to save it.

```bash
cp /usr/bin/ton/local.config.json ~/config.json
```

4. Create an empty `config.json` file on your local machine.

5. Copy the content from the console to your local machine `config.json` file.

```bash
cat ~/config.json
```

### Check the firewall settings

First, verify the Liteserver port specified in your `config.json` file. This port changes with each new installation of `MyTonCtrl`. It is located in the `port` field:

```json
{
  ...
  "liteservers": [
    {
      "ip": 1605600994,
      "port": LITESERVER_PORT
      ...
    }
  ]
}
```

If you are using a cloud provider, you need to open this port in the firewall settings. For example, if you are using AWS, you need to open the port in the [security group](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html).

Below is an example of opening a port in the bare metal server firewall.

#### Opening a port in the firewall

We will use the `ufw` utility ([cheatsheet](https://www.cyberciti.biz/faq/ufw-allow-incoming-ssh-connections-from-a-specific-ip-address-subnet-on-ubuntu-debian/)). You can use the one you prefer.

1. Install `ufw` if it is not installed:

```bash
sudo apt update
sudo apt install ufw
```

2. Allow ssh connections:

```bash
sudo ufw allow ssh
```

3. Allow the port specified in the `config.json` file:

```bash
sudo ufw allow <port>
```

4. Enable the firewall:

```bash
sudo ufw enable
```

5. Check the firewall status:

```bash
sudo ufw status
```

This way, you can open the port in the firewall settings of your server.

## Archive node installation

### Install ZFS and Prepare Volume

Dumps come in form of ZFS Snapshots compressed using plzip, you need to install zfs on your host and restore the dump, see [Oracle Documentation](https://docs.oracle.com/cd/E23824_01/html/821-1448/gavvx.html#scrolltoc) for more details.

Usually, it's a good idea to create a separate ZFS pool for your node on a _dedicated SSD drive_, this will allow you to easily manage storage space and backup your node.

1. Install [zfs](https://ubuntu.com/tutorials/setup-zfs-storage-pool#1-overview)
```shell
sudo apt install zfsutils-linux
```
2. [Create pool](https://ubuntu.com/tutorials/setup-zfs-storage-pool#3-creating-a-zfs-pool) on your dedicated 4TB `<disk>` and name it `data`

```shell
sudo zpool create data <disk>
```
3. Before restoring we highly recommend to enable compression on parent ZFS filesystem, this will save you a [lot of space](https://www.servethehome.com/the-case-for-using-zfs-compression/). To enable compression for the `data` volume enter using root account:

```shell
sudo zfs set compression=lz4 data
```

### Install MyTonCtrl

Please, use a [Running Full Node](/participate/run-nodes/full-node) to **install** and **run** mytonctrl.

### Run an Archive Node

#### Prepare the node

1. Before performing a restore, you must stop the validator using root account:
```shell
sudo -s
systemctl stop validator.service
```
2. Make a backup of `ton-work` config files (we will need the `/var/ton-work/db/config.json`, `/var/ton-work/keys`, and `/var/ton-work/db/keyring`).
```shell
mv /var/ton-work /var/ton-work.bak
```

#### Download the dump

1. Request `user` and `password` credentials to gain access for downloading dumps in the [@TONBaseChatEn](https://t.me/TONBaseChatEn) Telegram chat.
2. Here is an example command to download & restore the dump from the ton.org server:

```shell
wget --user <usr> --password <pwd> -c https://archival-dump.ton.org/dumps/latest.zfs.lz | pv | plzip -d -n <cores> | zfs recv data/ton-work
```

Size of the dump is __~1.5TB__, so it will take some time to download and restore it.

Prepare and run the command:
1. Install the tools if necessary (`pv`, `plzip`)
2. Replace `<usr>` and `<pwd>` with your credentials
2. Tell `plzip` to use as many cores as your machine allows to speed up extraction (`-n`)

#### Mount the dump

1. Mount zfs:
```shell
zfs set mountpoint=/var/ton-work data/ton-work && zfs mount data/ton-work
```
2. Restore `db/config.json`, `keys` and `db/keyring` from backup to `/var/ton-work`
```shell
cp /var/ton-work.bak/db/config.json /var/ton-work/db/config.json
cp -r /var/ton-work.bak/keys /var/ton-work/keys
cp -r /var/ton-work.bak/db/keyring /var/ton-work/db/keyring
```
3. Make sure that permissions for `/var/ton-work` and `/var/ton-work/keys` dirs promoted correctly:

- The owner for the `/var/ton-work/db` dir should be `validator` user:

```shell
chown -R validator:validator /var/ton-work/db
```

- The owner for the `/var/ton-work/keys` dir should be `ubuntu` user:

```shell
chown -R ubuntu:ubuntu /var/ton-work/keys
```

#### Update Configuration

Update node configuration for the archive node.

1. Open the node config file `/etc/systemd/system/validator.service`
```shell
nano /etc/systemd/system/validator.service
```

2. Add storage settings for the node in the `ExecStart` line:
```shell
--state-ttl 315360000 --archive-ttl 315360000 --block-ttl 315360000
```

:::info
Please be patient once you start the node and observe the logs. Dumps come without DHT caches, so it will take your node some time to find other nodes and then sync with them. Depending on the age of the snapshot, your node might take from a few hours to several days to catch up with the network. This is normal.
:::

#### Start the node

1. Start the validator by running the command:

```shell
systemctl start validator.service
```

2. Open `mytonctrl` from _local user_ and check the node status using the `status`.
