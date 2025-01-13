from modules.module import MtcModule
import dataclasses
import requests


@dataclasses.dataclass
class Metric:
    name: str
    description: str
    type: str

    def to_format(self, value):
        return f"""
# HELP {self.name} {self.description}
# TYPE {self.name} {self.type}
{self.name} {value}
"""


METRICS = {
    'master_out_of_sync': Metric('validator_masterchain_out_of_sync_seconds', 'Time difference between current time and timestamp of the last known block', 'gauge'),
    'shard_out_of_sync': Metric('validator_shardchain_out_of_sync_blocks', 'Number of blocks validator\'s shardclient is behind the last known block', 'gauge'),
    'out_of_ser': Metric('validator_out_of_serialization', 'Number of blocks last state serialization was ago', 'gauge'),
    'vc_up': Metric('validator_console_up', 'Is validator\'s validator client up', 'gauge'),
}


class PrometheusModule(MtcModule):

    description = 'Prometheus format data exporter'
    default_value = False

    def __init__(self, ton, local, *args, **kwargs):
        super().__init__(ton, local, *args, **kwargs)

    def get_validator_status_metrics(self):
        status = self.ton.GetValidatorStatus()
        result = []
        if status.masterchain_out_of_sync is not None:
            result.append(METRICS['master_out_of_sync'].to_format(status.masterchain_out_of_sync))
        if status.shardchain_out_of_sync is not None:
            result.append(METRICS['shard_out_of_sync'].to_format(status.shardchain_out_of_sync))
        if status.masterchain_out_of_ser is not None:
            result.append(METRICS['out_of_ser'].to_format(status.masterchain_out_of_ser))
        result.append(METRICS['vc_up'].to_format(int(status.is_working)))
        return result

    def push_metrics(self):
        if not self.ton.using_prometheus():
            return

        url = self.ton.local.db.get('prometheus_url')
        if url is None:
            raise Exception('Prometheus url is not set')
        metrics = self.get_validator_status_metrics()
        requests.post(url, data='\n'.join(metrics).encode())

    def add_console_commands(self, console):
        ...
