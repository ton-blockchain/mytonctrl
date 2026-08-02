#!/bin/bash
set -e

BENCHMARK_URL="https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/mytonctrl/scripts/benchmark.py"
BENCHMARK_PATH=""
BUILD_DIR="/usr/bin/ton"
SRC_DIR="/usr/src/ton"

while getopts "p:b:s:" opt; do
	case $opt in
		p) BENCHMARK_PATH="$OPTARG" ;;
		b) BUILD_DIR="$OPTARG" ;;
		s) SRC_DIR="$OPTARG" ;;
		*) echo "Usage: $0 [-p benchmark_path] [-b ton_bin] [-s ton_src] [-- benchmark args]"; exit 1 ;;
	esac
done
shift $((OPTIND - 1))

# Check uv is installed
if ! command -v uv &>/dev/null; then
	read -rp "uv is not installed. Install it? [y/n] " answer
	if [ "${answer,,}" = "y" ]; then
		curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv_install.sh
		sh /tmp/uv_install.sh
		export PATH="$HOME/.local/bin:$PATH"
		if ! command -v uv &>/dev/null; then
			echo "Error: uv installation failed"
			exit 1
		fi
	else
		exit 0
	fi
fi

# Check validator is not running
if systemctl is-active --quiet validator; then
	echo "Error: validator service is running. Stop it before running benchmark."
	exit 1
fi

TMP_DIR="$(realpath "$(mktemp -d)")"
trap 'rm -rf "$TMP_DIR"' EXIT

#   crypto/create-state, utils/generate-random-id,
#   validator-engine/validator-engine, dht-server/dht-server,
#   tonlib/libtonlibjson.so
BUILD_DIR="$(realpath "$BUILD_DIR")"
if [ -f "$BUILD_DIR/Makefile" ]; then  # mtc
	:
elif [ -f "$BUILD_DIR/libtonlibjson.so" ]; then  # package
	NORM_DIR="$TMP_DIR/build"
	mkdir -p "$NORM_DIR"/{crypto,utils,validator-engine,dht-server,tonlib}
	ln -s "$BUILD_DIR/create-state" "$NORM_DIR/crypto/"
	ln -s "$BUILD_DIR/generate-random-id" "$NORM_DIR/utils/"
	ln -s "$BUILD_DIR/validator-engine" "$NORM_DIR/validator-engine/"
	ln -s "$BUILD_DIR/dht-server" "$NORM_DIR/dht-server/"
	ln -s "$BUILD_DIR/libtonlibjson.so" "$NORM_DIR/tonlib/"
	BUILD_DIR="$NORM_DIR"
elif [ -f "$BUILD_DIR/lib/libtonlibjson.so" ]; then  # dist
	NORM_DIR="$TMP_DIR/build"
	mkdir -p "$NORM_DIR"/{crypto,utils,validator-engine,dht-server,tonlib}
	ln -s "$BUILD_DIR/bin/create-state" "$NORM_DIR/crypto/"
	ln -s "$BUILD_DIR/bin/generate-random-id" "$NORM_DIR/utils/"
	ln -s "$BUILD_DIR/bin/validator-engine" "$NORM_DIR/validator-engine/"
	ln -s "$BUILD_DIR/bin/dht-server" "$NORM_DIR/dht-server/"
	ln -s "$BUILD_DIR/lib/libtonlibjson.so" "$NORM_DIR/tonlib/"
	BUILD_DIR="$NORM_DIR"
fi

if [ -n "$BENCHMARK_PATH" ]; then
	cp "$BENCHMARK_PATH" "$TMP_DIR/benchmark.py"
else
	curl -LsSf "$BENCHMARK_URL" -o "$TMP_DIR/benchmark.py"
fi

uv init --python 3.14 --no-workspace --name benchmark "$TMP_DIR"

TEST_DIR="$TMP_DIR/test"
TONTESTER_DIR="$TEST_DIR/tontester"

cp -r "$SRC_DIR/test" "$TEST_DIR"

TL_DEST="$TMP_DIR/tl/generate/scheme"
mkdir -p "$TL_DEST"
cp "$SRC_DIR/tl/generate/scheme/"*.tl "$TL_DEST/"

cd "$TMP_DIR"
uv add --editable "$TONTESTER_DIR"
uv run "$TONTESTER_DIR/generate_tl.py"

set +e
uv run benchmark.py \
	--build-dir "$BUILD_DIR" \
	--source-dir "$SRC_DIR" \
	--work-dir "$TMP_DIR/test/integration/.network" \
	"$@"
set -e