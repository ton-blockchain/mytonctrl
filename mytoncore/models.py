# pyright: strict

from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass
class Wallet:
    name: str
    path: str
    version: str
    addrFull: str | None = None
    workchain: int | None = None
    addr: str | None = None
    addrB64: str | None = None
    addrB64_init: str | None = None
    oldseqno: int | None = None
    subwallet: int | None = None

    def __post_init__(self):
        self.addrFilePath: str = f"{self.path}.addr"
        self.privFilePath: str = f"{self.path}.pk"
        self.bocFilePath: str = f"{self.path}-query.boc"

    def Delete(self):
        os.remove(self.addrFilePath)
        os.remove(self.privFilePath)


@dataclass
class Account:
    workchain: int
    addr: str
    addrB64: str | None = None
    addrFull: str | None = None
    status: str = "empty"
    balance: float = 0
    lt: str | None = None
    hash: str | None = None
    codeHash: str | None = None


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


@dataclass
class Pool:
    name: str
    path: str
    addrFull: str | None = None
    workchain: int | None = None
    addr: str | None = None
    addrB64: str | None = None
    addrB64_init: str | None = None

    def __post_init__(self):
        self.addrFilePath: str = f"{self.path}.addr"
        self.bocFilePath: str = f"{self.path}-query.boc"

    def Delete(self):
        os.remove(self.addrFilePath)
