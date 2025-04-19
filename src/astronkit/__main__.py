import pathlib
import sys
from typing import Literal, get_args


from astronkit.dclass_parser import parse_dcfiles
from astronkit.python_dumper import PythonDumper


def main():
    paths = sys.argv[1:]
    if not paths:
        print("Usage: astronkit <args>")
        return
    parsed = parse_dcfiles(paths)

    for k in get_args(Literal["AI", "CL", "UD", "OV"]):
        out_path = pathlib.Path("astronkit_data", f"AstronStubs{k}.py")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        dumper = PythonDumper(sys.version_info[:2], k)
        with open(out_path, "w") as f:
            _ = f.write(dumper.dump_file(parsed))


if __name__ == "__main__":
    main()
