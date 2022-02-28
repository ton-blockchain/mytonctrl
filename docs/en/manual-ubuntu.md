# How to become a validator using mytonctrl (v0.2, OS Ubuntu)

### 1. Install mytonctrl:
Download the installation script on behalf of the user on whose name mytonctrl will be installed. I strongly advise against installing mytoncore as root. In our case, on behalf of user:

```sh
wget https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/scripts/install.sh
```

![wget output](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_wget-ls_ru.png)

Run the installation script as administrator:

```sh
sudo bash install.sh -m full
```


### 2. We check that everything is installed correctly:
Run mytonctrl on behalf of the user on whose name you installed:

```sh
mytonctrl
```

Look at the status of mytonctrl. Here we are interested in:

- mytoncore status. Should be green.
- Local validator status. Should be green.
- Local validator out of sync. There will be a huge number in the beginning. After the validator contacts the rest of the validators, the number will be around 250k. Then, as the validator synchronizes, the number will decrease. As soon as the number becomes less than 20, it means that the validator has synchronized.

![status](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/mytonctrl-status.png)

Look at the available wallets. The validator_wallet_001 wallet was created when mytonctrl was installed:

![wallet list](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-wl_ru.png)


### 3. Put the required number of coins on the validator's wallet and activate the wallet:
The minimum number of coins to participate in one election can be found on the site tonmon.xyz, section `Participants stakes`.

On the screen, the `vas` command displays the history of transfers, and the `aw` command activates the wallet:

![account history](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-vas-aw_ru.png)


### 4. At this stage, everything is ready for the validator to work.
mytoncore will automatically participate in the elections - it will divide the wallet balance into two parts and use them as a bet to participate in the elections. You can manually set the size of the steak yourself:

`set stake 50000` — set the steak size to 50k coins. If the bet was accepted and we became a validator, then we will be able to pick up our bet only at the second election - these are the rules of the electorate.

![setting stake](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytonctrl-set_ru.png)

Feel free to command help.

The mytoncrl logs can be viewed in `~/.local/share/mytoncore/mytoncore.log` if it was not installed as root, otherwise in `/usr/local/bin/mytoncore/mytoncore.log`.

![logs](https://raw.githubusercontent.com/ton-blockchain/mytonctrl/master/screens/manual-ubuntu_mytoncore-log.png)
