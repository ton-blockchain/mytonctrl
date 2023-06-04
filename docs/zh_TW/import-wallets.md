# 匯入錢包

MyTonCtrl支援多種類型的類似錢包的合約，包括wallet-v1，wallet-v3，[lockup-wallet](https://github.com/ton-blockchain/lockup-wallet-contract/tree/main/universal)等等。通常，這是處理這些合約的最簡單方法。

## 使用私鑰匯入

如果你知道私鑰，你只需要在控制台輸入以下指令：

```
iw <wallet-addr> <wallet-secret-key>
```

在此，`<wallet-secret-key>` 是以base64格式的私鑰。

## 使用助記詞匯入

如果你知道助記詞短語（像是由24個單詞組成的短語，例如 `tattoo during ...`），請執行以下步驟：

1. 安裝Node.js。
2. 複製並安裝 [mnemonic2key](https://github.com/ton-blockchain/mnemonic2key)：
    ```
    git clone https://github.com/ton-blockchain/mnemonic2key.git
    cd mnemonic2key
    npm install
    ```
3. 執行以下命令，其中 `word1`，`word2` ... 是你的助記詞短語，`address` 是你的錢包合約地址：
    ```
    node index.js word1 word2 ... word24 [address]
    ```
4. 腳本將生成 `wallet.pk` 和 `wallet.addr`，將它們重命名為 `imported_wallet.pk` 和 `imported_wallet.addr`。
5. 將這兩個檔案複製到 `~/.local/share/mytoncore/wallets/` 目錄。
6. 開啟mytonctrl控制台，並使用 `wl` 命令列出錢包。
7. 確認錢包已經匯入並且餘額正確。
8. 現在你可以使用 `mg` 命令發送金錢（輸入 `mg` 可查看使用說明）。

在執行命令時，記得將尖括號內的佔位符（例如 `<wallet-addr>`、`<wallet-secret-key>`）替換為實際的值。