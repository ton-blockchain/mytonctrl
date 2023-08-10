# Говнокод ON
import os
from sys import path
from os.path import dirname as dir
path.append(dir(path[0]))
# Говнокод OFF

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
