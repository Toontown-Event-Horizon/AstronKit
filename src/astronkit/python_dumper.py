from textwrap import indent
from typing import Literal
from astronkit.types import (
    DCKeyword,
    DistributedClass,
    DistributedFileDef,
    DistributedMethod,
    DistributedStruct,
)


class PythonDumper:
    def __init__(
        self, target_version: tuple[int, int], category: Literal["CL", "OV", "AI", "UD"]
    ) -> None:
        self.category: Literal["CL", "OV", "AI", "UD"] = category
        self.appendix = {"CL": "", "OV": "", "AI": "AI", "UD": "UD"}[category]
        self.superclass = "DistributedObject" + self.appendix

        self.target_version = target_version
        self.symbols: set[str] = set()

    def add_symbol(self, sym: str):
        self.symbols.add(sym)

    def dump_methods(
        self, obj: DistributedClass, only_sendUpdates: bool = False
    ) -> tuple[int, list[str]]:
        rows: list[str] = []
        sendUpdate_count = 0
        for method in obj.fields:
            if self.canSend(method):
                cnt, dumped_sendUpdate = self.dump_sendUpdate_overload(method)
                rows.append(indent(dumped_sendUpdate, " " * 4))
                sendUpdate_count += cnt

            if not only_sendUpdates:
                if DCKeyword.required in method.keywords and self.category == "AI":
                    rows.append(indent(self.dump_getter(method), " " * 4))

                if self.canReceive(method):
                    rows.append(indent(self.dump_receiver(method), " " * 4))

        for sc in obj.superclasses:
            sendUpdate_count_inside, methods = self.dump_methods(
                sc, only_sendUpdates=True
            )
            sendUpdate_count += sendUpdate_count_inside
            rows = methods + rows
        return sendUpdate_count, rows

    def dump_class(self, obj: DistributedClass) -> str:
        self.add_symbol("abc")
        self.add_symbol("direct.distributed." + self.superclass + "." + self.superclass)
        superclasses = ["Stub" + x.name + self.appendix for x in obj.superclasses] + [
            self.superclass,
            "abc.ABC",
        ]
        rows = [f"class Stub{obj.name + self.appendix}({', '.join(superclasses)}):"]

        sendUpdate_count, methods = self.dump_methods(obj)
        if sendUpdate_count == 1:
            rows += [r.replace("    @overload\n", "") for r in methods]
        elif sendUpdate_count > 1:
            rows += methods
            rows.append(
                indent(
                    "def sendUpdate(self, _field: str, _args: object = None, /) -> None: ...",
                    " " * 4,
                )
            )
            rows.append(
                indent(
                    "def sendUpdateToAvatarId(self, _av: int, _field: str, _args: object = None, /) -> None: ...",
                    " " * 4,
                )
            )
            rows.append(
                indent(
                    "def sendUpdateToAccountId(self, _acct: int, _field: str, _args: object = None, /) -> None: ...",
                    " " * 4,
                )
            )
        elif not methods:
            rows.append("    pass")
        else:
            rows += methods

        return "\n".join(rows)

    def canSend(self, method: DistributedMethod):
        if self.category == "OV":
            return (
                DCKeyword.ownsend in method.keywords
                or DCKeyword.clsend in method.keywords
            )
        elif self.category == "CL":
            return DCKeyword.clsend in method.keywords
        else:
            return True

    def canReceive(self, method: DistributedMethod):
        if self.category == "OV":
            return (
                DCKeyword.broadcast in method.keywords
                or DCKeyword.ownrecv in method.keywords
            )
        elif self.category == "CL":
            return DCKeyword.broadcast in method.keywords
        elif self.category == "AI":
            return DCKeyword.airecv in method.keywords
        else:
            return (
                DCKeyword.airecv not in method.keywords
                and DCKeyword.broadcast not in method.keywords
                and DCKeyword.ownrecv not in method.keywords
            )

    def get_tuple_id(self):
        if self.target_version < (3, 9):
            self.add_symbol("typing.Tuple")
            return "Tuple"
        else:
            return "tuple"

    def dump_sendUpdate_overload(self, method: DistributedMethod):
        if self.target_version < (3, 11):
            self.add_symbol("typing_extensions.overload")
        else:
            self.add_symbol("typing.overload")

        self.add_symbol("typing.Literal")
        args = ", ".join(x.type.dump(self) for x in method.parameters)
        if not args:
            return 2, "\n".join(
                [
                    "@overload",
                    f'def sendUpdate(self, _field: Literal["{method.name}"], /) -> None: ...',
                    "@overload",
                    f'def sendUpdateToAvatarId(self, _av: int, _field: Literal["{method.name}"], /) -> None: ...',
                    "@overload",
                    f'def sendUpdateToAccountId(self, _acct: int, _field: Literal["{method.name}"], /) -> None: ...',
                    "@overload",
                    f'def sendUpdate(self, _field: Literal["{method.name}"], '
                    f"_args: {self.get_tuple_id()}[()], /) -> None: ...",
                    "@overload",
                    f'def sendUpdateToAvatarId(self, _av: int, _field: Literal["{method.name}"], '
                    f"_args: {self.get_tuple_id()}[()], /) -> None: ...",
                    "@overload",
                    f'def sendUpdateToAccountId(self, _acct: int, _field: Literal["{method.name}"], '
                    f"_args: {self.get_tuple_id()}[()], /) -> None: ...",
                ]
            )
        return 1, "\n".join(
            [
                "@overload",
                f'def sendUpdate(self, _field: Literal["{method.name}"], '
                f"_args: {self.get_tuple_id()}[{args}], /) -> None: ...",
                "@overload",
                f'def sendUpdateToAvatarId(self, _av: int, _field: Literal["{method.name}"], '
                f"_args: {self.get_tuple_id()}[{args}], /) -> None: ...",
                "@overload",
                f'def sendUpdateToAccountId(self, _acct: int, _field: Literal["{method.name}"], '
                f"_args: {self.get_tuple_id()}[{args}], /) -> None: ...",
            ]
        )

    def dump_receiver(self, method: DistributedMethod):
        self.add_symbol("abc")
        args = ", ".join(
            (x.name or f"arg{i}") + ": " + x.type.dump(self)
            for i, x in enumerate(method.parameters)
        )
        return "\n".join(
            ["@abc.abstractmethod", f"def {method.name}(self, {args}) -> object: ..."]
        )

    def dump_getter(self, method: DistributedMethod):
        self.add_symbol("abc")
        args = ", ".join(x.type.dump(self) for x in method.parameters)
        if method.name.startswith("set"):
            correct_name = "get" + method.name[3:]
        else:
            correct_name = "get" + method.name
        return "\n".join(
            [
                "@abc.abstractmethod",
                f"def {correct_name}(self) -> {self.get_tuple_id()}[{args}]: ...",
            ]
        )

    def dump_struct(self, obj: DistributedStruct) -> str:
        return (
            obj.name
            + f"T = {self.get_tuple_id()}["
            + ", ".join(f.type.dump(self) for f in obj.fields)
            + "]"
        )

    def visible(self, cls: DistributedClass):
        return self.category in cls.visibility

    def dump_file(self, obj: DistributedFileDef) -> str:
        result = (
            "\n".join([self.dump_struct(s) for s in obj.structs])
            + "\n\n"
            + "\n\n".join([self.dump_class(c) for c in obj.classes if self.visible(c)])
        )

        symbol_dumps: list[str] = []
        for s in self.symbols:
            if "." in s:
                start, end = s.rsplit(".", 1)
                symbol_dumps.append(f"from {start} import {end}")
            else:
                symbol_dumps.append(f"import {s}")

        return "\n".join(symbol_dumps) + "\n\n" + result
