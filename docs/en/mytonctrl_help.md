# List of all mytonctrl commands on TestNet

## General Commands
**update**: Update mytonctrl.
Param combinations:

| Format name            | Format                                                                     | Example                                                                     | Description                                                             |
  |:-----------------------|:---------------------------------------------------------------------------|:----------------------------------------------------------------------------|-------------------------------------------------------------------------|
| No args                | `update`                                                                   | `update`                                                                    | Update from current repo                                                |
| URL format             | `update [https://github.com/author/repo/tree/branch]`                      | `update https://github.com/ton-blockchain/mytonctrl/tree/mytonctrl2`        | Update from specified URL                                               |
| Branch Only format     | `update [BRANCH]`                                                          | `update mytonctrl2`                                                         | Update from specified branch of current repo                            |
| Branch Override format | `update [https://github.com/authorName/repoName/tree/branchName] [BRANCH]` | `update https://github.com/ton-blockchain/mytonctrl/tree/master mytonctrl2` | Update from branch specified by second argument of specified repository |                       

**upgrade**: Update node.
Param combinations:

| Format name            | Format                                                                      | Example                                                             | Description                                                              |
  |:-----------------------|:----------------------------------------------------------------------------|:--------------------------------------------------------------------|--------------------------------------------------------------------------|
| No args                | `upgrade`                                                                   | `upgrade`                                                           | Upgrade from current repo                                                |
| URL format             | `upgrade [https://github.com/author/repo/tree/branch]`                      | `upgrade https://github.com/ton-blockchain/ton/tree/master`         | Upgrade from specified URL                                               |
| Branch Only format     | `upgrade [BRANCH]`                                                          | `upgrade master`                                                    | Upgrade from specified branch of current repo                            |
| Branch Override format | `upgrade [https://github.com/authorName/repoName/tree/branchName] [BRANCH]` | `upgrade https://github.com/ton-blockchain/ton/tree/master testnet` | Upgrade from branch specified by second argument of specified repository |

**status**: Get current mytonctrl and node status.
Param combinations:

| Format name | Format        | Example       | Description                                                                                      |
  |-------------|---------------|---------------|--------------------------------------------------------------------------------------------------|
| No args     | `status`      | `status`      | Full status report including validator efficiency and online validators.                         |
| Fast        | `status fast` | `status fast` | Must be used on TestNet. Status report without validator efficiency and online validators count. |

TODO explain all fields of responses

- **installer**: Run the installer of TON modules.
    - No parameters required. It runs `python3 /usr/src/mytonctrl/mytoninstaller.py` and do nothing else.



- **status_modes**: Show MTC modes.
    - No parameters required.

- **status_settings**: Show all available settings with their description and values.
    - No parameters required.
- **enable_mode [mode]**: Enable a specific mode.
    - `mode`: The name of the mode to enable.
- **disable_mode [mode]**: Disable a specific mode.
    - `mode`: The name of the mode to disable.
- **about**: Provide a description of the current mode.
    - No parameters required.
- **get [setting]**: Get the value of a specific setting.
    - `setting`: The name of the setting to retrieve.
- **set [setting] [value]**: Set the value of a specific setting.
    - `setting`: The name of the setting to modify.
    - `value`: The new value for the setting.
- **rollback**: Rollback to mytonctrl 1.0.
    - No parameters required.

## Wallet Commands
- **seqno**: Get the sequence number of the wallet.
    - No parameters required.
- **nw [wallet_name]**: Create a new local wallet.
    - `wallet_name`: The desired name for the new wallet.
- **aw [wallet_name]**: Activate a local wallet.
    - `wallet_name`: The name of the wallet to activate.
- **wl**: Show the list of wallets.
    - No parameters required.
- **iw [wallet_file]**: Import a wallet from a file.
    - `wallet_file`: The file containing the wallet data.
- **swv [version]**: Set the wallet version.
    - `version`: The version number to set for the wallet.
- **ew [wallet_name]**: Export a wallet to a file.
    - `wallet_name`: The name of the wallet to export.
- **dw [wallet_name]**: Delete a local wallet.
    - `wallet_name`: The name of the wallet to delete.

## Account and Transaction Commands
- **vas [account_address]**: View the status of an account.
    - `account_address`: The address of the account to check.
- **vah [account_address]**: View the transaction history of an account.
    - `account_address`: The address of the account to check.
- **mg [from_wallet] [to_account] [amount]**: Move coins to an account.
    - `from_wallet`: The wallet from which to move coins.
    - `to_account`: The account to which to move coins.
    - `amount`: The amount of coins to move.
- **mgtp [from_wallet] [to_account] [amount] [proxy]**: Move coins through a proxy.
    - `from_wallet`: The wallet from which to move coins.
    - `to_account`: The account to which to move coins.
    - `amount`: The amount of coins to move.
    - `proxy`: The proxy through which to move coins.

## Bookmark Commands
- **nb [bookmark_name] [account_address]**: Create a new bookmark.
    - `bookmark_name`: The name for the new bookmark.
    - `account_address`: The address of the account to bookmark.
- **bl**: Show the list of bookmarks.
    - No parameters required.
- **db [bookmark_name]**: Delete a bookmark.
    - `bookmark_name`: The name of the bookmark to delete.

## Offer and Election Commands
- **ol**: Show the list of offers.
    - No parameters required.
- **od [offer_id]**: Show the details of a specific offer.
    - `offer_id`: The identifier of the offer to view.
- **el**: Show the list of election entries.
    - No parameters required.
- **vo [offer_id]**: Vote for a specific offer.
    - `offer_id`: The identifier of the offer to vote for.
- **ve [entry_id]**: Vote for a specific election entry.
    - `entry_id`: The identifier of the election entry to vote for.

## Validator and Complaint Commands
- **vl**: Show the list of active validators.
    - No parameters required.
- **cl**: Show the list of complaints.
    - No parameters required.
- **vc [complaint_id]**: Vote for a specific complaint.
    - `complaint_id`: The identifier of the complaint to vote for.

## Pool Commands
- **pools_list**: List all pools.
    - No parameters required.
- **delete_pool [pool_id]**: Delete a specific pool.
    - `pool_id`: The identifier of the pool to delete.
- **import_pool [pool_file]**: Import a pool from a file.
    - `pool_file`: The file containing the pool data.
- **new_single_pool [pool_name]**: Create a new single pool.
    - `pool_name`: The desired name for the new pool.
- **activate_single_pool [pool_id]**: Activate a single pool.
    - `pool_id`: The identifier of the pool to activate.

## Miscellaneous Commands
- **add_custom_overlay [overlay_id]**: Add a custom overlay.
    - `overlay_id`: The identifier of the overlay to add.
- **list_custom_overlays**: List all custom overlays.
    - No parameters required.
- **delete_custom_overlay [overlay_id]**: Delete a custom overlay.
    - `overlay_id`: The identifier of the overlay to delete.
- **cleanup**: Perform a cleanup operation.
    - No parameters required.
- **benchmark**: Run a benchmark test.
    - No parameters required.
- **activate_ton_storage_provider**: Activate the TON storage provider.
    - No parameters required.
- **getconfig**: Get the current configuration.
    - No parameters required.
- **get_pool_data**: Get data from the pool.
    - No parameters required.
