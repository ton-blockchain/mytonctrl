#!/usr/bin/env bash
# Prepare a standalone Docker deployment using published images.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: bash install.sh [--branch master|dev] [--image IMAGE] [--ton-image IMAGE] [--archive]

Download .env and compose.yml into the current directory.
Use --archive to also prepare a new mainnet archive liteserver, downloading
compose.override.yml and the latest released tonutils-storage executable.
Existing environment, Compose files and archive executables are never overwritten.

  --branch master|dev  Asset branch and default image tag (default: master/latest)
  --image IMAGE        Override the published MyTonCtrl image
  --ton-image IMAGE    Override the published TON image
  --archive            Prepare a fresh mainnet archive liteserver (Linux amd64/arm64)
  -h, --help           Show this help

Docker and Compose must be installed separately; --archive also requires jq.
This script does not start containers.
EOF
}

fail() {
    printf 'MyTonCtrl Docker setup: %s\n' "$*" >&2
    exit 1
}

branch=master
image=
ton_image=
archive=0
while (($#)); do
    case "$1" in
        --branch|--image|--ton-image)
            (($# >= 2)) || fail "$1 requires a value"
            case "$1" in
                --branch) branch=$2 ;;
                --image) image=$2 ;;
                --ton-image) ton_image=$2 ;;
            esac
            shift 2
            ;;
        --archive)
            archive=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *) fail "Unknown option: $1. Use --help for usage." ;;
    esac
done

case "$branch" in
    master) default_tag=latest ;;
    dev) default_tag=dev ;;
    *) fail "--branch must be master or dev" ;;
esac
image=${image:-ghcr.io/neodix42/mytonctrl:$default_tag}
[[ "$image" =~ ^[a-zA-Z0-9][a-zA-Z0-9._:/@-]*$ ]] || fail "Invalid --image value"
if [[ -n "$ton_image" ]]; then
    [[ "$ton_image" =~ ^[a-zA-Z0-9][a-zA-Z0-9._:/@-]*$ ]] || fail "Invalid --ton-image value"
fi

outputs=(.env compose.yml)
existing_names=(.env compose.yml compose.yaml docker-compose.yml docker-compose.yaml
    compose.override.yml compose.override.yaml docker-compose.override.yml docker-compose.override.yaml)
if ((archive)); then
    case "$(uname -s)" in
        Linux) ;;
        *) fail "--archive requires a Linux host" ;;
    esac
    case "$(uname -m)" in
        x86_64) storage_arch=amd64 ;;
        aarch64|arm64) storage_arch=arm64 ;;
        *) fail "--archive supports Linux amd64 and arm64 only" ;;
    esac
    command -v jq >/dev/null 2>&1 || fail "Install jq to resolve the latest tonutils-storage release for --archive"
    outputs+=(compose.override.yml tonutils-storage)
    existing_names+=(tonutils-storage)
fi

check_existing_files() {
    local path
    for path in "${existing_names[@]}"; do
        if [[ -e "$path" || -L "$path" ]]; then
            fail "$path already exists. Use an empty deployment directory; existing files were preserved."
        fi
    done
}
check_existing_files

if command -v curl >/dev/null 2>&1; then
    downloader=curl
elif command -v wget >/dev/null 2>&1; then
    downloader=wget
else
    fail "Install wget or curl to download the setup files"
fi

stage_dir=$(mktemp -d .mytonctrl-install.XXXXXX)
installed=0
cleanup() {
    local path
    if ((!installed)); then
        # Remove only files linked by this attempt, preserving files created by others.
        for path in "${outputs[@]}"; do
            if [[ ! -L "$path" && "$path" -ef "$stage_dir/$path" ]]; then
                rm -- "$path"
            fi
        done
    fi
    rm -rf -- "$stage_dir"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

download() {
    local url=$1 destination=$2
    if [[ "$downloader" == curl ]]; then
        curl --fail --silent --show-error --location --retry 3 \
            --connect-timeout 10 --max-time 120 --output "$destination" "$url" \
            || fail "Download failed: $url"
    else
        wget --quiet --timeout=30 --tries=3 -O "$destination" "$url" \
            || fail "Download failed: $url"
    fi
    [[ -s "$destination" ]] || fail "Downloaded file is empty: $url"
}

base_url=https://raw.githubusercontent.com/neodiX42/mytonctrl/$branch
download "$base_url/.env.example" "$stage_dir/env.example"
download "$base_url/docker/compose.yml" "$stage_dir/compose.yml"
if ((archive)); then
    download "$base_url/docker/compose.archive.yml" "$stage_dir/compose.override.yml"
    download "https://api.github.com/repos/xssnick/tonutils-storage/releases/latest" \
        "$stage_dir/tonutils-storage-release.json"
    storage_version=$(jq -er '.tag_name | select(type == "string")' "$stage_dir/tonutils-storage-release.json") \
        || fail "Could not read the latest tonutils-storage release tag"
    [[ "$storage_version" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] \
        || fail "Invalid latest tonutils-storage release tag"
    download "https://github.com/xssnick/tonutils-storage/releases/download/$storage_version/tonutils-storage-linux-$storage_arch" \
        "$stage_dir/tonutils-storage"
    chmod 644 "$stage_dir/compose.override.yml"
    chmod 755 "$stage_dir/tonutils-storage"
fi

# Select the published image without sourcing or expanding environment contents.
image_settings=0
ton_image_settings=0
args_settings=0
dump_settings=0
while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == MYTONCTRL_IMAGE=* ]]; then
        printf 'MYTONCTRL_IMAGE=%s\n' "$image"
        ((image_settings += 1))
    elif [[ -n "$ton_image" && "$line" == TON_IMAGE=* ]]; then
        printf 'TON_IMAGE=%s\n' "$ton_image"
        ((ton_image_settings += 1))
    elif ((archive)) && [[ "$line" == MYTONCTRL_ARGS=* ]]; then
        printf 'MYTONCTRL_ARGS=-m liteserver -n mainnet --archive\n'
        ((args_settings += 1))
    elif ((archive)) && [[ "$line" == DUMP=* ]]; then
        printf 'DUMP=false\n'
        ((dump_settings += 1))
    else
        printf '%s\n' "$line"
    fi
done < "$stage_dir/env.example" > "$stage_dir/.env"
((image_settings == 1)) || fail "The environment template must contain one MYTONCTRL_IMAGE setting"
if [[ -n "$ton_image" ]]; then
    ((ton_image_settings == 1)) || fail "The environment template must contain one TON_IMAGE setting"
fi
if ((archive)); then
    ((args_settings == 1)) || fail "The environment template must contain one MYTONCTRL_ARGS setting"
    ((dump_settings <= 1)) || fail "The environment template must contain at most one DUMP setting"
    if ((dump_settings == 0)); then
        printf 'DUMP=false\n' >> "$stage_dir/.env"
    fi
fi
chmod 600 "$stage_dir/.env"
chmod 644 "$stage_dir/compose.yml"

# Finish all downloads before installing any file. Hard links refuse collisions,
# including directories and dangling symlinks that appear during publication.
check_existing_files
for path in "${outputs[@]}"; do
    ln -T -- "$stage_dir/$path" "$path" \
        || fail "Could not install $path; existing files were preserved"
done
installed=1

printf 'Installed .env and compose.yml in %s\n' "$PWD"
printf 'Controller image: %s\n' "$image"
if [[ -n "$ton_image" ]]; then
    printf 'TON image: %s\n' "$ton_image"
fi
if ((archive)); then
    printf 'Archive setup: compose.override.yml and tonutils-storage %s (Linux %s) installed.\n' \
        "$storage_version" "$storage_arch"
    printf 'Use empty node storage with room for the full archive; keep both archive files for upgrades.\n'
fi
cat <<'EOF'

Leave TON_WORK_HOST_DIR blank to use the standard TON_WORK_VOLUME Docker volume.
For an external data disk, mount it and set TON_WORK_HOST_DIR to an absolute directory on it.
Edit .env to choose installation arguments and images, then run:
  docker compose pull
  docker compose up -d --no-build --pull never
  docker compose logs -f mytonctrl
Go inside mytonctrl with:
  docker compose exec mytonctrl mytonctrl

The exporter is included in the MyTonCtrl image. No extra script download is needed.
EOF
