# Importing wallets

MyTonCtrl can work with different types of wallet-like contracts: wallet-v1, wallet-v3, [lockup-wallet](https://github.com/ton-blockchain/lockup-wallet-contract/tree/main/universal), etc

Sometimes it is even the simplest way to deal with contract.

## Import via private key
If you know private key just type in console:
```
iw <wallet-addr> <wallet-secret-key>
```
where `wallet-secret-key` is private key in base64 format

## Import via mnemonic
If you know mnemonic phrase (24 words like `tattoo during ...`) do the following steps:
1) Install nodejs
2) Install https://github.com/ton-blockchain/mnemonic2key:
```
git clone https://github.com/ton-blockchain/mnemonic2key.git

cd mnemonic2key

npm install
```
3) Run `node index.js word1 word2 ... word24 [address]`, where `word1`, `word2` ... are your mnemonic phrase and `address` is address of your wallet contract
4) Script will generate `wallet.pk` и `wallet.addr`, rename them to `imported_wallet.pk` and `imported_wallet.addr`
5) Copy both files to `~/.local/share/mytoncore/wallets/`
6) Open mytonctrl console and list wallets via `wl` command
7) Check that wallet was imported and has correct balance
8) Now you can send money via `mg` command (type `mg` to get help docs)
