# Importing Wallets

MyTonCtrl supports various types of wallet-like contracts, including wallet-v1, wallet-v3, [lockup-wallet](https://github.com/ton-blockchain/lockup-wallet-contract/tree/main/universal), and others. Often, it provides a straightforward way to interact with these contracts.

## Importing Using a Private Key

If you have access to a private key, you can easily import a wallet. Enter the following command into the console:

```
iw <wallet-addr> <wallet-secret-key>
```

Here, `<wallet-secret-key>` is your private key in base64 format.

## Importing Using a Mnemonic Phrase

If you have a mnemonic phrase (a sequence of 24 words like `tattoo during ...`), follow these steps:

1. Install Node.js.
2. Clone and install [mnemonic2key](https://github.com/ton-blockchain/mnemonic2key):
    ```
    git clone https://github.com/ton-blockchain/mnemonic2key.git
    cd mnemonic2key
    npm install
    ```
3. Run the following command, replacing `word1`, `word2`... with your mnemonic phrase and `address` with the address of your wallet contract:
    ```
    node index.js word1 word2 ... word24 [address]
    ```
4. The script will generate `wallet.pk` and `wallet.addr`. Rename them to `imported_wallet.pk` and `imported_wallet.addr`.
5. Copy both files to the `~/.local/share/mytoncore/wallets/` directory.
6. Open the mytonctrl console and list the wallets using the `wl` command.
7. Verify that the wallet has been imported and displays the correct balance.
8. You can now send funds using the `mg` command. Enter `mg` to view the help documentation.

Remember to replace placeholders (words inside `< >`) with your actual values when running commands.