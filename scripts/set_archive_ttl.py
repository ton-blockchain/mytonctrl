import subprocess
import sys

with open('/etc/systemd/system/validator.service', 'r') as file:
    service = file.read()


for line in service.split('\n'):
    if line.startswith('ExecStart'):
        exec_start = line
        break


if '--archive-ttl' in exec_start:
    print('Archive TTL is already set')
    sys.exit(100)

default_command = 'ExecStart = /usr/bin/ton/validator-engine/validator-engine --threads --daemonize --global-config /usr/bin/ton/global.config.json --db /var/ton-work/db/ --logname /var/ton-work/log --state-ttl 604800 --verbosity'

# ExecStart = /usr/bin/ton/validator-engine/validator-engine --threads 31 --daemonize --global-config /usr/bin/ton/global.config.json --db /var/ton-work/db/ --logname /var/ton-work/log --state-ttl 604800 --verbosity 1

t = exec_start.split(' ')
t.pop(t.index('--threads') + 1)  # pop threads value since it's different for each node
t.pop(t.index('--verbosity') + 1)  # pop verbosity value

if ' '.join(t) != default_command:
    print('ExecStart is not default. Please set archive-ttl manually in `/etc/systemd/system/validator.service`.')
    sys.exit(101)

archive_ttl = sys.argv[1]

new_exec_start = exec_start + f' --archive-ttl {archive_ttl}'

with open('/etc/systemd/system/validator.service', 'w') as file:
    file.write(service.replace(exec_start, new_exec_start))

subprocess.run(['systemctl', 'daemon-reload'])
subprocess.run(['systemctl', 'restart', 'validator'])
