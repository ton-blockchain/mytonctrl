![GitHub stars](https://img.shields.io/github/stars/ton-blockchain/mytonctrl?style=flat-square&logo=github) ![GitHub forks](https://img.shields.io/github/forks/ton-blockchain/mytonctrl?style=flat-square&logo=github) ![GitHub issues](https://img.shields.io/github/issues/ton-blockchain/mytonctrl?style=flat-square&logo=github) ![GitHub pull requests](https://img.shields.io/github/issues-pr/ton-blockchain/mytonctrl?style=flat-square&logo=github) ![GitHub last commit](https://img.shields.io/github/last-commit/ton-blockchain/mytonctrl?style=flat-square&logo=github) ![GitHub license](https://img.shields.io/github/license/ton-blockchain/mytonctrl?style=flat-square&logo=github)

# MyTonCtrl

MyTonCtrl is a console application that is used for launching and managing TON blockchain nodes.

The extended documentation can be found at https://docs.ton.org/v3/documentation/nodes/mytonctrl/overview and https://docs.ton.org/v3/guidelines/nodes/overview.

## Operating Systems

It is recommended to use Ubuntu 22.04 LTS or Ubuntu 24.04 LTS for using MyTonCtrl. However, the full list of tested OS is below:

| Operating System | Status        |
|------------------|---------------|
| Ubuntu 20.04 LTS | OK            |
| Ubuntu 22.04 LTS | OK            |
| Ubuntu 24.04 LTS | OK            |
| Debian 10        | Deprecated    |
| Debian 11        | OK            |
| Debian 12        | OK            |
| Debian 13        | Not supported |

## Installation
Please note that during the installation and upgrade procedures, MyTonCtrl will need to escalate privileges using the `sudo` or `su` methods in order to upgrade / install system wide components. Depending on your environment, you may be prompted to enter the password for the root or sudo user.


### Modes
MyTonCtrl supports these installation modes:

- `liteserver` - run the node as a liteserver only
- `collator` - run the node as a collator
- `validator` - run a validator node using the validator wallet for staking
- `single-nominator` - run a validator node with single-nominator staking (recommended for validators)
- `nominator-pool` - run a validator node with nominator-pool staking
- `liquid-staking` - run a validator node with liquid-staking enabled

`single-nominator`, `nominator-pool`, and `liquid-staking` all install a validator node and enable `validator` mode automatically.
You can change enabled modes later after installation.

Learn more about node types: https://docs.ton.org/v3/documentation/nodes/overview

### Install

1. Download installation script:
	```shell
	wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/install.sh
	```

2. Run script with desired options:
	```shell
	sudo bash install.sh -m <mode>
	```
	Or for Debian:
	```shell
	su root -c 'bash install.sh -m <mode>'
	```

To install a full archive liteserver, use:
```shell
sudo bash install.sh -m liteserver --archive
```

To view all available installation options use `bash install.sh --help`

### Installation configuration

You can also configure some installation parameters using environment variables. For example:
* `VALIDATOR_CONSOLE_PORT` - port for validator console (default: random port in range 2000-65000)
* `LITESERVER_PORT` - port for liteserver (default: random port in range 2000-65000)
* `VALIDATOR_PORT` - port for validator (default: random port in range 2000-64000)

You can provide `env` file with allowed variables to installation script:
```shell
sudo bash install.sh -m <mode> --env-file /path/to/env/
```

### Interactive CLI installer

To install MyTonCtrl using convenient interactive CLI installer, run the installation script without providing mode to it:

```shell
sudo bash install.sh [args]
```
You will be prompted to choose the installation mode and other options.

To run the interactive installer in `dry-run` mode, which will show you all the options you have selected and command 
that will be executed during installation without actually installing MyTonCtrl, use flag `--print-env`:

```shell
sudo bash install.sh --print-env
```

After installation, you can run MyTonCtrl console using the command:
```shell
mytonctrl
```

## Telemetry
By default, MyTonCtrl sends validator statistics to the https://toncenter.com server.
It is necessary to identify network abnormalities, as well as to quickly give feedback to developers.
To disable telemetry during installation, use the `-t` flag:
```sh
sudo bash install.sh -m <mode> -t
```

To disable telemetry after installation, do the following:
```sh
MyTonCtrl> set sendTelemetry false
```
