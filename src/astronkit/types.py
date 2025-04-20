import dataclasses
from enum import Enum
from typing import List, Literal, Protocol, Set, Tuple, Union


class Dumper(Protocol):
    target_version: Tuple[int, int]

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
    bool_ = "bool"
    char = "str"
    null = "None"

    def dump(self, _dumper: Dumper, _is_input: bool) -> str:
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

    def dump(self, dumper: Dumper, is_input: bool) -> str:
        if is_input:
            if dumper.target_version < (3, 9):
                dumper.add_symbol("typing.List")
                return "List[" + self.type.dump(dumper, is_input) + "]"
            else:
                return "list[" + self.type.dump(dumper, is_input) + "]"

        if dumper.target_version < (3, 9):
            dumper.add_symbol("typing.Sequence")
        else:
            dumper.add_symbol("collections.abc.Sequence")
        return "Sequence[" + self.type.dump(dumper, is_input) + "]"


DistributedType = Union[DistributedTypeVanilla, "DistributedStruct", DistributedArray]


@dataclasses.dataclass(frozen=True)
class DCParameter:
    name: Union[str, None]
    type: DistributedType
    has_default: bool


@dataclasses.dataclass(frozen=True)
class DistributedMethod:
    name: str
    parameters: List[DCParameter]
    keywords: List[DCKeyword]


@dataclasses.dataclass(frozen=True)
class DistributedClass:
    name: str
    superclasses: List["DistributedClass"]
    visibility: Set[Literal["AI", "CL", "OV", "UD"]]
    fields: List[DistributedMethod]


@dataclasses.dataclass(frozen=True)
class DistributedStruct:
    name: str
    fields: List[DCParameter]

    def dump(self, _dumper: Dumper, is_input: bool):
        if is_input:
            return '"' + self.name + 'TIn"'
        return '"' + self.name + 'T"'


@dataclasses.dataclass(frozen=True)
class DistributedFileDef:
    classes: List[DistributedClass]
    structs: List[DistributedStruct]
