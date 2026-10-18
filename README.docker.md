# Docker image

MyTonCtrl and TON use separate images. The official TON image supplies binaries
and Fift resources to a shared volume, with its `init.sh` entrypoint bypassed.
The MyTonCtrl image initializes and runs the node using those mounted artifacts.
It requires the artifacts to be mounted before startup. Node state, keys,
wallets, downloaded dumps and controller settings persist in a standard Docker
volume or an optional host data directory, mounted at `/var/ton-work` inside the container.

Use the Compose quick setup below, or follow
[the examples without Docker Compose](#use-docker-without-compose).
For an existing `ton-docker-ctrl` installation, follow
[the migration wizard](#migrate-from-ton-docker-ctrl) before starting this image.

## Quick setup

Install Docker and Compose on Linux, plus `skopeo` and `jq` on the host for
image tag lookups (on Debian/Ubuntu: `sudo apt-get install skopeo jq`).
Prepare an empty deployment directory:

```sh
mkdir mytonctrl-docker
cd mytonctrl-docker
wget -O install.sh https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/docker/install.sh
bash install.sh
```

Alternatively, run the installer directly from an empty deployment directory:

```sh
wget -qO- https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/docker/install.sh | bash
```

By default, the installer downloads only `.env` and `compose.yml` into the
current directory. For a full archive liteserver, use
[`--archive`](#set-up-an-archive-node) instead. It refuses existing environment
or Compose files.
It prepares the setup without installing Docker or starting containers.

Retrieve the newest stable version tags published in GHCR. Each command prints
one full image reference to copy into `.env` as `TON_IMAGE` or `MYTONCTRL_IMAGE`:

```sh
skopeo list-tags docker://ghcr.io/ton-blockchain/ton |
  jq -er --arg arch "$(uname -m | sed 's/^x86_64$/amd64/; s/^aarch64$/arm64/')" '
    .Tags | map(select(test("^v[0-9]+(\\.[0-9]+)+(-[0-9]+)?(-" + $arch + ")?$")))
    | sort_by([sub("-(amd64|arm64)$"; "") | ltrimstr("v") | splits("[.-]") | tonumber])
    | last // error("No stable TON image tag found")
    | "ghcr.io/ton-blockchain/ton:\(.)"'

skopeo list-tags docker://ghcr.io/ton-blockchain/mytonctrl |
  jq -er '
    .Tags | map(select(test("^v[0-9]+\\.[0-9]+\\.[0-9]+$")))
    | sort_by(ltrimstr("v") | split(".") | map(tonumber))
    | last // error("No stable MyTonCtrl image tag found")
    | "ghcr.io/ton-blockchain/mytonctrl:\(.)"'
```

The TON lookup includes tags for the host architecture (`amd64` or `arm64`)
and tags without an architecture suffix. For example, the output may be
`ghcr.io/ton-blockchain/ton:v2026.08-amd64` and
`ghcr.io/ton-blockchain/mytonctrl:v1.0.2`; the actual versions change as images are
published. These commands query published image tags, independently of GitHub
releases, and select the highest version rather than the most recently built tag.
See the [TON package](https://github.com/ton-blockchain/ton/pkgs/container/ton)
and [MyTonCtrl package](https://github.com/ton-blockchain/mytonctrl/pkgs/container/mytonctrl).

**Avoid using the `latest` tag for either image.** It can move to another build
without an explicit version change in your configuration. Pin a version tag or
digest in `.env`, choose the [data storage](#store-ton-data-on-a-separate-disk),
then [start the containers and open the console](#start-and-open-the-console).

The default `--branch master` selects master assets and
`ghcr.io/ton-blockchain/mytonctrl:latest`; replace that default in `.env` before
starting. For dev assets and the `dev` image, use:

```sh
wget -qO- https://raw.githubusercontent.com/ton-blockchain/mytonctrl/dev/docker/install.sh | bash -s -- --branch dev
```

Use `--image IMAGE` and `--ton-image IMAGE` to select published controller and
TON images, and `--help` to view setup options. The download commands require
these installer files on the selected branch; startup requires its image tag
to have been published by GitHub Actions.

The commands below use the downloaded `compose.yml`. Keep the same `.env`
volume names, optional host data directory and Compose project name throughout
the setup's lifetime. Compose uses host networking for Linux nodes. See
[Docker setup](docker/README.md) for
standalone Docker commands, existing TON mounts and runtime details.

## Store TON data on a separate disk

Both Compose files use the original Docker-managed named volume when
`TON_WORK_HOST_DIR` is empty or unset. Existing installations keep using the
same volume, including custom names selected by `TON_WORK_VOLUME`:

```dotenv
TON_WORK_VOLUME=mytonctrl-ton-work
TON_WORK_HOST_DIR=
```

To place the node database, keys, wallets, controller state, logs and dump cache
on a separate disk, set `TON_WORK_HOST_DIR` to an absolute directory on the Docker
host. For example, after mounting your data disk at `/mnt/ton`:

```sh
findmnt --mountpoint /mnt/ton &&
  sudo mkdir -p /mnt/ton/ton-work
df -h /mnt/ton/ton-work
```

Set this in `.env`:

```dotenv
TON_WORK_HOST_DIR=/mnt/ton/ton-work
```

Compose bind-mounts that directory at `/var/ton-work`; keep `-W` and
`DUMP_CACHE_DIR` as container paths. With a nonempty host path, `TON_WORK_VOLUME`
is unused and the small script and binary artifact volumes remain Docker-managed.
Compose's short mount syntax creates a missing host directory automatically,
so prepare it explicitly and verify the storage device before starting. See Docker's
[bind mount options](https://docs.docker.com/reference/compose-file/services/#volumes).

Mount the disk before starting the container, including after a host reboot.
Check that `df` shows the intended data filesystem. Directory existence does
not establish that the intended disk is mounted. Use a dedicated child directory
on that disk and keep the same path during image upgrades and recovery.

### Move an existing named-volume installation

Changing the mount does not move existing data. With the old Compose setup,
stop the controller first; this also stops its validator and background service:

```sh
docker compose stop mytonctrl
```

Prepare an empty directory on the mounted data disk as above. Copy the old
volume while the node is stopped, using its actual volume name and an already
available controller image:

```sh
OLD_TON_WORK_VOLUME=mytonctrl-ton-work
TON_WORK_HOST_DIR=/mnt/ton/ton-work
MYTONCTRL_IMAGE=ghcr.io/ton-blockchain/mytonctrl:v1.0.2

docker volume inspect "$OLD_TON_WORK_VOLUME" >/dev/null &&
  docker run --rm --pull never --network none --user 0 --entrypoint /bin/sh \
    --mount "type=volume,src=$OLD_TON_WORK_VOLUME,dst=/old,readonly" \
    --mount "type=bind,src=$TON_WORK_HOST_DIR,dst=/new" \
    "$MYTONCTRL_IMAGE" -eu -c 'test -z "$(ls -A /new)"; cp -a /old/. /new/'
```

This copies the database, keys, configuration and cached dumps with ownership
and permissions preserved. The destination must be empty. Install the updated
Compose file, set `TON_WORK_HOST_DIR` in `.env` to the destination, and
keep the other image, port and installer settings. Then start the setup:

```sh
docker compose up -d --no-build --pull never
docker compose exec mytonctrl mytonctrl --cmd status
```

Keep the old volume until you have verified the copied installation and backup.
Do not run the old and new controllers against the same data concurrently.

## Migrate from ton-docker-ctrl

Use the interactive wizard to migrate an existing
[`ton-blockchain/ton-docker-ctrl`](https://github.com/ton-blockchain/ton-docker-ctrl)
installation on the **same Linux host**. Install Python 3.8 or newer and Docker
Compose, then run this from a terminal on that host:

```sh
wget -O migrate.sh https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/docker/migrate.sh
sudo bash migrate.sh
```

The migration requires root privileges to preserve the donor's file ownership,
read private keys and inspect Docker storage for disk-space checks. Membership
in the `docker` group alone is insufficient. If already in a root shell, run
`bash migrate.sh` without `sudo`.

For the dev version, download from `dev` and run `sudo bash migrate.sh --branch dev`.
Use `bash migrate.sh --help` for options. Download the script before running it;
the wizard needs an interactive terminal for its questions and confirmations.

Before proceeding, take an independent backup or storage snapshot. The selected
destination needs enough free space for a **complete additional copy** of the old
node; archive databases can require many terabytes. It must be separate from all
of the old installation's data directories. Keep the old container, image,
volumes and deployment files until migration is verified.

The wizard checks the migration metadata directory, the selected TON work
storage and Docker storage separately. Its budget includes the full data copy,
legacy controller copy, identity staging, backup archive, controller import,
temporary backup extraction, exported TON binaries and their running snapshot.
It copies node data directly into the selected storage, without another staging
copy of the database. If storage locations share a filesystem, it adds their
requirements together. Estimates
assume no compression or sparse-file savings and retain at least 10% or 1 GiB
of extra space per storage area for metadata, logs and initial growth.
Images are pulled while the old node is running; the wizard checks the remaining
space again after pulling and immediately before downtime. It also rechecks
after stopping the node, before backup creation and before startup. Insufficient
space stops migration and preserves the original data. Keep monitoring free
space as the migrated node syncs and its database grows.

### What the wizard does

The wizard identifies the old container and asks you to review its network,
node mode, advertised IP, ports, retention settings and replacement images. It
asks for the node storage type first, then requests confirmation before stopping
the old node and before starting the replacement:

- **Host directory (default):** asks for the migration directory, suggesting
  `<current-directory>/migration`, then asks for the TON work directory,
  suggesting `<migration-directory>/ton-work`. The wizard sets
  `TON_WORK_HOST_DIR` to that directory. Choose a path on your mounted data disk
  to keep node data off the root filesystem.
- **Docker volume:** asks for a new volume name, suggesting `mytonctrl-ton-work`.
  The wizard leaves `TON_WORK_HOST_DIR` empty and sets `TON_WORK_VOLUME` to the
  selected name. It uses `<current-directory>/migration` for deployment files,
  backups and rollback instructions automatically, without asking for a
  migration directory. This uses Docker's volume storage for node data, so check
  which disk backs it.

Compose files are stored in `<migration-directory>/deployment`. If the automatic
migration directory already contains a previous migration, run the wizard from
another directory. If the suggested volume already exists, enter a new name.

The wizard rejects nonempty destinations, reused volumes and paths overlapping
the original data. The migration journal and final output record the selected
storage. The Compose project and controller container are both named `mytonctrl`.
The wizard stops if that container name or project already exists, preserving
the existing deployment. Artifact volumes still have independent names.

It downloads `.env.example` and generates `<migration-directory>/deployment/.env`.
If the destination already contains only `deployment/.env`, the wizard asks before
replacing it and saves the original as `.env.before-migration`. Declining cancels
migration before stopping the old node. Your current directory's `.env` is untouched.

It then:

1. Disables the old container's
   [automatic restart](https://docs.docker.com/engine/containers/start-containers-automatically/),
   then stops its controller and validator before taking the copy.
2. Copies the entire TON work directory directly to the chosen host directory or
   Docker volume, and saves controller state, wallets, private keys, console
   settings and network configuration for import.
3. Downloads this repository's `.env.example` and Compose file, configures the
   new deployment, and imports the saved identities and controller settings.
4. Checks the backup, configuration and copied key files, then starts the new
   node after confirmation and prints status, console and rollback commands.

To open the migrated console, use the printed Compose command ending in
`exec mytonctrl mytonctrl`, which includes both configuration files. You can
also use the fixed container name directly:

```sh
sudo docker exec -it mytonctrl mytonctrl
```

The migration retains the blockchain database, archive history and cached
downloads; it does **not** request another dump download. The original data
stays intact and the old container remains stopped. Sources and build tools from
the old image are replaced by prebuilt binaries and Fift resources from the
separately selected `TON_IMAGE`.

### Network and node mode

Network selection is independent of node mode. Review the detected values;
migration preserves the existing installation rather than converting its role
or switching networks.

| Existing installation | Migration behavior |
| --- | --- |
| Mainnet | Keeps the saved mainnet configuration and uses `-n mainnet`. |
| Testnet | Keeps the saved testnet configuration and uses `-n testnet`. Select a compatible TON image; the old `TON_BRANCH=testnet` is not an image tag and does not carry over. |
| Validator | Keeps its validator wallet, ADNL identity, election/staking settings and node keys. Never run both installations with these keys at the same time. |
| Liteserver | Keeps its liteserver key, TCP port and retention settings so existing clients can continue using it. |
| Collator | Keeps existing collator ADNL keys, registrations, validator whitelist, collation options and delegated collators. Restores the saved mode without creating another collator. |
| Single-nominator | Keeps validator and single-nominator mode flags, wallets, pool files and staking settings. |
| Nominator-pool v2 | Keeps the v2 pool files, addresses and staking settings. |
| Nominator-pool v1 (deprecated) | Keeps the existing v1 pool and mode; migration does not convert it to v2. |
| Liquid-staking | Keeps controller lists, liquid pool address, wallets and loan settings. |
| Archive node, on either network | Keeps saved node and staking modes, complete history, permanent storage and retention settings before the first start. It does not bootstrap a new archive. |

Saved mode flags take precedence over stale installation environment settings.
An explicitly disabled validator remains disabled, including paused staking nodes.
For collators, the generated `-m none -p ...` restores the backup without fresh
collator setup; the restored controller still runs in its saved collator mode.
Ambiguous legacy mode schemas and conflicting validator/liteserver/collator flags
must be resolved using the old controller first. A separate `collator.service`
is an additional service and requires its own migration; the supported collator
mode runs inside `validator-engine`.

Use a TON image compatible with the existing database first; upgrade TON
separately after confirming migration. Check available releases in the
[official TON package](https://github.com/ton-blockchain/ton/pkgs/container/ton).
The new setup uses host networking. Allow the retained node UDP/QUIC and
liteserver TCP ports through the host firewall; keep the console port private.
Unusual layouts, multiple local console/liteserver endpoints, auxiliary services
or different-host/IP moves need review before migration; the wizard stops when
it cannot safely handle the detected configuration.
Bounded archive imports using `--sync-shards-upto` also require a separate review.

### Verify or roll back

Use the commands printed by the wizard to inspect `status`, wallet and ADNL
addresses, network, ports and logs. For archive nodes, also verify historical
queries and retained archive files. Successful startup alone does not establish
that all required data and identities have been preserved.

On failure, the wizard stops the replacement and leaves the old node stopped.
For rollback, stop the new deployment and confirm its validator has exited,
then start the original container using its original data and image; follow the
printed rollback script, which also restores the original restart policy.
Never attach the old engine to the new database copy. Transactions broadcast
after migration are not undone by rollback; reconcile validator elections,
stake and wallet state before resuming the old controller.

Do not use `docker compose down -v`, prune volumes or delete the old data during
migration. The wizard never deletes the source installation automatically.
The new migration data volume is marked external in the migration override, so
Compose [does not remove it with `down -v`](https://docs.docker.com/reference/cli/docker/compose/down/);
a host directory also stays intact.
To deliberately remove migrated volume data, stop and remove the replacement
container first, retain an independent backup, then run
`sudo docker volume rm <selected-TON_WORK_VOLUME>`.

## Installation arguments in .env

Use the same [installation options](README.md#installation-options) as the host installer,
provided through `MYTONCTRL_ARGS` in the `.env` created by quick setup.
The default installation arguments install a mainnet validator using a prepared
dump. Replace the template's `latest` image tags with pinned versions, for example:

```dotenv
TON_IMAGE=ghcr.io/ton-blockchain/ton:v2026.08-amd64
MYTONCTRL_IMAGE=ghcr.io/ton-blockchain/mytonctrl:v1.0.2
TON_WORK_HOST_DIR=
MYTONCTRL_ARGS=-m validator -n mainnet -d
PUBLIC_IP=
```

Leave `PUBLIC_IP` blank to autodetect the public IPv4 address, or set the address
the node should advertise. The entrypoint validates it before initialization.
Avoid `latest`; pin version tags or digests in `TON_IMAGE` and `MYTONCTRL_IMAGE`.
Run these commands on the host with `skopeo` and `jq` installed to retrieve the
newest stable published image references, then copy their output into `.env`:

```sh
skopeo list-tags docker://ghcr.io/ton-blockchain/ton |
  jq -er --arg arch "$(uname -m | sed 's/^x86_64$/amd64/; s/^aarch64$/arm64/')" '
    .Tags | map(select(test("^v[0-9]+(\\.[0-9]+)+(-[0-9]+)?(-" + $arch + ")?$")))
    | sort_by([sub("-(amd64|arm64)$"; "") | ltrimstr("v") | splits("[.-]") | tonumber])
    | last // error("No stable TON image tag found")
    | "ghcr.io/ton-blockchain/ton:\(.)"'

skopeo list-tags docker://ghcr.io/ton-blockchain/mytonctrl |
  jq -er '
    .Tags | map(select(test("^v[0-9]+\\.[0-9]+\\.[0-9]+$")))
    | sort_by(ltrimstr("v") | split(".") | map(tonumber))
    | last // error("No stable MyTonCtrl image tag found")
    | "ghcr.io/ton-blockchain/mytonctrl:\(.)"'
```

These examples use `v2026.08-amd64` for x86-64 hosts; the TON lookup selects
tags for the host architecture. `.env` requires literal image references;
shell commands and `$(...)` substitutions are not executed there.

Installation arguments apply when initializing an empty work volume. Existing
installations keep their configuration; use console commands for later changes.
Keep `-u`, `-B`, `-S` and `-W` fixed when reusing a work volume. The controller user
defaults to `root`; `-u USER` selects the controller service account. The TON node
runs as `validator`.

For example, to install a testnet liteserver with telemetry disabled:

```dotenv
MYTONCTRL_ARGS=-m liteserver -n testnet -t
```

Docker supports these adaptations of the host arguments:

| Option | Docker behavior |
| --- | --- |
| `-c`, `--config` | Accepts a URL or an absolute path to a mounted network configuration file. For a custom network, use `-n custom -c URL` or `-n custom -c /mounted/global.config.json`. |
| `-e`, `--env-file` | Reads a mounted file of `KEY=value` data. Compose already loads `.env`; standalone Docker uses `--env-file .env`. |
| `-a`/`-r`/`-b`, `--author`/`--repo`/`--branch` | Select the checkout when building the controller image, then select `MYTONCTRL_IMAGE`. These source-selection arguments are unavailable at runtime. |
| `-g`/`-v`, `--node-repo`/`--node-version` | Select `TON_IMAGE` to choose prebuilt TON binaries. These source-selection arguments are unavailable at runtime. |
| `--print-env`, `--help` | Print parsed installation settings or help and exit. |
| `-s`, `--no-startup-checks` | Docker extension: add to `MYTONCTRL_ARGS` to skip console startup checks. Installation flags are kept separate from console arguments. |

Mount files referenced by `-c`, `-p` or `-e` into the controller using Compose
volumes or Docker's `--mount` option. `--archive` also requires a mounted
prebuilt `tonutils-storage` executable, which `install.sh --archive` prepares
automatically; follow [archive node setup](#set-up-an-archive-node).

## Set up an archive node

With Docker, Compose and `jq` installed on a Linux `amd64` or `arm64` host, run the
[installer](docker/install.sh) with `--archive` in a new deployment directory. Choose
pinned image references using the [lookup commands](#quick-setup); the following
TON image example is for `amd64`:

```sh
mkdir mytonctrl-archive
cd mytonctrl-archive
wget -O install.sh https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/docker/install.sh
bash install.sh --archive \
  --ton-image ghcr.io/ton-blockchain/ton:v2026.08-amd64 \
  --image ghcr.io/ton-blockchain/mytonctrl:v1.0.2
```

The installer prepares `.env` and `compose.yml`, installs
[the archive Compose configuration](docker/compose.archive.yml) as
`compose.override.yml`, and queries GitHub for the latest `tonutils-storage`
release tag before downloading its executable for the host architecture. It sets
`MYTONCTRL_ARGS=-m liteserver -n mainnet --archive` and `DUMP=false` automatically.
Compose loads the override and exports the tool with the TON binaries.
Keep all four generated files in the deployment directory for future starts
and image upgrades.

Use empty node storage with room for the full history, download/import working
space and continued growth; this can require many terabytes. The default uses
a Docker volume. For a dedicated disk, set `TON_WORK_HOST_DIR` in `.env` as
described in [storage setup](#store-ton-data-on-a-separate-disk). For testnet,
change `-n mainnet` to `-n testnet` in `MYTONCTRL_ARGS` and select a compatible
pinned TON image. Then start the archive installation:

```sh
docker compose pull
docker compose up -d --no-build --pull never
docker compose logs -f mytonctrl
```

The archive mode downloads history from block 1, enables `--permanent-celldb`,
and sets archive and state retention to `1000000000` seconds. Leave `ADD_SHARD`
unset to synchronize all shards. Initial download, import and synchronization
can take a long time. In another terminal, check progress and validator settings:

```sh
docker compose exec mytonctrl mytonctrl --cmd status
docker compose exec mytonctrl mytonctrl --cmd 'installer status'
```

`installer status` should show the permanent cell database flag and retention
values described above. After synchronization, query an early masterchain block
through the local liteserver to check historical access:

```sh
docker compose exec mytonctrl bash -ic \
  '_mytonctrl_lite_client -c "byseqno -1 8000000000000000 1"'
```

Verify current block progress as well. These installation settings apply to empty
storage; changing `.env` does not rebuild missing history in an existing node.
To retain an existing archive installation, use
[migration](#migrate-from-ton-docker-ctrl).

## Start and open the console

After editing `.env`, pull the selected images and start the setup from
the deployment directory:

```sh
docker compose pull
docker compose up -d --no-build --pull never
docker compose logs -f mytonctrl
```

The one-shot `ton-exporter` service uses the same controller image to copy its
packaged exporter script into a shared script volume. `ton-binaries` then runs
that script in the official TON image and exits after exporting artifacts.
These three services use two images. The `mytonctrl` service keeps the node and
controller running. Allow the configured validator and QUIC UDP ports and
liteserver TCP port through the host firewall; keep the validator console port
private.

Open the console or run a command using the same [console arguments](README.md#console-arguments)
as the host utility:

```sh
docker compose exec mytonctrl mytonctrl
docker compose exec mytonctrl mytonctrl --cmd "get modes"
```

In Docker mode, status displays image references instead of Git commits:

```text
Version mytonctrl: ghcr.io/ton-blockchain/mytonctrl:v1.0.2
Version validator: ghcr.io/ton-blockchain/ton:v2026.08-amd64
```

The controller reference is embedded when building the image. The TON reference
comes from the exported release copied into the running container; exporting
a newer release leaves this display unchanged until the controller restarts.
Mounted binaries without exported image metadata display an unknown image.

Console defaults can also be set in `.env` using `MYTONCTRL_CONFIG`,
`MYTONCTRL_WALLETS` and `MYTONCTRL_CMD`. Use `-s` in `MYTONCTRL_ARGS` for the startup
check default. Explicit console arguments take precedence for options with values.

The publishing workflows use `dev` for commits to `dev`, `latest` for commits to
`master`, and a required tag input for manual builds.

### Bash aliases

Open an interactive Bash shell to use the image's local node shortcuts:

```sh
docker compose exec mytonctrl bash
# Without Compose: docker exec -it mytonctrl bash
getstats
last
config34
sync
```

These are Bash commands; enter them outside the `MyTonCtrl>` prompt.

| Alias | Query |
| --- | --- |
| `config32`, `config34`, `config36` | Local network configuration parameters 32, 34 and 36. |
| `elid` | Elector's active election ID. |
| `participants` | Elector's participant list. |
| `getstats` | Local validator console statistics. |
| `last` | Latest masterchain block known to the local liteserver. |
| `sync` | Age of that block in seconds. |
| `egrep` | `grep -E` with automatic color. |

The aliases use the container's active TON binaries and keys. They read the
console and liteserver ports from `db/config.json` with `jq` on every invocation,
so they follow ports configured in `.env` or retained during migration. Custom
`-W` work directories are supported. They require the corresponding node
endpoints to have been initialized; local results can lag while syncing.
`last` and `sync` override the usual Linux commands in Bash; use `command last`
or `command sync` to call those tools. Aliases arrive with the updated controller
image and require no `.env` or migration script changes.

## Run a benchmark

The controller image includes `uv`, Python 3.14 and TON's Python benchmark
framework with its generated bindings. The benchmark uses the binaries and
Fift resources supplied by the separate TON image; it does not download a
repository, install dependencies or compile TON when invoked.

View the benchmark options without stopping the node:

```sh
docker compose exec mytonctrl mytonctrl --cmd "benchmark -- --help"
```

The benchmark starts a temporary local TON network and measures its workload.
After node initialization completes, stop the live controller and validator
services before running it. Run these commands in your host shell, outside the
`MyTonCtrl>` prompt (type `exit` to leave the console):

```sh
docker compose exec mytonctrl sudo systemctl stop mytoncore
docker compose exec mytonctrl sudo systemctl stop validator
docker compose exec mytonctrl mytonctrl --cmd "benchmark --nodes 2 --duration 60"
```

Stopping these services keeps the container running. Pass workload options
such as `--tps`, `--shards`, `--spammers` or `--sync-test` to `benchmark`. Use
`--tmp-dir /mounted/path` to select benchmark storage; its default parent is
`/var/ton-work/tmp`. Each run uses a separate temporary directory and removes
its test network afterward. The container manages `--build-dir`, `--source-dir`
and `--work-dir` to keep benchmark cleanup separate from the live node's data.
Its database, keys, wallet and dump cache are retained.

Restart the live services after the benchmark, including if it failed or was
interrupted:

```sh
docker compose exec mytonctrl sudo systemctl start validator
docker compose exec mytonctrl sudo systemctl start mytoncore
```

## Build from a local checkout (optional)

For development, use the repository root's `compose.yaml`, which supports
building the local checkout. The quick setup's `compose.yml` uses published
images only. On the first setup in a checkout, create its `.env`:

```sh
cp .env.example .env
```

Leave `TON_WORK_HOST_DIR` blank for the named volume, or select a host directory
as described in [storage setup](#store-ton-data-on-a-separate-disk). Keep
`MYTONCTRL_IMAGE=mytonctrl:local` or choose another local image tag, then run
these commands from that checkout's root:

```sh
docker compose -f compose.yaml pull ton-binaries
docker compose -f compose.yaml build mytonctrl
docker compose -f compose.yaml up -d --no-build --pull never
```

Compose embeds `MYTONCTRL_IMAGE` as the controller image reference. For a direct
`docker build`, pass `--build-arg MYTONCTRL_IMAGE_REF=mytonctrl:local` alongside
`-t mytonctrl:local`, replacing both values with your chosen image name and tag.

## Stop and resume

Stop the node and controller while keeping their containers and data:

```sh
docker compose stop mytonctrl
```

Resume the stopped container:

```sh
docker compose restart --no-deps mytonctrl
```

To remove the service containers while keeping the persistent volumes, use:

```sh
docker compose down
```

Start them again with `docker compose up -d --no-build --pull never`.

## Upgrade the TON image

Retrieve the newest stable TON image reference for the host architecture using
`skopeo` and `jq` on the host:

```sh
skopeo list-tags docker://ghcr.io/ton-blockchain/ton |
  jq -er --arg arch "$(uname -m | sed 's/^x86_64$/amd64/; s/^aarch64$/arm64/')" '
    .Tags | map(select(test("^v[0-9]+(\\.[0-9]+)+(-[0-9]+)?(-" + $arch + ")?$")))
    | sort_by([sub("-(amd64|arm64)$"; "") | ltrimstr("v") | splits("[.-]") | tonumber])
    | last // error("No stable TON image tag found")
    | "ghcr.io/ton-blockchain/ton:\(.)"'
```

Review compatibility with your network and database, then copy the full output
into `TON_IMAGE` in `.env`, or pin a specific compatible version or digest.
Avoid `latest`. Pull the selected image and export its binaries:

```sh
docker compose pull ton-binaries
docker compose run --rm ton-binaries
```

The running controller keeps using its private copy of the previous TON binaries
and resources. Adopt the newly exported TON release when ready:

```sh
docker compose restart --no-deps mytonctrl
```

Every controller start, restart or recreation selects the currently exported
TON release. Updating `TON_IMAGE` in `.env` alone does not export new binaries.

## Upgrade the MyTonCtrl image

For a published image, retrieve the newest stable MyTonCtrl image reference using
`skopeo` and `jq` on the host:

```sh
skopeo list-tags docker://ghcr.io/ton-blockchain/mytonctrl |
  jq -er '
    .Tags | map(select(test("^v[0-9]+\\.[0-9]+\\.[0-9]+$")))
    | sort_by(ltrimstr("v") | split(".") | map(tonumber))
    | last // error("No stable MyTonCtrl image tag found")
    | "ghcr.io/ton-blockchain/mytonctrl:\(.)"'
```

Copy the full output into `MYTONCTRL_IMAGE` in `.env`, or pin another version
or digest. Avoid `latest`. Pull the image and recreate the controller:

```sh
docker compose pull mytonctrl
docker compose run --rm --no-deps ton-exporter
docker compose up -d --no-deps --no-build --pull never mytonctrl
```

For a [local development setup](#build-from-a-local-checkout-optional), update
the checkout and keep its local `MYTONCTRL_IMAGE` tag in `.env`. From that same
checkout's root, build and recreate using its `compose.yaml`:

```sh
docker compose -f compose.yaml build mytonctrl
docker compose -f compose.yaml run --rm --no-deps ton-exporter
docker compose -f compose.yaml up -d --no-deps --no-build --pull never mytonctrl
```

Both methods refresh the packaged exporter script, preserve the work volume and
reuse node keys, wallets, settings and an unfinished dump download. An upgrade
during initialization resumes the original installation using its saved settings;
it does not select a newer dump or discard the existing archive.
Recreation also adopts the currently exported TON release. Use these image
updates for container deployments; the console's `update` and `upgrade` commands
are disabled and display instructions to update the corresponding Docker image.
A container restart alone does not replace its controller image or reload `.env`
changes.

## Use Docker without Compose

These examples use Docker directly on Linux, with the same two images and
persistent volumes as the Compose setup. Run them from your deployment
directory. Keep the image and volume variables available in your shell; in a
new terminal, set them again to the values used for this installation.

### Set up and open the console

Prepare an empty directory and download the environment template:

```sh
mkdir mytonctrl-docker &&
  cd mytonctrl-docker &&
  wget -O .env https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/.env.example
```

Edit `.env` with the same [installation arguments](#installation-arguments-in-env)
and `PUBLIC_IP` settings described above. For a published controller, set
`MYTONCTRL_IMAGE` to a pinned version from the lookup commands above in that
file. Then set the following shell variables to match your chosen image
references and volume names in `.env`:

```sh
TON_IMAGE=ghcr.io/ton-blockchain/ton:v2026.08-amd64
MYTONCTRL_IMAGE=ghcr.io/ton-blockchain/mytonctrl:v1.0.2
TON_SCRIPTS_VOLUME=mytonctrl-ton-scripts
TON_ARTIFACTS_VOLUME=mytonctrl-ton-artifacts
TON_WORK_VOLUME=mytonctrl-ton-work
TON_WORK_HOST_DIR=

docker pull "$MYTONCTRL_IMAGE"
docker pull "$TON_IMAGE"
docker volume create "$TON_SCRIPTS_VOLUME"
docker volume create "$TON_ARTIFACTS_VOLUME"
if [ -n "$TON_WORK_HOST_DIR" ]; then
  TON_WORK_MOUNT="type=bind,src=$TON_WORK_HOST_DIR,dst=/var/ton-work"
else
  docker volume create "$TON_WORK_VOLUME"
  TON_WORK_MOUNT="type=volume,src=$TON_WORK_VOLUME,dst=/var/ton-work"
fi
```

The default uses a named volume. For a host directory, set `TON_WORK_HOST_DIR`
in both your shell and `.env`, prepare it on your mounted disk as described in
[storage setup](#store-ton-data-on-a-separate-disk), then run the mount-selection
block above. Keep `TON_WORK_MOUNT` available for startup and image upgrades.

Docker's [`--env-file`](https://docs.docker.com/reference/cli/docker/container/run/#env)
passes settings to the container; it does not choose the image, volume names or
host path in these shell commands. Keep `MYTONCTRL_ARGS` unquoted as in `.env.example`,
and use literal values rather than `${VARIABLE}` substitutions in `.env`.

Copy the exporter bundled in the controller image into the script volume:

```sh
docker run --rm --pull never --network none --entrypoint /bin/sh \
  --mount "type=volume,src=$TON_SCRIPTS_VOLUME,dst=/scripts" \
  "$MYTONCTRL_IMAGE" -eu -c '
    staged_script=$(mktemp /scripts/.export-ton.sh.XXXXXX)
    trap "rm -f \"$staged_script\"" EXIT
    cp /usr/local/lib/mytonctrl/export-ton.sh "$staged_script"
    chmod 444 "$staged_script"
    mv -f "$staged_script" /scripts/export-ton.sh
  '
```

Export TON's binaries and Fift resources using the official image with its
`init.sh` entrypoint replaced. This helper exits after publishing the artifacts:

```sh
docker run --rm --pull never --network none --entrypoint /bin/sh \
  --env "TON_IMAGE_REF=$TON_IMAGE" \
  --mount "type=volume,src=$TON_ARTIFACTS_VOLUME,dst=/ton-artifacts" \
  --mount "type=volume,src=$TON_SCRIPTS_VOLUME,dst=/scripts,readonly" \
  "$TON_IMAGE" /scripts/export-ton.sh
```

Start the controller with the artifact volume read-only and your selected data
storage mounted read-write. These examples use the default container work
path `/var/ton-work`; if you select a different path with `-W`, change the work
mount destination to that container path.

```sh
docker run -d --name mytonctrl --pull never --network host \
  --restart unless-stopped --stop-timeout 75 --env-file .env \
  --mount "type=volume,src=$TON_ARTIFACTS_VOLUME,dst=/ton-artifacts,readonly" \
  --mount "$TON_WORK_MOUNT" \
  "$MYTONCTRL_IMAGE"
docker logs -f mytonctrl
```

Open the console in another terminal, or run a single command:

```sh
docker exec -it mytonctrl mytonctrl
docker exec mytonctrl mytonctrl --cmd status
```

### Stop and resume

Stop the container while retaining its data, then start it again when needed:

```sh
docker stop mytonctrl
docker start mytonctrl
```

Stopping uses the 75-second grace period configured above. Starting or restarting
retains the container's image and environment. Recreate it using the controller
upgrade commands below to load a changed image or `.env` file.

### Upgrade TON independently

Set `TON_IMAGE` to the desired tag or digest in `.env` and in your shell, then
pull and export it. Check the available tags in the
[official TON container package](https://github.com/ton-blockchain/ton/pkgs/container/ton)
and replace the example release below with your selected tag:

```sh
TON_IMAGE=ghcr.io/ton-blockchain/ton:v2026.08-amd64
docker pull "$TON_IMAGE"
docker run --rm --pull never --network none --entrypoint /bin/sh \
  --env "TON_IMAGE_REF=$TON_IMAGE" \
  --mount "type=volume,src=$TON_ARTIFACTS_VOLUME,dst=/ton-artifacts" \
  --mount "type=volume,src=$TON_SCRIPTS_VOLUME,dst=/scripts,readonly" \
  "$TON_IMAGE" /scripts/export-ton.sh
```

The running controller continues using its existing TON binaries. Adopt the
newly exported release when ready:

```sh
docker restart mytonctrl
```

This keeps the work volume, keys, wallets and downloaded dump data.

### Upgrade MyTonCtrl

Set `MYTONCTRL_IMAGE` to the desired tag or digest in `.env` and in your shell.
Pull it and refresh the packaged exporter for future TON exports:

```sh
MYTONCTRL_IMAGE=ghcr.io/ton-blockchain/mytonctrl:v1.0.2
docker pull "$MYTONCTRL_IMAGE"
docker run --rm --pull never --network none --entrypoint /bin/sh \
  --mount "type=volume,src=$TON_SCRIPTS_VOLUME,dst=/scripts" \
  "$MYTONCTRL_IMAGE" -eu -c '
    staged_script=$(mktemp /scripts/.export-ton.sh.XXXXXX)
    trap "rm -f \"$staged_script\"" EXIT
    cp /usr/local/lib/mytonctrl/export-ton.sh "$staged_script"
    chmod 444 "$staged_script"
    mv -f "$staged_script" /scripts/export-ton.sh
  '
docker stop mytonctrl
docker rm mytonctrl
docker run -d --name mytonctrl --pull never --network host \
  --restart unless-stopped --stop-timeout 75 --env-file .env \
  --mount "type=volume,src=$TON_ARTIFACTS_VOLUME,dst=/ton-artifacts,readonly" \
  --mount "$TON_WORK_MOUNT" \
  "$MYTONCTRL_IMAGE"
```

Keep the same volume names, optional host data directory and installation paths.
The recreated container reuses the node database, keys, wallets and settings; interrupted initialization
resumes with its existing dump cache. It also adopts the currently exported
TON release. There is no need to export TON again for a controller-only update.

### Remove the standalone setup

Remove this setup's container and its artifact/script volumes:

**In named-volume mode, these commands also delete node keys, wallets, blockchain
data and dumps. Back them up first.** With a host path, its directory remains intact.

```sh
docker stop mytonctrl
docker rm mytonctrl
docker volume rm "$TON_ARTIFACTS_VOLUME" "$TON_SCRIPTS_VOLUME"
if [ -z "$TON_WORK_HOST_DIR" ]; then
  docker volume rm "$TON_WORK_VOLUME"
fi
```

The helper containers were removed automatically after exporting. For complete
host data removal, follow [data cleanup](#remove-the-docker-setup).
Optionally, remove the downloaded images when other containers no
longer use them and delete the local environment file:

```sh
docker image rm "$MYTONCTRL_IMAGE" "$TON_IMAGE"
rm -f .env
```

## Recover interrupted initialization

Use a controller image containing the recovery fixes, then follow the image
upgrade commands above with the same `TON_WORK_VOLUME` or `TON_WORK_HOST_DIR`
and installation paths.
The container resumes initialization automatically, including installations
left by an older image with an empty `.initializing` marker. Keep the existing
work storage and marker. **In named-volume mode, `docker compose down -v` deletes
the downloaded dump and node data.** With a host directory, that command removes
only the script/artifact volumes and retains node data. Use `docker compose down`
without `-v` to retain all storage in either mode.

The default `DUMP_CACHE_DIR=/var/ton-work/dump-cache` is inside the persistent
work volume. Mount persistent storage there if you choose a cache outside the
work volume. Partial downloads resume the same pinned archive. Complete
archives are verified and reused locally; older caches without metadata look
up the existing archive's dated metadata rather than downloading today's dump.
If that metadata is unavailable, startup reports the problem and preserves the
archive. An interrupted extraction restarts from the cached archive while
preserving node keys and configuration. The archive is removed only after the
whole installation completes, reclaiming its disk space.

Follow progress with `docker compose logs -f mytonctrl`. In another terminal,
inspect initialization, dump, service and local resource status:

```sh
docker compose exec mytonctrl mytonctrl --cmd status
```

Opening `docker compose exec mytonctrl mytonctrl` also shows overall status.
Unavailable node/chain fields display `n/a` while initialization is in progress;
the controller's background tasks start after its client settings are ready.
Error summaries appear on stdout, while full tracebacks remain in the persistent
controller log at `/var/ton-work/controller/mytoncore/mytoncore.log`.

An extracted dump means the downloaded archive has been unpacked into the work
volume. The validator may still need to import archive blocks and catch up with
the network. It must start and accept console commands before installation can finish.
During this stage, console status shows local data and service state without
running validator-dependent startup checks. A service shown as `starting` or
`running (initializing)` has not yet completed initialization.

If the validator keeps restarting, inspect its own log and service exit status:

```sh
docker compose exec mytonctrl tail -n 80 /var/ton-work/log
docker compose exec mytonctrl systemctl show validator --property=SubState,ExecMainStatus
```

Installer failures and their full tracebacks are saved in
`/var/ton-work/controller/mytoninstaller.log`. Keep the data volumes while
diagnosing a failed start; retries reuse the extracted database.

## Diagnose a node that is not catching up

`Initialization status: ready` means installation and client configuration are
complete. Blockchain synchronization continues afterward. Docker status shows
masterchain lag in seconds and shardchain lag in blocks separately; compare
both over time rather than treating the shard block gap as elapsed seconds.

Inspect the engine's own log and process state when it restarts:

```sh
docker compose exec mytonctrl tail -n 160 /var/ton-work/log
docker compose exec mytonctrl systemctl show validator --property=SubState,MainPID,ExecMainStatus
docker compose logs --since 30m --tail 300 mytonctrl
```

TON also writes worker diagnostics to `/var/ton-work/log.threadN.log`. Inspect
those files when the main log contains only a fatal error and backtrace:

```sh
docker compose exec mytonctrl sh -c '
tail -n 80 /var/ton-work/log /var/ton-work/log.thread*.log |
grep -E "==>|FATAL_ERROR|Unexpected Status|STATUS:|import-db-slice|apply-block|celldb"
'
```

Compare the timestamps inside the messages. Persistent log files can contain
crashes from before an image upgrade, and inactive worker files retain older
entries. A running validator process can also be a replacement started by
Supervisor after a crash; check block progress as well as process state.

For raw progress counters, run this twice about a minute apart. It reads the
saved console settings, including the actual configured port:

```sh
docker compose exec mytonctrl /opt/mytonctrl/venv/bin/python -c '
import json
import subprocess
from pathlib import Path

config = json.loads(Path("/var/ton-work/controller/mytoncore/mytoncore.db").read_text())["validatorConsole"]
subprocess.run([
    config["appPath"], "-k", config["privKeyPath"], "-p", config["pubKeyPath"],
    "-a", config["addr"], "-v", "0", "--cmd", "getstats",
], check=True, timeout=15)
'
```

Compare `masterchainblock`, `masterchainblocktime` and
`shardclientmasterchainseqno`; increasing block numbers establish progress.
A changing `start_time` indicates validator restarts. State serialization
counters describe a separate background task.

Check the saved network addresses and current I/O activity:

```sh
docker compose exec mytonctrl jq '{addrs,fullnode,fullnodeslaves}' /var/ton-work/db/config.json
docker compose exec mytonctrl iostat -xz 1 5
docker compose exec mytonctrl vmstat 1 5
```

Verify the advertised IP and ports in this saved configuration, since changing
installation options in `.env` does not rewrite an initialized node. High disk
activity can delay catch-up; inspect I/O latency and queue sizes. Allocated swap
alone does not show active swapping; check `vmstat`'s `si` and `so` columns.

During initial sync, controller queries can use public liteservers. A public
server's latest block or zerostate banner describes that query, rather than
the local node's progress. Failed queries now report their exit code instead
of treating those banners as valid configuration data. Custom overlay messages
also need to be evaluated separately from the validator engine's own failure.

### Archive block application timeouts

An `Error : 652 : timeout` from `import-db-slice.cpp` with an actor named
`!apply(-1,...)` means applying an imported masterchain block failed. In
[TON commit `3d478cb`](https://github.com/ton-blockchain/ton/blob/3d478cbde854be03a18ab2a59f8fc3c565cf7d14/validator/import-db-slice.cpp#L258-L270),
the application request has a 600-second deadline, and a failed result triggers
a fatal assertion. Supervisor then restarts the engine. This deadline covers
block application, including database and state operations; the archive download
has a separate timeout. MyTonCtrl cannot increase this deadline through an
installer argument.

High disk latency or competing database workloads can prevent timely block
application. [TON's troubleshooting guide](https://github.com/ton-blockchain/docs/blob/main/content/nodes/cpp/run-archive-liteserver.mdx#performance-issues)
also identifies storage performance as a cause of archive import timeouts.
Use `iostat` to inspect latency and queues, rather than relying on disk utilization
alone. If another full node such as gton shares the storage, temporarily pause
it using its own service manager and compare TON's block progress and disk
latency. Change one setting at a time so the comparison is meaningful.

For a machine running many validator threads, a lower thread count is another
reversible trial. Record the existing value, then try 32 threads using the
existing installer command:

```sh
docker compose exec mytonctrl mytonctrl --cmd 'installer status'
docker compose exec mytonctrl mytonctrl --cmd 'installer set_node_argument --threads 32'
docker compose exec mytonctrl mytonctrl --cmd 'installer status'
docker compose exec mytonctrl systemctl show validator --property=SubState,MainPID,ExecMainStatus
```

This changes the persistent validator service and restarts the validator with
the same database and keys. Compare raw block counters and I/O readings over
at least 15 minutes, including the former ten-minute crash interval. If it does
not help, restore the recorded thread count with the same command. For example,
use `installer set_node_argument --threads 127` if the previous value was 127.
Changing `CUSTOM_PARAMETERS` in `.env` applies only during first installation;
use the installer command to adjust an existing node.

For a short diagnostic window, enable detailed engine logs, collect the worker
messages, then restore normal verbosity to limit log traffic:

```sh
docker compose exec mytonctrl mytonctrl --cmd 'installer set_node_argument --verbosity 3'
# After collecting the engine's logs and progress counters:
docker compose exec mytonctrl mytonctrl --cmd 'installer set_node_argument --verbosity 1'
```

Both commands restart the validator. Preserve the data volume when diagnosing
timeouts. The message `Too much metadata in the database, do only partial check`
means a [bounded metadata check](https://github.com/ton-blockchain/ton/blob/3d478cbde854be03a18ab2a59f8fc3c565cf7d14/validator/db/celldb.cpp#L119-L141)
reached its inspection limit; that message alone does not establish database
corruption or require a new dump.

For a setup without Compose, replace `docker compose exec mytonctrl` with
`docker exec mytonctrl`, and use `docker logs --since 30m --tail 300 mytonctrl`.
Retain the work volume while diagnosing synchronization or engine failures.

## Remove the Docker setup

Remove this Compose setup's containers, named volumes and service images:

**When `TON_WORK_HOST_DIR` is blank, this deletes the node data volume, including
keys, wallets, blockchain data, controller settings and downloaded dumps. Save a
backup outside these volumes first.** It also deletes the TON artifacts and
packaged script volume. When `TON_WORK_HOST_DIR` is set, that external directory
remains intact, including all node data.

```sh
docker compose down --volumes --rmi all --remove-orphans
```

The cleanup applies to the services and named volumes in this Compose file; see
[Compose down reference](https://docs.docker.com/reference/cli/docker/compose/down/)
for flag details. To also remove the files downloaded by quick setup after
teardown, run:

```sh
rm -f .env compose.yml compose.override.yml tonutils-storage install.sh
```

To erase the node data too, first stop and remove the containers, save any
required backup elsewhere, and verify the exact directory you selected. For the
example path in this guide, permanently delete it with:

```sh
sudo rm -rf -- /mnt/ton/ton-work
```

Replace that example with your actual `TON_WORK_HOST_DIR` when it differs.
