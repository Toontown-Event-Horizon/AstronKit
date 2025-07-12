import pathlib
import sys
from typing import Annotated, List, Literal, Optional, get_args

from typer import Option, Typer

from astronkit.dclass_parser import parse_dcfiles
from astronkit.python_dumper import PythonDumper

app = Typer()


@app.command()
def main(
    files: List[str],
    exclude: Annotated[
        Optional[List[str]],
        Option(help=">= 0 DClass names to not create stubs for, i.e. MyDclassAI"),
    ] = None,
    base_package: Annotated[
        str,
        Option(help="Package with the core Astron classes such as DistributedObject"),
    ] = "direct.distributed",
):
    parsed = parse_dcfiles(files, set(exclude or []))

    for k in get_args(Literal["AI", "CL", "UD", "OV"]):
        out_path = pathlib.Path("astronkit_data", f"AstronStubs{k}.py")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        dumper = PythonDumper(sys.version_info[:2], k, base_package)
        with open(out_path, "w") as f:
            _ = f.write(dumper.dump_file(parsed))


if __name__ == "__main__":
    app()
