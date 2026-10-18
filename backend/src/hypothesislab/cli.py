"""CLI shares the HTTP action contract and never evaluates arbitrary shell/Python."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .engine import Engine
from .validation import InputError

def bounded_utf8(path: str, max_bytes: int = 250_000) -> str:
    """Enforce resource limits before decoding or allocating an unbounded file."""
    try:
        with Path(path).open('rb') as src:
            raw = src.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise InputError("Input file exceeds the 250 KB limit")
        return raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise InputError("Input file must be UTF-8; original bytes were not rewritten") from exc


def main(argv=None) -> int:
    p=argparse.ArgumentParser(prog="hypothesislab")
    p.add_argument("--root",default="./hypothesislab-data")
    p.add_argument("--project",default="default")
    p.add_argument("mode",choices=["preview","apply","events","verify"])
    p.add_argument("action",nargs="?",default="molecule.inspect_smiles")
    p.add_argument("--smiles")
    p.add_argument("--molfile-path")
    p.add_argument("--csv-path", help="Measured CSV bytes; immutable original is preserved")
    p.add_argument("--x-column")
    p.add_argument("--y-column")
    p.add_argument("--x-unit")
    p.add_argument("--y-unit")
    p.add_argument("--preview-token", help="Single-use ticket from a prior preview command; mandatory for project writes and host commands")
    a=p.parse_args(argv)
    try:
        if a.molfile_path:
            params={"molfile":bounded_utf8(a.molfile_path)}
        elif a.csv_path:
            params={"csv":bounded_utf8(a.csv_path),
                "x_column":a.x_column,"y_column":a.y_column,
                "x_unit":a.x_unit,"y_unit":a.y_unit}
        elif a.smiles is not None:
            params={"smiles":a.smiles}
        else:
            params={}
    except (InputError, OSError) as exc:
        print(json.dumps({"status":"ERROR","type":type(exc).__name__,"message":str(exc)}), file=sys.stderr)
        return 2
    try:
        engine=Engine(a.root)
        if a.mode == "events":
            output={"events":engine.store.events(a.project)}
        elif a.mode == "verify":
            output=engine.store.verify_artifacts(a.project)
        elif a.mode == "preview":
            output=engine.preview(a.action,params,a.project)
        else:
            output=engine.execute(a.action,params,a.project,approved=True,preview_token=a.preview_token)
        print(json.dumps(output,sort_keys=True,indent=2))
        return 0
    except (InputError, ValueError, OSError) as e:
        print(json.dumps({"status":"ERROR","type":type(e).__name__,"message":str(e)}),file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
