import typing

from .module import MtcModule
from .pool import PoolModule
from .nominator_pool import NominatorPoolModule
from .single_pool import SingleNominatorModule
from .validator import ValidatorModule
from .controller import ControllerModule


MODES = {
    'validator': ValidatorModule,
    'nominator-pool': NominatorPoolModule,
    'single-nominator': SingleNominatorModule,
    'liquid-staking': ControllerModule,
}


def get_mode(mode_name: str) -> typing.Optional[MtcModule]:
    return MODES.get(mode_name)
