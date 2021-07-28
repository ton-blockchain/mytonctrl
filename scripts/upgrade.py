# Говнокод ON
import os
from sys import path
from os.path import dirname as dir
path.append(dir(path[0]))
# Говнокод OFF

from mypylib.mypylib import *


file = open("/etc/systemd/system/validator.service", 'rt')
text = file.read()
file.close()
lines = text.split('\n')

for i in range(len(lines)):
	line = lines[i]
	if "ExecStart" not in line:
		continue
	if " --threads " in line or " -t " in line:
		continue
	cpus = psutil.cpu_count() - 1
	lines[i] += " --threads {cpus}".format(cpus=cpus)
#end for

text = "\n".join(lines)
file = open("/etc/systemd/system/validator.service", 'wt')
file.write(text)
file.close()

args = ["systemctl", "daemon-reload"]
subprocess.run(args)
