# MyTonCtrl2 general commands

## Update mytonctrl

```bash
MyTonCtrl> update
```

Param combinations:

| Format name            | Format                                                                     | Example                                                                     | Description                                                             |
  |:-----------------------|:---------------------------------------------------------------------------|:----------------------------------------------------------------------------|-------------------------------------------------------------------------|
| No args                | `update`                                                                   | `update`                                                                    | Update from current repo                                                |
| URL format             | `update [https://github.com/author/repo/tree/branch]`                      | `update https://github.com/ton-blockchain/mytonctrl/tree/mytonctrl2`        | Update from specified URL                                               |
| Branch Only format     | `update [BRANCH]`                                                          | `update mytonctrl2`                                                         | Update from specified branch of current repo                            |
| Branch Override format | `update [https://github.com/authorName/repoName/tree/branchName] [BRANCH]` | `update https://github.com/ton-blockchain/mytonctrl/tree/master mytonctrl2` | Update from branch specified by second argument of specified repository |                       

## Update node

```bash
MyTonCtrl> upgrade
```

Param combinations:

| Format name            | Format                                                                      | Example                                                             | Description                                                              |
  |:-----------------------|:----------------------------------------------------------------------------|:--------------------------------------------------------------------|--------------------------------------------------------------------------|
| No args                | `upgrade`                                                                   | `upgrade`                                                           | Upgrade from current repo                                                |
| URL format             | `upgrade [https://github.com/author/repo/tree/branch]`                      | `upgrade https://github.com/ton-blockchain/ton/tree/master`         | Upgrade from specified URL                                               |
| Branch Only format     | `upgrade [BRANCH]`                                                          | `upgrade master`                                                    | Upgrade from specified branch of current repo                            |
| Branch Override format | `upgrade [https://github.com/authorName/repoName/tree/branchName] [BRANCH]` | `upgrade https://github.com/ton-blockchain/ton/tree/master testnet` | Upgrade from branch specified by second argument of specified repository |

## Get mytonctrl status

```bash
MyTonCtrl> status
```

Param combinations:

| Format name | Format        | Example       | Description                                                                                      |
  |-------------|---------------|---------------|--------------------------------------------------------------------------------------------------|
| No args     | `status`      | `status`      | Full status report including validator efficiency and online validators.                         |
| Fast        | `status fast` | `status fast` | Must be used on TestNet. Status report without validator efficiency and online validators count. |

TODO: explain all fields of responses

- **installer**: Run the installer of TON modules.
    - No parameters required. It runs `python3 /usr/src/mytonctrl/mytoninstaller.py` and do nothing else.

## Show MTC modes

```bash
MyTonCtrl> status_modes
```

## Show all settings

Show all available settings with their description and values.

```bash
MyTonCtrl> status_settings
```

## Enable a specific mode

```bash
MyTonCtrl> enable_mode <mode_name>
```

## Disable a specific mode

```bash
MyTonCtrl> disable_mode <mode_name>
```

## Mode descriptions

Provide a description of the specific mode.

```bash
MyTonCtrl> about <mode_name>
```

## Get settings value

Get the value of a specific setting.

```bash
MyTonCtrl> get <settings-name>
```

## Set settings value

Set the value of a specific setting.

```bash
MyTonCtrl> set <settings-name> <settings-value>
```

## Rollback to mytonctrl 1.0

```bash
MyTonCtrl> rollback
```

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

## Various Commands
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
