import sys
import subprocess
from mytoninstaller.node_args import get_node_args, get_node_start_command, get_validator_service


def set_node_arg(arg_name: str, arg_value: str = ''):
    """
    :param arg_name:
    :param arg_value: arg value. if None, remove the arg; if empty string, argument is set without value
    :return:
    """
    assert arg_name.startswith('-'), 'arg_name must start with "-" or "--"'
    service = get_validator_service()
    start_command = get_node_start_command()
    if start_command is None:
        raise Exception('Cannot find node start command in service file')
    first_arg = start_command.split(' ')[0]
    if first_arg != '/usr/bin/ton/validator-engine/validator-engine':
        raise Exception('Invalid node start command in service file')
    #end if
    
    node_args = get_node_args(start_command)
    if arg_value == '-d':
        node_args.pop(arg_name, None)
    else:
        if ' ' in arg_value:
            node_args[arg_name] = arg_value.split()
        else:
            node_args[arg_name] = [arg_value]
    #end if

    buffer = list()
    buffer.append(first_arg)
    for key, value_list in node_args.items():
        if len(value_list) == 0:
            buffer.append(f"{key}")
        for value in value_list:
            buffer.append(f"{key} {value}")
    new_start_command = ' '.join(buffer)
    new_service = service.replace(start_command, new_start_command)
    with open('/etc/systemd/system/validator.service', 'w') as file:
        file.write(new_service)
    restart_node()
#end define


def restart_node():
    exit_code = subprocess.run(["systemctl", "daemon-reload"]).returncode
    if exit_code:
        raise Exception(f"`systemctl daemon-reload` failed with exit code {exit_code}")
    exit_code = subprocess.run(["systemctl", "restart", "validator"]).returncode
    if exit_code:
        raise Exception(f"`systemctl restart validator` failed with exit code {exit_code}")
#end define


if __name__ == '__main__':
    name = sys.argv[1]
    value = sys.argv[2] if len(sys.argv) > 2 else ''
    set_node_arg(name, value)
