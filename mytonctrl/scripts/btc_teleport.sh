SOURCES_DIR=/usr/src
REPO=ton-teleport-btc-oracle
REPO_URL=https://github.com/RSquad/${REPO}.git


if ! command -v rustc >/dev/null 2>&1
then
  echo "installing rust"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rust.sh && bash /tmp/rust.sh -y
  rm /tmp/rust.sh
fi

if ! command -v bun >/dev/null 2>&1
then
  echo "installing bun"
  curl -fsSL https://bun.sh/install -o /tmp/bun.sh && bash /tmp/bun.sh
  rm /tmp/bun.sh
fi

cd $SOURCES_DIR
rm -rf $REPO
git clone $REPO_URL

cd $REPO
bun install
bun run build:frost