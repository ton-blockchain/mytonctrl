import base64
import json
import requests

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
    from mytonctrl import ton, local
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
        result = add_custom_overlay_to_vc(local, ton, parse_config(args[0], config))
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
        ton.delete_custom_overlay(args[0])
        print('Dynamic overlay will be deleted within 1 minute')
    else:
        ton.delete_custom_overlay(args[0])
        result = delete_custom_overlay_from_vc(ton, args[0])
        if not result:
            print('Failed to delete overlay from validator console')
            color_print("delete_custom_overlay - {red}ERROR{endc}")
            return
    color_print("delete_custom_overlay - {green}OK{endc}")


def check_node_eligible_for_custom_overlay(ton, config: dict):
    vconfig = ton.GetValidatorConfig()
    my_adnls = vconfig.adnl
    node_adnls = [i["adnl_id"] for i in config["nodes"]]
    for adnl in my_adnls:
        if adnl.id in node_adnls:
            return True
    return False


def delete_custom_overlay_from_vc(ton, name: str):
    result = ton.validatorConsole.Run(f"delcustomoverlay {name}")
    return 'success' in result


def add_custom_overlay_to_vc(local, ton, config: dict):
    if not check_node_eligible_for_custom_overlay(ton, config):
        local.add_log(f"Node has no adnl address required for custom overlay {config.get('name')}", "debug")
        return False
    local.add_log(f"Adding custom overlay {config.get('name')}", "debug")
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
                add_custom_overlay_to_vc(local, ton, node_config)

            if next_el_id != 0:
                new_name = name + '_elid' + str(next_el_id)
                if new_name not in names:
                    node_config = parse_config(new_name, config, next_vset)
                    add_custom_overlay_to_vc(local, ton, node_config)
        else:
            node_config = parse_config(name, config)
            add_custom_overlay_to_vc(local, ton, node_config)


def get_default_custom_overlay(local, ton):
    if not local.db.get('useDefaultCustomOverlays', True):
        return None
    network = ton.GetNetworkName()
    default_url = 'https://ton-blockchain.github.io/fallback_custom_overlays.json'
    url = local.db.get('defaultCustomOverlaysUrl', default_url)
    resp = requests.get(url)
    if resp.status_code != 200:
        local.add_log(f"Failed to get default custom overlays from {url}", "error")
        return None
    config = resp.json()
    return config.get(network)
