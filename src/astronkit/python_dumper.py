from textwrap import indent
from typing import List, Literal, Optional, Tuple
from astronkit.types import (
    DCKeyword,
    DistributedClass,
    DistributedFileDef,
    DistributedMethod,
    DistributedStruct,
)


class PythonDumper:
    def __init__(
        self, target_version: Tuple[int, int], category: Literal["CL", "OV", "AI", "UD"]
    ) -> None:
        self.category: Literal["CL", "OV", "AI", "UD"] = category
        self.appendix = {"CL": "", "OV": "", "AI": "AI", "UD": "UD"}[category]
        self.superclass = "DistributedObject" + self.appendix

        self.target_version = target_version
        self.symbols: set[str] = set()

    def add_symbol(self, sym: str):
        self.symbols.add(sym)

    def dump_methods(
        self,
        obj: DistributedClass,
        overloads: Optional[List[Tuple[str, str]]] = None,
        only_sendUpdates: bool = False,
    ) -> Tuple[List[str], List[Tuple[str, str]]]:
        if overloads is None:
            overloads = []
        rows: List[str] = []
        for method in obj.fields:
            if self.canSend(method):
                self.dump_sendUpdate_overload(method, overloads)

            if not only_sendUpdates:
                if DCKeyword.required in method.keywords and self.category == "AI":
                    rows.append(indent(self.dump_getter(method), " " * 4))

                if self.canReceive(method):
                    rows.append(indent(self.dump_receiver(method), " " * 4))

        for sc in obj.superclasses:
            _ = self.dump_methods(sc, overloads, only_sendUpdates=True)
        return rows, overloads

    def make_method(
        self, key: str, args: str, ellipsis: bool, no_overload: bool
    ) -> List[str]:
        out: List[str] = []

        if not args:
            argsIn = argsOut = ""
        else:
            argsIn = ", value: " + args
            argsOut = ", value"

        if no_overload:
            key = "str"
            argsIn = ", value: object = None"
            argsOut = ", value"
        else:
            self.symbols.add("typing.Literal")
            key = f'Literal["{key}"]'
        out.extend(
            [
                "@overload",
                f"def sendUpdate(self, field: {key}{argsIn}, /):",
                "    ..."
                if ellipsis
                else " " * 4 + f"{self.superclass}.sendUpdate(self, field{argsOut})",
            ]
        )
        if self.category in ("AI", "UD"):
            out.extend(
                [
                    "@overload",
                    f"def sendUpdateToAvatarId(self, avId: int, field: {key}{argsIn}, /):",
                    "    ..."
                    if ellipsis
                    else " " * 4
                    + f"{self.superclass}.sendUpdateToAvatarId(self, avId, field{argsOut})",
                ]
            )
            out.extend(
                [
                    "@overload",
                    f"def sendUpdateToAccountId(self, avId: int, field: {key}{argsIn}, /):",
                    "    ..."
                    if ellipsis
                    else " " * 4
                    + f"{self.superclass}.sendUpdateToAccountId(self, avId, field{argsOut})",
                ]
            )

        return out

    def make_methods(self, overloads: List[Tuple[str, str]]) -> str:
        lines: List[str] = []
        if len(overloads) == 1:
            methods = self.make_method(
                overloads[0][0], overloads[0][1], ellipsis=False, no_overload=False
            )
            methods = [m for m in methods if "@overload" not in m]
            lines = methods
        else:
            self.add_symbol("typing.overload")
            for key, args in overloads:
                lines.extend(
                    self.make_method(key, args, ellipsis=True, no_overload=False)
                )
            lines.extend(
                [
                    m
                    for m in self.make_method("", "", ellipsis=False, no_overload=True)
                    if "@overload" not in m
                ]
            )

        return "\n".join(lines)

    def dump_class(self, obj: DistributedClass) -> str:
        self.add_symbol("abc")
        self.add_symbol("direct.distributed." + self.superclass + "." + self.superclass)
        superclasses = ["Stub" + x.name + self.appendix for x in obj.superclasses] + [
            self.superclass,
            "abc.ABC",
        ]
        rows = [f"class Stub{obj.name + self.appendix}({', '.join(superclasses)}):"]

        methods, sendUpdate_overloads = self.dump_methods(obj)
        methods.append(indent(self.make_methods(sendUpdate_overloads), " " * 4))
        if not methods:
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
            return (
                DCKeyword.clsend not in method.keywords
                and DCKeyword.ownsend not in method.keywords
            )

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

    def make_supercall(self, method: str, arg_names: List[str]):
        return f"return {self.superclass}.{method}({', '.join(['self'] + arg_names)})"

    def dump_sendUpdate_overload(
        self, method: DistributedMethod, overloads: List[Tuple[str, str]]
    ):
        args = ", ".join(x.type.dump(self) for x in method.parameters)
        if not args:
            overloads.append((method.name, ""))
            overloads.append((method.name, f"{self.get_tuple_id()}[()]"))
        else:
            overloads.append((method.name, f"{self.get_tuple_id()}[{args}]"))

    def dump_receiver(self, method: DistributedMethod):
        self.add_symbol("abc")
        args = ", ".join(
            (x.name or f"arg{i}") + ": " + x.type.dump(self)
            for i, x in enumerate(method.parameters)
        )
        return "\n".join(
            [
                "@abc.abstractmethod",
                f"def {method.name}(self, {args}, /) -> object: ...",
            ]
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
