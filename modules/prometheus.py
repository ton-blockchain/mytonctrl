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
    'shard_out_of_sync': Metric('validator_shardchain_out_of_sync_blocks', 'Number of blocks node\'s shardclient is behind the last known block', 'gauge'),
    'out_of_ser': Metric('validator_out_of_serialization', 'Number of blocks last state serialization was ago', 'gauge'),
    'vc_up': Metric('validator_console_up', 'Is `validator-console` up', 'gauge'),
    'validator_id': Metric('validator_index', 'Validator index', 'gauge'),
    'stake': Metric('validator_stake', 'Validator stake', 'gauge'),
    'celldb_gc_block': Metric('validator_celldb_gc_block', 'Celldb GC block latency', 'gauge'),
    'celldb_gc_state': Metric('validator_celldb_gc_state', 'Celldb GC queue size', 'gauge'),
    'collated_master_ok': Metric('validator_blocks_collated_master_ok', 'Number of masterchain blocks successfully collated', 'gauge'),
    'collated_master_err': Metric('validator_blocks_collated_master_err', 'Number of masterchain blocks failed to collate', 'gauge'),
    'collated_shard_ok': Metric('validator_blocks_collated_shard_ok', 'Number of shardchain blocks successfully collated', 'gauge'),
    'collated_shard_err': Metric('validator_blocks_collated_shard_err', 'Number of shardchain blocks failed to collate', 'gauge'),
    'validated_master_ok': Metric('validator_blocks_validated_master_ok', 'Number of masterchain blocks successfully validated', 'gauge'),
    'validated_master_err': Metric('validator_blocks_validated_master_err', 'Number of masterchain blocks failed to validate', 'gauge'),
    'validated_shard_ok': Metric('validator_blocks_validated_shard_ok', 'Number of shardchain blocks successfully validated', 'gauge'),
    'validated_shard_err': Metric('validator_blocks_validated_shard_err', 'Number of shardchain blocks failed to validate', 'gauge'),
    'validator_groups_master': Metric('validator_active_groups_master', 'Number of masterchain validation groups validator participates in', 'gauge'),
    'validator_groups_shard': Metric('validator_active_groups_shard', 'Number of shardchain validation groups validator participates in', 'gauge'),
    'ls_queries_ok': Metric('validator_ls_queries_ok', 'Number of Liteserver successful queries', 'gauge'),
    'ls_queries_err': Metric('validator_ls_queries_err', 'Number of Liteserver failed queries', 'gauge'),
}


class PrometheusModule(MtcModule):

    description = 'Prometheus format data exporter'
    default_value = False

    def __init__(self, ton, local, *args, **kwargs):
        super().__init__(ton, local, *args, **kwargs)

    def get_validator_status_metrics(self, result: list):
        status = self.ton.GetValidatorStatus()
        is_working = status.is_working or (status.unixtime is not None)
        if status.masterchain_out_of_sync is not None:
            result.append(METRICS['master_out_of_sync'].to_format(status.masterchain_out_of_sync))
        if status.shardchain_out_of_sync is not None:
            result.append(METRICS['shard_out_of_sync'].to_format(status.shardchain_out_of_sync))
        if status.stateserializerenabled and status.masterchain_out_of_ser is not None and status.stateserializermasterchainseqno != 0:
            result.append(METRICS['out_of_ser'].to_format(status.masterchain_out_of_ser))
        if status.masterchainblock is not None and status.gcmasterchainblock is not None:
            result.append(METRICS['celldb_gc_block'].to_format(status.masterchainblock - status.gcmasterchainblock))
        if status.gcmasterchainblock is not None and status.last_deleted_mc_state is not None:
            if status.last_deleted_mc_state != 0:
                result.append(METRICS['celldb_gc_state'].to_format(status.gcmasterchainblock - status.last_deleted_mc_state))
            else:
                result.append(METRICS['celldb_gc_state'].to_format(-1))
        if status.validator_groups_master is not None:
            result.append(METRICS['validator_groups_master'].to_format(status.validator_groups_master))
            result.append(METRICS['validator_groups_shard'].to_format(status.validator_groups_shard))
        result.append(METRICS['vc_up'].to_format(int(is_working)))

    def get_validator_validation_metrics(self, result: list):
        index = self.ton.GetValidatorIndex()
        result.append(METRICS['validator_id'].to_format(index))
        config = self.ton.GetConfig34()
        save_elections = self.ton.GetSaveElections()
        elections = save_elections.get(str(config["startWorkTime"]))
        if elections is not None:
            adnl = self.ton.GetAdnlAddr()
            stake = elections.get(adnl, {}).get('stake')
            if stake:
                result.append(METRICS['stake'].to_format(round(stake, 2)))

    def get_node_stats_metrics(self, result: list):
        stats = self.ton.get_node_statistics()
        if stats and 'ls_queries' in stats:
            if stats['ls_queries']['time'] < 50:
                self.local.add_log(f'Liteserver queries time is too low: {stats}')
                return
            result.append(METRICS['ls_queries_ok'].to_format(stats['ls_queries']['ok']))
            result.append(METRICS['ls_queries_err'].to_format(stats['ls_queries']['error']))
        if stats and 'collated' in stats:
            result.append(METRICS['collated_master_ok'].to_format(stats['collated']['master']['ok']))
            result.append(METRICS['collated_master_err'].to_format(stats['collated']['master']['error']))
            result.append(METRICS['collated_shard_ok'].to_format(stats['collated']['shard']['ok']))
            result.append(METRICS['collated_shard_err'].to_format(stats['collated']['shard']['error']))
        if stats and 'validated' in stats:
            result.append(METRICS['validated_master_ok'].to_format(stats['validated']['master']['ok']))
            result.append(METRICS['validated_master_err'].to_format(stats['validated']['master']['error']))
            result.append(METRICS['validated_shard_ok'].to_format(stats['validated']['shard']['ok']))
            result.append(METRICS['validated_shard_err'].to_format(stats['validated']['shard']['error']))

    def push_metrics(self):
        if not self.ton.using_prometheus():
            return

        url = self.ton.local.db.get('prometheus_url')
        if url is None:
            raise Exception('Prometheus url is not set')
        metrics = []
        self.local.try_function(self.get_validator_status_metrics, args=[metrics])
        self.local.try_function(self.get_validator_validation_metrics, args=[metrics])
        self.local.try_function(self.get_node_stats_metrics, args=[metrics])
        requests.post(url, data='\n'.join(metrics).encode())

    def add_console_commands(self, console):
        ...
