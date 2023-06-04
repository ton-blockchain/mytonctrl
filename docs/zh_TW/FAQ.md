# MyTonCtrl 使用的目錄

MyTonCtrl 是一個包裝器，會在兩個地方儲存檔案：

1. `~/.local/share/mytonctrl/` - 儲存長期檔案，如日誌檔
2. `/tmp/mytonctrl/` - 儲存臨時檔案

MyTonCtrl 也包含了另一個腳本 mytoncore，它將檔案儲存到以下位置：

1. `~/.local/share/mytoncore/` - 持久檔案，主要的設定檔會儲存在這裡
2. `/tmp/mytoncore/` - 臨時檔案，選舉使用的參數將會保存在此

MyTonCtrl 會將自身和驗證者的源碼下載到以下資料夾：

1. `/usr/src/mytonctrl/`
2. `/usr/src/ton/`

MyTonCtrl 會將驗證者的組件編譯到以下資料夾：

1. `/usr/bin/ton/`

MyTonCtrl 會在這裡建立一個驗證者工作的資料夾：

1. `/var/ton/`

---

## 若 MyTonCtrl 以 root 使用者安裝：

那麼，設定檔會以不同的方式存放：

1. `/usr/local/bin/mytonctrl/`
2. `/usr/local/bin/mytoncore/`

---

## 如何移除 MyTonCtrl：

以管理員身份執行腳本並移除已編譯的 TON 組件：

```bash
sudo bash /usr/src/mytonctrl/scripts/uninstall.sh
sudo rm -rf /usr/bin/ton
```

在這個過程中，確保你有足夠的權限來刪除或更改這些檔案或目錄。

# 處理錯誤和更改 MyTonCtrl 的工作目錄

如果您在使用不同的使用者執行 MyTonCtrl 時遇到問題，或者您想要在安裝前更改驗證者的工作目錄，以下的指南可以提供幾種解決方案。

## 以不同的使用者執行 MyTonCtrl

當以不同的使用者執行 MyTonCtrl 時，可能會出現以下錯誤：

```
Error: expected str, bytes or os.PathLike object, not NoneType
```

要解決此問題，您需要以安裝 MyTonCtrl 的使用者執行程式。

## 在安裝前更改驗證者的工作目錄

如果您想在安裝前更改驗證者的工作目錄，有兩種方式可以達成：

1. **分叉專案** - 您可以分叉專案並在其中進行修改。查看 `man git-fork` 指令以瞭解如何進行分叉操作。
2. **創建符號連結** - 您也可以使用以下指令創建一個符號連結：

    ```bash
    ln -s /opt/ton/var/ton
    ```
此指令會創建一個名為 `/var/ton` 的連結，導向 `/opt/ton` 目錄。

## 在安裝後更改驗證者的工作目錄

如果您希望在安裝後將驗證者的工作目錄從 `/var/ton/` 改為其他目錄，請按照以下步驟進行：

1. **停止服務** - 使用以下指令停止相關服務：

    ```bash
    systemctl stop validator
    systemctl stop mytoncore
    ```

2. **移動驗證者的檔案** - 接著使用以下指令將驗證者的檔案移至新的目錄：

    ```bash
    mv /var/ton/* /opt/ton/
    ```

3. **更改配置中的路徑** - 將 `~/.local/share/mytoncore/mytoncore.db` 中的路徑替換為新的路徑。

4. **注意事項** - 之前並未有過如此的轉移經驗，所以進行此操作時請小心。

請確認您擁有足夠的權限來執行這些修改和指令。

# 如何在 MyTonCtrl 中確認驗證者狀態並重啟驗證者

本文檔將幫助你了解如何確認 MyTonCtrl 是否已成為全功能驗證者，以及如何重啟你的驗證者。

## 在 MyTonCtrl 中確認驗證者狀態

你可以透過以下條件來確認你的節點是否已成為全功能驗證者：

1. **驗證者的異步狀態** - 本地驗證者的異步狀態應該小於 20。
2. **驗證者的索引** - 驗證者的索引應該大於 -1。

你可以透過 MyTonCtrl 的 `vl` 命令查看驗證者的工作率：

1. 在列表中按照其 ADNL 地址（`adnlAddr`）找到你的驗證者。
2. 如果 `mr` 和 `wr` 的係數接近 1，則表示你的驗證者運行正常。

## 重啟你的驗證者

如果你需要重啟你的驗證者，可以執行以下命令：

```bash
systemctl restart validator
```

請確保你具有執行這些命令的適當權限，並進行必要的調整。在執行可能影響你的驗證者的操作之前，請始終記得備份重要數據。