# Bookmarks

You can create an alias (bookmark) for an account address to simplify it usage.

## Bookmark Commands
- **nb [bookmark_name] [account_address]**: Create a new bookmark.
    - `bookmark_name`: The name for the new bookmark.
    - `account_address`: The address of the account to bookmark.
- **bl**: Show the list of bookmarks.
    - No parameters required.
- **db [bookmark_name]**: Delete a bookmark.
    - `bookmark_name`: The name of the bookmark to delete.

## Create a new bookmark

```bash
MyTonCtrl> nb <bookmark-name> <account-addr | domain-name>
```

![](/docs/img/nb.png)

## Show the list of bookmarks

```bash
MyTonCtrl> bl
```

![](/docs/img/bl.png)

## Delete a bookmark

```bash
MyTonCtrl> db <bookmark-name> <bookmark-type>
```

![](/docs/img/db.png)