import argparse
import json
import subprocess
import sys
import time
import logging


def run_vc(cmd: str):
    if binary:
        return subprocess.run([binary, '-k', client, '-p', server, '-a', address, '--cmd', cmd],
                              stdout=subprocess.PIPE).stdout.decode()
    else: # use symlink
        return subprocess.run(['bash', 'validator-console', '--cmd', cmd],
                              stdout=subprocess.PIPE).stdout.decode()

def get_last_mc_seqno():
    stats = run_vc('getstats')
    for line in stats.split('\n'):
        if line.startswith('masterchainblock'):
            return int(line.split()[1].split(',')[2].split(')')[0])

def restart_node():
    return subprocess.run(['systemctl', 'restart', 'validator']).returncode

def get_config():
    with open(config_path) as f:
        return json.load(f)

def set_config(config: dict):
    with open(config_path, 'w') as f:
        f.write(json.dumps(config, indent=4))

def set_hardforks(hfks: list):
    c = get_config()
    c['validator']['hardforks'] = hfks
    set_config(c)

def add_hardfork(hfk: dict):
    c = get_config()
    c['validator']['hardforks'].append(hfk)
    set_config(c)


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

parser = argparse.ArgumentParser(description="Python script to process hardforks when syncing archive node.")
parser.add_argument('--from-seqno', type=int, required=True, help='Global config path')
parser.add_argument('--config-path', type=str, required=True, help='Global config path')
parser.add_argument('--bin', type=str, help='VC bin')
parser.add_argument('--client', type=str, help='VC Client')
parser.add_argument('--server', type=str, help='VC Server')
parser.add_argument('--address', type=str, help='VC Address')

args = parser.parse_args()
config_path = args.config_path
binary = args.bin
client = args.client
server = args.server
address = args.address
from_seqno = args.from_seqno


hardforks = get_config()['validator']['hardforks']
keep_hardforks = [h for h in hardforks if h['seqno'] <= from_seqno]
hardforks = [h for h in hardforks if h['seqno'] > from_seqno]
if len(hardforks) == 0:
    logger.info("No hardforks to process.")
    sys.exit(0)
set_hardforks(keep_hardforks)

while True:
    if len(hardforks) == 0:
        break
    try:
        last_mc_seqno = get_last_mc_seqno()
        if not last_mc_seqno:
            logger.info("Waiting for last mc seqno...")
            time.sleep(300)
            continue
        if last_mc_seqno != hardforks[0]['seqno'] - 1:
            logger.info(f"Waiting for hardfork {hardforks[0]['seqno']}...")
            time.sleep(300)
            continue
        hardfork = hardforks.pop(0)
        logger.info(f"Processing hardfork {hardfork['seqno']}.")
        add_hardfork(hardfork)
        logger.info(f"Hardfork {hardfork['seqno']} has been added.")
        restart_node()
        logger.info(f"Node is restarted")
    except Exception as e:
        import traceback
        logger.error(f"Exception occurred: {e}\n{traceback.format_exc()}")
    time.sleep(60)

logger.info(f"All done.")
