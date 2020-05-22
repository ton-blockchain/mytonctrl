## HOWTO
This console program is a wrapper over `fift`,` lite-client` and `validator-engine-console`. It was created to facilitate the management of wallets, domains, and validators on the Linux.

Installing the TON validator through the MyTonCtrl console utility.
The instructions and scripts below were verified on ```Ubuntu 18.04``` and ```Debian 10.3```.

![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/mytonctrl-status.png)

## System requirements

To start a validator (full node) in testnet we recommend looking at these system requirements.

| Configuration | CPU (cores) | RAM (GB) | SSD/NVME (GB) | Network (Mbit/s)|
|---|:---|:---|:---|:---|
| Minimal |6|16|256|100|
| Recommended |8|32|480-960|500|

UP and DOWN traffic is symmetrical during the validator is working and equal to average 50 Mbit/s in both directions.

These minimum requirements were obtained based on our experience of raising validators. In order to save your personal funds on powerful servers and more people can join the network, we tried to specify the minimum parameters that are possible for the validator to work :)

## Console features
- [x] TON network status
- [x] Local Wallets Management
- [x] Show account status
- [x] Show account balance
- [x] Show account history
- [x] Show account status from bookmarks
- [x] Transfer funds to wallet
- [x] Transfer a fixed amount
- [x] Transfer the entire amount (all)
- [x] Transferring the entire amount with wallet deactivation (all)
- [x] Transfer funds to your wallet from bookmarks
- [x] Bookmark management
- [x] Bookmark this account
- [x] Show bookmarks
- [x] Delete bookmark
- [x] Offer Management
- [x] Show offers
- [x] Vote for the proposal
- [x] Automatic voting for previously voted offers
- [x] Domain Management
- [x] Rent a new domain
- [x] Show leased domains
- [x] Show domain status
- [x] Delete domain
- [x] Validator Management
- [x] Participate in the election of a validator
- [x] Return bid + reward

##TODO
- [] Automatically renew domains
- [] Automatic scheduled funds sending
- [] Add rule to schedule
- [] Show schedule rules
- [] Remove rule from schedule
- [] Autostart validator during abnormal termination
- [] Send validator statistics to http://validators.ton
- [] Pass funds through the mixer



## Installation Modes
There are two installation modes: `lite` and` full`. Both of them ** compile ** and install the `TON` components.
However, the `lite` version does not configure or launch the validator.
`full` installation mode will compile and install all the necessary components for your node to participate in the election of validators.

## Installation (Ubuntu)
1. Download and run the `install.sh` script with the installation mode you need. During installation, you will be asked for the superuser password several times.
```sh
wget https://raw.githubusercontent.com/igroman787/mytonctrl/master/scripts/install.sh
```

2. If you want to install `full` node to participate in elections run:
```sh
sudo sh install.sh -m full
```
Or  
```sh
sudo sh install.sh -m lite
```
to install `lite` version of the client.

If the installation was completed successfully, then you will receive the following response in the console:

![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/mytonctrl-inst.png)


3. Then you can run `MytonCtrl` with the command:
```sh
MyTonCtrl
```

4. To learn more about the available commands type `help`


## Установка (Debian)
1. Download and run the `install.sh` script with the installation mode you need. During installation, you will be asked for the superuser password several times.
```sh
wget https://raw.githubusercontent.com/igroman787/mytonctrl/master/scripts/install.sh
```
2. If you want to install `full` node to participate in elections run:
```sh
su root -c 'sh install.sh -m full'
```
Or  
```sh
su root -c 'sh install.sh -m lite'
```
to install `lite` version of the client.

If the installation was completed successfully, then you will receive the following response in the console:

![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/mytonctrl-inst.jpeg)

3. Then you can run `MytonCtrl` with the command:
```sh
MyTonCtrl
```

4. To learn more about the available commands type `help`.


## How to become a validator (`full` mode)

TON network automatically turns on when MytonCtrl is installed.
To view the logs type:

```sh
tail -f ~/.local/share/mytoncore/mytoncore.log
```
Go to the console, enter help and wait until the parameter "Time difference" is in the range from -1 to -10
Now your node is synchronized!

1. Creating and activating a wallet

`MytonCtrl` automatically creates a wallet for your validator during installation.
Type `wl` to display a list of wallets.
Now you see your wallet address, balance and status: `empty`

![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/mytonctrl-ewl.jpeg)

To activate your wallet type `aw` (Activate Wallet).
After that, you will see that the wallet is activated:

![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/mytonctrl-awl.jpeg)

Now you need to fund the wallet balance by an amount sufficient for voting. (This parameter is opposite the column "Minimum stake")

// Write to faucet bot take some tokens.
