SRC_DIR=""

while getopts s: flag
do
	case "${flag}" in
		s) SRC_DIR=${OPTARG};;
    *) echo "Flag -${flag} is not recognized. Aborting"; exit 1 ;;
	esac
done

# install rust
if ! command -v rustc >/dev/null 2>&1
then
  echo "installing rust"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rust.sh && bash /tmp/rust.sh -y
  rm /tmp/rust.sh
  . "$HOME/.cargo/env"
  echo "installed rust"
fi

cargo install cbindgen

# build frost

cd $SRC_DIR/frost || exit 1

cd rust
./build.sh
cd ..

/usr/local/go/bin/go build .
/usr/local/go/bin/go test -v || exit 1

echo "frost built successfully"

cd $SRC_DIR
/usr/local/go/bin/go build -o out/oracle ./oracle/cmd/main.go

echo "oracle built successfully"
