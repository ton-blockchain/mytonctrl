# Manual config of myTonCtrl super rapid guide

## Prerequesites not covered by this mini guide
* Compiled and installed binaries
* Sources (for fift scripts)
* Access to operational full node
* Python 3.x with different modules required by script. Python will tell you which ones.

## Create a wallet on masterchain 
If you do not have a wallet on masterchain (-1) yet, then make one. 
Manual way described in chapter 2 of https://test.ton.org/Validator-HOWTO.txt

## Create node `adnlAddr`
Again, if you do not have this yet, make it.
Use `validator-engine-console`, here is example of the commands
```
> newkey
created new key C5C2B94529405FB07D1DDFB4C42BFB07727E7BA07006B2DB569FBF23060B9E5C
> addadnl C5C2B94529405FB07D1DDFB4C42BFB07727E7BA07006B2DB569FBF23060B9E5C 0
success
```

## Edit config and install config / wallets
1. Edit the config file mytoncore.db (it is JSON) and set your values.
2. Create a directory $HOME/.local/share/mytoncore under the user that runs myTonCtrl and copy config there.
3. Create $HOME/.local/share/mytoncore/wallet and place the `validatorWalletName` wallet files there.

## Done
