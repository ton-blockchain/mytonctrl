[Данный текст доступен на русском языке.](https://github.com/ton-blockchain/mytonctrl/blob/master/README.Ru.md)

## What is it?
This console is a wrapper over `fift`,`lite-client` and `validator-engine-console`. It was created to facilitate wallet, domain and validator management on Linux OS.

![](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/mytonctrl-status.png)

## Functionality
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

## Installation scripts overview
- `toninstaller.sh`: clones `TON` and` mytonctrl` sources to `/usr/src/ton` and`/usr/src/mytonctrl` folders, compiles programs from sources and writes them to `/usr/bin/`.
- `mytoninstaller.py`: configures the validator and `mytonctrl`; generates validator connection keys.

## Installation modes
There are two installation modes: `lite` and` full`. They both **compile** and install `TON` components. However, the `lite` version does not configure or run the node/validator.

## Installation (Ubuntu)
1. Download and execute the script `install.sh` with the desired installation mode. During installation, you will be prompted for the superuser password several times.
```sh
wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/install.sh
sudo bash install.sh -m <mode>
```

2. Done. You can try to run the program `mytonctrl`.
```sh
mytonctrl
```


## Installation (Debian)
1. Download and execute the script `install.sh` with the desired installation mode. During installation, you will be prompted for the superuser password several times.
```sh
wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/install.sh
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

## Web admin panel
To be able to control the node/validator through the browser, you need to install an additional module:
`mytonctrl` -> `installer` -> `enable JR`

Next, you need to create a password for the connection:
`mytonctrl` -> `installer` -> `setwebpass`

Ready. Now you can go to the site https://tonadmin.org and log in using your data.
git: https://github.com/igroman787/mtc-jsonrpc

## Local copy of toncenter
In order to raise a local copy of https://toncenter.com on the server, you need to install an additional module:
`mytonctrl` ->` installer` -> `enable PT`

Ready. A local copy of toncenter is available at `http://<server-ip-address>:8000`
git: https://github.com/igroman787/pytonv3

## Useful links
1. https://github.com/ton-blockchain/mytonctrl/blob/master/docs/en/manual-ubuntu.md
2. https://ton.org/docs/
