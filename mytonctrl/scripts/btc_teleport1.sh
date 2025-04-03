REPO=""
SRC_DIR=""
USER=$(logname)

while getopts s:r: flag
do
	case "${flag}" in
		s) SRC_DIR=${OPTARG};;
    r) REPO=${OPTARG};;
    *) echo "Flag -${flag} is not recognized. Aborting"; exit 1 ;;
	esac
done

# install go
GO_BIN_PATH=/usr/local/go/bin/go
if [ ! -f $GO_BIN_PATH ] || { [ -f $GO_BIN_PATH ] && [[ "$($GO_BIN_PATH version)" != *"1.23.1"* ]]; }; then
    wget https://go.dev/dl/go1.23.1.linux-amd64.tar.gz
    rm -rf /usr/local/go && tar -C /usr/local -xzf go1.23.1.linux-amd64.tar.gz && rm go1.23.1.linux-amd64.tar.gz
    echo installed go 1.23.1
fi


# clone repo

REPO_URL=git@github.com:RSquad/${REPO}.git

cd $SRC_DIR || exit 1
rm -rf $REPO
git clone $REPO_URL

chown -R $USER:$USER $REPO

git config --global --add safe.directory $SRC_DIR/$REPO

echo "oracle sources cloned successfully"
