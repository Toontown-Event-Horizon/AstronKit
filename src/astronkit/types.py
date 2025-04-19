import dataclasses
from enum import Enum
from typing import Literal, Protocol, Union


class Dumper(Protocol):
    target_version: tuple[int, int]

    def add_symbol(self, sym: str): ...


class DistributedTypeVanilla(Enum):
    uint8 = "int"
    uint16 = "int"
    uint32 = "int"
    uint64 = "int"
    int8 = "int"
    int16 = "int"
    int32 = "int"
    int64 = "int"
    double = "float"
    string = "str"
    blob = "bytes"
    largeblob = "bytes"
    bool = "bool"
    char = "str"
    null = "None"

    def dump(self, _dumper: Dumper) -> str:
        return self.value


class DCKeyword(Enum):
    broadcast = "broadcast"
    ownrecv = "ownrecv"
    airecv = "airecv"
    clsend = "clsend"
    ownsend = "ownsend"
    db = "db"
    ram = "ram"
    required = "required"


@dataclasses.dataclass(frozen=True)
class DistributedArray:
    type: "DistributedType"
    size: int = -1

    def dump(self, dumper: Dumper) -> str:
        if dumper.target_version < (3, 9):
            dumper.add_symbol("typing.List")
            return "List[" + self.type.dump(dumper) + "]"
        else:
            return "list[" + self.type.dump(dumper) + "]"


DistributedType = Union[DistributedTypeVanilla, "DistributedStruct", DistributedArray]


@dataclasses.dataclass(frozen=True)
class DCParameter:
    name: Union[str, None]
    type: DistributedType
    has_default: bool


@dataclasses.dataclass(frozen=True)
class DistributedMethod:
    name: str
    parameters: list[DCParameter]
    keywords: list[DCKeyword]


@dataclasses.dataclass(frozen=True)
class DistributedClass:
    name: str
    superclasses: list["DistributedClass"]
    visibility: set[Literal["AI", "CL", "OV", "UD"]]
    fields: list[DistributedMethod]


@dataclasses.dataclass(frozen=True)
class DistributedStruct:
    name: str
    fields: list[DCParameter]

    def dump(self, _dumper: Dumper):
        return '"' + self.name + 'T"'


@dataclasses.dataclass(frozen=True)
class DistributedFileDef:
    classes: list[DistributedClass]
    structs: list[DistributedStruct]
