# MyTonCtrl with a separate TON image

The root `Dockerfile` packages this checkout's MyTonCtrl Python utility. It does
not contain TON binaries, a compiler, or TON/MyTonCtrl source repositories. TON executables
run in the controller container; the separate official image supplies their
artifacts. Only the global network configuration is downloaded during normal
first initialization. Optional dump/archive downloads remain explicit settings.

The [official TON image](https://github.com/ton-blockchain/ton/blob/master/Dockerfile)
contains executables in `/usr/local/bin`, Fift libraries in `/usr/lib/fift`, and
wallet/contract scripts in `/usr/share/ton/smartcont`. All three are required.
The controller image packages `export-ton.sh`. Compose first runs `ton-exporter`
using that same image to copy the script into a shared `ton-scripts` volume.
`ton-binaries` mounts the script volume read-only and runs the script in the
unchanged official image with `init.sh` bypassed. It publishes immutable binaries
to a shared artifact volume and atomically selects `current`. There are two
images and three services; the exporter helper exits after copying the script.
MyTonCtrl mounts that volume read-only, checks its contents and binary architecture,
then copies one release to a private `/run/ton-active` snapshot before starting.
The `status` command shows each image reference instead of a source commit and
branch. TON's reference is copied into that snapshot, so publishing an updated
TON image does not change the identity shown by a running controller. Re-exporting
identical binaries under another tag updates the export metadata for the next
controller start. Existing native mounts without export metadata show an unknown
TON image reference.
It refuses startup if artifacts are missing or their runtime dependencies cannot
be loaded. The controller image uses Ubuntu 22.04, matching the current official
TON runtime, with runtime libraries and diagnostic tools only.

## Start with Compose

Use the [quick setup installer](../README.docker.md#quick-setup) in an empty deployment
directory. It creates `.env` and `compose.yml` for published images. Leave
`TON_WORK_HOST_DIR` blank for the standard `TON_WORK_VOLUME` Docker volume, or
set it to an absolute directory on your mounted data disk;
see [storage setup and migration](../README.docker.md#store-ton-data-on-a-separate-disk).
For a new archive liteserver, use `install.sh --archive` to prepare the required
tool and Compose override automatically;
see [archive node setup](../README.docker.md#set-up-an-archive-node).
After editing `.env`, start the setup:

```sh
# Edit .env: choose installation options in MYTONCTRL_ARGS.
# PUBLIC_IP is optional: leave blank to autodetect, or set the advertised IPv4.
# Pin TON_IMAGE and select your tagged MYTONCTRL_IMAGE.
docker compose pull
docker compose up -d --no-build --pull never
docker compose logs -f mytonctrl
docker compose exec mytonctrl mytonctrl
```

The selected controller image tag must have been published by GitHub Actions
before it can be pulled. For a local build, use the checkout root's `compose.yaml`
as described in [development setup](../README.docker.md#build-from-a-local-checkout-optional).
For build metadata, set `MYTONCTRL_BUILD_COMMIT` and `MYTONCTRL_BUILD_VERSION` in
the checkout's `.env`, or pass `--build-arg MYTONCTRL_COMMIT=...`
and `--build-arg MYTONCTRL_VERSION=...` to `docker build`. Custom builds can also
pass `--build-arg MYTONCTRL_IMAGE_REF=repository/image:tag` for the status display.
Published images include their complete reference, and local Compose builds use
`MYTONCTRL_IMAGE`. This build identity takes precedence over runtime `.env` values.
No controller code or
Python environment is stored in a data volume.

Compose uses host networking, intended for Linux TON nodes. Allow the selected
validator UDP port, QUIC UDP port and liteserver TCP port through the host firewall.
Keep the validator console port private. Installation defaults in `.env.example`
select fixed ports, while empty values let the original installer choose them.
Startup defaults retain the original CPU/memory requirement check;
add `-i` to `MYTONCTRL_ARGS` to bypass it for testing.

`ton-binaries` exits after publishing; MyTonCtrl supervises the node and controller
services without systemd, privileged mode or a Docker socket. All node state,
keys, wallets, controller databases, network configurations and service settings
live in the selected Docker volume or host directory mounted at `/var/ton-work`.
The entrypoint locks that storage to prevent two controllers from opening the same node state.

## Start without Compose

Prepare `.env` with the [quick setup installer](../README.docker.md#quick-setup), then
use Docker directly. Replace the image tags below with your selected versions.
Check the latest available TON release tag in the
[official TON container package](https://github.com/ton-blockchain/ton/pkgs/container/ton)
and choose the tag for your host architecture; the examples use x86-64 (`amd64`).
Use the same `TON_WORK_VOLUME` and optional `TON_WORK_HOST_DIR` values in `.env`
and your shell. The exporter comes from the controller image:

```sh
docker pull ghcr.io/neodix42/mytonctrl:latest
docker pull ghcr.io/ton-blockchain/ton:latest
docker volume create mytonctrl-ton-scripts
docker volume create mytonctrl-ton-artifacts
TON_WORK_VOLUME=mytonctrl-ton-work
TON_WORK_HOST_DIR=
docker run --rm --entrypoint /bin/sh \
  --mount type=volume,src=mytonctrl-ton-scripts,dst=/scripts \
  ghcr.io/neodix42/mytonctrl:latest \
  -c 'cp /usr/local/lib/mytonctrl/export-ton.sh /scripts/export-ton.sh'
docker run --rm --entrypoint /bin/sh \
  -e TON_IMAGE_REF=ghcr.io/ton-blockchain/ton:latest \
  --mount type=volume,src=mytonctrl-ton-artifacts,dst=/ton-artifacts \
  --mount type=volume,src=mytonctrl-ton-scripts,dst=/scripts,readonly \
  ghcr.io/ton-blockchain/ton:latest /scripts/export-ton.sh
docker run -d --name mytonctrl --network host --stop-timeout 75 \
  --env-file .env \
  --mount type=volume,src=mytonctrl-ton-artifacts,dst=/ton-artifacts,readonly \
  -v "${TON_WORK_HOST_DIR:-$TON_WORK_VOLUME}:/var/ton-work" \
  ghcr.io/neodix42/mytonctrl:latest
docker exec -it mytonctrl mytonctrl
```

Check mounts and binary dependencies without initializing the node state:

```sh
docker run --rm \
  --mount type=volume,src=mytonctrl-ton-artifacts,dst=/ton-artifacts,readonly \
  ghcr.io/neodix42/mytonctrl:latest check
```

## Use an existing TON container's volumes

The controller also accepts the official image's native directories, without
an export script or metadata. Use the same storage settings as in `.env`;
blank `TON_WORK_HOST_DIR` uses `TON_WORK_VOLUME`. For example, start a binary-provider container:

```sh
docker run -d --name ton-provider --entrypoint /bin/sleep \
  -v ton-native-bin:/usr/local/bin \
  -v ton-native-fift:/usr/lib/fift \
  -v ton-native-smartcont:/usr/share/ton/smartcont \
  ghcr.io/ton-blockchain/ton:latest infinity
docker run -d --name mytonctrl --network host --stop-timeout 75 --env-file .env \
  -v ton-native-bin:/ton-source/bin:ro \
  -v ton-native-fift:/ton-source/fift:ro \
  -v ton-native-smartcont:/ton-source/smartcont:ro \
  -v "${TON_WORK_HOST_DIR:-${TON_WORK_VOLUME:-mytonctrl-ton-work}}:/var/ton-work" \
  ghcr.io/neodix42/mytonctrl:latest
```

Docker populates new empty named volumes from the official image directories.
Reuse the existing provider's actual volume names if it is already running.
Bind mounts containing exported files also work. Override `TON_BINARIES_DIR`,
`FIFT_LIB_DIR` and `TON_SMARTCONT_DIR` when mounting at other paths. Docker does
not expose another container's unmounted filesystem automatically; its directories
must be available as shared volumes or bind mounts.

Reusing populated native volumes with a newer TON image does **not** refresh
their contents. Use fresh volume names for each TON release, or use the exporter
above, which handles this explicitly. Do not modify native files while a new
controller is taking its startup snapshot.

## Update independently

To publish a newer TON image, change `TON_IMAGE` in `.env`, then:

```sh
docker compose pull ton-binaries
docker compose run --rm ton-binaries
```

The running controller keeps its private binaries and Fift resources. Its node
process and later console commands continue using the old release. To adopt the
new TON binaries, explicitly restart it:

```sh
docker compose restart --no-deps mytonctrl
```

To update MyTonCtrl, select a published controller image tag in `.env`, pull it,
and recreate only the controller:

```sh
docker compose pull mytonctrl
docker compose run --rm --no-deps ton-exporter
docker compose up -d --no-deps --no-build --pull never mytonctrl
```

Local development builds use the checkout's `compose.yaml`; see
[controller updates](../README.docker.md#upgrade-the-mytonctrl-image).

The helper refreshes the packaged exporter script for future TON exports.
Persisted node and controller data are reused. Console `update` and `upgrade`
are disabled and display instructions to update the corresponding Docker image.
No in-container TON or MyTonCtrl upgrade downloads, cloning or binary compilation
take place. Old exported TON releases are retained; clean them up only when they
are no longer needed.

Git is available for MyTonCtrl's existing optional contract downloads (legacy
nominator pools and liquid staking). It is never used to install or upgrade
TON or MyTonCtrl in this image.

## Published controller images

GitHub Actions builds and publishes `ghcr.io/<lowercase-repository-owner>/mytonctrl` for
both `linux/amd64` and `linux/arm64`:

| Trigger | Image tag |
| --- | --- |
| A commit pushed to `dev` | `dev` |
| A commit pushed to `master` | `latest` |
| Manually run **Publish tagged Docker image** | The required `tag` input |

The automatic workflow is [Publish Docker image](../.github/workflows/docker-publish.yml).
For a release, open Actions, select
[Publish tagged Docker image](../.github/workflows/docker-publish-tag.yml),
choose the branch or tag to build, and supply the image tag (for example,
`v1.0.0`). These workflows build the selected checkout and publish using the
repository's `GITHUB_TOKEN`.

Image tags become available after the publishing workflow completes successfully.

Set `MYTONCTRL_IMAGE=ghcr.io/<lowercase-repository-owner>/mytonctrl:<tag>` in
`.env` to use a published image. Pull and recreate only the controller:

```sh
docker compose pull mytonctrl
docker compose run --rm --no-deps ton-exporter
docker compose up -d --no-deps --no-build --pull never mytonctrl
```

## Environment options

Compose reads `.env` and passes it to the controller. Standalone Docker uses
`--env-file .env`. Values are parsed as data; the entrypoint never sources or
evaluates the file. Put the original installation flags in `MYTONCTRL_ARGS`,
with shell-style quoting for values containing spaces. See the
[host installation option table](../README.md#installation-options) for the
original flags and [Docker arguments](../README.docker.md#installation-arguments-in-env)
for their container behavior.

`TON_WORK_HOST_DIR` is an optional absolute host storage path, independent of
the installer work path (`-W`). Empty or unset selects the original named Docker
volume, `TON_WORK_VOLUME` (default `mytonctrl-ton-work`). A nonempty path selects
a bind mount at `/var/ton-work`. Mount your data disk and prepare its directory
before startup; Compose's short mount syntax can create a missing directory.
Image upgrades reuse the selected storage. `docker compose down -v` deletes
named-volume node data, while host directory contents remain intact.
See [storage setup and migration](../README.docker.md#store-ton-data-on-a-separate-disk)
to move an existing named-volume installation without losing data.

The default installs a mainnet validator using a prepared dump:

```dotenv
MYTONCTRL_ARGS=-m validator -n mainnet -d
PUBLIC_IP=
```

Blank or omitted `PUBLIC_IP` autodetects the public IPv4 address, matching the
original installer's default behavior. Set it explicitly when the node should
advertise a different address, such as behind NAT. The entrypoint validates the
address before installation starts; autodetection failures produce an error
asking you to set `PUBLIC_IP`.

For a custom network, use `-n custom -c https://example.com/global.config.json`
or `-n custom -c /config/global.config.json` in `MYTONCTRL_ARGS`. Mount a local
configuration file at the supplied absolute path. Add `-t` to disable telemetry,
`-i` to skip the installer CPU/RAM check, or `-s` to disable console startup
checks. The last option is a Docker extension; `-i` retains its original
installation meaning.

To load additional native installation parameters from a mounted file, add
`-e /config/installer.env` to `MYTONCTRL_ARGS`. The container reads `KEY=value`
data without executing shell code. `MYTONCTRL_ARGS=--help` and
`MYTONCTRL_ARGS=--print-env` print help or parsed installation settings and exit
without requiring TON binary mounts.

Repository-selection variables (`AUTHOR`, `REPO`, `BRANCH`, `NODE_REPO`,
`NODE_VERSION`, `MYTONCTRL_VERSION`) are rejected at runtime: select images
instead. `MYTONCTRL_BUILD_VERSION` supplies build metadata without changing code.

The original native settings pass through unchanged: `VALIDATOR_PORT`,
`VALIDATOR_CONSOLE_PORT`, `LITESERVER_PORT`, `QUIC_PORT`, `PUBLIC_IP`, `ARCHIVE_TTL`,
`STATE_TTL`, `ADD_SHARD`, `ARCHIVE_BLOCKS`, `DUMP_CACHE_DIR`, `DUMP_EXTRACT_THREADS`,
and `DUMP_VALIDATE_BEFORE_EXTRACT`. `VERBOSITY` and `CUSTOM_PARAMETERS` append
node arguments on first initialization. Custom parameters cannot replace the
controller-managed binary, state/config/log paths, or foreground service behavior.

Installation flags apply once. Subsequent starts keep the persisted service
configuration and wallet settings. Use normal console commands to change mode,
telemetry and node arguments after installation. Keep the `-u`, `-B`, `-S` and
`-W` values fixed for a data volume; the entrypoint rejects changes. Defaults
are `root`, `/usr/bin`, `/usr/src` and `/var/ton-work`, respectively. Compose
aliases a custom `-W` path to its mounted `/var/ton-work` volume, preserving
persistent storage. Standalone Docker can mount persistent data directly at the
selected `-W` path instead.
Interrupted initialization resumes automatically using persisted settings and
checkpoints. Cached dumps, node keys and existing configuration are preserved;
background tasks start after the controller's client settings are ready. See
[recovery instructions](../README.docker.md#recover-interrupted-initialization).

All original console arguments work with `docker exec ... mytonctrl`. They can
also be supplied through `.env`:

| Console argument | Environment setting |
| --- | --- |
| `-c`, `--config` | `MYTONCTRL_CONFIG` |
| `-w`, `--wallets` | `MYTONCTRL_WALLETS` |
| `-s`, `--no-startup-checks` | Add `-s` to `MYTONCTRL_ARGS` |
| `--cmd` | `MYTONCTRL_CMD` |

For example, set `MYTONCTRL_CMD=status` to make the console run `status` by
default. Explicit CLI arguments follow these defaults and take precedence for
options with a value. `MYTONCTRL_ARGS` configures installation and the optional
`-s` console default; installation flags are never forwarded to the console.
Installer `-c` selects global network configuration; console `-c` selects the
controller database. The default container command runs services;
`image console --cmd ...` initializes them and runs a foreground console command.

`--archive` in `MYTONCTRL_ARGS` and `ARCHIVE_BLOCKS` use MyTonCtrl's existing
archive downloader, which requires **tonutils-storage**, a different program/API
from the official TON `storage-daemon`. For a new archive node,
[`install.sh --archive`](../README.docker.md#set-up-an-archive-node) downloads a
pinned prebuilt executable and installs [the Compose override](compose.archive.yml)
to include it in the exported artifacts. For custom native mounts, supply it as
`tonutils-storage` in the mounted flat binaries directory. Startup fails early
with an actionable message when it is absent. The image never compiles this
optional tool. `enable TS` uses the same executable. Optional `enable THA` and
`enable LSP` install other projects on a host; in container deployments run those
tools in separate images instead.

## Troubleshooting

Inspect installation progress with `docker compose logs mytonctrl` and
`docker compose exec mytonctrl mytonctrl --cmd status`. The console shows
initialization and dump stages, service state and local resources even before
ValidatorConsole is configured. Full tracebacks remain in the persistent
`/var/ton-work/controller/mytoncore/mytoncore.log`; stdout shows error summaries.

"Previous initialization was interrupted" is an error from older images.
Select an image with the recovery fixes and use the normal
[controller upgrade commands](../README.docker.md#upgrade-the-mytonctrl-image) with the
same work volume. The empty pending marker from those images is supported and
initialization resumes without deleting the archive or node identity. Keep the
marker and data volumes. A completed cached archive is verified and reused;
an interrupted download continues the same archive, and an interrupted
extraction restarts locally. Cache metadata pins the dump across image changes.

An older image could pass `--ip :30303` to the validator when `PUBLIC_IP` was
empty, leaving a failed installation. Current images autodetect and validate
blank or missing `PUBLIC_IP` before installation begins.

For local development, rebuild the controller from the checkout using
`compose.yaml` before retrying. Invalid or ambiguous node keys/configuration
still require inspection or a valid backup; recovery does not replace them.

## Development checks

```sh
python3 -m unittest discover -s tests/docker -v
python3 -m pytest tests/unit
MYTONCTRL_ENV_FILE=.env.example docker compose --env-file .env.example config
```

Supervisor lifecycle tests run when the `supervisor` Python package is available;
pure unit tests and exporter tests run with Python's standard library.
