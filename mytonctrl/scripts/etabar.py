#!/usr/bin/env python3

from sys import exit, argv
from subprocess import run, PIPE
from mytonctrl.progressbar import EtaBar


timeout = int(argv[1])
script = argv[2]
result = argv[3]

bar = EtaBar(timeout=timeout)
args = ["bash", script]
process = bar.run(run, args, stdin=PIPE, stdout=PIPE, stderr=PIPE, timeout=timeout)
exit_code = -1
output = "process is None"
if process != None:
	exit_code = process.returncode
	stdout = process.stdout.decode("utf-8")
	stderr = process.stderr.decode("utf-8")
	if exit_code == 0:
		output = stdout
	else:
		output = stderr
with open(result, 'wt') as file:
	file.write(output)
exit(exit_code)
