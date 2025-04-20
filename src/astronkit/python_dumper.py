from textwrap import indent
from typing import List, Literal, Optional, Tuple
from astronkit.types import (
    DCKeyword,
    DCParameter,
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
        self.appendix = {"CL": "", "OV": "OV", "AI": "AI", "UD": "UD"}[category]
        self.superclass = "DistributedObject" + (
            self.appendix if self.appendix != "OV" else ""
        )

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
                if (
                    DCKeyword.required in method.keywords
                    and self.category == "AI"
                    and any(not x.has_default for x in method.parameters)
                ):
                    rows.append(indent(self.dump_getter(method), " " * 4))

                if self.canReceive(obj, method):
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
            if self.target_version >= (3, 9):
                self.add_symbol("collections.abc.Collection")
            else:
                self.add_symbol("typing.Collection")
            key = "str"
            argsIn = ", value: Collection[object] = ()"
            argsOut = ", value"
        else:
            self.add_symbol("typing.Literal")
            key = f'Literal["{key}"]'
        out.extend(
            [
                "@overload",
                f"def sendUpdate(self, field: {key}{argsIn}, /) -> None:",
                "    ..."
                if ellipsis
                else " " * 4 + f"{self.superclass}.sendUpdate(self, field{argsOut})",
            ]
        )
        if self.category in ("AI", "UD"):
            out.extend(
                [
                    "@overload",
                    f"def sendUpdateToAvatarId(self, avId: int, field: {key}{argsIn}, /) -> None:",
                    "    ..."
                    if ellipsis
                    else " " * 4
                    + f"{self.superclass}.sendUpdateToAvatarId(self, avId, field{argsOut})",
                ]
            )
            out.extend(
                [
                    "@overload",
                    f"def sendUpdateToAccountId(self, avId: int, field: {key}{argsIn}, /) -> None:",
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
        ovSuperclass: List[str] = []
        if self.category == "OV":
            self.add_symbol(f".AstronStubsCL.Stub{obj.name}")
            ovSuperclass.append(f"Stub{obj.name}")
        superclasses = (
            ["Stub" + x.name + self.appendix for x in obj.superclasses]
            + ovSuperclass
            + [self.superclass, "abc.ABC"]
        )
        rows = [f"class Stub{obj.name + self.appendix}({', '.join(superclasses)}):"]

        methods, sendUpdate_overloads = self.dump_methods(obj)
        if sendUpdate_overloads:
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
                (
                    DCKeyword.clsend not in method.keywords
                    and DCKeyword.ownsend not in method.keywords
                )
                or DCKeyword.db in method.keywords
                or DCKeyword.ram in method.keywords
            )

    def canReceive(self, cls: DistributedClass, method: DistributedMethod):
        # We need to make sure that methods deeper in the MRO don't get @abc treatment
        if cls.name in {
            "DistributedNode",
            "DistributedSmoothNode",
            "DistributedCamera",
            "DistributedObject",
            "DistributedObjectGlobal",
        }:
            return False

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
            if "AI" in cls.visibility:
                return (
                    DCKeyword.airecv not in method.keywords
                    and DCKeyword.broadcast not in method.keywords
                    and DCKeyword.ownrecv not in method.keywords
                )
            # A bit cheating, we assume that all UD-receivable methods are CL-sendable (or OV-sendable)
            return (
                DCKeyword.clsend in method.keywords
                or DCKeyword.ownsend in method.keywords
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
        args = ", ".join(x.type.dump(self, False) for x in method.parameters)
        if not args:
            overloads.append((method.name, ""))
            overloads.append((method.name, f"{self.get_tuple_id()}[()]"))
        else:
            overloads.append((method.name, f"{self.get_tuple_id()}[{args}]"))

    def dump_receiver(self, method: DistributedMethod):
        self.add_symbol("abc")
        args = ", ".join(
            ["self"]
            + [
                (x.name or f"arg{i}") + ": " + x.type.dump(self, True)
                for i, x in enumerate(method.parameters)
            ]
        )
        self.add_symbol("typing.Any")
        return "\n".join(
            [
                "@abc.abstractmethod",
                f"def {method.name}({args}, /) -> Any: ...",
            ]
        )

    def dump_getter(self, method: DistributedMethod):
        self.add_symbol("abc")
        args = ", ".join(x.type.dump(self, False) for x in method.parameters)
        if method.name.startswith("set"):
            correct_name = "get" + method.name[3:]
        else:
            correct_name = "get" + method.name

        options = [f"{self.get_tuple_id()}[{args}]"]
        if len(method.parameters) == 1:
            options.append(method.parameters[0].type.dump(self, False))
        return "\n".join(
            [
                "@abc.abstractmethod",
                f"def {correct_name}(self) -> {self.make_union(options)}: ...",
            ]
        )

    def make_option(self, fields: List[DCParameter], is_input: bool) -> str:
        return (
            f"{self.get_tuple_id()}["
            + ", ".join(
                [f.type.dump(self, is_input) for f in fields] if fields else ["()"]
            )
            + "]"
        )

    def dump_struct(self, obj: DistributedStruct) -> str:
        options: List[str] = []
        for i in range(len(obj.fields) + 1):
            if all(x.has_default for x in obj.fields[i:]):
                options.append(self.make_option(obj.fields[:i], False))

        return f"{obj.name}T = {self.make_union(options)}\n{obj.name}TIn = {self.make_option(obj.fields, True)}"

    def make_union(self, options: List[str]) -> str:
        assert options
        if len(options) == 1:
            return options[0]
        if self.target_version >= (3, 10) and all(
            not x.startswith('"') for x in options
        ):
            return " | ".join(options)
        self.add_symbol("typing.Union")
        return f"Union[{', '.join(options)}]"

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
