REPO=ton-teleport-btc-oracle
SRC_DIR=""

while getopts s:r: flag
do
	case "${flag}" in
		s) SRC_DIR=${OPTARG};;
    r) REPO=${OPTARG};;
    *) echo "Flag -${flag} is not recognized. Aborting"; exit 1 ;;
	esac
done

REPO_URL=https://github.com/RSquad/${REPO}.git

if ! command -v unzip >/dev/null 2>&1
then
  echo "installing unzip"
  apt-get install -y unzip
fi

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

cd $SRC_DIR || exit 1
rm -rf $REPO
git clone $REPO_URL

cd $REPO || exit 1
bun install
bun run build:frost

python3 -c "import mypylib; mypylib.add2systemd(name='btc_teleport', user=os.getlogin(), start='bun start', workdir=${SRC_DIR})"
