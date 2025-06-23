

def get_validator_service():
    path = '/etc/systemd/system/validator.service'
    with open(path, 'r') as file:
        return file.read()
#end define


def get_node_start_command():
    service = get_validator_service()
    for line in service.split('\n'):
        if line.startswith('ExecStart'):
            return line.split('=')[1].strip()
#end define

def get_node_args(start_command: str = None):
    if start_command is None:
        start_command = get_node_start_command()
    #end if

    result = dict() # {key: [value1, value2]}
    node_args = start_command.split(' ')[1:]
    key = None
    for item in node_args:
        if item.startswith('-'):
            key = item
            if key not in result:
                result[key] = []
        else:
            result[key].append(item)
    return result
#end define
