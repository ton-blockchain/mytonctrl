import subprocess
import sys

with open('/etc/systemd/system/validator.service', 'r') as file:
    service = file.read()


for line in service.split('\n'):
    if line.startswith('ExecStart'):
        exec_start = line
        break


if exec_start.split(' ')[2] != '/usr/bin/ton/validator-engine/validator-engine':
    raise Exception('Invalid node start command in service file')


if '--state-ttl 604800' not in exec_start:
    print('No state-ttl or custom one found in ExecStart')
    sys.exit(0)

new_exec_start = exec_start.replace('--state-ttl 604800', '')

with open('/etc/systemd/system/validator.service', 'w') as file:
    file.write(service.replace(exec_start, new_exec_start))

subprocess.run(['systemctl', 'daemon-reload'])
subprocess.run(['systemctl', 'restart', 'validator'])

print('Removed state-ttl from service file.')
