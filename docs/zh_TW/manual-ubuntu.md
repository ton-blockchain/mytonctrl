# 如何使用 mytonctrl 成為驗證者 (v0.2, Ubuntu操作系統)

以下為使用 mytonctrl 成為驗證者的步驟。此範例適用於Ubuntu操作系統。

## 1. 安裝 mytonctrl：

1. 下載安裝腳本。我們建議在您的本地用戶帳戶下安裝該工具，而非 Root。在我們的示例中，使用的是本地用戶帳戶：

    ```sh
    wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/install.sh
    ```

    ![wget output](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_wget-ls_ru.png)

2. 以管理員身份運行安裝腳本：

    ```sh
    sudo bash install.sh -m full
    ```

## 2. 操作測試：

1. 從在第一步中用於安裝的本地用戶帳戶運行 **mytonctrl**：

    ```sh
    mytonctrl
    ```

2. 檢查 **mytonctrl** 的狀態，特別是以下幾點：

* **mytoncore status**：應為綠色。
* **Local validator status**：應為綠色。
* **Local validator out of sync**：首次顯示出一個大數字。新創建的驗證者一旦與其他驗證者聯繫，該數字約為250k。隨著同步的進行，這個數字會減少。當它降至20以下時，驗證者就同步了。

    ![status](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/mytonctrl-status.png)


## 3. 查看可用錢包列表

檢查可用的錢包列表。例如，在安裝 **mytonctrl** 時，會創建 **validator_wallet_001** 錢包：

![wallet list](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-wl_ru.png)

## 4. 向錢包發送所需數量的幣並激活它

要確定參與一輪選舉所需的最小幣數，請轉到 **tonmon.xyz** > **參與者賭注**。

* 使用 `vas` 命令顯示轉賬歷史
* 使用 `aw` 命令激活錢包

    ![account history](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-vas-aw_ru.png)

## 5. 現在你的驗證人準備好了

**mytoncore** 將自動加入選舉。它將錢包餘額分為兩部分，並將它們作為賭注參與選舉。您也可以手動設定賭注大小：

`set stake 50000` — 這將賭注大小設定為50k幣。如果賭注被接受，並且我們的節點成為驗證人，則只能在第二次選舉中撤回賭注（根據選民的規則）。

![setting stake](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-set_ru.png)

您也可以隨時命令求助。

![help command](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-help_ru.png)

要檢查 **mytoncrl** 日誌，對於本地用戶，打開 `~/.local/share/mytoncore/mytoncore.log`，對於 Root，打開 `/usr/local/bin/mytoncore/mytoncore.log`。

![logs](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytoncore-log.png)