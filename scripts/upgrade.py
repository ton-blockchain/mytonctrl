# Говнокод ON
from sys import path
from os.path import dirname as dir
path.append(dir(path[0]))
# Говнокод OFF

from mypylib.mypylib import *

# Add to systemd
validatorAppPath = "/usr/bin/ton2/validator-engine/validator-engine"
globalConfigPath = "/usr/bin/ton/validator-engine/ton-global.config.json"
tonDbDir = "/var/ton-work/db/"
tonLogPath = "/var/ton-work/log"
cmd = "{validatorAppPath} -d -C {globalConfigPath} --db {tonDbDir} -l {tonLogPath} -v 1".format(validatorAppPath=validatorAppPath, globalConfigPath=globalConfigPath, tonDbDir=tonDbDir, tonLogPath=tonLogPath)
Add2Systemd(name="validator2", user="validator", start=cmd)
args = ["systemctl", "disable", "validator2"]
subprocess.run(args)
