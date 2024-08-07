# Fift scripts for single-validator contract

### Init

usage: `./init.fif <code-boc> <owner-addr> <validator-addr>` \
Creates a state-init to deploy a single-nominator-pool contract.

`<code-boc>` is a filename of the compiled contract code BoC bytes or HEX. \
Saves the contract address in `snominator.addr`. \
Saves the init boc into `snominator-state-init.boc`.

### Wallet V3 (Modded)

> A basic [wallet-v3.fif](https://github.com/ton-blockchain/ton/blob/master/crypto/smartcont/wallet-v3.fif) but with an init-state option for deploy.

usage: 
```
./wallet-v3.fif <filename-base> <dest-addr>
                <subwallet-id> <seqno> <amount>
                [-x <extra-amount>*<extra-currency-id>]
                [-n|-b] [-t<timeout>] [-B <body-boc>]
                [-C <comment>] [-I <init-boc>] [<savefile>]
```

Creates a request to advanced wallet created by `new-wallet-v3.fif`, \
with private key loaded from file `<filename-base>.pk` \
and address from `<filename-base>.addr`, and saves it \
into `<savefile>.boc` (`wallet-query.boc` by default).

### Withdraw

usage: `./withdraw.fif <withdraw-amount>` \
Creates a message body to withdraw from a single-nominator pool.

### Upgrade

usage: `./upgrade.fif <new-code-file>` \
Creates a message body to update the nominator's code. \
Takes `<new-code-file>` - BoC file path as argument. \
Saves the result into `upgrade.boc`.

### Change Validator Address

usage: `./change-validator.fif <new-validator-addr>` \
Takes user friendly address as parameter - not file. \
Creates change validator action msg body BoC. \
Saves it into `change-validator.boc`.

### Send Raw Message

usage: `./send-raw-msg.fif <msg-full-boc> <send-mode>` \
Creates a request to send a message through single-nominator-poll. \
`<msg-full-boc>` - BoC full msg file path. \
Saves the result msg body into `send-raw-msg.boc`.
