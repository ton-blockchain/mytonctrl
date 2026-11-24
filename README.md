![GitHub stars](https://img.shields.io/github/stars/ton-blockchain/mytonctrl?style=flat-square&logo=github) ![GitHub forks](https://img.shields.io/github/forks/ton-blockchain/mytonctrl?style=flat-square&logo=github) ![GitHub issues](https://img.shields.io/github/issues/ton-blockchain/mytonctrl?style=flat-square&logo=github) ![GitHub pull requests](https://img.shields.io/github/issues-pr/ton-blockchain/mytonctrl?style=flat-square&logo=github) ![GitHub last commit](https://img.shields.io/github/last-commit/ton-blockchain/mytonctrl?style=flat-square&logo=github) ![GitHub license](https://img.shields.io/github/license/ton-blockchain/mytonctrl?style=flat-square&logo=github)

# MyTonCtrl

MyTonCtrl is a console application that is used for launching and managing TON blockchain nodes.

The extended documentation can be found at https://docs.ton.org/v3/documentation/nodes/mytonctrl/overview and https://docs.ton.org/v3/guidelines/nodes/overview.

## Host installation

Native installations use the host installer and systemd services. Docker-specific
initialization checkpoints, dump recovery and validator readiness polling apply
only inside the MyTonCtrl image. Native installations keep their existing
installation, console, backup and upgrade workflows.

### Operating systems

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

### Modes

MyTonCtrl supports these installation modes:

- `liteserver` - run the node as a liteserver only
- `collator` - run the node as a collator
- `validator` - run a validator node using the validator wallet for staking
- `single-nominator` - run a validator node with single-nominator staking (recommended for validators)
- `nominator-pool-v2` - run a validator node with nominator-pool v2 staking
- `nominator-pool` - run a validator node with nominator-pool v1 staking (**deprecated**, use `nominator-pool-v2`)
- `liquid-staking` - run a validator node with liquid-staking enabled

`single-nominator`, `nominator-pool-v2`, `nominator-pool`, and `liquid-staking` all install a validator node and enable `validator` mode automatically.
You can change enabled modes later after installation.

Learn more about node types: https://docs.ton.org/v3/documentation/nodes/overview

### Install

Host installation uses `scripts/install.sh`, downloaded below as `install.sh`.
Installation and upgrades use `sudo` or `su` to install system components. You
may be prompted for the root or sudo user's password.

1. Download the installation script:
	```shell
	wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/install.sh
	```

2. Run a script with desired options:
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

### Installation options

Pass these options directly to `sudo bash install.sh`. For example:

```sh
sudo bash install.sh -m validator -n mainnet -d
```

| Installation option | Description |
| --- | --- |
| `-m`, `--mode MODE` | Select a mode listed above. Omitting both mode and backup opens the interactive installer. |
| `-n`, `--network NETWORK` | Select `mainnet` (default) or `testnet`. For a custom network, supply its configuration with `-c URL`. |
| `-c`, `--config URL` | Use a custom global network configuration URL when installing TON. |
| `-u`, `--user USER` | Select the MyTonCtrl account; defaults to the invoking account. The TON node runs as `validator`. |
| `-t`, `--telemetry` | Disable telemetry. |
| `-i`, `--ignore-reqs` | Skip the minimum CPU and RAM check. |
| `-d`, `--dump` | Download a prepared dump to reduce initial synchronization time. |
| `--archive` | Install a full archive liteserver; requires `-m liteserver`. |
| `-o`, `--only-mtc` | Configure MyTonCtrl for an existing node using a backup; requires `-p`. |
| `-l`, `--only-node` | Configure node operation with a separate controller and export a backup. |
| `-p`, `--backup PATH` | Restore an installation from a backup. |
| `-B`, `--bin-dir PATH` | Select the binary directory (default `/usr/bin` on Linux). |
| `-S`, `--src-dir PATH` | Select the source directory (default `/usr/src` on Linux). |
| `-W`, `--ton-work-dir PATH` | Select the node's work directory (default `/var/ton-work`). |
| `-e`, `--env-file PATH` | Load installation environment variables from a shell environment file. |
| `-a`, `--author AUTHOR` | Select the MyTonCtrl GitHub owner. |
| `-r`, `--repo REPO` | Select the MyTonCtrl repository. |
| `-b`, `--branch BRANCH` | Select the MyTonCtrl branch. |
| `-g`, `--node-repo REPO` | Select the TON repository. |
| `-v`, `--node-version VERSION` | Select the TON commit, branch or tag to build. |
| `--print-env` | Print the interactive installer's chosen settings and command; use without `-m` or `-p`. |
| `-h`, `--help` | Print installation help. |

### Installation configuration

You can also configure some installation parameters using environment variables. For example:

* `VALIDATOR_CONSOLE_PORT` - port for validator console (default: random port in range 2000-65000)
* `LITESERVER_PORT` - port for liteserver (default: random port in range 2000-65000)
* `VALIDATOR_PORT` - port for validator (default: random port in range 2000-64000)

You can provide `env` file with allowed variables to an installation script:
```shell
sudo bash install.sh -m <mode> --env-file /path/to/installer.env
```

### Interactive CLI installer

To use the interactive CLI installer, run the installation script without a
mode (`-m`) or backup (`-p`):

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

### Console arguments

Pass console arguments directly to `mytonctrl`:

| Console argument | Description |
| --- | --- |
| `-c`, `--config PATH` | Read a different controller database (`mytoncore.db`). |
| `-w`, `--wallets DIR` | Use a different wallets directory. |
| `-s`, `--no-startup-checks` | Skip console startup checks. |
| `--cmd COMMAND` | Run a console command and exit; also skips startup checks. |
| `-h`, `--help` | Print console help. |

```sh
mytonctrl --cmd "get modes"
```

Installer `-c` selects the network configuration; console `-c` selects the
controller database. Installer `-i` skips hardware checks; console `-s` skips
startup checks.

### Telemetry

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

## Docker image

See the [Docker image guide](README.docker.md) for setup with or without
Docker Compose, configuration, benchmarks, image upgrades, recovery,
troubleshooting and cleanup.
