# pyright: strict

from __future__ import annotations
import os
import struct
from dataclasses import dataclass
from typing import TypedDict

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
    comment: str | None
    ihr_fee: float | None
    fwd_fee: float | None
    ihr_disabled: bool | None

    @property
    def time(self):
        return self.transaction.time

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return self.__str__()


class Config12(TypedDict):
    enabled_since: int
    monitor_min_split: int
    min_split: int
    max_split: int
    basic: int
    active: int
    accept_msgs: int
    flags: int
    zerostate_root_hash: str
    zerostate_file_hash: str


class Config15(TypedDict):
    validatorsElectedFor: int
    electionsStartBefore: int
    electionsEndBefore: int
    stakeHeldFor: int
