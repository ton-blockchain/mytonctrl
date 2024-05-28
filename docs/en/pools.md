# General Pools Commands

There are two types of pools in MyTonCtrl2:

1. [Nominator Pool](/docs/en/nominator-pool.md)
2. [Single Nominator Pool](/docs/en/single-nominator-pool.md)

All of them are managed by the following set of commands:

## List of pools

```bash
MyTonCtrl> pools_list
```

![](/docs/img/test-pools-list.png)

## Delete a pool

```bash
MyTonCtrl> delete_pool <pool-name>
```

## Importing a pool

You can create already created pool to the list of local pools:

```bash
MyTonCtrl> import_pool <pool-name> <pool-addr>
```
