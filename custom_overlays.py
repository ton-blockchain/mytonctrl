import base64
import json

from mypylib.mypylib import color_print


def hex2base64(h):
    b = bytes.fromhex(h)
    b64 = base64.b64encode(b)
    s = b64.decode("utf-8")
    return s


def parse_config(name: str, config: dict, vset: list = None):
    """
    Converts config to validator-console friendly format
    :param name: custom overlay name
    :param config: config
    :param vset: list of validators adnl addresses, can be None if `@validators` not in config
    :return:
    """
    result = {
        "name": name,
        "nodes": []
    }
    for k, v in config.items():
        if k == '@validators' and v:
            if vset is None:
                raise Exception("Validators set is not defined but @validators is in config")
            for v_adnl in vset:
                result["nodes"].append({
                    "adnl_id": hex2base64(v_adnl),
                    "msg_sender": False,
                })
        else:
            result["nodes"].append({
                "adnl_id": hex2base64(k),
                "msg_sender": v["msg_sender"],
            })
            if v["msg_sender"]:
                result["nodes"][-1]["msg_sender_priority"] = v["msg_sender_priority"]
    return result


def add_custom_overlay(args):
    from mytonctrl import ton
    if len(args) != 2:
        color_print("{red}Bad args. Usage:{endc} add_custom_overlay <name> <path_to_config>")
        return
    path = args[1]
    with open(path, 'r') as f:
        config = json.load(f)
    ton.set_custom_overlay(args[0], config)
    if '@validators' in config:
        print('Dynamic overlay will be added within 1 minute')
    else:
        result = add_custom_overlay_to_vc(ton, parse_config(args[0], config))
        if not result:
            print('Failed to add overlay to validator console')
            color_print("add_custom_overlay - {red}ERROR{endc}")
            return
    color_print("add_custom_overlay - {green}OK{endc}")


def list_custom_overlays(args):
    from mytonctrl import ton
    if not ton.get_custom_overlays():
        color_print("{red}No custom overlays{endc}")
        return
    for k, v in ton.get_custom_overlays().items():
        color_print(f"Custom overlay {{bold}}{k}{{endc}}:")
        print(json.dumps(v, indent=4))


def delete_custom_overlay(args):
    from mytonctrl import ton
    if len(args) != 1:
        color_print("{red}Bad args. Usage:{endc} delete_custom_overlay <name>")
        return
    if '@validators' in ton.get_custom_overlays().get(args[0], {}):
        print('Dynamic overlay will be deleted within 1 minute')
    else:
        ton.delete_custom_overlay(args[0])
        result = delete_custom_overlay_from_vc(ton, args[0])
        if not result:
            print('Failed to delete overlay from validator console')
            color_print("delete_custom_overlay - {red}ERROR{endc}")
            return
    color_print("delete_custom_overlay - {green}OK{endc}")


def delete_custom_overlay_from_vc(ton, name: str):
    result = ton.validatorConsole.Run(f"delcustomoverlay {name}")
    return 'success' in result


def add_custom_overlay_to_vc(ton, config: dict):
    path = ton.tempDir + f'/custom_overlay_{config["name"]}.json'
    with open(path, 'w') as f:
        json.dump(config, f)
    result = ton.validatorConsole.Run(f"addcustomoverlay {path}")
    return 'success' in result


def custom_overlays(local, ton):
    config = get_default_custom_overlay(local, ton)
    if config is not None:
        ton.set_custom_overlay('default', config)
    deploy_custom_overlays(local, ton)


def deploy_custom_overlays(local, ton):
    result = ton.validatorConsole.Run("showcustomoverlays")
    if 'unknown command' in result:
        return  # node old version
    names = []
    for line in result.split('\n'):
        if line.startswith('Overlay'):
            names.append(line.split(' ')[1].replace('"', '').replace(':', ''))

    config34 = ton.GetConfig34()
    current_el_id = config34['startWorkTime']
    current_vset = [i["adnlAddr"] for i in config34['validators']]

    config36 = ton.GetConfig36()
    next_el_id = config36['startWorkTime'] if config36['validators'] else 0
    next_vset = [i["adnlAddr"] for i in config36['validators']]

    for name in names:
        # check that overlay still exists in mtc db
        pure_name = name
        suffix = name.split('_')[-1]
        if suffix.startswith('elid') and suffix.split('elid')[-1].isdigit():  # probably election id
            pure_name = '_'.join(name.split('_')[:-1])
            el_id = int(suffix.split('elid')[-1])
            if el_id not in (current_el_id, next_el_id):
                local.add_log(f"Overlay {name} is not in current or next election, deleting", "debug")
                delete_custom_overlay_from_vc(ton, name)  # delete overlay if election id is not in current or next election
                continue

        if pure_name not in ton.get_custom_overlays():
            local.add_log(f"Overlay {name} ({pure_name}) is not in mtc db, deleting", "debug")
            delete_custom_overlay_from_vc(ton, name)  # delete overlay if it's not in mtc db

    for name, config in ton.get_custom_overlays().items():
        if name in names:
            continue
        if '@validators' in config:
            new_name = name + '_elid' + str(current_el_id)
            if new_name not in names:
                node_config = parse_config(new_name, config, current_vset)
                local.add_log(f"Adding custom overlay {new_name}", "debug")
                add_custom_overlay_to_vc(ton, node_config)

            if next_el_id != 0:
                new_name = name + '_elid' + str(next_el_id)
                if new_name not in names:
                    node_config = parse_config(new_name, config, next_vset)
                    local.add_log(f"Adding custom overlay {new_name}", "debug")
                    add_custom_overlay_to_vc(ton, node_config)
        else:
            node_config = parse_config(name, config)
            local.add_log(f"Adding custom overlay {name}", "debug")
            add_custom_overlay_to_vc(ton, node_config)


MAINNET_DEFAULT_CUSTOM_OVERLAY = {
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA": {
        "msg_sender": True,
        "msg_sender_priority": 15
    },
    "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB": {
        "msg_sender": True,
        "msg_sender_priority": 10
    },
    "@validators": True
}


TESTNET_DEFAULT_CUSTOM_OVERLAY = {
    "DF27B30444D07087863B77F8BD27BABA8E57EDECA393605F6610FDCB64FFECD1": {
        "msg_sender": True,
        "msg_sender_priority": 15
    },
    "B360D229CA597906ADFC522FAC3EB5F8AE9D80981693225E7083577A4F016118": {
        "msg_sender": True,
        "msg_sender_priority": 10
    },
    "F794DE0B21423B6F4C168C5652758E5743CD977ACE13B3B2BA88E28580D9BEDB": {
        "msg_sender": True,
        "msg_sender_priority": 10
    },
    "6447CEAC80573AF2ABCA741FC940BB690AC263DC4B779FB6609CE5E9A4B31AE1": {
        "msg_sender": True,
        "msg_sender_priority": 5,
    },
    "@validators": True
}


def get_default_custom_overlay(local, ton):
    if not local.db.get('useDefaultCustomOverlays', True):
        return None
    network = ton.GetNetworkName()
    if network == 'mainnet':
        config = MAINNET_DEFAULT_CUSTOM_OVERLAY
    elif network == 'testnet':
        config = TESTNET_DEFAULT_CUSTOM_OVERLAY
    else:
        return None
    return config
