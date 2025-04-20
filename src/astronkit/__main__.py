import pathlib
import sys
from typing import List, Literal, Set, get_args


from astronkit.dclass_parser import parse_dcfiles
from astronkit.python_dumper import PythonDumper


def main():
    paths = sys.argv[1:]
    if not paths:
        print("Usage: astronkit [--exclude=ClassName...] <files>")
        return
    exclusions: Set[str] = set()
    good_paths: List[str] = []
    for p in paths:
        if p.startswith("--exclude="):
            exclusions |= set(p.split("=", 1)[1].split(","))
        else:
            good_paths.append(p)
    parsed = parse_dcfiles(good_paths, exclusions)

    for k in get_args(Literal["AI", "CL", "UD", "OV"]):
        out_path = pathlib.Path("astronkit_data", f"AstronStubs{k}.py")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        dumper = PythonDumper(sys.version_info[:2], k)
        with open(out_path, "w") as f:
            _ = f.write(dumper.dump_file(parsed))


if __name__ == "__main__":
    main()
