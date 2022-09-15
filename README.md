[Данный текст доступен на русском языке.](https://github.com/ton-blockchain/mytonctrl/blob/master/README.Ru.md)

**Current fork updates** [here](#cli-wrapper-for-mytonctrl) 

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
There are two installation modes: `lite` and` full`. They both **compile** and install `TON` components. However the `lite` version does not configure or run the node/validator.

## Installation for Ubuntu
1. Download and execute the `install.sh` script in the desired installation mode. During installation the script prompts you for the superuser password several times.
```sh
wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/install.sh
sudo bash install.sh -m <mode>
```

2. Done. You can try to run the `mytonctrl` console now.
```sh
mytonctrl
```


## Installation for Debian
1. Download and execute the `install.sh` script in the desired installation mode. During installation the script prompts you for the superuser password several times.
```sh
wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/install.sh
su root -c 'bash install.sh -m <mode>'
```

2. Done. You can try to run the `mytonctrl` console now.
```sh
mytonctrl
```

## Telemetry
By default, `mytonctrl` sends validator statistics to the https://toncenter.com server.
It is necessary to identify network abnormalities, as well as to quickly give feedback to developers.
To disable telemetry during installation, use the `-t` flag:
```sh
sudo bash install.sh -m <mode> -t
```

To disable telemetry after installation, do the following:
```sh
MyTonCtrl> set sendTelemetry false
```

## Web admin panel
To control the node/validator through the browser, you need to install an additional module:
`mytonctrl` -> `installer` -> `enable JR`

Next, you need to create a password for connection:
`mytonctrl` -> `installer` -> `setwebpass`

Ready. Now you can go to https://tonadmin.org site and log in with your credentials.
git: https://github.com/igroman787/mtc-jsonrpc

## Local copy of toncenter
To set up a local https://toncenter.com copy on your server, install an additional module:
`mytonctrl` ->` installer` -> `enable PT`

Ready. A local copy of toncenter is available at `http://<server-ip-address>:8000`
git: https://github.com/igroman787/pytonv3

## Useful links
1. https://github.com/ton-blockchain/mytonctrl/blob/master/docs/en/manual-ubuntu.md
2. https://ton.org/docs/


# Cli wrapper for "mytonctrl"

1. As first step you must clone repository to your machine:
```bash
git clone git@github.com:tonbakers/mytonctrl.git
```
2. When repository is copied type next commands:
```bash
poetry shell
poetry install
```
3. To run cli wrapper type a:
```bash
poetry run python manage.py
# or
python manage.py
```
You will get the next message with application description:
```bash
> poetry run python manage.py 
Usage: manage.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  get-settings  Get network settings.
  move-coins    Move coins to specified account/wallet.
  set-settings  Set network settings.
  status        Get wallet status information.
  update        Update "mytonctrl" to actual version
  upgrade       Upgrade TON sources to the latest version.
  vote          Vote offer.
  wallets-list  Wallets list of your account.
```
To get more information about **cli** commands, you need to type a command and flag `--help` after:
```bash
# Example:
> python manage.py status --help
Usage: manage.py status [OPTIONS] [STATUS_TYPE]

  Get wallet status information.

Options:
  --help  Show this message and exit.
```
