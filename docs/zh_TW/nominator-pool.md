# Nominator pool

## 在提名人池模式下運行驗證人

1. 為驗證人準備硬體 - 8個虛擬 CPU、64GB 內存、1TB SSD、固定 IP 地址、1Gb/s 的網路速度。

   為了維護網路穩定性，建議將驗證節點分布在世界不同地點，而不是集中在一個數據中心。可以使用 https://status.toncenter.com/ 確定位置的負載。根據地圖，你可以看到歐洲、芬蘭、德國和巴黎的數據中心使用率高。因此，我們不建議使用像 Hetzner 和 OVH 這樣的提供商。

   > 你的硬體必須符合指定的配置或更高。不要在弱硬體上運行驗證器 - 這將對網路產生負面影響，並將對你進行罰款。

   > 由於 2021 年 5 月，Hetzner 已經禁止在其伺服器上挖礦，目前 PoW 和 PoS 算法都適用於此規則。即使安裝了常規節點，也將被視為違反協議條款。

   > **推薦的提供商:** [amazon](https://aws.amazon.com/), [digitalocean](https://www.digitalocean.com/), [linode](https://www.linode.com/), [alibaba cloud](https://alibabacloud.com/), [latitude](https://www.latitude.sh/).

2. 安裝並同步 **mytonctrl**，如 https://github.com/ton-blockchain/mytonctrl/blob/master/docs/zh_TW/manual-ubuntu.md 中描述的那樣，**僅**執行步驟1、2和3。

   [視頻指導](https://ton.org/docs/#/nodes/run-node)。

3. 將 1 TON 發送到顯示在 `wl` 列表中的驗證人錢包地址。

4. 輸入 `aw` 以啟動驗證人錢包。

5. 建立兩個池子（對於偶數和奇數的驗證輪次）：
   
   ```
   new_pool p1 0 1 1000 300000
   new_pool p2 0 1 1001 300000
   ```
   其中
    * `p1` 是池名稱；
    * `0` % 是驗證人的獎勵份額（例如，對於 40% 使用 40）；
    * `1` 是池中的最大提名人數量（應 <= 40）；
    * `1000` TON 是最低驗證人的股份（應 >= 1K TON）；
    * `300000` TON 是最低提名人的股份（應 >= 10K TON）；

   > (!) 池的配置不必相同，你可以向其中一個池的最小股份增加 1 以使它們不同。

   > (!) 使用 https://tonmon.xyz/ 確定當前最小驗證人股份。

6. 輸入 `pools_list` 顯示池地址：

   ```
   pools_list
   Name  Status  Balance  Address
   p1    empty   0        0f98YhXA9wnr0d5XRXT-I2yH54nyQzn0tuAYC4FunT780qIT
   p2    empty   0        0f9qtmnzs2-PumMisKDmv6KNjNfOMDQG70mQdp-BcAhnV5jL
   ```

7. 向每個池發送 1 TON 並激活池：
   
   ```
   mg validator_wallet_001 0f98YhXA9wnr0d5XRXT-I2yH54nyQzn0tuAYC4FunT780qIT 1
   mg validator_wallet_001 0f9qtmnzs2-PumMisKDmv6KNjNfOMDQG70mQdp-BcAhnV5jL 1
   activate_pool p1
   activate_pool p2
   ```

8. 輸入 `pools_list` 來顯示池：
   
   ```
   pools_list
   Name  Status  Balance      Address
   p1    active  0.731199733  kf98YhXA9wnr0d5XRXT-I2yH54nyQzn0tuAYC4FunT780v_W
   p2    active  0.731199806  kf9qtmnzs2-PumMisKDmv6KNjNfOMDQG70mQdp-BcAhnV8UO
   ```

9. 打開每個池的連結 "https://tonscan.org/nominator/<address_of_pool>" 並驗證池配置。
    
10. 向每個池進行驗證者存款：

    ```bash
    deposit_to_pool validator_wallet_001 <address_of_pool_1> 1005
    deposit_to_pool validator_wallet_001 <address_of_pool_2> 1005
    ```

    其中 `1005` TON 是存款金額。請注意，池會扣除 1 TON 用於處理存款。

11. 向每個池進行提名人存款：

    轉到池鏈接（**第9步**）並單擊 **ADD STAKE**。
    您也可以使用 **mytonctrl** 進行存款，使用以下命令進行。

    ```bash
    mg nominator_wallet_001 <address_of_pool_1> 300001 -C d
    mg nominator_wallet_001 <address_of_pool_2> 300001 -C d
    ```

    > (!) 提名人錢包必須在 basechain (workchain 0) 初始化。

    > (!) 請注意，驗證者錢包和提名人錢包必須單獨存放！驗證者錢包存放在具有驗證者節點的服務器上，以確保所有系統交易的處理。提名人錢包存放在您的冷加密貨幣錢包中。

    > 如需撤回提名人存款，發送附註 `w` 的交易到池地址（必須附加 1 TON 以處理交易）。您也可以使用 **mytonctrl** 進行此操作。

12. 啟動池模式：
    
    ```bash
    set usePool true
    set stake null
    ```

13. 邀請提名人向您的池存款。驗證參與將自動開始。
    
    > (!) 您需要在驗證者錢包上至少有 200 TON/月的操作費用。

## 設定池

如果你打算借給自己，則使用 `new_pool p1 0 1 1000 300000`（最大1個提名人，驗證者的份額為0％）。

如果你為許多提名人創建池，則可以使用類似以下的設定：`new_pool p1 40 40 10000 10000`（最多40個提名人，驗證者的份額為40％，最低參與者的賭注為10K TON）。

## 將一般驗證者轉換為提名人池模式

1. 輸入 `set stake 0` 來停止參加選舉。

2. 等待你的兩個賭注從選民那裡返回。

3. 從**第四步**開始，按照"在提名人池模式下運行驗證者"的步驟進行操作。