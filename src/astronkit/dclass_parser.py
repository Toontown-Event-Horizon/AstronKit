from collections.abc import Collection
import pathlib
from typing import Literal, Union
from astronkit.types import (
    DCKeyword,
    DCParameter,
    DistributedArray,
    DistributedClass,
    DistributedFileDef,
    DistributedMethod,
    DistributedStruct,
    DistributedType,
    DistributedTypeVanilla,
)
import panda3d.direct as types
from panda3d.direct import DCClass, DCField, DCFile


uint32uint8 = DistributedStruct(
    "uint32uint8",
    [
        DCParameter(None, DistributedTypeVanilla.uint32, False),
        DCParameter(None, DistributedTypeVanilla.uint8, False),
    ],
)

subatomic_to_dctypes = {
    types.ST_int8: DistributedTypeVanilla.int8,
    types.ST_int16: DistributedTypeVanilla.int16,
    types.ST_int32: DistributedTypeVanilla.int32,
    types.ST_int64: DistributedTypeVanilla.int64,
    types.ST_uint8: DistributedTypeVanilla.uint8,
    types.ST_uint16: DistributedTypeVanilla.uint16,
    types.ST_uint32: DistributedTypeVanilla.uint32,
    types.ST_uint64: DistributedTypeVanilla.uint64,
    types.ST_float64: DistributedTypeVanilla.double,
    types.ST_string: DistributedTypeVanilla.string,
    types.ST_blob: DistributedTypeVanilla.blob,
    types.ST_blob32: DistributedTypeVanilla.largeblob,
    types.ST_char: DistributedTypeVanilla.char,
    types.ST_int8array: DistributedArray(DistributedTypeVanilla.int8),
    types.ST_int16array: DistributedArray(DistributedTypeVanilla.int16),
    types.ST_int32array: DistributedArray(DistributedTypeVanilla.int32),
    types.ST_uint8array: DistributedArray(DistributedTypeVanilla.uint8),
    types.ST_uint16array: DistributedArray(DistributedTypeVanilla.uint16),
    types.ST_uint32array: DistributedArray(DistributedTypeVanilla.uint32),
    types.ST_uint32uint8array: DistributedArray(uint32uint8),
}

typedef_cache: dict[str, DistributedType] = {}


def parse_type(param: types.DCParameter) -> DistributedType:
    if struct := param.as_class_parameter():
        return parse_struct(struct.get_class())
    elif array := param.as_array_parameter():
        return DistributedArray(
            parse_type(array.get_element_type()), array.get_array_size()
        )
    elif simple := param.as_simple_parameter():
        if simple.get_type() == types.ST_invalid:
            raise ValueError(f"Parameter {param} is invalid!")
        return subatomic_to_dctypes[simple.get_type()]
    else:
        raise ValueError(
            f"Parameter {param.get_class().get_name()}::{param.get_name()} could not be parsed!"
        )


def parse_param(dcfield: DCField) -> list[DCParameter]:
    parameters: list[DCParameter] = []
    if atomic := dcfield.as_atomic_field():
        for i in range(atomic.get_num_elements()):
            elt = atomic.get_element(i)
            parameters.append(
                DCParameter(elt.get_name(), parse_type(elt), elt.has_default_value())
            )
        return parameters
    elif molecular := dcfield.as_molecular_field():
        for i in range(molecular.get_num_atomics()):
            parameters.extend(parse_param(molecular.get_atomic(i)))
        return parameters
    elif param := dcfield.as_parameter():
        return [
            DCParameter(param.get_name(), parse_type(param), param.has_default_value())
        ]
    else:
        raise ValueError(
            f"DCField {dcfield.get_class().get_name()}::{dcfield.get_name()} could not be parsed!"
        )


def parse_method(dcfield: DCField) -> DistributedMethod:
    params = parse_param(dcfield)
    keywords: list[DCKeyword] = []
    for i in range(dcfield.get_num_keywords()):
        keyword = dcfield.get_keyword(i).get_name()
        keywords.append(DCKeyword(keyword))
    return DistributedMethod(dcfield.get_name(), params, keywords)


def parse_struct(dcclass: DCClass) -> DistributedStruct:
    fields: list[DCParameter] = []
    for i in range(dcclass.get_num_fields()):
        fields.extend(parse_param(dcclass.get_field(i)))
    return DistributedStruct(dcclass.get_name(), fields)


def parse_class(classnames: Collection[str], dcclass: DCClass) -> DistributedClass:
    parents: list[DistributedClass] = []
    fields: list[DistributedMethod] = []
    for i in range(dcclass.get_num_parents()):
        parents.append(parse_class(classnames, dcclass.get_parent(i)))
    for i in range(dcclass.get_num_fields()):
        fields.append(parse_method(dcclass.get_field(i)))

    visibility = set[Literal["AI", "OV", "UD", "CL"]]()
    if dcclass.get_name() + "AI" in classnames:
        visibility.add("AI")
    if dcclass.get_name() + "UD" in classnames:
        visibility.add("UD")
    if dcclass.get_name() in classnames:
        visibility.add("CL")
    if any(
        DCKeyword.ownrecv in x.keywords or DCKeyword.ownsend in x.keywords
        for x in fields
    ):
        # OwnerView does not have its own class type, so we assume
        # that anything that cares about the owner has an ownerview and nothing else
        visibility.add("OV")
    return DistributedClass(dcclass.get_name(), parents, visibility, fields)


def parse_dcfile(dcfile: DCFile) -> DistributedFileDef:
    classes: list[DistributedClass] = []
    structs: list[DistributedStruct] = []
    classnames = set[str]()

    for i in range(dcfile.get_num_import_modules()):
        for j in range(dcfile.get_num_import_symbols(i)):
            symbols = dcfile.get_import_symbol(i, j).split("/")
            symbols = [symbols[0]] + [symbols[0] + x for x in symbols[1:]]
            classnames |= set(symbols)

    for i in range(dcfile.get_num_classes()):
        cls = dcfile.get_class(i)
        if cls.is_struct():
            structs.append(parse_struct(cls))
        else:
            classes.append(parse_class(classnames, cls))

    # Make sure that superclasses are in the OV file, mainly
    classes_dict = {x.name: x for x in classes}
    for f in classes:
        for g in f.superclasses:
            classes_dict[g.name].visibility.update(f.visibility)

    return DistributedFileDef(list(classes_dict.values()), structs)


def parse_dcfiles(dcfiles: Collection[Union[str, pathlib.Path]]) -> DistributedFileDef:
    dcfile = DCFile()
    for f in dcfiles:
        if not dcfile.read(f):
            raise ValueError(f"Unable to read dcfile: {f}")
    return parse_dcfile(dcfile)
