

def get_validator_service():
    path = '/etc/systemd/system/validator.service'
    with open(path, 'r') as f:
        return f.read()


def get_node_start_command():
    service = get_validator_service()
    for line in service.split('\n'):
        if 'ExecStart' in line:
            return line.split('=')[1].strip()


def get_node_args(command: str = None):
    if command is None:
        command = get_node_start_command()
    result = {}
    key = ''
    for c in command.split(' ')[1:]:
        if c.startswith('--') or c.startswith('-'):
            if key:
                result[key] = ''
            key = c
        elif key:
            result[key] = c
            key = ''
    return result


def set_node_arg(arg_name: str, arg_value: str = ''):
    """
    :param arg_name:
    :param arg_value: arg value. if None, remove the arg; if empty string, argument is set without value
    :return:
    """
    assert arg_name.startswith('-'), 'arg_name must start with "-" or "--"'
    service = get_validator_service()
    command = get_node_start_command()
    if command is None:
        raise Exception('Cannot find node start command in service file')
    args = get_node_args(command)
    if arg_value is None:
        args.pop(arg_name, None)
    else:
        args[arg_name] = arg_value
    new_command = command.split(' ')[0] + ' ' + ' '.join([f'{k} {v}' for k, v in args.items()])
    new_service = service.replace(command, new_command)
    with open('/etc/systemd/system/validator.service', 'w') as f:
        f.write(new_service)
