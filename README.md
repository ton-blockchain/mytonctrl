[Данный текст доступен на русском языке.](https://github.com/igroman787/mytonctrl/blob/master/README.Ru.md)

## What is it
This console program is a wrapper over `fift`,`lite-client` and `validator-engine-console`. It was created to facilitate the management of wallets, domains and a validator on the Linux operating system.
![](https://raw.githubusercontent.com/igroman787/mytonctrl/master/screens/mytonctrl-status.png)

## Functional
- [x] Show TON network status
- [x] Management of local wallets
	- [x] Create local wallet
	- [x] Activate local wallet
	- [x] Show local wallets
	- [x] Import wallet from file (.pk)
	- [x] Save wallet address to file (.addr)
	- [x] Delete local wallet
- [x] Show account status
	- [x] Show account balance
	- [x] Show account history
	- [x] Show account status from bookmarks
- [x] Transferring funds to the wallet
	- [x] Transfer of a fixed amount
	- [x] Transfer of the entire amount (all)
	- [x] Transfer of the entire amount with wallet deactivation (alld)
	- [x] Transferring funds to the wallet from bookmarks
	- [x] Transferring funds to a wallet through a chain of self-deleting wallets
- [x] Manage bookmarks
	- [x] Add account to bookmarks
	- [x] Show bookmarks
	- [x] Delete bookmark
- [x] Offer management
	- [x] Show offers
	- [x] Vote for the proposal
	- [x] Automatic voting for previously voted proposals
- [x] Domain management
	- [x] Rent a new domain
	- [x] Show rented domains
	- [x] Show domain status
	- [x] Delete domain
	- [ ] Automatic domain renewal
- [x] Controlling the validator
	- [x] Participate in the election of a validator
	- [x] Return bet + reward
	- [x] Autostart validator on abnormal termination (systemd)
	- [x] Send validator statistics to https://toncenter.com

## List of tested operating systems
```
Ubuntu 16.04 LTS (Xenial Xerus) - Error: TON compilation error
Ubuntu 18.04 LTS (Bionic Beaver) - OK
Ubuntu 20.04 LTS (Focal Fossa) - OK
Debian 8 - Error: Unable to locate package libgsl-dev
Debian 9 - Error: TON compilation error
Debian 10 - OK
```

## Description of installation scripts
- `toninstaller.sh` - This script clones the sources of `TON` and` mytonctrl` in the folders `/usr/src/ton` and`/usr/src/mytonctrl`, compiles programs from sources and writes them to `/usr/bin/`.
- `mytoninstaller.py` - This script configures the validator, `mytonctrl` and creates keys for connecting to the validator.

## Installation modes
There are two installation modes: `lite` and` full`. They both **compile** and install the `TON` components. However, the `lite` version does not configure or run the validator.

## Installation (Ubuntu)
1. Download and execute the script `install.sh` with the desired installation mode. During installation, you will be prompted for the superuser password several times.
```sh
wget https://raw.githubusercontent.com/igroman787/mytonctrl/master/scripts/install.sh
sudo bash install.sh -m <mode>
```

2. Done. You can try to run the program `mytonctrl`.
```sh
mytonctrl
```


## Installation (Debian)
1. Download and execute the script `install.sh` with the desired installation mode. During installation, you will be prompted for the superuser password several times.
```sh
wget https://raw.githubusercontent.com/igroman787/mytonctrl/master/scripts/install.sh
su root -c 'bash install.sh -m <mode>'
```

2. Done. You can try to run the program `mytonctrl`.
```sh
mytonctrl
```

## Telemetry
By default, `mytonctrl` sends validator statistics to the server https://toncenter.com
This is necessary to identify anomalies in the network, as well as to quickly respond to developers.
To disable telemetry during installation, use the `-t` flag:
```sh
sudo bash install.sh -m <mode> -t
```

To disable telemetry after installation:
```sh
MyTonCtrl> set sendTelemetry false
```

## Useful links
1. https://ton.org/docs/#/howto/
2. https://test.ton.org/FullNode-HOWTO.txt
3. https://test.ton.org/Validator-HOWTO.txt
4. https://test.ton.org/TonSites-HOWTO.txt
5. https://test.ton.org/DNS-HOWTO.txt
6. https://test.ton.org/ConfigParam-HOWTO.txt
