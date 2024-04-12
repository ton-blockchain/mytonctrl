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
    command = get_node_start_command()
    if command.split(' ')[0] != '/usr/bin/ton/validator-engine/validator-engine':
        raise Exception('Invalid node start command in service file')
    if command is None:
        raise Exception('Cannot find node start command in service file')
    args = get_node_args(command)
    if arg_value == '-d':
        args.pop(arg_name, None)
    else:
        args[arg_name] = arg_value
    new_command = command.split(' ')[0] + ' ' + ' '.join([f'{k} {v}' for k, v in args.items()])
    new_service = service.replace(command, new_command)
    with open('/etc/systemd/system/validator.service', 'w') as f:
        f.write(new_service)
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
