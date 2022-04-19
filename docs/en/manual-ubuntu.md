# How to become a validator with mytonctrl (v0.2, OS Ubuntu)

### 1. Install mytonctrl:
1. Download the installation script. We recommend to install the tool under your local user account, not as Root. In our example a local user account is used:

```sh
wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/install.sh
```

![wget output](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_wget-ls_ru.png)

2. Run the installation script as administrator:

```sh
sudo bash install.sh -m full
```


### 2. Operability test:
1. Run **mytonctrl** from local user account used for installation at step 1:

```sh
mytonctrl
```

2. Check **mytonctrl** statuses, in particular the following:

* **mytoncore status**: should be green.
* **Local validator status**: should be green.
* **Local validator out of sync**. First a big number displays. Once the newly created validator contacts other validators, the number is around 250k. As synchronization goes on, the number decreases. When it falls below 20, the validator is synchronized.

![status](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/mytonctrl-status.png)

3. Look at the list of available wallets. In our example the **validator_wallet_001** wallet was created at **mytonctrl** installation:

![wallet list](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-wl_ru.png)


### 3. Send the required number of coins to the wallet and activate it:
Go to **tonmon.xyz** > **Participant stakes** to check the the minimum amount of coins required to participate in one election round.

* The `vas` command displays the history of transfers
* The `aw` command activates the wallet

![account history](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-vas-aw_ru.png)


### 4. Now your validator is good to go
**mytoncore** automatically joins the elections. It divides the wallet balance into two parts and uses them as a bet to participate in the elections. You can also manually set the stake size:

`set stake 50000` — set the stake size to 50k coins. If the bet is accepted and our node becomes a validator, the bet can only be withdrawn at the second election (according to the rules of the electorate).

![setting stake](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-set_ru.png)

Feel free to command help.

To check **mytoncrl** logs, open `~/.local/share/mytoncore/mytoncore.log` for a local user or `/usr/local/bin/mytoncore/mytoncore.log` for Root.

![logs](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytoncore-log.png)
