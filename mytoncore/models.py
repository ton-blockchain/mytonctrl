# pyright: strict

from __future__ import annotations
import os
import re
from pathlib import Path
import struct
from dataclasses import dataclass, fields
from typing import TypedDict, Any

from mytoncore.output import parse_int, parse_nanograms
from mytoncore.utils import raw_addr_to_b64


@dataclass
class _HasAddress:
    workchain: int
    addr: str

    @property
    def addr_full(self) -> str:
        return f"{self.workchain}:{self.addr}"

    @property
    def addrB64(self) -> str:
        return raw_addr_to_b64(self.addr_full, bounceable=True)

    @property
    def addrB64_init(self) -> str:
        return raw_addr_to_b64(self.addr_full, bounceable=False)

    @staticmethod
    def _get_data_from_file(path: str) -> tuple[int, str]:
        with open(path, "rb") as file:
            data = file.read()
            addr = data[:32].hex()
            workchain = struct.unpack("i", data[32:])[0]
            return workchain, addr


@dataclass
class Wallet(_HasAddress):
    name: str
    path: str
    version: str
    subwallet: int | None = None
    seqno: int | None = None

    def __post_init__(self):
        self.addrFilePath: str = f"{self.path}.addr" if self.subwallet is None else f"{self.path}{self.subwallet}.addr"
        self.privFilePath: str = f"{self.path}.pk"
        self.bocFilePath: str = f"{self.path}-query.boc" if self.subwallet is None else f"{self.path}{self.subwallet}-query.boc"

    @classmethod
    def from_file(cls, name: str, path: str, version: str, subwallet: int | None = None):
        addr_file = f"{path}.addr" if subwallet is None else f"{path}{subwallet}.addr"
        workchain, addr = cls._get_data_from_file(addr_file)
        return cls(workchain, addr, name, path, version, subwallet)

    def delete(self):
        os.remove(self.addrFilePath)
        os.remove(self.privFilePath)


@dataclass
class Account(_HasAddress):
    status: str = "empty"
    balance: float = 0
    lt: str | None = None
    hash: str | None = None
    codeHash: str | None = None


@dataclass
class Pool(_HasAddress):
    name: str
    path: str

    def __post_init__(self):
        self.addrFilePath: str = f"{self.path}.addr"
        self.bocFilePath: str = f"{self.path}-query.boc"

    @classmethod
    def from_file(cls, name: str, path: str):
        workchain, addr = cls._get_data_from_file(f"{path}.addr")
        return cls(workchain, addr, name, path)

    def delete(self):
        os.remove(self.addrFilePath)


@dataclass
class Block:
    workchain: int
    shardchain: str
    seqno: int
    rootHash: str
    fileHash: str

    @classmethod
    def from_str(cls, s: str):
        buff = s.split(":")
        root_hash = buff[1]
        file_hash = buff[2]
        buff = buff[0]
        buff = buff.replace("(", "")
        buff = buff.replace(")", "")
        buff = buff.split(",")
        workchain = int(buff[0])
        shardchain = buff[1]
        seqno = int(buff[2])
        return cls(workchain, shardchain, seqno, root_hash, file_hash)

    def __str__(self):
        result = f"({self.workchain},{self.shardchain},{self.seqno}):{self.rootHash}:{self.fileHash}"
        return result

    def __repr__(self):
        return self.__str__()


@dataclass
class Transaction:
    block: Block
    type: str | None
    time: int | None
    total_fees: float | None

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return self.__str__()


@dataclass
class Message:
    transaction: Transaction
    src_workchain: int | None
    dest_workchain: int | None
    src_addr: str | None
    dest_addr: str | None
    value: float | None
    body: str | None

    @property
    def time(self):
        return self.transaction.time

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return self.__str__()


@dataclass
class CacheResult:
    time: int
    data: Any


@dataclass
class WorkchainConfig:  # some useful data from config param 12
    enabled_since: int
    monitor_min_split: int
    min_split: int
    max_split: int

    @classmethod
    def from_str(cls, s: str):
        return cls(
            enabled_since=parse_int("enabled_since", s),
            monitor_min_split=parse_int("monitor_min_split", s),
            min_split=parse_int("min_split", s),
            max_split=parse_int("max_split", s),
        )


@dataclass
class Config15:
    validators_elected_for: int
    elections_start_before: int
    elections_end_before: int
    stake_held_for: int

    @classmethod
    def from_str(cls, s: str):
        return cls(
            validators_elected_for=parse_int("validators_elected_for", s),
            elections_start_before=parse_int("elections_start_before", s),
            elections_end_before=parse_int("elections_end_before", s),
            stake_held_for=parse_int("stake_held_for", s),
        )


@dataclass
class Config17:
    min_stake: float
    max_stake: float
    min_total_stake: float
    max_stake_factor: int

    @classmethod
    def from_str(cls, s: str):
        return cls(
            min_stake=parse_nanograms("min_stake", s),
            max_stake=parse_nanograms("max_stake", s),
            min_total_stake=parse_nanograms("min_total_stake", s),
            max_stake_factor=parse_int("max_stake_factor", s),
        )


class ElectionsParticipant(TypedDict):
    adnlAddr: str
    pubkey: str
    stake: float
    maxFactor: float
    walletAddr: str


class BlockHead(TypedDict):
    seqno: int
    rootHash: str
    fileHash: str


@dataclass
class ValidatorConfig:
    adnl_addr: str
    pubkey: str
    weight: int


@dataclass
class ValidatorConfigExt(ValidatorConfig):
    mr: float
    wr: float
    efficiency: float
    online: bool
    master_blocks_created: float
    master_blocks_expected: float
    blocks_created: float
    blocks_expected: float
    is_masterchain: bool
    wallet_addr: str | None = None
    stake: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidatorConfigExt:
        legacy_aliases = {"adnlAddr": "adnl_addr", "walletAddr": "wallet_addr"}
        names = {f.name for f in fields(cls)}
        return cls(**{name: value for key, value in data.items()
                      if (name := legacy_aliases.get(key, key)) in names})


@dataclass
class Config:
    total_validators: int
    main_validators: int
    start_work_time: int
    end_work_time: int
    total_weight: int
    validators: list[ValidatorConfig]

    @staticmethod
    def _parse_validator_set(param: str):
        lines = param.split("\n")
        validator_re = re.compile(
            r"pubkey:x([0-9A-Fa-f]+)"  # public key hex
            + r".*?weight:(\d+)"  # weight digits
            + r".*?adnl_addr:x([0-9A-Fa-f]+)"  # adnl address hex
        )

        validators: list[ValidatorConfig] = []
        for line in lines:
            if "public_key:" not in line:
                continue
            m = validator_re.search(line)
            if not m:
                continue
            pubkey, weight, adnl_addr = m.groups()
            validators.append(
                ValidatorConfig(adnl_addr=adnl_addr, pubkey=pubkey, weight=int(weight))
            )
        return Config(
            total_validators=parse_int("total", param),
            main_validators=parse_int("main", param),
            start_work_time=parse_int("utime_since", param),
            end_work_time=parse_int("utime_until", param),
            total_weight=parse_int("total_weight", param),
            validators=validators,
        )

    @classmethod
    def from_str(cls, s: str):
        return cls._parse_validator_set(s)


@dataclass(frozen=True)
class Paths:
    ton_work: Path = Path('/var/ton-work/')
    ton_db: Path = Path('/var/ton-work/db/')
    ton_keys: Path = Path('/var/ton-work/keys/')
    ton_src: Path = Path('/usr/src/ton/')
    ton_bin: Path = Path('/usr/bin/ton/')
    mtc_src: Path = Path('/usr/src/mytonctrl/')
    src_dir: Path = Path('/usr/src/')

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Paths:
        names = {f.name for f in fields(cls)}
        return cls(**{key: Path(value) for key, value in data.items() if key in names})

    @property
    def keyring_dir(self) -> Path:
        return self.ton_db / "keyring"

    @property
    def vconfig_path(self) -> Path:
        return self.ton_db / "config.json"

    @property
    def global_config_path(self) -> Path:
        return self.ton_bin / "global.config.json"

    @property
    def local_config_path(self) -> Path:
        return self.ton_bin / "local.config.json"
