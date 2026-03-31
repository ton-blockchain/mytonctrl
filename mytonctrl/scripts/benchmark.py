import argparse
import asyncio
import logging
import math
import shutil
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import os

from pytoniq_core import Address, InternalMsgInfo, MessageAny, Slice, StateInit, WalletMessage, begin_cell

from contract import WalletV1, ton
from tontester.install import Install
from tontester.network import DHTNode, FullNode, Network
from tontester.zerostate import SimplexConsensusConfig

POLL_INTERVAL = 2
AVG_WINDOW = 10
GB_PER_MINUTE = 0.4


SPAMMERS = [
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEyCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABMABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAI1mqzYw==",  # 0000
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAByCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAcABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIcGZI9A==",  # 1111
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGSCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABkABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIr/lRbg==",  # 0100
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAISCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACEABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIgUMqKA==",  # 1000
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALSCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC0ABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIL15pIQ==",  # 0010
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABSCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIkjFzCw==",  # 0111
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOyCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADsABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIawWpSQ==",  # 1010
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGyCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABsABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAITa5qkQ==",  # 1100

    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACSCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAkABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIPCwwAg==",  # 0001
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADyCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA8ABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAI66KRBg==",  # 0011
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACyCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAsABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAI3nsL/Q==",  # 0101
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAASyCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEsABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIFfouvA==",  # 0110
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKyCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACsABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAI+NDIJQ==",  # 1001
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAyCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIRb/SDw==",  # 1011
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJSCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACUABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAItJqw0w==",  # 1101
    "te6cckECHgEAA7QAAgE0AR0BFP8A9KQT9LzyyAsCAgFiAw4CAs4ECwIBIAUKA/c+JGS8ALgIMcAkTDg7UTQ+kjTANMf0x/TP9M/0x/RB9csIIVt93yOu/iS+CjHBZJfCOElwACSXwjg1wsfJ72SXwfgghJUC+QAcvsCI6cKIIIBhqC8lTCCAYag3lMguZJfCOMN4NcsIuc+DpTjAjUE1ywgPhlZ/DHjAvI/gBgcJAIgCpAGkBsj6UhXLABPLH8sfIs8LPxPLPyPPCx/J7VS8jiD4KIIILcbAyM+FCBL6UgH6AoIQEK2+788LissfyXL7AJEw4gFwbCIy+JIkxwXy4ZEB1wsf+COm9qYFBfABI8AAjhkEyPpSE8sAEssfE8sfcM8LPxLLP8sfye1U4w0IANgzA8j6Us+DE8sfE8sfcM8LPyHPCz8Syx/J7VSCElQL5ABy+wKNCGf4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQyCEDuaygDIz5NUydtuE8s/ycjPhYgS+lJY+gJxzwtqzMlz+wAAMgXwAQTI+lLPgRLLH8sfE8s/Ess/yx/J7VQAEwghB++kjBw4KSAC90MO1E0PpI0wDTH9Mf0z8x0z/TH9EkwACSXwbg+CNSBKGCElQL5ABy+wLCCY5I8AEFyPpSFMsAIs8LH8sfcM8LPyLPCz8jzwsfye1UpwrCAI4h+CiCCC3GwMjPhQgS+lIB+gKCEBCtvu/PC4oSyx/JcvsAkTHikxVfBeKJgMDQBDn+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEMABIghA7msoAyM+TVMnbbhPLP8nIz4WIEvpSWPoCcc8LaszJc/sAAgEgDxgCASAQEwIBIBESAC20cH2omh9JGmAaY/pj+mf6Z/pj+iIK0AA1tLBdqJofSQY6YAY6Y+Y6Y+Y6Z+Y6Z/pj5jowAgEgFBUANbSjvaiaH0kaYAY6Y+Y6Y+Y6Z+Y6Z+Y6Y+Y6MAIBIBYXADWwiHtRND6SDHTADHTHzHTHzHTPzHTPzHTH9GAANbIbO1E0PpIMdMAMdMfMdMfMdM/0z8x0x8x0YAIBIBkaAAu6HDgScQgCASAbHAA1tkF9qJofSQY6YBpj5jpj5jpn5jpn5jpj5jowADW3BR2omh9JBjpgBjpj+mPmOmfmOmfmOmPmOjAAe5/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIjj73Tg==",  # 1110
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TON network benchmark")
    parser.add_argument(
        "--nodes", type=int, default=2, help="number of validator nodes (default: 2)"
    )
    parser.add_argument(
        "--tps", type=int, default=2500, help="target transactions per second per spammer (default: 2500)"
    )
    parser.add_argument(
        "--block-rate", type=int, default=160, help="target shard blocks rate in ms (default: 160)"
    )
    parser.add_argument(
        "--master-block-rate", type=int, default=1000, help="target master blocks rate in ms (default: 1000)"
    )
    parser.add_argument(
        "--spammers", type=int, default=8, help="amount of spammers contracts divided by shards (default: 8)"
    )
    parser.add_argument(
        "--shards", type=int, default=8, help="workchain shards (default: 8)"
    )
    parser.add_argument(
        "--duration", type=int, default=630, help="benchmark duration in seconds (default: 630)"
    )
    parser.add_argument(
        "--sync-test", action="store_true", default=False,
        help="after benchmark, stop spammers and measure sync time of a new node"
    )
    parser.add_argument(
        "--build-dir", type=Path, default=None,
        help="path to build directory (default: <repo_root>/build)"
    )
    parser.add_argument(
        "--source-dir", type=Path, default=None,
        help="path to source directory (default: auto-detected repo root)"
    )
    parser.add_argument(
        "--work-dir", type=Path, default=None,
        help="path to working directory for network data (default: <source_dir>/test/integration/.network)"
    )
    parser.add_argument(
        "--no-disk-check", action="store_true", default=False,
        help="skip free disk space check before benchmark"
    )
    return parser.parse_args()


@dataclass
class Stats:
    txs_per_second: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    blocks_per_second: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    shards_per_second: dict[int, set[int]] = field(default_factory=lambda: defaultdict(set))
    seen_blocks: set[tuple[int, int, int]] = field(default_factory=set)
    reported_seconds: set[int] = field(default_factory=set)

    def record_block(self, gen_utime: int, tx_count: int, shard: int) -> None:
        self.blocks_per_second[gen_utime] += 1
        self.txs_per_second[gen_utime] += tx_count
        self.shards_per_second[gen_utime].add(shard)

    def rolling_avg_tps(self, t: int) -> int | None:
        window = [self.txs_per_second.get(t - i) for i in range(AVG_WINDOW)]
        if any(v is None for v in window):
            return None
        return round(sum(window) / len(window))

    def print_new_seconds(self) -> None:
        if not self.txs_per_second:
            return
        max_ts = max(self.txs_per_second)
        for t in sorted(self.txs_per_second):
            if t >= max_ts or t in self.reported_seconds:
                continue
            self.reported_seconds.add(t)
            avg = self.rolling_avg_tps(t)
            print(
                f"  t={t}  blocks={self.blocks_per_second[t]}  "
                f"txs={self.txs_per_second[t]}  avg_tps_10s={avg}"
            )

    def print_summary(self, expected_bps: int, expected_tps: int, shards: int) -> None:
        if not self.reported_seconds:
            print("No data collected.")
            return
        seconds = sorted(self.reported_seconds)
        # skip warmup
        while seconds and (
            self.txs_per_second[seconds[0]] <= 1 * shards
            or len(self.shards_per_second[seconds[0]]) < shards
        ):
            seconds.pop(0)
        assert seconds, "No meaningful data after skipping warmup."
        duration = seconds[-1] - seconds[0] + 1
        total_blocks = sum(self.blocks_per_second[t] for t in seconds)
        total_txs = sum(self.txs_per_second[t] for t in seconds)
        avg_bps = total_blocks / duration
        avg_tps = total_txs / duration
        print("\n===== Benchmark Summary =====")
        print(f"Duration:        {duration}s")
        print(f"Total blocks:    {total_blocks}")
        print(f"Total txs:       {total_txs}")
        print(
            f"Avg blocks/s:    {avg_bps:.2f}  ({avg_bps / expected_bps * 100:.1f}% of expected {expected_bps:.1f})"
        )
        print(
            f"Avg TPS:         {avg_tps:.2f}  ({avg_tps / expected_tps * 100:.1f}% of expected {expected_tps})"
        )
        print("=============================")


def block_key(b) -> tuple[int, int, int]:
    return b.workchain, b.shard, b.seqno


async def setup_network(
    source_dir: Path, build_dir: Path, working_dir: Path,
    shards: int, nodes_count: int, block_rate: int, master_block_rate: int,
) -> tuple[Network, list[FullNode], DHTNode]:
    install = Install(build_dir, source_dir)
    install.tonlibjson.client_set_verbosity_level(3)
    network = Network(install, working_dir)

    dht = network.create_dht_node(threads=1)
    network.config.shard_consensus = SimplexConsensusConfig(target_block_rate_ms=block_rate)
    network.config.mc_consensus = SimplexConsensusConfig(target_block_rate_ms=master_block_rate)
    network.config.shard_validators = nodes_count
    network.config.split = int(math.log2(shards))

    threads_per_node = max(1, (os.cpu_count() or 4) // nodes_count)

    nodes: list[FullNode] = []
    for _ in range(nodes_count):
        node = network.create_full_node(threads=threads_per_node)
        node.make_initial_validator()
        node.announce_to(dht)
        nodes.append(node)

    await dht.run()
    print(f"Running each node with {threads_per_node} threads")
    for node in nodes:
        await node.run()
        await asyncio.sleep(3)

    return network, nodes, dht


async def send_with_retry(wallet: WalletV1, message: WalletMessage, seqno: int) -> None:
    while True:
        try:
            await wallet.send(message, seqno)
            return
        except Exception as e:
            print(f"Sending message failed ({e}), retrying...")
            await asyncio.sleep(1)


async def collect_stats(client, stats: Stats) -> None:
    info = await client.get_masterchain_info()
    print(f"mc seqno={info.last.seqno}")

    shards = await client.get_shards(info.last)
    for shard in shards.shards:
        current = shard
        while block_key(current) not in stats.seen_blocks:
            if current.seqno <= 0:
                stats.seen_blocks.add(block_key(current))
                break
            try:
                txs = await client.get_block_transactions(current)
                header = await client.get_block_header(current)
            except Exception as e:
                print(f"  failed to get block wc={current.workchain} seqno={current.seqno}: {e}")
                break
            stats.seen_blocks.add(block_key(current))
            stats.record_block(header.gen_utime, len(txs), current.shard)
            print(
                f"  shard wc={current.workchain} shard={current.shard} "
                f"seqno={current.seqno} txs={len(txs)}"
            )
            if not header.prev_blocks or header.prev_blocks[0].seqno <= 0:
                break
            current = header.prev_blocks[0]

    stats.print_new_seconds()


def create_deploy_spammer_message(wallet: WalletV1, tps: int, i: int) -> WalletMessage:
    s_i = StateInit.deserialize(Slice.one_from_boc(SPAMMERS[i]))
    body = begin_cell().store_uint(0x5ce7c1d2, 32).store_uint(tps, 32).end_cell()
    return WalletMessage(
        send_mode=3,
        message=MessageAny(
            info=InternalMsgInfo(
                ihr_disabled=True,
                bounce=False,
                bounced=False,
                src=wallet.address,
                dest=Address((0, s_i.serialize().hash)),
                value=ton(1000),
                ihr_fee=0,
                fwd_fee=0,
                created_lt=0,
                created_at=0,
            ),
            init=s_i,
            body=body,
        ),
    )


def get_spammer_address(i: int) -> Address:
    s_i = StateInit.deserialize(Slice.one_from_boc(SPAMMERS[i]))
    return Address((0, s_i.serialize().hash))


def create_stop_spammer_message(wallet: WalletV1, spammer_addr: Address) -> WalletMessage:
    body = begin_cell().store_uint(0x07c32b3f, 32).end_cell()
    return WalletMessage(
        send_mode=3,
        message=MessageAny(
            info=InternalMsgInfo(
                ihr_disabled=True,
                bounce=False,
                bounced=False,
                src=wallet.address,
                dest=spammer_addr,
                value=ton(1),
                ihr_fee=0,
                fwd_fee=0,
                created_lt=0,
                created_at=0,
            ),
            init=None,
            body=body,
        ),
    )


async def stop_spammers(wallet: WalletV1, spammers_count: int) -> None:
    print("\n===== Stopping spammers =====")
    for i in range(spammers_count):
        addr = get_spammer_address(i)
        msg = create_stop_spammer_message(wallet, addr)
        await send_with_retry(wallet, msg, seqno=spammers_count + i)
        print(f"  Sent stop message to spammer {i}")
        await asyncio.sleep(2)
    print("All stop messages sent.")


async def run_sync_test(network: Network, dht: DHTNode) -> None:
    print("\n===== Sync Test =====")

    print("Starting new node from scratch...")
    sync_threads = max(2, (os.cpu_count() or 4) // 2)
    new_node = network.create_full_node(threads=sync_threads)
    new_node.announce_to(dht)
    await new_node.run()

    new_client = await new_node.tonlib_client()

    start_time = time.monotonic()
    last_seqno = 0

    print("Waiting for new node to sync...")
    while True:
        try:
            mc_info = await new_client.get_masterchain_info()
            current_seqno = mc_info.last.seqno
            if current_seqno != last_seqno:
                header = await new_client.get_block_header(mc_info.last)
                block_age = time.time() - header.gen_utime
                elapsed = time.monotonic() - start_time
                print(f"  mc seqno: {current_seqno}  block age: {block_age:.1f}s  elapsed: {elapsed:.1f}s")
                last_seqno = current_seqno
                if block_age <= 3:
                    break
        except Exception:
            pass

        await asyncio.sleep(POLL_INTERVAL)

    elapsed = time.monotonic() - start_time
    print("\n===== Sync Test Complete =====")
    print(f"Sync time: {elapsed:.1f}s")
    print("==============================")


async def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="[%(levelname)s][%(asctime)s][%(name)s] %(message)s",
    )

    source_dir = args.source_dir or Path(__file__).resolve().parents[2]

    spammers_count: int = args.spammers
    shards: int = args.shards
    tps: int = args.tps
    nodes: int = args.nodes
    shard_block_rate = args.block_rate
    master_block_rate = args.master_block_rate

    build_dir = args.build_dir or source_dir / "build"
    working_dir = args.work_dir or source_dir / "test/integration/.network"

    shutil.rmtree(working_dir, ignore_errors=True)
    working_dir.mkdir(exist_ok=True, parents=True)

    if not args.no_disk_check:
        duration_minutes = args.duration / 60
        required_gb = duration_minutes * shards * (tps / 1000) * GB_PER_MINUTE
        free_gb = shutil.disk_usage(working_dir).free / (1024 ** 3)
        if free_gb < required_gb:
            raise SystemExit(
                f"Not enough disk space: {free_gb:.1f} GB free, "
                f"estimated {required_gb:.1f} GB required ({GB_PER_MINUTE} GB/min × {shards} shards × {tps / 1000}k TPS × {duration_minutes:.1f} min)"
            )

    network, nodes, dht = await setup_network(source_dir, build_dir, working_dir, shards, nodes, shard_block_rate, master_block_rate)

    stats = Stats()

    async with network:
        try:
            print("Waiting for network to stabilize...")
            await asyncio.sleep(20)

            client = await nodes[0].tonlib_client()
            main_wallet = network.zerostate.main_wallet(client)

            assert spammers_count <= len(SPAMMERS), f'too many spammers, max: {len(SPAMMERS)}'

            for i in range(spammers_count):
                msg = create_deploy_spammer_message(main_wallet, tps, i)
                await send_with_retry(main_wallet, msg, seqno=i)
                await asyncio.sleep(2)

            start = time.monotonic()

            while time.monotonic() - start < args.duration:
                await collect_stats(client, stats)
                await asyncio.sleep(POLL_INTERVAL)

        finally:
            stats.print_summary(expected_bps=(1000 / shard_block_rate) * shards, expected_tps=tps * shards, shards=shards)

        if args.sync_test:
            await stop_spammers(main_wallet, spammers_count)
            print("Waiting for spammers to fully stop...")
            await asyncio.sleep(10)
            await run_sync_test(network, dht)


if __name__ == "__main__":
    asyncio.run(main())
