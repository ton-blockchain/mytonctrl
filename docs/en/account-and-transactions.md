# MyTonCtrl2 Account and Transaction commands

## Account status

To check account status and its transaction history use the following command:

```bash
MyTonCtrl> vas <account-addr>
```

![](/docs/img/vas.png)

## Account history

To check account transaction history use the following command using the number of listed operations as `limit` (but not less then 10):

```bash
MyTonCtrl> vah <account-addr> <limit>
```

![](/docs/img/vah.png)

## Transfer coins

Transfer coins from local wallet to an account:

```bash
MyTonCtrl> mg <wallet-name> <account-addr | bookmark-name> <amount>
```

> [!WARNING] 
> **Wallet version 'v4' is not supported for transfering from**


## Transfer coins through a proxy

Transfer coins from local wallet to an account through a proxy:

```bash
MyTonCtrl> mgtp <wallet-name> <account-addr | bookmark-name> <amount>
```
