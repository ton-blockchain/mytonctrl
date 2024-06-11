import os
from sys import path
from os.path import dirname, abspath

# Add the parent directory of the current script to the Python module search path
current_dir = dirname(abspath(__file__))
path.append(current_dir)

from mypylib.mypylib import *


# validator.service
file = open("/etc/systemd/system/validator.service", 'rt')
text = file.read()
file.close()
lines = text.split('\n')

for i in range(len(lines)):
	line = lines[i]
	if "ExecStart" not in line:
		continue
	if "ton-global.config.json" in line:
		lines[i] += line.replace("validator-engine/ton-global.config.json", "global.config.json")
#end for

text = "\n".join(lines)
file = open("/etc/systemd/system/validator.service", 'wt')
file.write(text)
file.close()

args = ["systemctl", "daemon-reload"]
subprocess.run(args)
