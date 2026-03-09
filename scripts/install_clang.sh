#!/usr/bin/env bash
set -euo pipefail

# check sudo permissions
if [ "$(id -u)" != "0" ]; then
    echo "Please run script as root"
    exit 1
fi

fix_broken_apt_state_if_needed() {
  if apt-get check >/dev/null 2>&1; then
    return
  fi

  echo "Detected broken apt/dpkg state. Running apt --fix-broken install..."
  apt-get -y --fix-broken install || true

  if apt-get check >/dev/null 2>&1; then
    return
  fi

  echo "Broken state persists. Clearing possible clang-21 holds and removing conflicting packages..."
  for pkg in clang-21 clang-tools-21; do
    if apt-mark showhold 2>/dev/null | grep -qx "$pkg"; then
      apt-mark unhold "$pkg"
    fi
  done

  apt-get -y remove --purge clang-tools-21 clang-21 || true
  apt-get -y --fix-broken install
}

fix_broken_apt_state_if_needed

apt install -y lsb-release gpg-agent software-properties-common gnupg libssl-dev wget

require_clang_21() {
  local bin="$1"
  local version_line

  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "ERROR: '$bin' is not available in PATH."
    exit 1
  fi

  version_line=$("$bin" --version 2>/dev/null | head -n1 || true)
  if ! echo "$version_line" | grep -Eq 'version[[:space:]]+21([.[:space:]]|$)'; then
    echo "ERROR: '$bin' is not clang 21."
    echo "$bin --version output:"
    "$bin" --version || true
    exit 1
  fi
}

is_clang_21() {
  local bin="$1"
  local version_line

  if ! command -v "$bin" >/dev/null 2>&1; then
    return 1
  fi

  version_line=$("$bin" --version 2>/dev/null | head -n1 || true)
  echo "$version_line" | grep -Eq 'version[[:space:]]+21([.[:space:]]|$)'
}

remove_clang_tools_21_if_installed() {
  if dpkg-query -W -f='${Status}\n' clang-tools-21 2>/dev/null | grep -q "^install ok installed$"; then
    echo "Removing clang-tools-21 to avoid dpkg file conflicts with clang-21 upgrades..."
    apt remove -y clang-tools-21
  fi
}

DISTRO_CODENAME=$(lsb_release -cs)
DISTRO_ID="$(. /etc/os-release && echo "${ID:-}")"
DISTRO_VERSION_ID="$(. /etc/os-release && echo "${VERSION_ID:-}")"

if is_clang_21 clang; then
  echo "Default clang is already version 21, skipping package installation."
else
  remove_clang_tools_21_if_installed

  if [ "$DISTRO_CODENAME" = "jammy" ] || [ "$DISTRO_CODENAME" = "bookworm" ] || { [ "$DISTRO_ID" = "debian" ] && [ "${DISTRO_VERSION_ID%%.*}" = "12" ]; }; then
    wget https://apt.llvm.org/llvm.sh
    chmod +x llvm.sh
    ./llvm.sh 21 clang
  elif [ "$DISTRO_CODENAME" = "noble" ]; then
    mkdir -p /etc/apt/keyrings
    wget -O - https://apt.llvm.org/llvm-snapshot.gpg.key | tee /etc/apt/keyrings/llvm.asc >/dev/null
    cat <<EOF | tee /etc/apt/sources.list.d/llvm.sources >/dev/null
Types: deb
URIs: https://apt.llvm.org/${DISTRO_CODENAME}/
Suites: llvm-toolchain-${DISTRO_CODENAME}-21
Components: main
Signed-By: /etc/apt/keyrings/llvm.asc
EOF
    apt -y update
    apt install -y clang-21
  else
    echo "Unsupported distribution/codename: ID=$DISTRO_ID VERSION_ID=$DISTRO_VERSION_ID CODENAME=$DISTRO_CODENAME"
    echo "Supported versions: Ubuntu 22.04 (jammy), Ubuntu 24.04 (noble), Debian 12 (bookworm)"
    exit 1
  fi
fi

update-alternatives --install /usr/bin/clang clang /usr/bin/clang-21 200
update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-21 200
ln -sf /usr/bin/clang-21 /usr/bin/clang
ln -sf /usr/bin/clang++-21 /usr/bin/clang++

require_clang_21 clang-21
require_clang_21 clang

echo "clang-21 installation complete."
